import json
import uuid
import traceback
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, connection

from .models import PolicyTemplate, Organization, OrgPolicy, PolicyVersion, Employee, PolicyApprover
from .services.policy_service import format_html_with_ai, reconstruct_policy_html_at_version
from .utils.diff_utils import compute_html_diff, apply_diff


class PolicyService:
    """Service class for policy-related operations"""


    @staticmethod
    def get_latest_version_number(org_policy_id):
        """Fetch the latest version number string for a given OrgPolicy ID."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT version
                FROM policy_versions
                WHERE org_policy_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, [org_policy_id])
            row = cursor.fetchone()
            return row[0] if row else None
    
    @staticmethod
    def validate_uuid(uuid_string, field_name):
        """Validate UUID format"""
        try:
            return uuid.UUID(uuid_string)
        except ValueError:
            raise ValueError(f"Invalid {field_name} format")
    
    @staticmethod
    def get_org_policy_by_id(org_policy_id):
        """Get OrgPolicy by ID with raw SQL"""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title FROM org_policies WHERE id = %s",
                [org_policy_id]
            )
            return cursor.fetchone()
    
    @staticmethod
    def count_policy_versions(org_policy_id):
        """Count existing versions for a policy"""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM policy_versions WHERE org_policy_id = %s",
                [org_policy_id]
            )
            return cursor.fetchone()[0]
    
    @staticmethod
    def get_first_policy_version(org_policy_id):
        """Get the first version of a policy"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id, 
                    version, 
                    diff_data::text as diff_data_str,
                    created_at 
                FROM policy_versions 
                WHERE org_policy_id = %s 
                ORDER BY created_at ASC 
                LIMIT 1
            """, [org_policy_id])
            return cursor.fetchone()
    
    @staticmethod
    def create_policy_version_record(version_data):
        """Create a new PolicyVersion record"""
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO policy_versions 
                (id, org_policy_id, version, diff_data, checkpoint_template, status, created_at, updated_at)
                VALUES 
                (%s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW())
                RETURNING id
            """, version_data)
            result = cursor.fetchone()
            return result[0] if result else version_data[0]


class PolicyResponseBuilder:
    """Builder class for standardized API responses"""
    
    @staticmethod
    def success(message, data=None, status=200):
        """Build success response"""
        response = {"message": message, "status": "success"}
        if data:
            response.update(data)
        return JsonResponse(response, status=status)
    
    @staticmethod
    def error(message, status=400, details=None):
        """Build error response"""
        response = {"error": message, "status": "error"}
        if details:
            response["details"] = details
        return JsonResponse(response, status=status)


