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

@csrf_exempt
def create_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        # Load JSON data
        data = json.loads(request.body)
        title = data.get("title")
        version = data.get("version")
        files = data.get("file", [])

        if files is not None:
            files = [{
            "type": "application/pdf",
            "data": files,
            "name": "document.pdf"
        }]
        content = data.get("content", "")
        html = data.get("html")

        # Determine content to process
        raw_content = ""
        content_source = ""

        # Case 1: Files array with PDF (extract title and version from PDF)
        if files and len(files) > 0:
            pdf_data = extract_pdf_from_content({"files": files})
            if pdf_data:
                pdf_text = extract_text_from_pdf_preserve_formatting(pdf_data)
                if pdf_text:
                    raw_content = pdf_text
                    content_source = "pdf"
                    print("Using PDF content for LLM processing")
                    
                    # Extract title and version from PDF content
                    extraction_result = extract_title_version_from_pdf(pdf_text)
                    
                    # If title/version extraction failed, return error
                    if extraction_result[0].get("status") != 200:
                        return JsonResponse({
                            "status": "error",
                            "message": extraction_result[0].get("message"),
                            "missing_fields": extraction_result[0].get("missing_fields", []),
                            "extracted_data": extraction_result[0].get("extracted_data", {})
                        }, status=400)
                    
                    # Use extracted title and version (override provided ones)
                    extracted_data = extraction_result[0].get("extracted_data", {})
                    if not title:
                        title = extracted_data.get("title")
                    if not version:
                        version = extracted_data.get("version")
                    
                    print(f"Extracted from PDF - Title: {title}, Version: {version}")

        # Validate required fields after potential PDF extraction
        # if not title:
        #     return JsonResponse({"error": "title is required and could not be extracted from PDF"}, status=400)

        # if not version or not version.strip():
        #     return JsonResponse({"error": "version is required and could not be extracted from PDF"}, status=400)

        # Case 2: Direct HTML field
        elif html is not None:
            # Convert HTML to text for LLM processing
            html_text = html_to_text(html)
            if html_text:
                raw_content = html_text
                content_source = "html_field"
                print("Using HTML field for LLM processing")
        
        # Case 3: Only title and version with content field
        elif content:
            # Content field provided
            html_text = html_to_text(content)
            if html_text:
                raw_content = html_text
                content_source = "html_content"
                print("Using content field for LLM processing")
        else:
            # Only title and version provided - LLM will create from scratch
            raw_content = ""
            content_source = "metadata_only"
            print("Only title and version provided - LLM will create policy from scratch")

        # Send content to LLM for policy generation
        formatting_result = format_html_with_ai(title, version, raw_content, content_source)
        status_code = formatting_result[0].get("status")
        
        if status_code == 200:
            # LLM formatting succeeded - return HTML directly
            formatted_html = formatting_result[1]
            
            # Return as plain text HTML response
            return JsonResponse({
                "status": "success", 
                "message": formatted_html,
                "content_source": content_source,
                "title": title,
                "version": version
            }, status=200)
            
        elif status_code == 206:
            # LLM formatting failed
            return JsonResponse({
                "status": "error", 
                "message": "LLM failed to generate policy content",
                "content_source": content_source,
                "title": title,
                "version": version
            }, status=500)
        else:
            raise Exception(f"Unexpected LLM formatting status: {status_code}")

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    except Exception as e:
        return JsonResponse(
            {"error": f"Internal server error: {str(e)}"}, status=500
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