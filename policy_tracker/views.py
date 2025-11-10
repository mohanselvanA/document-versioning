from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .services.view_operations import (
    initialise_policy_op,
    create_initialised_policy_op,
    update_policy_op,
    get_policy_version_html_op,
    get_policy_pdf_op,
)


@csrf_exempt
@require_http_methods(["POST"])
def initialise_policy(request):
    body_bytes = request.body
    return initialise_policy_op(body_bytes)


@csrf_exempt
@require_http_methods(["POST"])
def create_the_initialised_policy(request):
    body_bytes = request.body
    return create_initialised_policy_op(body_bytes)


@csrf_exempt
@require_http_methods(["POST"])
def update_policy(request):
    body_bytes = request.body
    return update_policy_op(body_bytes)


@csrf_exempt
@require_http_methods(["POST"])
def get_policy_version_html(request):
    body_bytes = request.body
    return get_policy_version_html_op(body_bytes)


@csrf_exempt
@require_http_methods(["POST"])
def get_policy_pdf(request):
    body_bytes = request.body
    return get_policy_pdf_op(body_bytes)