import json
import uuid
import traceback
from django.db import transaction, connection
from decouple import config
from io import BytesIO
from xhtml2pdf import pisa
from .policy_service import format_html_with_ai
from ..utils.diff_utils import compute_html_diff, apply_diff
from ..models import PolicyTemplate, Organization, OrgPolicy, PolicyVersion, Employee, PolicyApprover
from .view_helpers import PolicyService, PolicyResponseBuilder

def initialise_policy_op(body_bytes):
    try:
        data = json.loads(body_bytes)
        required_fields = ['organization_id', 'policy_template_id']
        for field in required_fields:
            if not data.get(field):
                return PolicyResponseBuilder.error(f"{field} is required", status=400)
        org_id = data['organization_id']
        try:
            organization = Organization.objects.get(id=uuid.UUID(org_id))
        except Exception:
            return PolicyResponseBuilder.error("Organization not found", status=404)
        organization_name = organization.name
        policy_template_id = data['policy_template_id']
        department = data.get('department')
        category = data.get('category')
        version = data.get('version', '1')
        workforce_assignment = data.get('workforce_assignment') or []
        organization_logo = organization.light_logo
        try:
            policy_template = PolicyTemplate.objects.get(
                id=PolicyService.validate_uuid(policy_template_id, 'policy_template_id')
            )
        except PolicyTemplate.DoesNotExist:
            return PolicyResponseBuilder.error("Policy template not found", status=404)
        if not policy_template.title or policy_template.title.strip() == '':
            return PolicyResponseBuilder.error("Policy template title is required but missing or empty", status=400)
        formatting_result, llm_template = format_html_with_ai(
            policy_template.template,
            policy_template.title,
            department,
            category,
            organization_name,
            organization_logo
        )
        if not formatting_result or formatting_result.get('status') != 200:
            error_msg = formatting_result.get('message', 'Unknown LLM error') if formatting_result else 'LLM service unavailable'
            return PolicyResponseBuilder.error(f"AI policy generation failed: {error_msg}", status=502)
        with transaction.atomic():
            workforce_assignments_obj = {"assignments": workforce_assignment}
            workforce_assignments_json = json.dumps(workforce_assignments_obj, ensure_ascii=False)
            org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
                title=policy_template.title,
                organization=organization,
                defaults={
                    'template': llm_template,
                    'policy_type': 'existingpolicy',
                    'department': department,
                    'category': category,
                    'workforce_assignments': workforce_assignments_json,
                },
            )
            if not created:
                org_policy.template = llm_template
                org_policy.department = department
                org_policy.category = category
                org_policy.workforce_assignments = workforce_assignments_json
                org_policy.save()
        return PolicyResponseBuilder.success(
            "Policy initialized successfully",
            {
                "org_policy_id": str(org_policy.id),
                "created": created,
                "title": policy_template.title,
                "version": version,
                "workforce_assignments": workforce_assignment,
            },
            status=201 if created else 200
        )
    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except ValueError as e:
        return PolicyResponseBuilder.error(str(e), status=400)
    except Exception as e:
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