@csrf_exempt
@require_http_methods(["POST"])
def initialise_policy(request):
    """
    Initialize a new policy from a template with AI-generated content
    """
    try:
        # Parse and validate request data
        data = json.loads(request.body)
        
        required_fields = ['organization_id', 'policy_template_id']
        for field in required_fields:
            if not data.get(field):
                return PolicyResponseBuilder.error(f"{field} is required", status=400)
        
        org_id = data['organization_id']
        organization_name = None
        organization_name_check = (Organization.objects.filter(id=uuid.UUID(org_id))).exists()
        if organization_name_check == False:
            return PolicyResponseBuilder.error("Organization not found", status=404)
        else:
            organization_name = (Organization.objects.get(id=uuid.UUID(org_id))).name
        policy_template_id = data['policy_template_id']
        department = data.get('department')
        category = data.get('category')
        version = data.get('version', '1')
        workforce_assignment = data.get('workforce_assignment')
        # approver = data.get('approver', "")

        # if approver!=None or approver!="":
        #     approver = uuid.UUID(approver)
        #     checkingApproverExists = Employee.objects.filter(id=approver).exists()
        #     if not checkingApproverExists:
        #         return PolicyResponseBuilder.error("Approver not found", status=404)

        # Validate and fetch policy template
        try:
            policy_template = PolicyTemplate.objects.get(
                id=PolicyService.validate_uuid(policy_template_id, 'policy_template_id')
            )
        except PolicyTemplate.DoesNotExist:
            return PolicyResponseBuilder.error("Policy template not found", status=404)

        # Validate and fetch organization
        try:
            organization = Organization.objects.get(
                id=PolicyService.validate_uuid(org_id, 'organization_id')
            )
        except Organization.DoesNotExist:
            return PolicyResponseBuilder.error("Organization not found", status=404)

        # CRITICAL: Validate title is not None or empty (NOT NULL constraint in DB)
        if not policy_template.title or policy_template.title.strip() == '':
            return PolicyResponseBuilder.error("Policy template title is required but missing or empty", status=400)

        # llm_template = "This is a sample policy"
        # Generate AI-formatted HTML
        formatting_result, llm_template = format_html_with_ai(
            policy_template.template, 
            policy_template.title, 
            department, 
            category,
            organization_name
        )

        # # # Validate AI response
        if not formatting_result or formatting_result.get('status') != 200:
            error_msg = formatting_result.get('message', 'Unknown LLM error') if formatting_result else 'LLM service unavailable'
            print(f"[ERROR] LLM generation failed: {error_msg}")
            return PolicyResponseBuilder.error(f"AI policy generation failed: {error_msg}", status=502)

        # FIXED: Remove created_by and updated_by fields since they don't exist in DB
        with transaction.atomic():

            if len(workforce_assignment) != 0:
                workforce_assignments_list = json.dumps({"assignments": workforce_assignment})
            else:
                workforce_assignments_list = json.dumps({"assignments": []})
                

            org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
                title=policy_template.title,
                organization=organization,
                defaults={
                    'template': llm_template,
                    'policy_type': 'existingpolicy',
                    'department': department,
                    'category': category,
                    'workforce_assignments': workforce_assignments_list,
                },
            )

            if not created:
                org_policy.template = llm_template
                org_policy.department = department
                org_policy.category = category
                org_policy.save()

            # savingApprover = PolicyApprover.objects.create(
            #     policy_version_id=org_policy.id,
            #     approver_id=approver
            # )

            

        return PolicyResponseBuilder.success(
            "Policy initialized successfully",
            {
                "org_policy_id": str(org_policy.id),
                "created": created,
                "title": policy_template.title,
                "version": version,
                'workforce_assignments': workforce_assignment,
            },
            status=201 if created else 200
        )

    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except ValueError as e:
        return PolicyResponseBuilder.error(str(e), status=400)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_the_initialised_policy(request):
    """
    Create the first version of an initialized policy
    """
    try:
        data = json.loads(request.body)
        
        if not data.get('org_policy_id'):
            return PolicyResponseBuilder.error("org_policy_id is required", status=400)
        
        org_policy_id = data['org_policy_id']
        html_content = data.get('html_content')
        created_by = data.get('created_by', 'system')
        version = "1.0"
        approver = data.get('approver', "")
        # workforce_assignment = data.get('workforce_assignment', [])

        # if len(workforce_assignment) != 0:
        #     workforce_assignment = json.dumps({"assignments": workforce_assignment})
        # else:   
        #     workforce_assignment = json.dumps({"assignments": []})

        if approver!=None or approver!="":
            approver = uuid.UUID(approver)
            checkingApproverExists = Employee.objects.filter(id=approver).exists()
            if not checkingApproverExists:
                return PolicyResponseBuilder.error("Approver not found", status=404)

        # Validate UUID and fetch OrgPolicy
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
            org_policy = OrgPolicy.objects.get(id=uuid.UUID(org_policy_id))
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)
        except OrgPolicy.DoesNotExist:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)

        # Determine checkpoint content
        checkpoint_content = html_content if html_content is not None else org_policy.template or ""
        checkpoint_source = "provided_html" if html_content is not None else "org_policy_template"
        
        print(f"Creating version {version} for policy: {org_policy.title}")
        print(f"Checkpoint source: {checkpoint_source}, length: {len(checkpoint_content)}")

        # Calculate diff from empty to current content
        old_html = ""
        new_html = org_policy.template or ""
        diff_json = compute_html_diff(old_html, new_html)
        
        print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

        # Create PolicyVersion record
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

            created_policy_version_id = policy_version.id

            # org_policy.workforce_assignments = workforce_assignment
            # org_policy.save()

            savingApprover = PolicyApprover.objects.create(
                policy_version_id=created_policy_version_id,
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
                "approver":approver
            },
            status=201
        )

    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_policy(request):
    """
    Update an existing policy with a new version.
    If version not provided, auto-increment as x.y.1
    If version is provided, increment to (x+1).0
    """
    try:
        # Decode body
        body_content = request.body
        if isinstance(body_content, bytes):
            body_content = body_content.decode('utf-8')
        data = json.loads(body_content)

        # Validate required fields
        required_fields = ['org_policy_id', 'organization_id', 'html_content', 'workforce_assignment', 'approver']
        for field in required_fields:
            if not data.get(field):
                return PolicyResponseBuilder.error(f"{field} is required", status=400)

        org_policy_id = data['org_policy_id']
        organization_id = data['organization_id']
        new_html = data['html_content']
        workforce_assignment = data['workforce_assignment']
        approver = data['approver']
        version = data.get('version')

        # Validate UUID
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)

        # Verify OrgPolicy exists
        org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
        if not org_policy_row:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)

        org_policy_id_db, org_policy_title = org_policy_row
        print(f"Updating OrgPolicy: {org_policy_title}")

        # Count existing versions
        existing_versions_count = PolicyService.count_policy_versions(org_policy_id)
        new_version_position = existing_versions_count + 1

        # 🟢 VERSION LOGIC
        last_version_str = PolicyService.get_latest_version_number(org_policy_id)

        def parse_version(v):
            parts = v.split('.')
            while len(parts) < 3:
                parts.append('0')
            return list(map(int, parts[:3]))

        if not version:
            # No version provided → increment patch version
            if last_version_str:
                try:
                    major, minor, patch = parse_version(last_version_str)
                    patch += 1
                    version = f"{major}.{minor}.{patch}"
                except Exception as e:
                    print(f"Error parsing version '{last_version_str}': {e}")
                    version = "1.0.1"
            else:
                version = "1.0.1"  # default for first entry
        else:
            # Version provided → increment major only
            try:
                major, *_ = parse_version(version)
                major += 1
                version = f"{major}.0"
            except Exception as e:
                print(f"Error parsing provided version '{version}': {e}")
                version = "1.0"

        print(f"Computed version: {version}")

        # Get first version (for diff base)
        first_version_row = PolicyService.get_first_policy_version(org_policy_id)
        old_html = ""
        if first_version_row:
            first_version_id, first_version_number, diff_data_str, created_at = first_version_row
            if diff_data_str and diff_data_str.strip():
                try:
                    diff_dict = json.loads(diff_data_str)
                    old_html = apply_diff("", diff_dict)
                except Exception as e:
                    print(f"Error reconstructing HTML: {e}")

        # Compute diff
        diff_json = compute_html_diff(old_html, new_html)

        # Determine checkpoint
        is_checkpoint_version = (new_version_position % 10 == 1) and (new_version_position >= 11)
        checkpoint_content = new_html if is_checkpoint_version else ""

        # Insert new PolicyVersion
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

                print(f"✅ New PolicyVersion created: {inserted_id}")

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


