# import requests
# from decouple import config
# from django.core.exceptions import ObjectDoesNotExist
# from django.db import transaction
# from ..models import Organization, Policy, OrganizationPolicy, PolicyVersion
# from ..utils.diff_utils import compute_html_diff, apply_diff, split_html_lines

# AI_CHAT_URL = config("AI_CHAT_URL")

# def extract_title_version_from_pdf(pdf_text):
#     """
#     Extract policy title and version from PDF text content
#     """
#     prompt = f"""
#     Analyze the following PDF text content and extract the policy title and version number.
    
#     PDF CONTENT:
#     {pdf_text[:4000]}  # Limit content to avoid token limits
    
#     INSTRUCTIONS:
#     1. Identify the main policy title - look for the most prominent heading or document title
#     2. Identify the version number - look for patterns like "Version X.X", "v1.0", "Rev 2.3", etc.
#     3. If you find both title and version, return them in JSON format
#     4. If title is missing, indicate which field is missing
#     5. If version is missing, indicate which field is missing
#     6. If both are missing, indicate both are missing
    
#     RETURN FORMAT (JSON):
#     {{
#         "title": "Extracted Policy Title or null if not found",
#         "version": "Extracted Version Number or null if not found"
#     }}
    
#     Return ONLY the JSON object without any additional text or explanations.
#     """
    
#     payload = {"query": prompt}
#     try:
#         res = requests.post(AI_CHAT_URL, json=payload)
#         res.raise_for_status()
#         response_text = res.json().get("response", "").strip()
        
#         # Clean the response to extract JSON
#         response_text = response_text.replace('```json', '').replace('```', '').strip()
        
#         import json
#         extracted_data = json.loads(response_text)
        
#         missing_fields = []
#         if not extracted_data.get("title"):
#             missing_fields.append("title")
#         if not extracted_data.get("version"):
#             missing_fields.append("version")
        
#         if missing_fields:
#             return {
#                 "status": 400,
#                 "message": f"Missing required fields from PDF: {', '.join(missing_fields)}",
#                 "missing_fields": missing_fields,
#                 "extracted_data": extracted_data
#             }, None
#         else:
#             return {
#                 "status": 200,
#                 "message": "Title and version successfully extracted from PDF",
#                 "extracted_data": extracted_data
#             }, extracted_data
            
#     except Exception as e:
#         print(f"PDF title/version extraction failed: {str(e)}")
#         return {
#             "status": 400,
#             "message": f"Failed to extract title and version from PDF: {str(e)}",
#             "missing_fields": ["title", "version"],
#             "extracted_data": {"title": None, "version": None}
#         }, None

# def format_html_with_ai(title: str, version: str, raw_content: str = "", content_source: str = "metadata_only", 
#                         department: str = "", category: str = "", approver_1: str = "", approver_2: str = "", 
#                         assignees: str = "", review_date: str = "", expiry_date: str = ""):
#     """
#     Send policy information to AI service to generate complete policy HTML.
#     Dynamically includes optional fields if provided.
#     """

#     # Prepare optional metadata block
#     metadata_html = ""
#     if department:
#         metadata_html += f"<p><strong>Department:</strong> {department}</p>\n"
#     if category:
#         metadata_html += f"<p><strong>Category:</strong> {category}</p>\n"
#     if approver_1:
#         metadata_html += f"<p><strong>Approver 1:</strong> {approver_1}</p>\n"
#     if approver_2:
#         metadata_html += f"<p><strong>Approver 2:</strong> {approver_2}</p>\n"
#     if assignees:
#         metadata_html += f"<p><strong>Assignees:</strong> {assignees}</p>\n"
#     if review_date:
#         metadata_html += f"<p><strong>Review Date:</strong> {review_date}</p>\n"
#     if expiry_date:
#         metadata_html += f"<p><strong>Expiry Date:</strong> {expiry_date}</p>\n"

#     if content_source == "metadata_only":
#         prompt = f"""
#         Create a comprehensive, professional policy document in HTML format with clean, readable styling.

