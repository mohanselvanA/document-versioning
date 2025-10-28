# import json, requests
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.core.exceptions import ObjectDoesNotExist
# from .models import Policy, PolicyVersion

# from .utils.pdf_processor import process_content, extract_pdf_from_content, html_to_text, extract_text_from_pdf_preserve_formatting
# from .services.policy_service import (
#     analyze_policy_content, 
#     link_policy_to_organization, 
#     get_all_policy_titles,
#     create_or_update_policy_for_approval,
#     reconstruct_policy_html_at_version,
#     format_html_with_ai,
#     approve_policy_and_create_version,
#     extract_title_version_from_pdf
# )

# from .utils.diff_utils import compute_html_diff, apply_diff, split_html_lines

# @csrf_exempt
# def policy_template_check(request):
#     if request.method != "POST":
#         return JsonResponse({"error": "POST method required"}, status=405)

#     try:
#         org_id = 1
        
#         data = json.loads(request.body)
#         content = data.get('content', '')
#         files = data.get('files', [])
#         content_data = {'content': content, 'files': files}

#         processed_content = process_content(content_data)
        
#         if not processed_content:
#             return JsonResponse({"error": "No extractable content found in PDF or HTML"}, status=400)

#         policy_titles = get_all_policy_titles()
        
#         if not policy_titles:
#             return JsonResponse({"error": "No policies found in database"}, status=404)

#         ai_reply = analyze_policy_content(processed_content, policy_titles)

#         if ai_reply and ai_reply != "No matching policy found":
#             try:
#                 link_policy_to_organization(org_id, ai_reply)
#             except ObjectDoesNotExist as e:
#                 return JsonResponse({"error": str(e)}, status=404)
#             except Exception as e:
#                 print(f"Warning: Could not link policy to organization: {str(e)}")

#         return JsonResponse({
#             "analysis": ai_reply,
#             "processed_content_length": len(processed_content),
#             "status": "success"
#         }, status=200)

#     except json.JSONDecodeError:
#         return JsonResponse({"error": "Invalid JSON data"}, status=400)
#     except requests.RequestException as e:
#         return JsonResponse({"error": f"AI service error: {str(e)}"}, status=503)
#     except Exception as e:
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

# @csrf_exempt
# def create_policy(request):
#     if request.method != "POST":
#         return JsonResponse({"error": "POST method required"}, status=405)

#     try:
#         # Parse and preserve the ENTIRE original request payload
#         data = json.loads(request.body)
#         original_payload = data.copy()  # This contains ALL fields: assignees, approver_1, department, etc.

#         # Validate required fields
#         organization_id = data.get("organization_id")
#         if not organization_id:
#             return JsonResponse(
#                 {**original_payload, "error": "organization_id is required"}, 
#                 status=400
#             )

#         # Extract known fields (for processing)
#         title = data.get("title")
#         version = data.get("policy_version")
#         files = data.get("file", [])
#         content = data.get("content", "")
#         html = data.get("html")

#         # Process files if present
#         raw_content = ""
#         content_source = ""

#         if files:
#             # Normalize files structure as before
#             normalized_files = [{
#                 "type": "application/pdf",
#                 "data": files,
#                 "name": "document.pdf"
#             }]
#             pdf_data = extract_pdf_from_content({"files": normalized_files})
#             if pdf_data:
#                 pdf_text = extract_text_from_pdf_preserve_formatting(pdf_data)
#                 if pdf_text:
#                     raw_content = pdf_text
#                     content_source = "pdf"
#                     extraction_result = extract_title_version_from_pdf(pdf_text)
#                     if extraction_result[0].get("status") != 200:
#                         response = {
#                             **original_payload,
#                             "status": "error",
#                             "message": extraction_result[0].get("message"),
#                             "missing_fields": extraction_result[0].get("missing_fields", []),
#                             "extracted_data": extraction_result[0].get("extracted_data", {})
#                         }
#                         return JsonResponse(response, status=400)

#                     extracted_data = extraction_result[0].get("extracted_data", {})
#                     if not title:
#                         title = extracted_data.get("title")
#                     if not version:
#                         version = extracted_data.get("version")

