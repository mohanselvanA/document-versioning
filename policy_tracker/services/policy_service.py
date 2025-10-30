import requests
import json
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, OrgPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff

AI_CHAT_URL = config("AI_CHAT_URL")


class PolicyAIService:
    """Service class for AI-related policy operations"""
    
    @staticmethod
    def extract_title_version_from_pdf(pdf_text):
        """
        Extract policy title and version from PDF text content using AI
        """
        prompt = f"""
        Analyze the following PDF text content and extract the policy title and version number.
        
        PDF CONTENT:
        {pdf_text[:4000]}  # Limit content to avoid token limits
        
        INSTRUCTIONS:
        1. Identify the main policy title - look for the most prominent heading or document title
        2. Identify the version number - look for patterns like "Version X.X", "v1.0", "Rev 2.3", etc.
        3. If you find both title and version, return them in JSON format
        4. If title is missing, indicate which field is missing
        5. If version is missing, indicate which field is missing
        6. If both are missing, indicate both are missing
        
        RETURN FORMAT (JSON):
        {{
            "title": "Extracted Policy Title or null if not found",
            "version": "Extracted Version Number or null if not found"
        }}
        
        Return ONLY the JSON object without any additional text or explanations.
        """
        
        payload = {"query": prompt}
        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=30)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()
            
            # Clean the response to extract JSON
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            extracted_data = json.loads(response_text)
            
            missing_fields = []
            if not extracted_data.get("title"):
                missing_fields.append("title")
            if not extracted_data.get("version"):
                missing_fields.append("version")
            
            if missing_fields:
                return {
                    "status": 400,
                    "message": f"Missing required fields from PDF: {', '.join(missing_fields)}",
                    "missing_fields": missing_fields,
                    "extracted_data": extracted_data
                }, None
            else:
                return {
                    "status": 200,
                    "message": "Title and version successfully extracted from PDF",
                    "extracted_data": extracted_data
                }, extracted_data
                
        except requests.Timeout:
            return {
                "status": 408,
                "message": "AI service timeout",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None}
            }, None
        except Exception as e:
            print(f"PDF title/version extraction failed: {str(e)}")
            return {
                "status": 400,
                "message": f"Failed to extract title and version from PDF: {str(e)}",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None}
            }, None

    @staticmethod
    def format_html_with_ai(template, title, department, category):
        """
        Send policy information to AI service to generate complete policy HTML.
        """
        version = "V1"
        company_name = "Your Company"
        company_logo = "logo"

        if template:
            prompt = f"""Create a detailed policy document in HTML format based on {department} and {category}
                        IMPORTANT:
                        - Return ONLY the HTML document.
                        - The HTML must start with <!DOCTYPE html> and end with </html>.
                        - Do NOT include any explanation, markdown, or comments.
                        - The document should have:
                            - One main heading (policy title)
                            - Multiple subheadings
                            - A descriptive paragraph for each subheading
                        - Do NOT include pagination or mention of pages (no “Page 1 of X”).
                        - Do NOT repeat the title after the header section.
                        - Keep formatting clean, professional, and easy to read.

                                    """
        
        payload = {"query": prompt}

        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=100)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()

            # Clean response
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            if response_text.startswith('```html'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Optionally slice starting from <h1> for consistency
            start_index = response_text.find("<h1>")
            if start_index >= 0:
                response_text = response_text[start_index:]

            return {"status": 200, "message": "Policy generated successfully by LLM"}, response_text

        except requests.Timeout:
            return {"status": 408, "message": "AI service timeout"}, ""
        except Exception as e:
            print(f"AI policy generation failed: {str(e)}")
            return {"status": 500, "message": f"AI policy generation failed: {str(e)}"}, ""



class PolicyVersionService:
    """Service class for policy version operations"""
    
    @staticmethod
    @transaction.atomic
    def create_or_update_policy_with_version(title, html_template, version, org, created_at, updated_by, description=None):
        """
        Create a new OrgPolicy or update an existing one, recording a PolicyVersion diff.
        """
        formatted_html = html_template
        
        org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
            title=title,
            organization=org,
            defaults={
                'template': formatted_html,
                'policy_type': 'existingpolicy',
                'created_at': created_at,
                'updated_by': updated_by,
            },
        )

        if created:
            print(f"Creating new OrgPolicy: {title} with version: {version} for organization: {org.id}")
            # New policy - create first version with empty diff
            old_html = ""
            new_html = formatted_html
            
            diff_json = compute_html_diff(old_html, new_html)
            
            policy_version = PolicyVersion.objects.create(
                org_policy=org_policy,
                version=version,
                diff_data=diff_json,
                status='published',
                created_at=created_at,
                updated_by=updated_by,
            )
            print(f"New OrgPolicy created successfully. OrgPolicy ID: {org_policy.id}, PolicyVersion ID: {policy_version.id}")
            return {
                "org_policy_id": org_policy.id,
                "policy_version_id": policy_version.id,
                "version_number": version,
                "created": True,
            }

        print(f"Updating existing OrgPolicy: {title} to version {version} for organization: {org.id}")
        print(f"Old HTML length: {len(org_policy.template or '')}")
        print(f"New HTML length: {len(formatted_html)}")
        
        # Existing policy: compute diff vs current template
        old_html = org_policy.template or ""
        new_html = formatted_html
        
        diff_json = compute_html_diff(old_html, new_html)
        print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

        # Update OrgPolicy template
        org_policy.template = new_html
        org_policy.updated_by = updated_by
        org_policy.save()

        # Create new PolicyVersion with diff
        policy_version = PolicyVersion.objects.create(
            org_policy=org_policy,
            version=version,
            diff_data=diff_json,
            status='published',
            created_at=created_at,
            updated_by=updated_by,
        )
        
        print(f"OrgPolicy updated successfully. New version: {version}, PolicyVersion ID: {policy_version.id}")
        return {
            "org_policy_id": org_policy.id,
            "policy_version_id": policy_version.id,
            "version_number": version,
            "created": False,
        }

    @staticmethod
    def reconstruct_policy_html_at_version(org_policy_id, target_version):
        """
        Reconstruct policy HTML for a specific version using optimal checkpoint strategy.
        """
        try:
            # Get all versions for this policy
            all_versions = list(PolicyVersion.objects.filter(
                org_policy_id=org_policy_id
            ).order_by('version'))
            
            if not all_versions:
                raise ObjectDoesNotExist("No versions found for this policy")
            
            # Find target version
            target_version_obj = None
            for version in all_versions:
                if version.version == target_version:
                    target_version_obj = version
                    break
            
            if not target_version_obj:
                raise ObjectDoesNotExist(f"Version {target_version} not found")
            
            # Find the nearest checkpoint BEFORE the target version
            nearest_checkpoint = None
            for version in reversed(all_versions):
                if version.version <= target_version and version.checkpoint_template:
                    nearest_checkpoint = version
                    break
            
            if nearest_checkpoint:
                print(f"Using checkpoint at version {nearest_checkpoint.version} to reconstruct version {target_version}")
                return PolicyVersionService._reconstruct_from_checkpoint(nearest_checkpoint, target_version_obj, all_versions)
            else:
                # No checkpoint found, reconstruct from beginning
                print(f"No checkpoint found, reconstructing version {target_version} from beginning")
                return PolicyVersionService._reconstruct_sequentially(all_versions, target_version)
            
        except Exception as e:
            print(f"Error reconstructing policy HTML: {str(e)}")
            raise e

    @staticmethod
    def _reconstruct_from_checkpoint(checkpoint_version, target_version, all_versions):
        """Reconstruct HTML from checkpoint to target version"""
        current_html = checkpoint_version.checkpoint_template or ""
        start_applying = False
        
        for version in all_versions:
            if version.version == checkpoint_version.version:
                start_applying = True
                continue
                
            if start_applying and version.diff_data:
                current_html = apply_diff(current_html, version.diff_data)
                
            if version.version == target_version.version:
                break
                
        return current_html

    @staticmethod
    def _reconstruct_sequentially(all_versions, target_version):
        """Reconstruct HTML sequentially from beginning to target version"""
        current_html = ""
        
        for version in all_versions:
            if version.diff_data:
                current_html = apply_diff(current_html, version.diff_data)
                
            if version.version == target_version:
                break
                
        return current_html


