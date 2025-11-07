import requests
import json
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from ..models import Organization, OrgPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff

AI_CHAT_URL = config("AI_CHAT_URL")


# =============================================================================
# AI SERVICE HANDLER
# =============================================================================
class PolicyAIService:
    """Handles AI-related operations such as title extraction and HTML generation."""

    @staticmethod
    def extract_title_version_from_pdf(pdf_text):
        """
        Extract policy title and version from PDF text content using AI.
        """
        prompt = f"""
        Analyze the following PDF text content and extract the policy title and version number.

        PDF CONTENT:
        {pdf_text[:4000]}

        INSTRUCTIONS:
        1. Identify the main policy title — look for the most prominent heading or title.
        2. Identify the version number — patterns like "Version X.X", "v1.0", "Rev 2.3", etc.
        3. Return both in JSON format, or null if missing.

        RETURN FORMAT (JSON ONLY):
        {{
            "title": "Extracted Policy Title or null if not found",
            "version": "Extracted Version Number or null if not found"
        }}
        """

        payload = {"query": prompt}
        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=30)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            extracted_data = json.loads(response_text)

            missing_fields = []
            if not extracted_data.get("title"):
                missing_fields.append("title")
            if not extracted_data.get("version"):
                missing_fields.append("version")

            if missing_fields:
                return {
                    "status": 400,
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                    "missing_fields": missing_fields,
                    "extracted_data": extracted_data,
                }, None
            else:
                return {
                    "status": 200,
                    "message": "Title and version successfully extracted.",
                    "extracted_data": extracted_data,
                }, extracted_data

        except requests.Timeout:
            return {
                "status": 408,
                "message": "AI service timeout",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None},
            }, None
        except Exception as e:
            print(f"PDF extraction failed: {str(e)}")
            return {
                "status": 400,
                "message": f"Failed to extract title and version: {str(e)}",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None},
            }, None

    @staticmethod
    def format_html_with_ai(template, title, department, category, organization_name):
        """
        Generate policy HTML content using AI based on department & category.
        """
        prompt = f"""
        Create a detailed policy document in HTML format based on {department} and {category}.
        Read the whole {template} template provided below and use it to structure the new policy document,
        and give your best to fill in relevant content.
        

        IMPORTANT:
        - Make sure the title in document matches: {title}
        - Make sure to reference the organization name: {organization_name} wherever it is possible in strong/bold text. But dont make any heading of {organization_name}
        - Return ONLY the HTML document.
        - Start with <!DOCTYPE html> and end with </html>.
        - Make sure the html is created in such a way that, when I convert it into pdf, and if it is multi paged pdf, it should look very much well structured and professional. No need of pagination tags in html.
        - Include:
            - One main heading (policy title)
            - Multiple subheadings
            - A descriptive paragraph for each subheading
            - Create HTML structure with proper tags, try to create one table at least
        - No pagination, markdown, or explanations.
        - Do NOT repeat the title after the header section.
        - Keep formatting clean and professional.
        - Content must be 1000 to 1200 words long.
        """

        payload = {"query": prompt}

        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=100)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()

            # Clean unwanted formatting
            response_text = response_text.strip('"\n ')
            if response_text.startswith("```html"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            start_index = response_text.find("<!DOCTYPE html>")
            if start_index >= 0:
                response_text = response_text[start_index:]

            return {"status": 200, "message": "Policy generated successfully"}, response_text

        except requests.Timeout:
            return {"status": 408, "message": "AI service timeout"}, ""
        except Exception as e:
            print(f"AI policy generation failed: {str(e)}")
            return {"status": 500, "message": f"AI policy generation failed: {str(e)}"}, ""


# =============================================================================
# POLICY VERSION SERVICE
# =============================================================================
class PolicyVersionService:
    """Handles policy versioning and reconstruction logic."""

    @staticmethod
    @transaction.atomic
    def create_or_update_policy_with_version(title, html_template, version, org, created_at, updated_by, description=None):
        """
        Create a new OrgPolicy or update existing one with a diff-based version.
        """
        formatted_html = html_template

        org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
            title=title,
            organization=org,
            defaults={
                "template": formatted_html,
                "policy_type": "existingpolicy",
                "created_at": created_at,
                "updated_by": updated_by,
            },
        )

        # === Case 1: New Policy ===
        if created:
            print(f"Creating new OrgPolicy '{title}' ({version}) for organization {org.id}")
            diff_json = compute_html_diff("", formatted_html)

            policy_version = PolicyVersion.objects.create(
                org_policy_id=org_policy.id,
                version=version,
                diff_data=diff_json,
                status="draft",
                checkpoint_template=formatted_html,  # Initial checkpoint
                created_at=created_at,
                updated_by=updated_by,
            )
            return {
                "org_policy_id": org_policy.id,
                "policy_version_id": policy_version.id,
                "version_number": version,
                "created": True,
            }

        # === Case 2: Update existing policy ===
        print(f"Updating OrgPolicy '{title}' to version {version} for org {org.id}")
        old_html = org_policy.template or ""
        diff_json = compute_html_diff(old_html, formatted_html)
        print(f"Diff computed: {len(diff_json.get('changes', []))} changes")

        # Update OrgPolicy template
        org_policy.template = formatted_html
        org_policy.updated_by = updated_by
        org_policy.updated_at = timezone.now()
        org_policy.save()

        # Create new PolicyVersion
        policy_version = PolicyVersion.objects.create(
            org_policy_id=org_policy.id,
            version=version,
            diff_data=diff_json,
            status="draft",
            created_at=created_at,
            updated_by=updated_by,
        )

        # Add checkpoint every 5 versions
        try:
            version_num = int(version.strip("V"))
            if version_num % 5 == 0:
                policy_version.checkpoint_template = formatted_html
                policy_version.save(update_fields=["checkpoint_template"])
        except Exception:
            pass

        return {
            "org_policy_id": org_policy.id,
            "policy_version_id": policy_version.id,
            "version_number": version,
            "created": False,
        }

    # -------------------------------------------------------------------------
    # HTML Reconstruction
    # -------------------------------------------------------------------------
    @staticmethod
    def reconstruct_policy_html_at_version(org_policy_id, target_version):
        """
        Reconstruct HTML content for a specific policy version.
        """
        all_versions = PolicyVersion.objects.filter(
            org_policy_id=org_policy_id
        ).order_by("created_at")

        if not all_versions.exists():
            raise ObjectDoesNotExist("No versions found for this policy")

        nearest_checkpoint = PolicyVersion.objects.filter(
            org_policy_id=org_policy_id,
            checkpoint_template__isnull=False
        ).order_by("-created_at").first()

        if nearest_checkpoint:
            print(f"🧩 Using checkpoint {nearest_checkpoint.version} for reconstruction → target {target_version}")
            return PolicyVersionService._reconstruct_from_checkpoint(
                all_versions, nearest_checkpoint, target_version
            )
        else:
            print(f"🧩 No checkpoint found — reconstructing sequentially up to {target_version}")
            return PolicyVersionService._reconstruct_sequentially(all_versions, target_version)

    @staticmethod
    def _reconstruct_from_checkpoint(all_versions, checkpoint_version, target_version):
        """Reconstruct HTML from nearest checkpoint to target version."""
        current_html = checkpoint_version.checkpoint_template or ""
        start_applying = False

        for version in all_versions:
            if version.id == checkpoint_version.id:
                start_applying = True
                continue

            if start_applying and version.diff_data:
                try:
                    current_html = apply_diff(current_html, version.diff_data)
                except Exception as e:
                    print(f"⚠️ Diff apply failed for {version.version}: {e}")

            if version.version == target_version:
                break

        return current_html

    @staticmethod
    def _reconstruct_sequentially(all_versions, target_version):
        """Reconstruct HTML sequentially from version 1 up to target version."""
        base_version = all_versions.first()
        current_html = base_version.checkpoint_template or ""

        for version in all_versions:
            if version.diff_data:
                try:
                    current_html = apply_diff(current_html, version.diff_data)
                except Exception as e:
                    print(f"⚠️ Diff apply failed for {version.version}: {e}")

            if version.version == target_version:
                break

        return current_html


# =============================================================================
# LEGACY COMPATIBILITY ALIASES
# =============================================================================
def extract_title_version_from_pdf(pdf_text):
    return PolicyAIService.extract_title_version_from_pdf(pdf_text)

def format_html_with_ai(template, title, department, category, organization_name):
    return PolicyAIService.format_html_with_ai(template, title, department, category, organization_name)

def create_or_update_policy_with_version(title, html_template, version, org, created_at, updated_by, description=None):
    return PolicyVersionService.create_or_update_policy_with_version(title, html_template, version, org, created_at, updated_by, description)

def reconstruct_policy_html_at_version(org_policy_id, target_version):
    return PolicyVersionService.reconstruct_policy_html_at_version(org_policy_id, target_version)
