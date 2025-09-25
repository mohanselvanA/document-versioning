# policies/views.py
import os
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import Organization, Policy, PolicyVersion, PolicyTemplate
from .serializers import OrganizationSerializer, PolicySerializer, PolicyVersionListSerializer
from .utils import (
    extract_text_from_pdf,
    generate_diff_ops_and_patch,
    llm_validate,
    reconstruct_version,
    apply_patch,
    generate_policy
)

MEDIA_ROOT = settings.MEDIA_ROOT
CHECKPOINT_INTERVAL = getattr(settings, "CHECKPOINT_INTERVAL", 5)


@api_view(["POST"])
def create_organization(request):
    name = request.data.get("name")
    if not name:
        return Response({"detail":"name required"}, status=status.HTTP_400_BAD_REQUEST)
    org, created = Organization.objects.get_or_create(name=name)
    return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
@transaction.atomic
def create_policy(request):
    """
    Create a new policy: generate structured content via LLM from user input, then save when finalized.
    """
    org_id = request.data.get("organization_id")
    title = request.data.get("title")
    text = request.data.get("text")
    file = request.FILES.get("file")
    created_by = request.data.get("created_by", None)
    finalize = request.data.get("finalize", False)  # User confirms final content

    if not org_id or not title:
        return Response({"detail": "organization_id and title required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        org = Organization.objects.get(pk=org_id)
    except Organization.DoesNotExist:
        return Response({"detail": "organization not found"}, status=status.HTTP_404_NOT_FOUND)

    if not text and not file:
        return Response({"detail": "Provide text or upload PDF"}, status=status.HTTP_400_BAD_REQUEST)

    # Extract content from PDF if uploaded
    if file:
        fname = f"{int(__import__('time').time())}_{file.name}"
        path = os.path.join(MEDIA_ROOT, fname)
        os.makedirs(MEDIA_ROOT, exist_ok=True)
        with open(path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
        raw_content = extract_text_from_pdf(path)
    else:
        raw_content = text or ""

    # Fetch template sections for this policy title
    try:
        template = PolicyTemplate.objects.get(title__iexact=title)
        template_sections = template.sections  # JSONField storing list of section names
    except PolicyTemplate.DoesNotExist:
        template_sections = []

    # LLM generates structured content based on user raw text + template sections
    # structured_content = llm_validate(title, raw_content, template_sections=template_sections)
    structured_content = generate_policy(title, template_sections, raw_content)

    if not finalize:
        # Return structured content only, do not create policy yet
        return Response({
            "policy_id": None,
            "title": title,
            "version": None,
            "structured_content": structured_content
        }, status=status.HTTP_200_OK)

    # Save policy and version if user finalizes
    policy = Policy.objects.create(
        organization=org,
        title=title,
        description=request.data.get("description", "")
    )

    pv = PolicyVersion.objects.create(
        policy=policy,
        version_number=1,
        is_checkpoint=True,
        full_text=structured_content,
        created_by=created_by
    )

    return Response({
        "policy_id": policy.id,
        "title": policy.title,
        "version": 1,
        "structured_content": structured_content
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@transaction.atomic
def update_policy(request, policy_id: int):
    """
    Update a policy: LLM generates structured content from user input,
    then save as a new version if finalize=True.
    """
    try:
        policy = Policy.objects.get(pk=policy_id)
    except Policy.DoesNotExist:
        return Response({"detail": "policy not found"}, status=status.HTTP_404_NOT_FOUND)

    text = request.data.get("text")
    file = request.FILES.get("file")
    created_by = request.data.get("created_by", None)
    finalize = request.data.get("finalize", False)  # User confirms final content

    if not text and not file:
        return Response({"detail": "Provide text or upload PDF"}, status=status.HTTP_400_BAD_REQUEST)

    # Extract content from PDF if uploaded
    if file:
        fname = f"{int(__import__('time').time())}_{file.name}"
        path = os.path.join(MEDIA_ROOT, fname)
        with open(path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
        raw_content = extract_text_from_pdf(path)
    else:
        raw_content = text or ""

    # Fetch template sections for this policy title
    try:
        template = PolicyTemplate.objects.get(title__iexact=policy.title)
        template_sections = template.sections  # JSONField storing list of section names
    except PolicyTemplate.DoesNotExist:
        template_sections = []

    # LLM generates structured content from raw user input
    # structured_content = llm_validate(policy.title, raw_content, template_sections=template_sections)
    structured_content = generate_policy(policy.title, template_sections, raw_content)

    if not finalize:
        # Return structured content only for frontend editing
        return Response({
            "policy_id": policy.id,
            "version": policy.versions.order_by("-version_number").first().version_number,
            "structured_content": structured_content,
            "message": "LLM suggestions returned. Finalize to save new version."
        }, status=status.HTTP_200_OK)

    # Save as new version
    latest = policy.versions.order_by("-version_number").first()
    next_ver = latest.version_number + 1 if latest else 1
    is_checkpoint = (next_ver % CHECKPOINT_INTERVAL == 0)

    if is_checkpoint:
        pv = PolicyVersion.objects.create(
            policy=policy,
            version_number=next_ver,
            is_checkpoint=True,
            full_text=structured_content,
            created_by=created_by
        )
    else:
        latest_text = latest.full_text if latest else ""
        diff_result = generate_diff_ops_and_patch(latest_text, structured_content)
        pv = PolicyVersion.objects.create(
            policy=policy,
            version_number=next_ver,
            is_checkpoint=False,
            diff_ops=diff_result["ops"],
            patch_text=diff_result["patch_text"],
            created_by=created_by
        )

    return Response({
        "policy_id": policy.id,
        "version": next_ver,
        "is_checkpoint": is_checkpoint,
        "structured_content": structured_content
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_policies(request, org_id: int):
    try:
        org = Organization.objects.get(pk=org_id)
    except Organization.DoesNotExist:
        return Response({"detail":"organization not found"}, status=status.HTTP_404_NOT_FOUND)
    qs = org.policies.all()
    out = []
    for p in qs:
        latest = p.versions.order_by("-version_number").first()
        out.append({
            "policy_id": p.id,
            "title": p.title,
            "created_at": p.created_at,
            "latest_version": latest.version_number if latest else None
        })
    return Response(out, status=status.HTTP_200_OK)


@api_view(["GET"])
def list_versions(request, policy_id: int):
    try:
        policy = Policy.objects.get(pk=policy_id)
    except Policy.DoesNotExist:
        return Response({"detail":"policy not found"}, status=status.HTTP_404_NOT_FOUND)
    versions = policy.versions.order_by("version_number")
    data = PolicyVersionListSerializer(versions, many=True).data
    return Response({"policy_id":policy.id,"title":policy.title,"versions":data}, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_version(request, policy_id: int, version_number: int):
    try:
        policy = Policy.objects.get(pk=policy_id)
    except Policy.DoesNotExist:
        return Response({"detail":"policy not found"}, status=status.HTTP_404_NOT_FOUND)

    versions = policy.versions.order_by("version_number")
    try:
        content = reconstruct_version(versions, version_number)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    ver = versions.get(version_number=version_number)
    return Response({
        "policy_id": policy.id,
        "title": policy.title,
        "version": version_number,
        "is_checkpoint": ver.is_checkpoint,
        "created_at": ver.created_at,
        "created_by": ver.created_by,
        "content": content
    }, status=status.HTTP_200_OK)