#         POLICY TITLE: {title}
#         VERSION: {version}

#         Include the following metadata if present:
#         {metadata_html}

#         Generate a complete policy document that includes:

#         CONTENT STRUCTURE:
#         1. Clear, logical left-to-right reading layout
#         2. Comprehensive policy sections:
#            - Purpose and Objectives
#            - Scope and Applicability  
#            - Policy Statements and Principles
#            - Roles and Responsibilities
#            - Compliance Requirements
#            - Review and Revision Process
#            - Definitions
#         3. Proper heading hierarchy (h1, h2, h3)

#         STYLING REQUIREMENTS:
#         1. Clean, professional appearance without complex colors
#         2. Use system fonts (Arial, Helvetica, sans-serif) for best compatibility
#         3. Simple, readable typography with proper line spacing
#         4. Left-aligned content throughout
#         5. Adequate margins and padding for readability
#         6. Responsive design that works on all devices

#         TABULAR DATA (ONLY WHERE NECESSARY):
#         1. Create tables ONLY for structured data like:
#            - Roles and responsibilities matrix
#            - Definition lists
#            - Compliance requirements
#         2. Keep tables simple with minimal styling
#         3. Use tables only when they genuinely improve readability

#         CONTENT REQUIREMENTS:
#         1. Make content comprehensive and actionable
#         2. Use clear, professional language
#         3. Add proper bullet points and numbering for lists
#         4. Ensure content flows naturally from left to right
#         5. Avoid unnecessary visual elements

#         Return ONLY the complete, self-contained HTML document without any explanations.
#         Focus on clean, readable content rather than complex styling.
#         Include simple CSS within <style> tags in the head section.
#         """
#     else:
#         # For pdf or html content sources, include metadata_html in the instructions
#         prompt = f"""
#         Transform the provided content into a clean, professionally formatted policy document in HTML.

#         POLICY TITLE: {title}
#         VERSION: {version}

#         Include the following metadata if present:
#         {metadata_html}

#         CONTENT TO PROCESS:
#         {raw_content[:6000]}

#         Ensure content is structured with proper headings, readable typography, and tables only if necessary.

#         Return ONLY the complete HTML policy document.
#         Focus on content clarity, readability, and include metadata in the output HTML.
#         """

#     payload = {"query": prompt}

#     try:
#         res = requests.post(AI_CHAT_URL, json=payload)
#         res.raise_for_status()
#         response_text = res.json().get("response", "").strip()

#         # Clean response
#         if response_text.startswith('"') and response_text.endswith('"'):
#             response_text = response_text[1:-1]
#         if response_text.startswith('```html'):
#             response_text = response_text[7:]
#         if response_text.endswith('```'):
#             response_text = response_text[:-3]
#         response_text = response_text.strip()

#         # Optionally slice starting from <h1> for consistency
#         start_index = response_text.find("<h1>")
#         if start_index >= 0:
#             response_text = response_text[start_index:]

#         return {"status": 200, "message": "Policy generated successfully by LLM"}, response_text

#     except Exception as e:
#         print(f"AI policy generation failed: {str(e)}")
#         return {"status": 206, "message": f"AI policy generation failed: {str(e)}"}, ""


# # Keep other existing functions for backward compatibility
# def analyze_policy_content(content, policy_titles):
#     """Send content to AI service for policy analysis"""
#     prompt = f"""
#     You are a compliance assistant. Compare the new policy content with the list of existing policy titles.

#     New Policy Content:
#     {content}

#     Existing Policy Titles:
#     {', '.join(policy_titles)}

#     Instructions:
#     1. Analyze if the new policy content matches or is very similar to any of the existing policy titles
#     2. If there's a clear match, return ONLY the matching policy title from the list
#     3. If no clear match is found, return "No matching policy found"
#     4. Do not add any explanations, summaries, or additional text
#     5. Return only the exact policy title from the list or "No matching policy found"
#     """

