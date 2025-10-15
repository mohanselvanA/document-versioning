import json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Policy, PolicyVersion

from .utils.pdf_processor import process_content, extract_pdf_from_content, html_to_text, extract_text_from_pdf_preserve_formatting
from .services.policy_service import (
    analyze_policy_content, 
    link_policy_to_organization, 
    get_all_policy_titles,
    create_or_update_policy_for_approval,
    reconstruct_policy_html_at_version,
    format_html_with_ai,
    approve_policy_and_create_version,
    extract_title_version_from_pdf
)

@csrf_exempt
def policy_template_check(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        org_id = 1
        
        data = json.loads(request.body)
        content = data.get('content', '')
        files = data.get('files', [])
        content_data = {'content': content, 'files': files}

        processed_content = process_content(content_data)
        
        if not processed_content:
            return JsonResponse({"error": "No extractable content found in PDF or HTML"}, status=400)

        policy_titles = get_all_policy_titles()
        
        if not policy_titles:
            return JsonResponse({"error": "No policies found in database"}, status=404)

        ai_reply = analyze_policy_content(processed_content, policy_titles)

        if ai_reply and ai_reply != "No matching policy found":
            try:
                link_policy_to_organization(org_id, ai_reply)
            except ObjectDoesNotExist as e:
                return JsonResponse({"error": str(e)}, status=404)
            except Exception as e:
                print(f"Warning: Could not link policy to organization: {str(e)}")

        return JsonResponse({
            "analysis": ai_reply,
            "processed_content_length": len(processed_content),
            "status": "success"
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"error": f"AI service error: {str(e)}"}, status=503)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def create_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        # Parse and preserve the ENTIRE original request payload
        data = json.loads(request.body)
        original_payload = data.copy()  # This contains ALL fields: assignees, approver_1, department, etc.

        # Validate required fields
        organization_id = data.get("organization_id")
        if not organization_id:
            return JsonResponse(
                {**original_payload, "error": "organization_id is required"}, 
                status=400
            )

        # Extract known fields (for processing)
        title = data.get("title")
        version = data.get("policy_version")
        files = data.get("file", [])
        content = data.get("content", "")
        html = data.get("html")

        # Process files if present
        raw_content = ""
        content_source = ""

        if files:
            # Normalize files structure as before
            normalized_files = [{
                "type": "application/pdf",
                "data": files,
                "name": "document.pdf"
            }]
            pdf_data = extract_pdf_from_content({"files": normalized_files})
            if pdf_data:
                pdf_text = extract_text_from_pdf_preserve_formatting(pdf_data)
                if pdf_text:
                    raw_content = pdf_text
                    content_source = "pdf"
                    extraction_result = extract_title_version_from_pdf(pdf_text)
                    if extraction_result[0].get("status") != 200:
                        response = {
                            **original_payload,
                            "status": "error",
                            "message": extraction_result[0].get("message"),
                            "missing_fields": extraction_result[0].get("missing_fields", []),
                            "extracted_data": extraction_result[0].get("extracted_data", {})
                        }
                        return JsonResponse(response, status=400)

                    extracted_data = extraction_result[0].get("extracted_data", {})
                    if not title:
                        title = extracted_data.get("title")
                    if not version:
                        version = extracted_data.get("version")

        elif html is not None:
            raw_content = html_to_text(html)
            content_source = "html_field"
        elif content:
            raw_content = html_to_text(content)
            content_source = "html_content"
        else:
            content_source = "metadata_only"

        # Call LLM
        formatting_result = format_html_with_ai(title, version, raw_content, content_source)
        status_code = formatting_result[0].get("status")

        if status_code == 200:
            formatted_html = formatting_result[1]
            response = {
                **original_payload,  # 👈 ALL original fields included here
                "status": "success",
                "message": formatted_html,
                "title": title,
                "version": version,
                "organization_id": organization_id,
            }
            return JsonResponse(response, status=200)

        elif status_code == 206:
            response = {
                **original_payload,  # 👈 Again, include everything
                "status": "error",
                "message": "LLM failed to generate policy content",
                "title": title,
                "version": version,
                "organization_id": organization_id,
            }
            return JsonResponse(response, status=500)

        else:
            raise Exception(f"Unexpected LLM formatting status: {status_code}")

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    except Exception as e:
        # Even on crash, try to return original data if possible
        try:
            original = json.loads(request.body)
        except:
            original = {}
        return JsonResponse(
            {**original, "error": f"Internal server error: {str(e)}"}, 
            status=500
        )

@csrf_exempt
def policy_save(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        title = data.get("title")
        html = data.get("html")
        version = data.get("version")
        
        print(f"Received save request - Title: {title}, Version: {version}")
        print(f"HTML length: {len(html) if html else 0}")
        
        if not title or html is None or version is None:
            return JsonResponse({"error": "title, html, and version are required"}, status=400)

        # Validate version is a valid string
        if not version.strip():
            return JsonResponse({"error": "version is required"}, status=400)

        # Use the new approval workflow instead of direct save
        result = create_or_update_policy_for_approval(
            title=title, 
            html_template=html,
            version=version.strip()
        )
        print(f"Save result: {result}")
        return JsonResponse({"status": "success", **result})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        print(f"Error in policy_save: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

def policy_version_html(request, policy_id: int, version_number: int):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        html = reconstruct_policy_html_at_version(policy_id=policy_id, version_number=version_number)
        return JsonResponse({"policy_id": policy_id, "version_number": version_number, "html": html})
    except ObjectDoesNotExist as e:
        return JsonResponse({"error": str(e)}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

@csrf_exempt
def list_policies(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    policies = list(Policy.objects.values("id", "title", "version"))
    return JsonResponse({"policies": policies})

def get_policy_latest(request, policy_id: int):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        policy = Policy.objects.get(id=policy_id)
        
        # Get all versions and convert version_number to float for proper numerical sorting
        versions = list(policy.versions.all())
        if not versions:
            return JsonResponse({"error": "No versions found"}, status=404)
        
        # Sort versions by converting version_number to float for numerical comparison
        versions_sorted = sorted(versions, key=lambda x: float(x.version_number), reverse=True)
        latest_version = versions_sorted[0]
        
        html = reconstruct_policy_html_at_version(policy_id, latest_version.version_number)
        return JsonResponse(
            {
                "html": html,
                "version": policy.version,
                "version_number": latest_version.version_number,
            }
        )
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Policy not found"}, status=404)
    except ValueError:
        return JsonResponse({"error": "Invalid version number format"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

def get_policy_versions(request, policy_id: int):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        policy = Policy.objects.get(id=policy_id)
        versions = list(policy.versions.all())
        
        # Sort versions numerically by converting to float
        versions_sorted = sorted(versions, key=lambda x: float(x.version_number), reverse=True)
        
        versions_data = []
        for version in versions_sorted:
            versions_data.append({
                "version_number": version.version_number,
                "created_at": version.created_at
            })
            
        return JsonResponse({
            "versions": versions_data,
            "policy_version": policy.version
        })
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Policy not found"}, status=404)
    except ValueError:
        return JsonResponse({"error": "Invalid version number format"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

@csrf_exempt
def approve_policy(request, policy_id: int):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        # Call the service to approve the policy and create version
        result = approve_policy_and_create_version(policy_id)
        
        return JsonResponse({
            "status": "success",
            "message": "Policy approved successfully",
            "policy_id": policy_id,
            "version_number": result["version_number"]
        })

    except ObjectDoesNotExist as e:
        return JsonResponse({"error": str(e)}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)