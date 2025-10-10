import json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Policy, PolicyVersion

from .utils.pdf_processor import process_content, process_content_to_html
from .services.policy_service import (
    analyze_policy_content, 
    link_policy_to_organization, 
    get_all_policy_titles,
    create_or_update_policy_for_approval,
    reconstruct_policy_html_at_version,
    format_html_with_ai,
    approve_policy_and_create_version
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
        files = data.get("files", [])
        content = data.get("content", "")
        html = data.get("html")

        # Validate required fields
        if not title:
            return JsonResponse({"error": "title is required"}, status=400)

        if not version or not version.strip():
            return JsonResponse({"error": "version is required"}, status=400)

        # Determine HTML content
        html_content = None

        if files and len(files) > 0:
            # New format: process files + content
            content_data = {"content": content, "files": files}
            html_content = process_content_to_html(content_data)

            if not html_content:
                return JsonResponse(
                    {"error": "No extractable content found in PDF or HTML files"}, status=400
                )

        elif html is not None:
            # Legacy format: process html via AI formatting
            html_result = format_html_with_ai(html)  # returns (status_dict, html_string)
            status_code = html_result[0].get("status")

            if status_code == 200:
                # AI formatting succeeded
                html_content = html_result[1]  # extract HTML string
            elif status_code == 206:
                # html_content = html
                raise Exception("AI formatting failed, using raw HTML")
            else:
                raise Exception(f"Unexpected AI formatting status: {status_code}")

        else:
            return JsonResponse(
                {"error": "Either html field or files array with content is required"}, status=400
            )

        # Create or update policy with processed HTML in getting_processed_for_approval
        result = create_or_update_policy_for_approval(
            title=title,
            html_template=html_content,  # always a string
            version=version.strip()
        )

        return JsonResponse({"status": "success", **result})

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