#         elif html is not None:
#             raw_content = html_to_text(html)
#             content_source = "html_field"
#         elif content:
#             raw_content = html_to_text(content)
#             content_source = "html_content"
#         else:
#             content_source = "metadata_only"

#         # Call LLM
#         formatting_result = format_html_with_ai(title, version, raw_content, content_source)
#         status_code = formatting_result[0].get("status")

#         if status_code == 200:
#             formatted_html = formatting_result[1]
            
#             # Compute diff details similar to second codebase
#             # For new policy creation, diff from empty to formatted_html
#             old_html = ""
#             new_html = formatted_html
#             diff_details = compute_html_diff(old_html, new_html)
#             print(diff_details)
            
#             response = {
#                 **original_payload,  # 👈 ALL original fields included here
#                 "status": "success",
#                 "message": formatted_html,
#                 "title": title,
#                 "version": version,
#                 "organization_id": organization_id,
#                 "diff_details": diff_details,  # 👈 Add diff details to response
#                 "old_num_lines": diff_details.get("old_num_lines", 0),
#                 "new_num_lines": diff_details.get("new_num_lines", 0),
#                 "changes_count": len(diff_details.get("changes", []))
#             }
#             return JsonResponse(response, status=200)

#         elif status_code == 206:
#             # Even if LLM fails, compute diff with the raw content
#             old_html = ""
#             new_html = raw_content
#             diff_details = compute_html_diff(old_html, new_html)
            
#             response = {
#                 **original_payload,  # 👈 Again, include everything
#                 "status": "error",
#                 "message": "LLM failed to generate policy content",
#                 "title": title,
#                 "version": version,
#                 "organization_id": organization_id,
#                 "diff_details": diff_details,  # 👈 Add diff details even for error case
#                 "old_num_lines": diff_details.get("old_num_lines", 0),
#                 "new_num_lines": diff_details.get("new_num_lines", 0),
#                 "changes_count": len(diff_details.get("changes", []))
#             }
#             return JsonResponse(response, status=500)

#         else:
#             raise Exception(f"Unexpected LLM formatting status: {status_code}")

#     except json.JSONDecodeError:
#         return JsonResponse({"error": "Invalid JSON data"}, status=400)

#     except Exception as e:
#         # Even on crash, try to return original data if possible
#         try:
#             original = json.loads(request.body)
#         except:
#             original = {}
#         return JsonResponse(
#             {**original, "error": f"Internal server error: {str(e)}"}, 
#             status=500
#         )

# @csrf_exempt
# def policy_save(request):
#     if request.method != "POST":
#         return JsonResponse({"error": "POST method required"}, status=405)

#     try:
#         data = json.loads(request.body)
#         title = data.get("title")
#         html = data.get("html")
#         version = data.get("version")
        
#         print(f"Received save request - Title: {title}, Version: {version}")
#         print(f"HTML length: {len(html) if html else 0}")
        
#         if not title or html is None or version is None:
#             return JsonResponse({"error": "title, html, and version are required"}, status=400)

#         # Validate version is a valid string
#         if not version.strip():
#             return JsonResponse({"error": "version is required"}, status=400)

#         # Use the new approval workflow instead of direct save
#         result = create_or_update_policy_for_approval(
#             title=title, 
#             html_template=html,
#             version=version.strip()
#         )
#         print(f"Save result: {result}")
#         return JsonResponse({"status": "success", **result})
#     except json.JSONDecodeError:
#         return JsonResponse({"error": "Invalid JSON data"}, status=400)
#     except Exception as e:
#         print(f"Error in policy_save: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

# def policy_version_html(request, policy_id: int, version_number: int):
#     if request.method != "GET":
#         return JsonResponse({"error": "GET method required"}, status=405)

#     try:
#         html = reconstruct_policy_html_at_version(policy_id=policy_id, version_number=version_number)
#         return JsonResponse({"policy_id": policy_id, "version_number": version_number, "html": html})
#     except ObjectDoesNotExist as e:
#         return JsonResponse({"error": str(e)}, status=404)
#     except Exception as e:
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

# @csrf_exempt
# def list_policies(request):
#     if request.method != "GET":
#         return JsonResponse({"error": "GET method required"}, status=405)

#     policies = list(Policy.objects.values("id", "title", "version"))
#     return JsonResponse({"policies": policies})