#     payload = {"query": prompt}
#     res = requests.post(AI_CHAT_URL, json=payload)
#     res.raise_for_status()
    
#     return res.json().get("response", "").strip()

# def analyze_policy_content(content, policy_titles):
#     """Send content to AI service for policy analysis"""
#     prompt = f"""
#     You are a compliance assistant. Compare the new policy content with the list of existing policy titles.

#     New Policy Content:
#     {content}

#     Existing Policy Titles:
#     {', '.join(policy_titles)}

#     Instructions:
#     1. Analyze if the new policy content matches or is very similar to any of the existing policy titles
#     2. If there's a clear match, return ONLY the matching policy title from the list
#     3. If no clear match is found, return "No matching policy found"
#     4. Do not add any explanations, summaries, or additional text
#     5. Return only the exact policy title from the list or "No matching policy found"
#     """

#     payload = {"query": prompt}
#     res = requests.post(AI_CHAT_URL, json=payload)
#     res.raise_for_status()
    
#     return res.json().get("response", "").strip()

# def link_policy_to_organization(org_id, policy_title):
#     """Link policy to organization if match found"""
#     try:
#         org = Organization.objects.get(id=org_id)
#         policy = Policy.objects.get(title=policy_title)

#         OrganizationPolicy.objects.get_or_create(
#             organization=org,
#             policy=policy
#         )
#         return True
#     except ObjectDoesNotExist as e:
#         raise e
#     except Exception as e:
#         raise e

# def get_all_policy_titles():
#     """Get all policy titles from database"""
#     return [policy.title for policy in Policy.objects.all()]


# @transaction.atomic
# def create_or_update_policy_with_version(title: str, html_template: str, version: str, description: str | None = None) -> dict:
#     """
#     Create a new policy or update an existing one, recording a PolicyVersion diff.
#     """
#     # Remove AI formatting for now to debug the issue
#     # formatted_html = format_html_with_ai(html_template)
#     formatted_html = html_template  # Use the HTML directly without AI formatting
    
#     policy, created = Policy.objects.select_for_update().get_or_create(
#         title=title,
#         defaults={
#             'policy_template': formatted_html,
#             'version': version,
#         },
#     )

#     if created:
#         print(f"Creating new policy: {title} with version: {version}")
#         # New policy - create first version with empty diff
#         old_html = ""
#         new_html = formatted_html
        
#         diff_json = compute_html_diff(old_html, new_html)
        
#         PolicyVersion.objects.create(
#             policy=policy,
#             version_number=version,
#             diffDetails=diff_json,
#         )
#         print(f"New policy created successfully. Policy ID: {policy.id}")
#         return {
#             "policy_id": policy.id, 
#             "version_number": version, 
#             "created": True,
#             "version": policy.version
#         }

#     print(f"Updating existing policy: {title} from version {policy.version} to {version}")
#     print(f"Old HTML length: {len(policy.policy_template or '')}")
#     print(f"New HTML length: {len(formatted_html)}")
    
#     # Existing policy: compute diff vs current template
#     old_html = policy.policy_template or ""
#     new_html = formatted_html
    
#     diff_json = compute_html_diff(old_html, new_html)
#     print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

#     # Update policy current template and version
#     policy.policy_template = new_html
#     policy.version = version
#     policy.save()

#     # Create new PolicyVersion with diff only
#     PolicyVersion.objects.create(
#         policy=policy,
#         version_number=version,
#         diffDetails=diff_json,
#     )
    
#     print(f"Policy updated successfully. New version: {version}")
#     return {
#         "policy_id": policy.id, 
#         "version_number": version, 
#         "created": False,
#         "version": policy.version
#     }

# def reconstruct_policy_html_at_version(policy_id: int, version_number: str) -> str:
#     """
#     Reconstruct policy HTML for a specific version by applying diffs sequentially.
#     Starts from empty and applies all diffs up to the target version.
#     """
#     try:
#         # Get all versions up to and including the target version
#         all_versions = list(PolicyVersion.objects.filter(
#             policy_id=policy_id
#         ).all())
        
