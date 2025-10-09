import requests
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, Policy, OrganizationPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff

AI_CHAT_URL = config("AI_CHAT_URL")

def format_html_with_ai(raw_html: str) -> str:
    """
    Send raw HTML to AI service for proper formatting and styling
    """
    prompt = f"""
    Please convert this raw policy HTML into a properly structured, visually appealing HTML document.
    
    Requirements:
    1. Maintain all the original content and meaning
    2. Add proper HTML structure with semantic tags
    3. Include CSS styling for better readability
    4. Format tables, lists, and sections properly
    5. Make it responsive and professional-looking
    6. Keep the same policy content but improve presentation
    
    Raw HTML Content:
    {raw_html}
    
    Return ONLY the formatted HTML without any explanations.
    """
    
    payload = {"query": prompt}
    try:
        res = requests.post(AI_CHAT_URL, json=payload)
        res.raise_for_status()
        return {
            "Status": "success",
            "message": "AI formatting service succeeded",
            "error": None,
            "status": 200
        }, res.json().get("response", "").strip()
    except Exception as e:
        print(f"AI formatting failed: {str(e)}")
        return {
            "Status": "error",
            "message": "AI formatting service failed, using raw HTML",
            "error": str(e),
            "status": 206
        }, raw_html


def analyze_policy_content(content, policy_titles):
    """Send content to AI service for policy analysis"""
    prompt = f"""
    You are a compliance assistant. Compare the new policy content with the list of existing policy titles.

    New Policy Content:
    {content}

    Existing Policy Titles:
    {', '.join(policy_titles)}

    Instructions:
    1. Analyze if the new policy content matches or is very similar to any of the existing policy titles
    2. If there's a clear match, return ONLY the matching policy title from the list
    3. If no clear match is found, return "No matching policy found"
    4. Do not add any explanations, summaries, or additional text
    5. Return only the exact policy title from the list or "No matching policy found"
    """

    payload = {"query": prompt}
    res = requests.post(AI_CHAT_URL, json=payload)
    res.raise_for_status()
    
    return res.json().get("response", "").strip()

def link_policy_to_organization(org_id, policy_title):
    """Link policy to organization if match found"""
    try:
        org = Organization.objects.get(id=org_id)
        policy = Policy.objects.get(title=policy_title)

        OrganizationPolicy.objects.get_or_create(
            organization=org,
            policy=policy
        )
        return True
    except ObjectDoesNotExist as e:
        raise e
    except Exception as e:
        raise e

def get_all_policy_titles():
    """Get all policy titles from database"""
    return [policy.title for policy in Policy.objects.all()]


@transaction.atomic
def create_or_update_policy_with_version(title: str, html_template: str, version: str, description: str | None = None) -> dict:
    """
    Create a new policy or update an existing one, recording a PolicyVersion diff.
    """
    # Remove AI formatting for now to debug the issue
    # formatted_html = format_html_with_ai(html_template)
    formatted_html = html_template  # Use the HTML directly without AI formatting
    
    policy, created = Policy.objects.select_for_update().get_or_create(
        title=title,
        defaults={
            'policy_template': formatted_html,
            'version': version,
        },
    )

    if created:
        print(f"Creating new policy: {title} with version: {version}")
        # New policy - create first version with empty diff
        old_html = ""
        new_html = formatted_html
        
        diff_json = compute_html_diff(old_html, new_html)
        
        PolicyVersion.objects.create(
            policy=policy,
            version_number=version,
            diffDetails=diff_json,
        )
        print(f"New policy created successfully. Policy ID: {policy.id}")
        return {
            "policy_id": policy.id, 
            "version_number": version, 
            "created": True,
            "version": policy.version
        }

    print(f"Updating existing policy: {title} from version {policy.version} to {version}")
    print(f"Old HTML length: {len(policy.policy_template or '')}")
    print(f"New HTML length: {len(formatted_html)}")
    
    # Existing policy: compute diff vs current template
    old_html = policy.policy_template or ""
    new_html = formatted_html
    
    diff_json = compute_html_diff(old_html, new_html)
    print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

    # Update policy current template and version
    policy.policy_template = new_html
    policy.version = version
    policy.save()

    # Create new PolicyVersion with diff only
    PolicyVersion.objects.create(
        policy=policy,
        version_number=version,
        diffDetails=diff_json,
    )
    
    print(f"Policy updated successfully. New version: {version}")
    return {
        "policy_id": policy.id, 
        "version_number": version, 
        "created": False,
        "version": policy.version
    }

def reconstruct_policy_html_at_version(policy_id: int, version_number: str) -> str:
    """
    Reconstruct policy HTML for a specific version by applying diffs sequentially.
    Starts from empty and applies all diffs up to the target version.
    """
    try:
        # Get all versions up to and including the target version
        all_versions = list(PolicyVersion.objects.filter(
            policy_id=policy_id
        ).all())
        
        # Sort versions numerically
        try:
            versions_sorted = sorted(all_versions, key=lambda x: float(x.version_number))
        except ValueError:
            versions_sorted = sorted(all_versions, key=lambda x: x.version_number)
        
        # Find target version index
        target_index = None
        for i, v in enumerate(versions_sorted):
            if v.version_number == str(version_number):
                target_index = i
                break
        
        if target_index is None:
            raise ObjectDoesNotExist("Requested version does not exist")
        
        # Start from empty HTML and apply all diffs up to target version
        current_html = ""
        
        for i in range(target_index + 1):  # Apply all diffs including target version
            if versions_sorted[i].diffDetails:
                current_html = apply_diff(current_html, versions_sorted[i].diffDetails)
        
        return current_html
        
    except PolicyVersion.DoesNotExist:
        raise ObjectDoesNotExist(f"Policy version {version_number} not found for policy {policy_id}")