# def get_policy_latest(request, policy_id: int):
#     if request.method != "GET":
#         return JsonResponse({"error": "GET method required"}, status=405)

#     try:
#         policy = Policy.objects.get(id=policy_id)
        
#         # Get all versions and convert version_number to float for proper numerical sorting
#         versions = list(policy.versions.all())
#         if not versions:
#             return JsonResponse({"error": "No versions found"}, status=404)
        
#         # Sort versions by converting version_number to float for numerical comparison
#         versions_sorted = sorted(versions, key=lambda x: float(x.version_number), reverse=True)
#         latest_version = versions_sorted[0]
        
#         html = reconstruct_policy_html_at_version(policy_id, latest_version.version_number)
#         return JsonResponse(
#             {
#                 "html": html,
#                 "version": policy.version,
#                 "version_number": latest_version.version_number,
#             }
#         )
#     except ObjectDoesNotExist:
#         return JsonResponse({"error": "Policy not found"}, status=404)
#     except ValueError:
#         return JsonResponse({"error": "Invalid version number format"}, status=400)
#     except Exception as e:
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

# def get_policy_versions(request, policy_id: int):
#     if request.method != "GET":
#         return JsonResponse({"error": "GET method required"}, status=405)

#     try:
#         policy = Policy.objects.get(id=policy_id)
#         versions = list(policy.versions.all())
        
#         # Sort versions numerically by converting to float
#         versions_sorted = sorted(versions, key=lambda x: float(x.version_number), reverse=True)
        
#         versions_data = []
#         for version in versions_sorted:
#             versions_data.append({
#                 "version_number": version.version_number,
#                 "created_at": version.created_at
#             })
            
#         return JsonResponse({
#             "versions": versions_data,
#             "policy_version": policy.version
#         })
#     except ObjectDoesNotExist:
#         return JsonResponse({"error": "Policy not found"}, status=404)
#     except ValueError:
#         return JsonResponse({"error": "Invalid version number format"}, status=400)
#     except Exception as e:
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

# @csrf_exempt
# def approve_policy(request, policy_id: int):
#     if request.method != "GET":
#         return JsonResponse({"error": "GET method required"}, status=405)

#     try:
#         # Call the service to approve the policy and create version
#         result = approve_policy_and_create_version(policy_id)
        
#         return JsonResponse({
#             "status": "success",
#             "message": "Policy approved successfully",
#             "policy_id": policy_id,
#             "version_number": result["version_number"]
#         })

#     except ObjectDoesNotExist as e:
#         return JsonResponse({"error": str(e)}, status=404)
#     except Exception as e:
#         return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from .models import PolicyTemplate, Organization, OrgPolicy, PolicyVersion
from .services.policy_service import format_html_with_ai, reconstruct_policy_html_at_version
from .utils.diff_utils import compute_html_diff,apply_diff 

