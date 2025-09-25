from django.db import models
from django.utils import timezone


class Organization(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Policy(models.Model):
    title = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    policy_template = models.TextField(blank=True, null=True)
    organizations = models.ManyToManyField(
        Organization,
        through='OrganizationPolicy',
        related_name='policies_linked'
    )

    def __str__(self):
        return f"{self.title} v{self.version}"


class PolicyVersion(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="versions")
    version_number = models.CharField(max_length=255)
    diffDetails = models.JSONField()
    snapshot_html = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("policy", "version_number")
        ordering = ["version_number"]

    def __str__(self):
        return f"{self.policy.title} v{self.version_number}"


class OrganizationPolicy(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='organization_policies'
    )
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name='organization_policies'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("organization", "policy")

    def __str__(self):
        return f"{self.organization.name} - {self.policy.title}"