# from .views import (
#     # policy_template_check,
#     create_policy,
#     # policy_save,
#     # policy_version_html,
#     # list_policies,
#     # get_policy_latest,
#     # get_policy_versions,
#     # approve_policy,  # Added
# )
# from django.urls import path
 
# urlpatterns = [
#     # path("policy-template-check/", policy_template_check, name="policy_template_check"),
#     path("policy/create/", create_policy, name="create_policy"),
#     # path("policy/save/", policy_save, name="policy_save"),
#     # path(
#     #     "policy/<int:policy_id>/version/<int:version_number>/",
#     #     policy_version_html,
#     #     name="policy_version_html",
#     # ),
#     # path("policies/", list_policies, name="list_policies"),
#     # path("policy/<int:policy_id>/latest/", get_policy_latest, name="get_policy_latest"),
#     # path("policy/<int:policy_id>/versions/", get_policy_versions, name="get_policy_versions"),
#     # path("policy/<int:policy_id>/approve/", approve_policy, name="approve_policy"),  # Added
# ]


from .views import (
    initialise_policy,
    create_the_initialised_policy,
    update_policy,
    get_policy_version_html,
)
from django.urls import path

urlpatterns = [
    path("policy/initialise", initialise_policy, name="initialise_policy"),
    path("policy/create-initialised", create_the_initialised_policy, name="create_the_initialised_policy"),
    path("policy/update", update_policy, name="update_policy"),
    path("policy/<int:org_policy_id>/version", get_policy_version_html, name="get_policy_version_html"),
]