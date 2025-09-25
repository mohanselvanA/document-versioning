import requests
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, Policy, OrganizationPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff

AI_CHAT_URL = config("AI_CHAT_URL")

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
    policy, created = Policy.objects.select_for_update().get_or_create(
        title=title,
        defaults={
            # 'description': description,
            'policy_template': html_template,
            'version': version,  # Use the version from frontend
        },
    )

    if created:
        # New policy - create first version with the provided version number
        version_obj = PolicyVersion.objects.create(
            policy=policy,
            version_number=version,  # Use the version from frontend
            snapshot_html=html_template,
            diffDetails={
                'changes': [],
                'old_num_lines': 0,
                'new_num_lines': len((html_template or '').splitlines()),
            },
        )
        return {
            "policy_id": policy.id, 
            "version_number": version_obj.version_number, 
            "created": True,
            "version": policy.version
        }

    # Existing policy: compute diff vs current latest template
    latest_version = PolicyVersion.objects.filter(policy=policy).order_by('-version_number').first()
    base_html = policy.policy_template or (latest_version.snapshot_html if latest_version and latest_version.snapshot_html else "")

    diff_json = compute_html_diff(base_html, html_template)

    # Update policy current template and version
    policy.policy_template = html_template
    policy.version = version  # Update to the new version from frontend
    # if description is not None:
    #     policy.description = description
    
    policy.save()

    # Create new PolicyVersion with the provided version number
    version_obj = PolicyVersion.objects.create(
        policy=policy,
        version_number=version,  # Use the version from frontend
        diffDetails=diff_json,
        snapshot_html=html_template,  # Store snapshot for this version
    )

    return {
        "policy_id": policy.id, 
        "version_number": version_obj.version_number, 
        "created": False,
        "version": policy.version
    }


def reconstruct_policy_html_at_version(policy_id: int, version_number: str) -> str:
    """
    Return the snapshot HTML for a specific policy version.
    If snapshot_html is None, reconstruct it by applying diffs from previous versions.
    """
    try:
        # Get the specific version directly
        policy_version = PolicyVersion.objects.get(
            policy_id=policy_id, 
            version_number=str(version_number)  # Ensure it's string to match the field
        )
        
        # If snapshot_html exists, return it directly
        if policy_version.snapshot_html is not None:
            return policy_version.snapshot_html
        
        # If snapshot_html is None, we need to reconstruct it by applying diffs
        # Get all versions up to this one, sorted numerically
        all_versions = list(PolicyVersion.objects.filter(policy_id=policy_id).all())
        
        # Sort versions numerically by converting to float
        try:
            versions_sorted = sorted(all_versions, key=lambda x: float(x.version_number))
        except ValueError:
            # Fallback to string sorting if version numbers can't be converted to float
            versions_sorted = sorted(all_versions, key=lambda x: x.version_number)
        
        # Find the index of our target version
        target_index = None
        for i, v in enumerate(versions_sorted):
            if v.version_number == str(version_number):
                target_index = i
                break
        
        if target_index is None:
            raise ObjectDoesNotExist("Requested version does not exist")
        
        # Start from the first version that has a snapshot
        base_version = None
        for i in range(target_index, -1, -1):
            if versions_sorted[i].snapshot_html is not None:
                base_version = versions_sorted[i]
                break
        
        if base_version is None:
            # No snapshot found, start from empty
            current_html = ""
            start_index = 0
        else:
            current_html = base_version.snapshot_html
            start_index = i + 1  # Start applying diffs from next version
        
        # Apply diffs from base_version up to target_version
        for i in range(start_index, target_index + 1):
            if versions_sorted[i].diffDetails:
                current_html = apply_diff(current_html, versions_sorted[i].diffDetails)
        
        return current_html
        
    except PolicyVersion.DoesNotExist:
        raise ObjectDoesNotExist(f"Policy version {version_number} not found for policy {policy_id}")