# @csrf_exempt
# @require_http_methods(["POST"])
# def update_policy(request):
#     """
#     Update an existing policy with a new version
#     """
#     try:
#         # Handle request body decoding
#         body_content = request.body
#         if isinstance(body_content, bytes):
#             body_content = body_content.decode('utf-8')
        
#         data = json.loads(body_content)
        
#         # Validate required fields
#         required_fields = ['org_policy_id', 'organization_id', 'html_content','workforce_assignment','approver']
#         for field in required_fields:
#             if not data.get(field):
#                 return PolicyResponseBuilder.error(f"{field} is required", status=400)
        
#         org_policy_id = data['org_policy_id']
#         organization_id = data['organization_id']
#         new_html = data['html_content']
#         workforce_assignment = data['workforce_assignment']
#         approver = data['approver']

#         # created_by = data.get('created_by', 'system')

#         # Validate UUID format
#         try:
#             PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
#         except ValueError:
#             return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)

#         # Verify OrgPolicy exists
#         org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
#         if not org_policy_row:
#             return PolicyResponseBuilder.error("OrgPolicy not found", status=404)
        
#         org_policy_id_db, org_policy_title = org_policy_row
#         print(f"Updating OrgPolicy: {org_policy_title}")

#         # Count existing versions and determine position
#         existing_versions_count = PolicyService.count_policy_versions(org_policy_id)
#         new_version_position = existing_versions_count + 1
#         print(f"Existing versions: {existing_versions_count}, New position: {new_version_position}")