#         # Sort versions numerically
#         try:
#             versions_sorted = sorted(all_versions, key=lambda x: float(x.version_number))
#         except ValueError:
#             versions_sorted = sorted(all_versions, key=lambda x: x.version_number)
        
#         # Find target version index
#         target_index = None
#         for i, v in enumerate(versions_sorted):
#             if v.version_number == str(version_number):
#                 target_index = i
#                 break
        
#         if target_index is None:
#             raise ObjectDoesNotExist("Requested version does not exist")
        
#         # Start from empty HTML and apply all diffs up to target version
#         current_html = ""
        
#         for i in range(target_index + 1):  # Apply all diffs including target version
#             if versions_sorted[i].diffDetails:
#                 current_html = apply_diff(current_html, versions_sorted[i].diffDetails)
        
#         return current_html
        
#     except PolicyVersion.DoesNotExist:
#         raise ObjectDoesNotExist(f"Policy version {version_number} not found for policy {policy_id}")


# @transaction.atomic
# def create_or_update_policy_for_approval(title: str, html_template: str, version: str, description: str | None = None) -> dict:
#     """
#     Create a new policy or update an existing one, but only save to getting_processed_for_approval.
#     Does not create PolicyVersion records until approved.
#     """
#     # Use the HTML directly without AI formatting for now
#     formatted_html = html_template
    
#     policy, created = Policy.objects.select_for_update().get_or_create(
#         title=title,
#         defaults={
#             'getting_processed_for_approval': formatted_html,
#             'policy_template': "",  # Keep policy_template empty until approved
#             'version': version,
#             'is_approved': False,  # Mark as not approved
#         },
#     )

#     if created:
#         print(f"Creating new policy for approval: {title} with version: {version}")
#         print(f"Policy created with ID: {policy.id}, awaiting approval")
#         return {
#             "policy_id": policy.id, 
#             "version_number": version, 
#             "created": True,
#             "version": policy.version,
#             "status": "awaiting_approval"
#         }

#     print(f"Updating existing policy for approval: {title} to version {version}")
#     print(f"Old getting_processed_for_approval length: {len(policy.getting_processed_for_approval or '')}")
#     print(f"New getting_processed_for_approval length: {len(formatted_html)}")
    
#     # Update policy staging template and version, but keep is_approved as False
#     policy.getting_processed_for_approval = formatted_html
#     policy.version = version
#     policy.is_approved = False
#     policy.save()

#     print(f"Policy updated for approval successfully. New version: {version}")
#     return {
#         "policy_id": policy.id, 
#         "version_number": version, 
#         "created": False,
#         "version": policy.version,
#         "status": "awaiting_approval"
#     }

# @transaction.atomic
# def approve_policy_and_create_version(policy_id: int) -> dict:
#     """
#     Approve a policy by moving getting_processed_for_approval to policy_template,
#     setting is_approved to True, and creating a PolicyVersion record.
#     """
#     try:
#         policy = Policy.objects.select_for_update().get(id=policy_id)
        
#         if not policy.getting_processed_for_approval:
#             raise ValueError("No content awaiting approval for this policy")
        
#         print(f"Approving policy: {policy.title} (ID: {policy_id})")
#         print(f"Moving content from getting_processed_for_approval to policy_template")
        
#         # Get the content that's being approved
#         new_approved_html = policy.getting_processed_for_approval
        
#         # Check if this is the first approval (no existing approved template)
#         if not policy.policy_template or policy.policy_template.strip() == "":
#             print("First approval for this policy - creating initial version")
            
#             # For first approval: diff from empty to new content (like original code)
#             old_html = ""
#             new_html = new_approved_html
            
#             diff_json = compute_html_diff(old_html, new_html)
#             print(f"First approval diff computed. Changes: {len(diff_json.get('changes', []))}")
            
#             is_first_approval = True
#         else:
#             # For update approval: diff from old approved template to new approved template
#             old_html = policy.policy_template
#             new_html = new_approved_html
            
