# policies/models.py
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
    id = models.AutoField(primary_key=True)
    organization = models.ForeignKey("Organization",on_delete=models.CASCADE,related_name="policies",null=True)  # ✅ Allow nulls initiallyblank=True)
    title = models.CharField(max_length=512)
    description = models.TextField(null=True, blank=True)
    template_text = models.TextField(null=True, blank=True)  # optional template for LLM validation
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.organization.name} / {self.title}"


class PolicyVersion(models.Model):
    id = models.AutoField(primary_key=True)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=255, null=True, blank=True)

    is_checkpoint = models.BooleanField(default=False)
    full_text = models.TextField(null=True, blank=True)

    # structured diff ops: list of {"op": -1|0|1, "text": "..."}
    diff_ops = models.JSONField(null=True, blank=True)
    # patch_text from diff-match-patch for reliable application
    patch_text = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("policy", "version_number")
        ordering = ("version_number",)

    def __str__(self):
        return f"{self.policy.title} v{self.version_number}"


class PolicyTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, unique=True)
    # version = models.IntegerField(default=1)
    sections = models.JSONField(default=list)  # Use JSONField for list of sections
    content = models.TextField()  # Use TextField for optional full content

    # def __str__(self):
    #     return f"{self.title} (v{self.version})"