def create_initialised_policy_op(body_bytes):
    try:
        data = json.loads(body_bytes)
        if not data.get('org_policy_id'):
            return PolicyResponseBuilder.error("org_policy_id is required", status=400)
        org_policy_id = data['org_policy_id']
        html_content = data.get('html_content')
        created_by = data.get('created_by', 'system')
        version = "1.0"
        approver = data.get('approver')
        if approver:
            try:
                approver = uuid.UUID(approver)
                if not Employee.objects.filter(id=approver).exists():
                    return PolicyResponseBuilder.error("Approver not found", status=404)
            except Exception:
                return PolicyResponseBuilder.error("Invalid approver id", status=400)
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
            org_policy = OrgPolicy.objects.get(id=uuid.UUID(org_policy_id))
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)
        except OrgPolicy.DoesNotExist:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)
        checkpoint_content = html_content if html_content is not None else org_policy.template or ""
        checkpoint_source = "provided_html" if html_content is not None else "org_policy_template"
        old_html = ""
        new_html = org_policy.template or ""
        diff_json = compute_html_diff(old_html, new_html)
        with transaction.atomic():
            policy_version = PolicyVersion.objects.create(
                org_policy_id=org_policy.id,
                version=version,
                diff_data=diff_json,
                checkpoint_template=checkpoint_content,
                status='draft',
                created_at=created_by,
                updated_at=created_by,
            )
            if approver:
                PolicyApprover.objects.create(
                    policy_version_id=policy_version.id,
                    approver_id=approver
                )
        return PolicyResponseBuilder.success(
            "Initialized policy version created successfully",
            {
                "org_policy_id": str(org_policy.id),
                "policy_version_id": str(policy_version.id),
                "version_number": version,
                "checkpoint_source": checkpoint_source,
                "changes_count": len(diff_json.get('changes', [])),
                "approver": str(approver) if approver else None
            },
            status=201
        )
    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except Exception as e:
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

def update_policy_op(body_bytes):
    try:
        body_content = body_bytes
        if isinstance(body_content, bytes):
            body_content = body_content.decode('utf-8')
        data = json.loads(body_content)
        required_fields = ['org_policy_id', 'organization_id', 'html_content', 'workforce_assignment', 'approver']
        for field in required_fields:
            if not data.get(field):
                return PolicyResponseBuilder.error(f"{field} is required", status=400)
        org_policy_id = data['org_policy_id']
        new_html = data['html_content']
        workforce_assignment = data.get('workforce_assignment') or []
        approver = data['approver']
        version = data.get('version')
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)
        org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
        if not org_policy_row:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)
        existing_versions_count = PolicyService.count_policy_versions(org_policy_id)
        new_version_position = existing_versions_count + 1
        last_version_str = PolicyService.get_latest_version_number(org_policy_id)
        def parse_version(v):
            parts = v.split('.')
            while len(parts) < 2:
                parts.append('0')
            try:
                major = int(parts[0])
                minor = int(parts[1])
            except Exception:
                return 1, 0
            return major, minor

        if not version:
            if last_version_str:
                try:
                    last_major, last_minor = parse_version(last_version_str)
                    latest_ver_obj = PolicyVersion.objects.filter(org_policy_id=org_policy_id).order_by('-created_at').first()
                    from django.utils import timezone
                    if latest_ver_obj and getattr(latest_ver_obj, "expired_at", None) and timezone.now().date() > latest_ver_obj.expired_at:
                        version = f"{last_major + 1}.0"
                    else:
                        version = f"{last_major}.{last_minor + 1}"
                except Exception:
                    version = "1.0"
            else:
                version = "1.0"
        else:
            try:
                prov_major, prov_minor = parse_version(version)
                latest_ver_obj = PolicyVersion.objects.filter(org_policy_id=org_policy_id).order_by('-created_at').first()
                from django.utils import timezone
                if latest_ver_obj and getattr(latest_ver_obj, "expired_at", None) and timezone.now().date() > latest_ver_obj.expired_at:
                    version = f"{prov_major + 1}.0"
                else:
                    version = f"{prov_major + 1}.0"
            except Exception:
                version = "1.0"
        first_version_row = PolicyService.get_first_policy_version(org_policy_id)
        old_html = ""
        if first_version_row:
            first_version_id, first_version_number, diff_data_str, created_at = first_version_row
            if diff_data_str and diff_data_str.strip():
                try:
                    diff_dict = json.loads(diff_data_str)
                    old_html = apply_diff("", diff_dict)
                except Exception:
                    pass
        diff_json = compute_html_diff(old_html, new_html)
        is_checkpoint_version = (new_version_position % 10 == 1) and (new_version_position >= 11)
        checkpoint_content = new_html if is_checkpoint_version else ""
        try:
            with transaction.atomic():
                new_policy_version_id = str(uuid.uuid4())
                diff_json_str = json.dumps(diff_json)
                inserted_id = PolicyService.create_policy_version_record([
                    new_policy_version_id,
                    org_policy_id,
                    version,
                    diff_json_str,
                    checkpoint_content,
                    'draft',
                ])
                org_policy = OrgPolicy.objects.get(id=uuid.UUID(org_policy_id))
                org_policy.workforce_assignments = json.dumps({"assignments": workforce_assignment}, ensure_ascii=False)
                org_policy.save()
                if Employee.objects.filter(id=uuid.UUID(approver)).exists():
                    PolicyApprover.objects.create(
                        policy_version_id=new_policy_version_id,
                        approver_id=uuid.UUID(approver)
                    )
                else:
                    raise Exception("Approver not found")
        except Exception as e:
            traceback.print_exc()
            return PolicyResponseBuilder.error(f"Failed to create policy version: {str(e)}", status=500)
        response_data = {
            "org_policy_id": org_policy_id,
            "policy_version_id": inserted_id,
            "version_number": version,
            "version_position": new_version_position,
            "is_checkpoint": is_checkpoint_version,
            "checkpoint_saved": bool(checkpoint_content),
            "changes_count": len(diff_json.get('changes', []))
        }
        return PolicyResponseBuilder.success("Policy updated successfully", response_data, status=201)
    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except Exception as e:
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

