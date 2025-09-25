import json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Policy, PolicyVersion

from .utils.pdf_processor import process_content
from .services.policy_service import (
    analyze_policy_content,
    link_policy_to_organization,
    get_all_policy_titles,
    create_or_update_policy_with_version,
    reconstruct_policy_html_at_version,
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
        data = json.loads(request.body)
        title = data.get("title")
        html = data.get("html")
        version = data.get("version")
       
        if not title or html is None:
            return JsonResponse({"error": "title and html are required"}, status=400)
 
        # Validate version is a valid string (not empty)
        if not version or not version.strip():
            return JsonResponse({"error": "version is required"}, status=400)
 
        # Remove integer validation since version is now string
        result = create_or_update_policy_with_version(
            title=title,
            html_template=html,
            version=version.strip()  # Pass the version string from frontend
        )
        return JsonResponse({"status": "success", **result})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
 