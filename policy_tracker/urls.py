from django.urls import path
from . import views

urlpatterns = [
    # Policy management endpoints
    path("policy/initialise", views.initialise_policy, name="initialise_policy"),
    path("policy/create-initialised", views.create_the_initialised_policy, name="create_the_initialised_policy"),
    path("policy/update", views.update_policy, name="update_policy"),
    path("policy/data", views.get_policy_version_html, name="get_policy_version_html"),
    path("policy/download", views.download_pdf_version, name="get_policy_version_html")
    
    # =========================================================================
    # UNUSED URL PATTERNS (COMMENTED OUT FOR NOW)
    # =========================================================================
    
    # path("policy/legacy-create", views.legacy_policy_creation, name="legacy_policy_creation"),
    # path("policy/approve", views.policy_approval_workflow, name="policy_approval_workflow"),
]