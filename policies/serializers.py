# policies/serializers.py
from rest_framework import serializers
from .models import Organization, Policy, PolicyVersion

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id","name","created_at","updated_at"]

class PolicySerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.IntegerField(write_only=True)
    class Meta:
        model = Policy
        fields = ["id","title","description","organization","organization_id","created_at"]

class PolicyVersionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyVersion
        fields = ["version_number","created_at","created_by","is_checkpoint"]
