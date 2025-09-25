from .views import (
    policy_template_check,
    create_policy,  # Added
    policy_save,
    policy_version_html,
    list_policies,
    get_policy_latest,
    get_policy_versions,
)
from django.urls import path
 
urlpatterns = [
    path("policy-template-check/", policy_template_check, name="policy_template_check"),
    path("policy/create/", create_policy, name="create_policy"),
    path("policy/save/", policy_save, name="policy_save"),
    path(
        "policy/<int:policy_id>/version/<int:version_number>/",
        policy_version_html,
        name="policy_version_html",
    ),
    path("policies/", list_policies, name="list_policies"),
    path("policy/<int:policy_id>/latest/", get_policy_latest, name="get_policy_latest"),
    path("policy/<int:policy_id>/versions/", get_policy_versions, name="get_policy_versions"),
]