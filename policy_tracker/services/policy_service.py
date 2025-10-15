import requests
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, Policy, OrganizationPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff, split_html_lines

AI_CHAT_URL = config("AI_CHAT_URL")

def extract_title_version_from_pdf(pdf_text):
    """
    Extract policy title and version from PDF text content
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
        res = requests.post(AI_CHAT_URL, json=payload)
        res.raise_for_status()
        response_text = res.json().get("response", "").strip()
        
        # Clean the response to extract JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        import json
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
            
    except Exception as e:
        print(f"PDF title/version extraction failed: {str(e)}")
        return {
            "status": 400,
            "message": f"Failed to extract title and version from PDF: {str(e)}",
            "missing_fields": ["title", "version"],
            "extracted_data": {"title": None, "version": None}
        }, None

def format_html_with_ai(title: str, version: str, raw_content: str = "", content_source: str = "metadata_only"):
    """
    Send policy information to AI service to generate complete policy HTML
    """
    
    if content_source == "metadata_only":
        # Only title and version provided - create complete policy from scratch
        prompt = f"""
        Create a comprehensive, professional policy document in HTML format with clean, readable styling.

        POLICY TITLE: {title}
        VERSION: {version}

        Generate a complete policy document that includes:

        CONTENT STRUCTURE:
        1. Clear, logical left-to-right reading layout
        2. Comprehensive policy sections:
           - Purpose and Objectives
           - Scope and Applicability  
           - Policy Statements and Principles
           - Roles and Responsibilities
           - Compliance Requirements
           - Review and Revision Process
           - Definitions
        3. Proper heading hierarchy (h1, h2, h3)

        STYLING REQUIREMENTS:
        1. Clean, professional appearance without complex colors
        2. Use system fonts (Arial, Helvetica, sans-serif) for best compatibility
        3. Simple, readable typography with proper line spacing
        4. Left-aligned content throughout
        5. Adequate margins and padding for readability
        6. Responsive design that works on all devices

        TABULAR DATA (ONLY WHERE NECESSARY):
        1. Create tables ONLY for structured data like:
           - Roles and responsibilities matrix
           - Definition lists
           - Compliance requirements
        2. Keep tables simple with minimal styling
        3. Use tables only when they genuinely improve readability

        CONTENT REQUIREMENTS:
        1. Make content comprehensive and actionable
        2. Use clear, professional language
        3. Add proper bullet points and numbering for lists
        4. Ensure content flows naturally from left to right
        5. Avoid unnecessary visual elements

        Return ONLY the complete, self-contained HTML document without any explanations.
        Focus on clean, readable content rather than complex styling.
        Include simple CSS within <style> tags in the head section.
        """

    elif content_source == "pdf":
        # PDF content provided - convert and format into proper policy
        prompt = f"""
        Transform the extracted PDF content into a clean, professionally formatted policy document in HTML.

        POLICY TITLE: {title}
        VERSION: {version}

        PDF EXTRACTED CONTENT:
        {raw_content[:6000]}

        CONTENT PROCESSING:
        1. Extract and organize the core policy content from the PDF text
        2. Structure content into logical policy sections
        3. Maintain all original policy intent and requirements
        4. Improve clarity and organization where needed
        5. Present content in clear left-to-right reading format

        DOCUMENT STRUCTURE:
        1. Simple, semantic HTML structure
        2. Clear heading hierarchy
        3. Left-aligned content throughout
        4. Proper paragraph spacing and line height

        TABLES (USE SPARINGLY):
        1. Convert to tables ONLY when content is naturally tabular:
           - Role/responsibility matrices
           - Definition lists
           - Comparison charts
        2. Keep table styling minimal and functional
        3. Avoid tables for regular paragraph content

        STYLING:
        1. Use clean, readable system fonts
        2. Simple black text on white background
        3. Adequate margins and padding
        4. Responsive design
        5. No complex colors or gradients

        Return ONLY the complete HTML policy document.
        Focus on content clarity and readability over visual design.
        """

    elif content_source in ["html_content", "html_field"]:
        # HTML content provided - clean and reformat into proper policy
        prompt = f"""
        Clean and reformat the existing HTML content into a professional policy document.

        POLICY TITLE: {title}
        VERSION: {version}

        ORIGINAL HTML CONTENT:
        {raw_content[:6000]}

        CONTENT CLEANUP:
        1. Remove any existing complex styling and colors
        2. Normalize HTML structure to clean, semantic markup
        3. Reorganize content into standard policy sections
        4. Ensure left-to-right reading flow
        5. Remove any unnecessary visual elements

        STRUCTURE IMPROVEMENT:
        1. Apply simple, clean CSS styling
        2. Use system fonts for maximum compatibility
        3. Ensure proper heading hierarchy
        4. Left-align all content
        5. Add adequate spacing for readability

        TABLES (ONLY IF BENEFICIAL):
        1. Convert to tables ONLY if content is naturally tabular
        2. Keep table structure simple and minimal
        3. Use tables for:
           - Role/responsibility lists
           - Definition sets
           - Compliance matrices

        CONTENT QUALITY:
        1. Maintain original content meaning
        2. Improve organization and clarity
        3. Ensure professional policy tone
        4. Remove any redundant or repetitive content

        Return ONLY the clean, reformatted HTML policy document.
        Focus on content readability and professional presentation.
        Keep styling minimal and functional.
        """

    else:
        # Fallback case
        prompt = f"""
        Create a professional policy document in HTML format.

        POLICY TITLE: {title}
        VERSION: {version}

        Generate a policy document with:

        CONTENT SECTIONS:
        1. Purpose and Objectives
        2. Scope
        3. Policy Statements
        4. Responsibilities
        5. Compliance
        6. Definitions
        7. Review Process

        DESIGN:
        1. Clean, left-aligned layout
        2. Simple system fonts
        3. Readable typography
        4. Responsive design

        TABLES:
        Use tables only for clearly tabular data like definitions or responsibility matrices.

        Return ONLY the complete HTML document with simple, functional styling.
        """
    
    payload = {"query": prompt}
    try:
        res = requests.post(AI_CHAT_URL, json=payload)
        res.raise_for_status()
        response_text = res.json().get("response", "").strip()
        
        # Clean up the response to ensure it's pure HTML
        if response_text.startswith('"') and response_text.endswith('"'):
            response_text = response_text[1:-1]
        
        # Remove any markdown code blocks if present
        if response_text.startswith('```html'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        return {
            "status": 200,
            "message": "Policy generated successfully by LLM"
        }, response_text
        
    except Exception as e:
        print(f"AI policy generation failed: {str(e)}")
        return {
            "status": 206,
            "message": f"AI policy generation failed: {str(e)}"
        }, ""

# Keep other existing functions for backward compatibility
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


@transaction.atomic
def create_or_update_policy_for_approval(title: str, html_template: str, version: str, description: str | None = None) -> dict:
    """
    Create a new policy or update an existing one, but only save to getting_processed_for_approval.
    Does not create PolicyVersion records until approved.
    """
    # Use the HTML directly without AI formatting for now
    formatted_html = html_template
    
    policy, created = Policy.objects.select_for_update().get_or_create(
        title=title,
        defaults={
            'getting_processed_for_approval': formatted_html,
            'policy_template': "",  # Keep policy_template empty until approved
            'version': version,
            'is_approved': False,  # Mark as not approved
        },
    )

    if created:
        print(f"Creating new policy for approval: {title} with version: {version}")
        print(f"Policy created with ID: {policy.id}, awaiting approval")
        return {
            "policy_id": policy.id, 
            "version_number": version, 
            "created": True,
            "version": policy.version,
            "status": "awaiting_approval"
        }

    print(f"Updating existing policy for approval: {title} to version {version}")
    print(f"Old getting_processed_for_approval length: {len(policy.getting_processed_for_approval or '')}")
    print(f"New getting_processed_for_approval length: {len(formatted_html)}")
    
    # Update policy staging template and version, but keep is_approved as False
    policy.getting_processed_for_approval = formatted_html
    policy.version = version
    policy.is_approved = False
    policy.save()

    print(f"Policy updated for approval successfully. New version: {version}")
    return {
        "policy_id": policy.id, 
        "version_number": version, 
        "created": False,
        "version": policy.version,
        "status": "awaiting_approval"
    }

@transaction.atomic
def approve_policy_and_create_version(policy_id: int) -> dict:
    """
    Approve a policy by moving getting_processed_for_approval to policy_template,
    setting is_approved to True, and creating a PolicyVersion record.
    """
    try:
        policy = Policy.objects.select_for_update().get(id=policy_id)
        
        if not policy.getting_processed_for_approval:
            raise ValueError("No content awaiting approval for this policy")
        
        print(f"Approving policy: {policy.title} (ID: {policy_id})")
        print(f"Moving content from getting_processed_for_approval to policy_template")
        
        # Get the content that's being approved
        new_approved_html = policy.getting_processed_for_approval
        
        # Check if this is the first approval (no existing approved template)
        if not policy.policy_template or policy.policy_template.strip() == "":
            print("First approval for this policy - creating initial version")
            
            # For first approval: diff from empty to new content (like original code)
            old_html = ""
            new_html = new_approved_html
            
            diff_json = compute_html_diff(old_html, new_html)
            print(f"First approval diff computed. Changes: {len(diff_json.get('changes', []))}")
            
            is_first_approval = True
        else:
            # For update approval: diff from old approved template to new approved template
            old_html = policy.policy_template
            new_html = new_approved_html
            
            diff_json = compute_html_diff(old_html, new_html)
            print(f"Update approval diff computed. Changes: {len(diff_json.get('changes', []))}")
            
            is_first_approval = False
        
        # Update policy: move staging to approved, mark as approved, and clear staging
        policy.policy_template = new_html
        policy.getting_processed_for_approval = None  # Clear the staging field
        policy.is_approved = True
        policy.save()
        
        # Create PolicyVersion record with the proper diff
        policy_version = PolicyVersion.objects.create(
            policy=policy,
            version_number=policy.version,
            diffDetails=diff_json,
        )
        
        print(f"Policy approved successfully. Version: {policy.version}, Version ID: {policy_version.id}")
        print(f"Diff contains {len(diff_json.get('changes', []))} changes")
        
        return {
            "policy_id": policy.id,
            "version_number": policy.version,
            "version_created": True,
            "is_first_approval": is_first_approval,
            "diff_changes_count": len(diff_json.get('changes', []))
        }
        
    except Policy.DoesNotExist:
        raise ObjectDoesNotExist(f"Policy with ID {policy_id} not found")
    except Exception as e:
        print(f"Error in approve_policy_and_create_version: {str(e)}")
        raise