#             diff_json = compute_html_diff(old_html, new_html)
#             print(f"Update approval diff computed. Changes: {len(diff_json.get('changes', []))}")
            
#             is_first_approval = False
        
#         # Update policy: move staging to approved, mark as approved, and clear staging
#         policy.policy_template = new_html
#         policy.getting_processed_for_approval = None  # Clear the staging field
#         policy.is_approved = True
#         policy.save()
        
#         # Create PolicyVersion record with the proper diff
#         policy_version = PolicyVersion.objects.create(
#             policy=policy,
#             version_number=policy.version,
#             diffDetails=diff_json,
#         )
        
#         print(f"Policy approved successfully. Version: {policy.version}, Version ID: {policy_version.id}")
#         print(f"Diff contains {len(diff_json.get('changes', []))} changes")
        
#         return {
#             "policy_id": policy.id,
#             "version_number": policy.version,
#             "version_created": True,
#             "is_first_approval": is_first_approval,
#             "diff_changes_count": len(diff_json.get('changes', []))
#         }
        
#     except Policy.DoesNotExist:
#         raise ObjectDoesNotExist(f"Policy with ID {policy_id} not found")
#     except Exception as e:
#         print(f"Error in approve_policy_and_create_version: {str(e)}")
#         raise



import requests
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, OrgPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff, split_html_lines, reconstruct_from_checkpoint

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

def format_html_with_ai(template, title, department, category):
    """
    Send policy information to AI service to generate complete policy HTML.
    Dynamically includes optional fields if provided.
    """
    version = "Initial Draft V0"
    date = "October 27, 2025"
    company_name = "Your Company"
    company_logo = "logo"
    expiry_date = "October 27, 2026"
    if template:

        prompt = f"""
        Create a comprehensive, professional policy document in HTML format with modern, visually appealing styling.

        POLICY TITLE: {title}
        DEPARTMENT: {department}
        CATEGORY: {category}
        VERSION: {version}
        COMPANY NAME: {company_name}
        COMPANY LOGO URL: {company_logo}
        DATE: {date}
        EXPIRY DATE: {expiry_date}

        Include the following metadata if present:
        {template}

        Generate a complete policy document that includes:

        CONTENT STRUCTURE:
        1. A header section with:
        - Company logo (if provided) centered at the top
        - Company name as a prominent subheading
        - Policy title as the main heading
        - Version, Date, Expiry Date, Department, and Category (if provided) in a metadata block
        2. Comprehensive policy sections tailored to the specified department ({department}) and category ({category}):
        - Purpose and Objectives (specific to {department} and {category})
        - Scope and Applicability (relevant to {department} and {category})
        - Policy Statements and Principles (customized for {department} and {category})
        - Roles and Responsibilities (defined within the context of {department} and {category})
        - Compliance Requirements (aligned with {department} and {category} standards)
        - Review and Revision Process
        - Definitions (terms relevant to {department} and {category})
        3. Proper heading hierarchy (h1 for title, h2 for sections, h3 for subsections)
        4. A footer with the company name and date

        STYLING REQUIREMENTS:
        1. Modern, professional appearance with a clean color palette:
        - Primary background: #F9FAFB (light gray)
        - Accent color: #1E3A8A (deep blue) for headings and borders
        - Secondary accent: #E5E7EB (light gray) for subtle dividers
        - Text color: #1F2937 (dark gray) for body text
        2. Use system fonts (Inter, Arial, sans-serif) for compatibility and modern look
        3. Typography:
        - Headings: Bold, Inter font, sizes (h1: 2.5rem, h2: 1.875rem, h3: 1.25rem)
        - Body: 1rem, line-height 1.5, Inter font
        4. Responsive design:
        - Max-width of 800px for main content, centered
        - Padding: 2rem on desktop, 1rem on mobile
        - Logo scales to max-width 200px on desktop, 150px on mobile
        5. Subtle shadows for header and tables (box-shadow: 0 2px 4px rgba(0,0,0,0.1))
        6. Left-aligned content with 1rem spacing between sections
        7. Footer with light gray background, centered text, and 1rem padding

        TABULAR DATA (ONLY WHERE NECESSARY):
        1. Use tables ONLY for structured data like:
        - Roles and responsibilities matrix
        - Definition lists
        - Compliance requirements
        2. Table styling:
        - Border: 1px solid #E5E7EB
        - Header background: #1E3A8A, text color: #FFFFFF
        - Alternating row backgrounds: #FFFFFF and #F9FAFB
        - Padding: 0.75rem
        - Subtle shadow: box-shadow: 0 2px 4px rgba(0,0,0,0.1)

        CONTENT REQUIREMENTS:
        1. Use clear, professional, and actionable language
        2. Include proper bullet points and numbering for lists
        3. Ensure content flows naturally from left to right
        4. Avoid unnecessary visual elements or complex animations
        5. Include metadata (version, date, expiry date, department, category) in a clean, labeled format
        6. Tailor all policy content, examples, and details to be relevant and specific to the provided department ({department}) and category ({category}), ensuring the policy addresses needs and scenarios typical to that department and category.

        Return ONLY the complete, self-contained HTML document without any explanations.
        Include CSS within <style> tags in the head section.
        Ensure the design is modern, professional, and responsive, with a focus on readability.
        """
    
    payload = {"query": prompt}

    try:
        res = requests.post(AI_CHAT_URL, json=payload)
        res.raise_for_status()
        response_text = res.json().get("response", "").strip()

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

    except Exception as e:
        print(f"AI policy generation failed: {str(e)}")
        return {"status": 206, "message": f"AI policy generation failed: {str(e)}"}, ""