#         # Get first version and reconstruct initial HTML
#         first_version_row = PolicyService.get_first_policy_version(org_policy_id)
#         old_html = ""

#         if first_version_row:
#             first_version_id, first_version_number, diff_data_str, created_at = first_version_row
            
#             print("=== FIRST VERSION DATA ===")
#             print(f"Version: {first_version_number}, Diff length: {len(diff_data_str) if diff_data_str else 0}")
            
#             # Parse and apply diff data to reconstruct HTML
#             if diff_data_str and diff_data_str.strip():
#                 try:
#                     diff_dict = json.loads(diff_data_str)
#                     old_html = apply_diff("", diff_dict)
#                     print(f"Reconstructed HTML length: {len(old_html)}")
#                 except (json.JSONDecodeError, Exception) as e:
#                     print(f"Error processing diff data: {e}")
#                     # Continue with empty HTML as fallback

#         # Calculate diff between initial and new HTML
#         diff_json = compute_html_diff(old_html, new_html)
#         print(f"Update diff computed. Changes: {len(diff_json.get('changes', []))}")

#         # Determine checkpoint strategy
#         is_checkpoint_version = (new_version_position % 10 == 1) and (new_version_position >= 11)
#         checkpoint_content = new_html if is_checkpoint_version else ""
#         print(f"Version position: {new_version_position}, Is checkpoint: {is_checkpoint_version}")

#         # Create new PolicyVersion
#         try:
#             with transaction.atomic():
#                 new_policy_version_id = str(uuid.uuid4())
#                 diff_json_str = json.dumps(diff_json)
                
#                 inserted_id = PolicyService.create_policy_version_record([
#                     new_policy_version_id,
#                     org_policy_id,
#                     version,
#                     diff_json_str,
#                     checkpoint_content,
#                     'published',
#                     # created_by,
#                     # created_by
#                 ])
                
#                 print(f"✅ New PolicyVersion created: {inserted_id}")

#         except Exception as e:
#             print(f"Error creating PolicyVersion: {str(e)}")
#             traceback.print_exc()
#             return PolicyResponseBuilder.error(f"Failed to create policy version: {str(e)}", status=500)

#         # Build success response
#         response_data = {
#             "org_policy_id": org_policy_id,
#             "policy_version_id": inserted_id,
#             "version_number": version,
#             "version_position": new_version_position,
#             "is_checkpoint": is_checkpoint_version,
#             "checkpoint_saved": bool(checkpoint_content),
#             "reconstructed_html_length": len(old_html),
#             "new_html_length": len(new_html),
#             "changes_count": len(diff_json.get('changes', []))
#         }
        
#         if first_version_row:
#             response_data["initial_version_used"] = first_version_number
        
#         return PolicyResponseBuilder.success("Policy updated successfully", response_data, status=201)