# Legacy function aliases for backward compatibility
def extract_title_version_from_pdf(pdf_text):
    """Legacy function - use PolicyAIService.extract_title_version_from_pdf instead"""
    return PolicyAIService.extract_title_version_from_pdf(pdf_text)

def format_html_with_ai(template, title, department, category):
    """Legacy function - use PolicyAIService.format_html_with_ai instead"""
    return PolicyAIService.format_html_with_ai(template, title, department, category)

def create_or_update_policy_with_version(title, html_template, version, org, created_at, updated_by, description=None):
    """Legacy function - use PolicyVersionService.create_or_update_policy_with_version instead"""
    return PolicyVersionService.create_or_update_policy_with_version(
        title, html_template, version, org, created_at, updated_by, description
    )

def reconstruct_policy_html_at_version(org_policy_id, target_version):
    """Legacy function - use PolicyVersionService.reconstruct_policy_html_at_version instead"""
    return PolicyVersionService.reconstruct_policy_html_at_version(org_policy_id, target_version)


# =============================================================================
# UNUSED FUNCTIONS (COMMENTED OUT FOR NOW)
# =============================================================================

"""
def analyze_policy_content(content, policy_titles):
    # Send content to AI service for policy analysis
    # This function is not currently used in the main workflow
    pass

def link_policy_to_organization(org_id, policy_title):
    # Link policy to organization if match found
    # This function is not currently used in the main workflow
    pass

def get_all_policy_titles():
    # Get all policy titles from database
    # This function is not currently used in the main workflow
    pass
"""