@csrf_exempt
def initialise_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        org_id = data.get("organization_id")
        if not org_id:
            return JsonResponse({"error": "organization_id is required"}, status=400)

        policy_template_id = data.get("policy_template_id")
        if not policy_template_id:
            return JsonResponse({"error": "policy_template_id is required"}, status=400)
        
        department = data.get("department")
        category = data.get("category")

        # Validate policy template
        try:
            policy_obj = PolicyTemplate.objects.get(id=uuid.UUID(policy_template_id))
        except PolicyTemplate.DoesNotExist:
            return JsonResponse({"error": "Policy template not found"}, status=404)

        template = policy_obj.template
        title = policy_obj.title
        version = data.get("version", "0.1")  # Default version for initialization
        created_by = data.get("created_by", "system")

        # === STEP 1: Generate AI formatted HTML ===
        formatting_result, llm_template = format_html_with_ai(template, title, department, category)

        # Validate AI response
        if not formatting_result or formatting_result.get("status") != 200:
            msg = formatting_result.get("message") if formatting_result else "Unknown LLM error"
            print(f"[ERROR] LLM generation failed: {msg}")
            return JsonResponse(
                {"error": f"AI policy generation failed: {msg}"},
                status=502
            )

        # if not llm_template or "<html" not in llm_template.lower():
        #     print("[ERROR] LLM returned invalid HTML content.")
        #     return JsonResponse(
        #         {"error": "AI returned invalid or empty policy HTML. Nothing was saved."},
        #         status=502
        #     )

        # === STEP 2: Fetch organization ===
        try:
            org = Organization.objects.get(id=uuid.UUID(org_id))
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        # === STEP 3: Create or update OrgPolicy ONLY (no PolicyVersion) ===
        with transaction.atomic():
            org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
                title=title,
                organization=org,
                defaults={
                    'template': llm_template,
                    'policy_type': 'existingpolicy',
                    'created_by': created_by,
                    'updated_by': created_by,
                },
            )

            if not created:
                # Update existing policy
                org_policy.template = llm_template
                org_policy.updated_by = created_by
                org_policy.save()

        # === STEP 4: Return success with org_policy_id ===
        return JsonResponse({
            "message": "Policy initialized successfully",
            "org_policy_id": str(org_policy.id),
            "created": created,
        }, status=201 if created else 200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

@csrf_exempt
def create_the_initialised_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        org_policy_id = data.get("org_policy_id")
        if not org_policy_id:
            return JsonResponse({"error": "org_policy_id is required"}, status=400)
        
        html_content = data.get("html_content", None)  # Optional parameter

        created_by = data.get("created_by", "system")
        version = "1.0"  # Fixed version as requested

        # === STEP 1: Fetch the initialized OrgPolicy ===
        try:
            org_policy = OrgPolicy.objects.get(id=uuid.UUID(org_policy_id))
        except OrgPolicy.DoesNotExist:
            return JsonResponse({"error": "OrgPolicy not found"}, status=404)

        # === STEP 2: Determine checkpoint content ===
        if html_content is None:
            # Save OrgPolicy template in checkpoint
            checkpoint_content = org_policy.template or ""
            print("Using OrgPolicy template for checkpoint")
        else:
            # Save the provided html_content in checkpoint
            checkpoint_content = html_content
            print("Using provided html_content for checkpoint")

        # === STEP 3: Calculate diff for version creation (empty → current content) ===
        old_html = ""  # Start from empty, same as your current system
        new_html = org_policy.template or ""
        
        print(f"Creating version {version} for policy: {org_policy.title}")
        print(f"Old HTML length: {len(old_html)}")
        print(f"New HTML length: {len(new_html)}")
        print(f"Checkpoint content length: {len(checkpoint_content)}")
        
        diff_json = compute_html_diff(old_html, new_html)
        print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

        # === STEP 4: Create PolicyVersion record with checkpoint ===
        with transaction.atomic():
            policy_version = PolicyVersion.objects.create(
                org_policy=org_policy,
                version=version,
                diff_data=diff_json,
                checkpoint_template=checkpoint_content,  # Save determined checkpoint content
                status='draft',
                created_by=created_by,
                updated_by=created_by,
            )

        # === STEP 5: Return success ===
        return JsonResponse({
            "message": "Initialized policy version created successfully",
            "org_policy_id": str(org_policy.id),
            "policy_version_id": str(policy_version.id),
            "version_number": version,
            "checkpoint_source": "provided_html" if html_content is not None else "org_policy_template"
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
    

@csrf_exempt
def update_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        org_policy_id = data.get("org_policy_id")
        new_html = data.get("html")
        version = data.get("version")
        created_by = data.get("created_by", "system")

        # Validate required fields
        if not org_policy_id:
            return JsonResponse({"error": "org_policy_id is required"}, status=400)
        if not new_html:
            return JsonResponse({"error": "html content is required"}, status=400)
        if not version:
            return JsonResponse({"error": "version is required"}, status=400)

        # === STEP 1: Fetch the existing OrgPolicy ===
        try:
            org_policy = OrgPolicy.objects.get(id=uuid.UUID(org_policy_id))
        except OrgPolicy.DoesNotExist:
            return JsonResponse({"error": "OrgPolicy not found"}, status=404)

        # === STEP 2: Count existing versions to determine position ===
        existing_versions_count = PolicyVersion.objects.filter(
            org_policy=org_policy
        ).count()
        
        # This new version will be the (existing_versions_count + 1)th version
        new_version_position = existing_versions_count + 1
        
        print(f"Existing versions: {existing_versions_count}, New version position: {new_version_position}")

        # === STEP 3: Get the first PolicyVersion to reconstruct initial HTML ===
        try:
            # Get all versions sorted by version number to find the first one
            first_version = PolicyVersion.objects.filter(
                org_policy=org_policy
            ).order_by('version').first()
            
            if not first_version:
                return JsonResponse({"error": "No PolicyVersion found for this OrgPolicy"}, status=404)
            
            # Reconstruct initial HTML from first version's diff
            # First version diff is from empty string to initial HTML
            old_html = apply_diff("", first_version.diff_data)
            print(f"Reconstructed initial HTML from first version {first_version.version}")
            
        except Exception as e:
            print(f"Error reconstructing initial HTML: {str(e)}")
            return JsonResponse({"error": "Failed to reconstruct initial HTML from versions"}, status=500)

        # === STEP 4: Calculate diff between initial HTML and new HTML ===
        diff_json = compute_html_diff(old_html, new_html)
        print(f"Update diff computed. Changes: {len(diff_json.get('changes', []))}")

        # === STEP 5: Determine checkpoint content based on VERSION POSITION ===
        # Checkpoint at 11th, 21st, 31st, etc. (every 10x + 1 position)
        is_checkpoint_version = (new_version_position % 10 == 1) and (new_version_position >= 11)
        
        print(f"Version position: {new_version_position}, Is checkpoint: {is_checkpoint_version}")

        if is_checkpoint_version:
            # Save the complete new HTML in checkpoint
            checkpoint_content = new_html
            print(f"✅ CHECKPOINT SAVED for version {version} (position {new_version_position}) - Complete HTML saved in checkpoint")
        else:
            # For regular versions, checkpoint remains empty
            checkpoint_content = ""
            print(f"Regular version {version} (position {new_version_position}) - No checkpoint saved")

        # === STEP 6: Create new PolicyVersion with diff and checkpoint ===
        with transaction.atomic():
            policy_version = PolicyVersion.objects.create(
                org_policy=org_policy,
                version=version,
                diff_data=diff_json,
                checkpoint_template=checkpoint_content,
                status='published',
                created_by=created_by,
                updated_by=created_by,
            )

        # === STEP 7: Return success ===
        return JsonResponse({
            "message": "Policy updated successfully",
            "org_policy_id": str(org_policy.id),
            "policy_version_id": str(policy_version.id),
            "version_number": version,
            "version_position": new_version_position,
            "is_checkpoint": is_checkpoint_version,
            "checkpoint_saved": bool(checkpoint_content),
            "initial_version_used": first_version.version,
            "checkpoint_positions": "11th, 21st, 31st, etc. (every 10x + 1)"
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
    
@csrf_exempt
def get_policy_version_html(request, org_policy_id: int):
    """
    Get specific version HTML for a policy.
    Payload: {"version": "1.0"} or {"version": "11.5"} etc.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        target_version = data.get("version")
        
        if not target_version:
            return JsonResponse({"error": "version is required in payload"}, status=400)

        # Validate OrgPolicy exists
        try:
            org_policy = OrgPolicy.objects.get(id=org_policy_id)
        except OrgPolicy.DoesNotExist:
            return JsonResponse({"error": "OrgPolicy not found"}, status=404)

        # Reconstruct the HTML for the target version
        html_content = reconstruct_policy_html_at_version(org_policy_id, target_version)
        
        # Get version info
        version_obj = PolicyVersion.objects.get(
            org_policy_id=org_policy_id, 
            version=target_version
        )
        
        return JsonResponse({
            "org_policy_id": org_policy_id,
            "policy_title": org_policy.title,
            "version": target_version,
            "html": html_content,
            "created_at": version_obj.created_at.isoformat() if version_obj.created_at else None,
            "status": version_obj.status,
            "created_by": version_obj.created_by,
            "has_checkpoint": bool(version_obj.checkpoint),
            "reconstruction_method": "checkpoint" if version_obj.checkpoint else "sequential"
        })

    except PolicyVersion.DoesNotExist:
        return JsonResponse({"error": f"Version {target_version} not found for this policy"}, status=404)
    except ObjectDoesNotExist as e:
        return JsonResponse({"error": str(e)}, status=404)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)