#     except json.JSONDecodeError as e:
#         print(f"JSON decode error: {e}")
#         return PolicyResponseBuilder.error("Invalid JSON payload", status=400)
#     except Exception as e:
#         print(f"[EXCEPTION] Internal error: {str(e)}")
#         traceback.print_exc()
#         return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_policy_version_html(request):
    """
    Get the latest (or specific) version HTML for a policy.
    If version not provided, fetch the latest version from DB.
    """
    try:
        body_content = request.body
        if isinstance(body_content, bytes):
            body_content = body_content.decode('utf-8')

        data = json.loads(body_content)
        org_policy_id = data.get("org_policy_id")
        input_version = data.get("version", None)
        organization_id = data.get("organization_id", None)

        if not org_policy_id:
            return PolicyResponseBuilder.error("org_policy_id is required in payload", status=400)

        # Validate UUID format
        try:
            PolicyService.validate_uuid(org_policy_id, 'org_policy_id')
        except ValueError:
            return PolicyResponseBuilder.error("Invalid org_policy_id format", status=400)

        # Validate OrgPolicy exists
        org_policy_row = PolicyService.get_org_policy_by_id(org_policy_id)
        if not org_policy_row:
            return PolicyResponseBuilder.error("OrgPolicy not found", status=404)

        org_policy_id_db, org_policy_title = org_policy_row

        # 🟩 Fetch latest version (if version not given)
        with connection.cursor() as cursor:
            if input_version:
                target_version = input_version
            else:
                cursor.execute("""
                    SELECT version
                    FROM policy_versions
                    WHERE org_policy_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, [org_policy_id])
                row = cursor.fetchone()
                target_version = row[0] if row else None

        if not target_version:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)

        # 🟩 Get all versions sequentially to reconstruct HTML
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT version, diff_data::text, checkpoint_template
                FROM policy_versions
                WHERE org_policy_id = %s
                ORDER BY created_at ASC
            """, [org_policy_id])
            all_versions = cursor.fetchall()

        if not all_versions:
            return PolicyResponseBuilder.error("No versions found for this policy", status=404)

        # 🟩 Sequential reconstruction from diffs
        current_html = ""
        target_found = False

        for version_data in all_versions:
            version_num, diff_data_str, checkpoint_content = version_data

            # Apply diff if available
            if diff_data_str and diff_data_str.strip():
                try:
                    diff_dict = json.loads(diff_data_str)
                    current_html = apply_diff(current_html, diff_dict)
                except Exception as e:
                    print(f"Error applying diff for version {version_num}: {e}")

            # Stop at the target version
            if version_num == target_version:
                target_found = True
                break

        if not target_found:
            return PolicyResponseBuilder.error(f"Version {target_version} not found for this policy", status=404)

        # 🟩 Get metadata for the target version
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT status, created_at
                FROM policy_versions
                WHERE org_policy_id = %s AND version = %s
                LIMIT 1
            """, [org_policy_id, target_version])
            version_info = cursor.fetchone()

        if version_info:
            status, created_at = version_info
        else:
            status, created_at = "unknown", None

        # 🟩 Success response
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
                "organization_id":organization_id
            }
        )

    except json.JSONDecodeError:
        return PolicyResponseBuilder.error("Invalid JSON payload", status=400)

    except Exception as e:
        print(f"[EXCEPTION] Internal error: {str(e)}")
        traceback.print_exc()
        return PolicyResponseBuilder.error(f"Internal server error: {str(e)}", status=500)


# =============================================================================
# UNUSED VIEW FUNCTIONS (COMMENTED OUT FOR NOW)
# =============================================================================

"""
@csrf_exempt
@require_http_methods(["POST"])
def legacy_policy_creation(request):
    # Legacy policy creation endpoint - not currently used
    pass

@csrf_exempt  
@require_http_methods(["GET"])
def policy_approval_workflow(request):
    # Policy approval workflow - not currently implemented
    pass
"""



# @staticmethod
# def get_latest_version_number(org_policy_id):
#     """Fetch the latest version number string for a given OrgPolicy ID."""
#     with connection.cursor() as cursor:
#         cursor.execute("""
#             SELECT version
#             FROM policy_versions
#             WHERE org_policy_id = %s
#             ORDER BY created_at DESC
#             LIMIT 1
#         """, [org_policy_id])
#         row = cursor.fetchone()
#         return row[0] if row else None