def get_policy_version_html_op(body_bytes):
    try:
        body_content = body_bytes
        if isinstance(body_content, bytes):
            body_content = body_content.decode('utf-8')
        data = json.loads(body_content)
        org_policy_id = data.get("org_policy_id")
        input_version = data.get("version", None)
        organization_id = data.get("organization_id", None)
        if not org_policy_id:
            return PolicyResponseBuilder.error("org_policy_id is required in payload", status=400)
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)
        org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
        if not org_policy_row:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)
        org_policy_id_db, org_policy_title = org_policy_row
        with connection.cursor() as cursor:
            if input_version:
                target_version = input_version
            else:
                cursor.execute("SELECT version FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at DESC LIMIT 1", [org_policy_id])
                row = cursor.fetchone()
                target_version = row[0] if row else None
        if not target_version:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)
        with connection.cursor() as cursor:
            cursor.execute("SELECT version, diff_data::text, checkpoint_template FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at ASC", [org_policy_id])
            all_versions = cursor.fetchall()
        if not all_versions:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)
        current_html = ""
        target_found = False
        for version_data in all_versions:
            version_num, diff_data_str, checkpoint_content = version_data
            if diff_data_str and diff_data_str.strip():
                try:
                    diff_dict = json.loads(diff_data_str)
                    current_html = apply_diff(current_html, diff_dict)
                except Exception:
                    pass
            if version_num == target_version:
                target_found = True
                break
        if not target_found:
            return PolicyResponseBuilder.error(f"Version {target_version} not found for this policy", status=404)
        with connection.cursor() as cursor:
            cursor.execute("SELECT status, created_at FROM policy_versions WHERE org_policy_id = %s AND version = %s LIMIT 1", [org_policy_id, target_version])
            version_info = cursor.fetchone()
        if version_info:
            status, created_at = version_info
        else:
            status, created_at = "unknown", None
        return PolicyResponseBuilder.success(
            "Policy version HTML retrieved successfully",
            {
                "org_policy_id": org_policy_id,
                "policy_title": org_policy_title,
                "version": target_version,
                "html": current_html,
                "created_at": created_at.isoformat() if created_at else None,
                "status": "draft",
                "reconstruction_method": "sequential",
                "html_length": len(current_html),
                "organization_id": organization_id
            }
        )
    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except Exception as e:
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

