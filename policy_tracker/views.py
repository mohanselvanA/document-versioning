import json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist

# Import from our modules
from .utils.pdf_processor import process_content
from .services.policy_service import (
    analyze_policy_content, 
    link_policy_to_organization, 
    get_all_policy_titles
)

@csrf_exempt
def policy_template_check(request):
    """
    Main entry point for policy template checking
    Handles both PDF and HTML content, prioritizing PDF
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        # Configuration
        org_id = 1
        
        # Parse request data
        data = json.loads(request.body)
        content_data = data.get("content")

        if not content_data:
            return JsonResponse({"error": "Content is required"}, status=400)

        # Process content (PDF prioritized over HTML)
        processed_content = process_content(content_data)
        
        if not processed_content:
            return JsonResponse({"error": "No extractable content found in PDF or HTML"}, status=400)

        # Get all policy titles from database
        policy_titles = get_all_policy_titles()
        
        if not policy_titles:
            return JsonResponse({"error": "No policies found in database"}, status=404)

        # Analyze content with AI service
        ai_reply = analyze_policy_content(processed_content, policy_titles)

        # If match found, link policy to organization
        if ai_reply and ai_reply != "No matching policy found":
            try:
                link_policy_to_organization(org_id, ai_reply)
            except ObjectDoesNotExist as e:
                return JsonResponse({"error": str(e)}, status=404)
            except Exception as e:
                # Continue even if linking fails, but return the analysis
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