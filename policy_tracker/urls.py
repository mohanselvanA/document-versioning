from .views import policy_template_check
from django.urls import path


urlpatterns = [
    path('policy-template-check/', policy_template_check, name='policy_template_check'),
]