import uuid
from django.db import models


class Organization(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, unique=True, null=True, blank=True)
    domain_name = models.CharField(max_length=250, unique=True, null=True, blank=True)
    short_name = models.CharField(max_length=250, null=True, blank=True)
    dark_logo = models.CharField(max_length=250, null=True, blank=True)
    light_logo = models.CharField(max_length=250, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inactive')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name or str(self.id)


class PolicyTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    short_name = models.CharField(max_length=255, unique=False, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    template = models.TextField(null=True, blank=True)
    security_group = models.CharField(max_length=255, null=True, blank=True)
    group = models.CharField(max_length=255, null=True, blank=True)
    highlights = models.TextField(null=True, blank=True)
    version = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=False, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now_add=False, null=True, blank=True)

    class Meta:
        db_table = 'policy_templates'

    def __str__(self):
        return self.title or str(self.id)


class OrgPolicy(models.Model):
    POLICY_TYPE_CHOICES = [
        ('orgpolicy', 'Org Policy'),
        ('existingpolicy', 'Existing Policy'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES, null=True, blank=True)
    template = models.TextField(null=True, blank=True)
    created_by = models.CharField(max_length=255, null=True, blank=True)
    updated_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_policies'

    def __str__(self):
        return self.title


class PolicyVersion(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_policy = models.ForeignKey('OrgPolicy', on_delete=models.CASCADE)
    version = models.CharField(max_length=50, null=True, blank=True)
    diff_data = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.CharField(max_length=255, null=True, blank=True)
    checkpoint_template = models.TextField(null=True, blank=True)
    reviewed_at = models.DateField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=255, null=True, blank=True)
    expired_at = models.DateField(null=True, blank=True)
    updated_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'policy_versions'

    def __str__(self):
        return f"{self.org_policy.title} - {self.version}"


class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    google2fa_secret = models.TextField(null=True, blank=True)
    two_factor_verified = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'roles'

    def __str__(self):
        return self.name


class UserRoleOrganization(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('invited', 'Invited'),
        ('resent-invited', 'Resent-Invited'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    role = models.ForeignKey('Role', on_delete=models.CASCADE)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_role_organizations'

    def __str__(self):
        return f"{self.user.email} - {self.organization.name}"