def get_policy_pdf_op(body_bytes):
    try:
        body_content = body_bytes
        if isinstance(body_content, bytes):
            body_content = body_content.decode('utf-8')
        data = json.loads(body_content)
        org_policy_id = data.get("org_policy_id")
        if not org_policy_id:
            return PolicyResponseBuilder.error("org-policy id is required in payload", status=400)
        input_version = data.get("version")
        if not input_version:
            return PolicyResponseBuilder.error("version is required in payload", status=400)
        organization_id = data.get("organization_id")
        if not organization_id:
            return PolicyResponseBuilder.error("organization id is required in payload", status=400)
        try:
            organization = Organization.objects.get(id=uuid.UUID(organization_id))
            if organization.light_logo:
                image_url = organization.light_logo
            elif organization.dark_logo:
                image_url = organization.dark_logo
            else:
                image_url = organization.name
        except Organization.DoesNotExist:
            image_url = ''
        image_url_parent = config('STACKFLOW_LOGO')
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)
        org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
        if not org_policy_row:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)
        org_policy_id_db, org_policy_title = org_policy_row
        with connection.cursor() as cursor:
            if input_version:
                target_version = input_version
            else:
                cursor.execute("SELECT version FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at DESC LIMIT 1", [org_policy_id])
                row = cursor.fetchone()
                target_version = row[0] if row else None
        if not target_version:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)
        with connection.cursor() as cursor:
            cursor.execute("SELECT version, diff_data::text, checkpoint_template FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at ASC", [org_policy_id])
            all_versions = cursor.fetchall()
        if not all_versions:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)
        current_html = ""
        target_found = False
        for version_data in all_versions:
            version_num, diff_data_str, checkpoint_content = version_data
            if diff_data_str and diff_data_str.strip():
                try:
                    diff_dict = json.loads(diff_data_str)
                    current_html = apply_diff(current_html, diff_dict)
                except Exception:
                    pass
            if version_num == target_version:
                target_found = True
                break
        if not target_found:
            return PolicyResponseBuilder.error(f"Version {target_version} not found for this policy", status=404)
        with connection.cursor() as cursor:
            cursor.execute("SELECT status, created_at FROM policy_versions WHERE org_policy_id = %s AND version = %s LIMIT 1", [org_policy_id, target_version])
            version_info = cursor.fetchone()
        if version_info:
            status, created_at = version_info
        else:
            status, created_at = "unknown", None
        html_with_logo = f"""
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            margin-bottom: 30px;
            padding-bottom: 15px;
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        .powered-by-section {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 10px;
            color: #666;
        }}
        .parent-logo {{
            height: 22px;
            width: auto;
        }}
        .main-logo-section {{
            text-align: center;
            flex-grow: 1;
        }}
        .main-logo {{
            height: 50px;
            width: auto;
        }}
        .policy-title {{
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            margin-top: 10px;
            color: #333;
        }}
        .company-name {{
            text-align: center;
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-top">
            <div class="powered-by-section">
                <span>Powered by </span>
                <img src="{image_url_parent}" alt="Stakflo" class="parent-logo">
            </div>
            <div class="main-logo-section">
                <img src="{image_url}" alt="Trust Cloud" style="height: 75px; width: auto;">
            </div>
        </div>
    </div>
    {current_html}
</body>
</html>
"""
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_with_logo, dest=pdf_buffer)
        if pisa_status.err:
            return PolicyResponseBuilder.error("Failed to generate PDF", status=500)
        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.getvalue()
        import base64 as _b64
        pdf_base64 = _b64.b64encode(pdf_bytes).decode('utf-8')
        return PolicyResponseBuilder.success(
            "Policy PDF generated successfully",
            {
                "org_policy_id": org_policy_id,
                "policy_title": org_policy_title,
                "version": target_version,
                "pdf_base64": pdf_base64,
                "created_at": created_at.isoformat() if created_at else None,
                "status": "draft",
                "organization_id": organization_id
            }
        )
    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except Exception as e:
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)