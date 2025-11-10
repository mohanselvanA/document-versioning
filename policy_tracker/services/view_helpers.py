import json
import uuid
from django.http import JsonResponse
from django.db import transaction, connection
from io import BytesIO
from xhtml2pdf import pisa

class PolicyService:
    @staticmethod
    def get_latest_version_number(org_policy_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT version FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at DESC LIMIT 1",
                [org_policy_id],
            )
            row = cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    def validate_uuid(uuid_string, field_name):
        try:
            return uuid.UUID(uuid_string)
        except ValueError:
            raise ValueError(f"Invalid {field_name} format")

    @staticmethod
    def get_org_policy_by_id(org_policy_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title FROM org_policies WHERE id = %s", [org_policy_id])
            return cursor.fetchone()

    @staticmethod
    def count_policy_versions(org_policy_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM policy_versions WHERE org_policy_id = %s", [org_policy_id])
            return cursor.fetchone()[0]

    @staticmethod
    def get_first_policy_version(org_policy_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, version, diff_data::text as diff_data_str, created_at FROM policy_versions WHERE org_policy_id = %s ORDER BY created_at ASC LIMIT 1",
                [org_policy_id],
            )
            return cursor.fetchone()

    @staticmethod
    def create_policy_version_record(version_data):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO policy_versions
                (id, org_policy_id, version, diff_data, checkpoint_template, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                version_data,
            )
            result = cursor.fetchone()
            return result[0] if result else version_data[0]

class PolicyResponseBuilder:
    @staticmethod
    def success(message, data=None, status=200):
        response = {"message": message, "status": "success"}
        if data:
            response.update(data)
        return JsonResponse(response, status=status)

    @staticmethod
    def error(message, status=400, details=None):
        response = {"error": message, "status": "error"}
        if details:
            response["details"] = details
        return JsonResponse(response, status=status)

def render_pdf_from_html(html_source: str) -> bytes:
    result = BytesIO()
    pdf = pisa.CreatePDF(src=html_source, dest=result)
    if pdf.err:
        raise RuntimeError(f"PDF generation failed: {pdf.err}")
    return result.getvalue()
