# policies/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("orgs/", views.create_organization, name="create_org"),
    path("orgs/<int:org_id>/policies/", views.list_policies, name="list_policies"),
    path("policies/", views.create_policy, name="create_policy"),
    path("policies/<int:policy_id>/update/", views.update_policy, name="update_policy"),
    path("policies/<int:policy_id>/versions/", views.list_versions, name="list_versions"),
    path("policies/<int:policy_id>/versions/<int:version_number>/", views.get_version, name="get_version"),
]
