from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """
    Stores organization details.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Policy(models.Model):
    """
    Stores base information about a policy.
    """
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    # Many-to-many relation through OrganizationPolicy
    organizations = models.ManyToManyField(
        Organization,
        through='OrganizationPolicy',
        related_name='policies_linked'  # <-- Change related_name to avoid conflict
    )

    def __str__(self):
        return self.title


class PolicyVersion(models.Model):
    """
    Stores versioned content of a policy.
    """
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("policy", "version_number")
        ordering = ["version_number"]

    def __str__(self):
        return f"{self.policy.title} v{self.version_number}"


class OrganizationPolicy(models.Model):
    """
    Reference table that links an organization with a policy.
    """
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
