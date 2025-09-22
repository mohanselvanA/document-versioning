from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
# Create your views here.
def test(request):
    return JsonResponse({"message": "This is a test response from the policy_tracker app."})