@transaction.atomic
def create_or_update_policy_with_version(title: str, html_template: str, version: str, org: Organization, created_by: str, updated_by: str, description: str | None = None) -> dict:
    """
    Create a new OrgPolicy or update an existing one, recording a PolicyVersion diff.
    """
    formatted_html = html_template  # Use HTML directly, as in original logic
    
    org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
        title=title,
        organization=org,
        defaults={
            'template': formatted_html,
            'policy_type': 'existingpolicy',
            'created_by': created_by,
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
            status='published',  # Set as published since we're bypassing approval
            created_by=created_by,
            updated_by=updated_by,
        )
        print(f"New OrgPolicy created successfully. OrgPolicy ID: {org_policy.id}, PolicyVersion ID: {policy_version.id}")
        return {
            "org_policy_id": org_policy.id,
            "policy_version_id": policy_version.id,
            "version_number": version,
            "created": True,
        }

    print(f"Updating existing OrgPolicy: {title} from version to {version} for organization: {org.id}")
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
        status='published',  # Set as published since we're bypassing approval
        created_by=created_by,
        updated_by=updated_by,
    )
    
    print(f"OrgPolicy updated successfully. New version: {version}, PolicyVersion ID: {policy_version.id}")
    return {
        "org_policy_id": org_policy.id,
        "policy_version_id": policy_version.id,
        "version_number": version,
        "created": False,
    }

def reconstruct_policy_html_at_version(org_policy_id: int, target_version: str) -> str:
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
            if version.version <= target_version and version.checkpoint:
                nearest_checkpoint = version
                break
        
        if nearest_checkpoint:
            print(f"Using checkpoint at version {nearest_checkpoint.version} to reconstruct version {target_version}")
            # Reconstruct from checkpoint
            return reconstruct_from_checkpoint(nearest_checkpoint, target_version_obj)
        else:
            # No checkpoint found, reconstruct from beginning
            print(f"No checkpoint found, reconstructing version {target_version} from beginning")
            current_html = ""
            for version in all_versions:
                if version.diff_data:
                    current_html = apply_diff(current_html, version.diff_data)
                if version.version == target_version:
                    break
            return current_html
        
    except Exception as e:
        print(f"Error reconstructing policy HTML: {str(e)}")
        raise e