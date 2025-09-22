import json
import requests
from decouple import config
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from .models import *

OPENAI_API_KEY = config("OPENAI_API_KEY")
AI_CHAT_URL = config("AI_CHAT_URL")

@csrf_exempt
def policy_template_check(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        org_id = 2
        data = json.loads(request.body)
        content = data.get("content")

        if not content:
            return JsonResponse({"error": "Content is required"}, status=400)

        all_policies = Policy.objects.all()
        policy_titles = [policy.title for policy in all_policies]

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

        ai_reply = res.json().get("response", "").strip()

        if ai_reply != "No matching policy found":
            try:
                org = Organization.objects.get(id=org_id)
                policy = Policy.objects.get(title=ai_reply)

                OrganizationPolicy.objects.get_or_create(
                    organization=org,
                    policy=policy
                )
            except Organization.DoesNotExist:
                return JsonResponse({"error": f"Organization {org_id} not found"}, status=404)
            except Policy.DoesNotExist:
                return JsonResponse({"error": f"Policy '{ai_reply}' not found in DB"}, status=404)

        return JsonResponse({"analysis": ai_reply}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
