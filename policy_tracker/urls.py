from django.urls import path
from . import views

urlpatterns = [
    path("policy/initialise", views.initialise_policy, name="initialise_policy"),
    path("policy/create-initialised", views.create_the_initialised_policy, name="create_the_initialised_policy"),
    path("policy/update", views.update_policy, name="update_policy"),
    path("policy/data", views.get_policy_version_html, name="get_policy_version_html"),
    path("policy/download", views.get_policy_pdf, name="get_policy_version_html"),
]