import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.CLIENT)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self):
        return self.email


class Project(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    scope = models.TextField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Contractor(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.phone and not self.email:
            raise ValidationError("Contractor must have a phone or email.")

    def __str__(self):
        return self.name


def generate_assignment_token():
    return secrets.token_urlsafe(settings.TOKEN_BYTES)


class Assignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assignments")
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE, related_name="assignments")
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    token = models.CharField(max_length=64, unique=True, default=generate_assignment_token, editable=False)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "contractor")]

    def __str__(self):
        return f"{self.contractor} @ {self.project}"

    @property
    def link_path(self):
        return f"/c/{self.token}"


class Visit(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DISPUTED = "disputed", "Disputed"

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="visits")
    date = models.DateField()
    hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal(str(settings.VISIT_MAX_HOURS))),
        ],
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    client_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Tracks lineage when a disputed visit is corrected/resubmitted
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_by",
    )

    def __str__(self):
        return f"Visit {self.date} ({self.hours}h)"


class Job(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETE = "complete", "Complete"
        APPROVED = "approved", "Approved"
        DISPUTED = "disputed", "Disputed"

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="jobs")
    label = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="found_issues",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    client_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_by",
    )

    def __str__(self):
        return self.label

    @property
    def is_found_issue(self):
        return self.parent_id is not None

    def has_before_photo(self):
        return self.photos.filter(kind=Photo.Kind.BEFORE).exists()

    def has_after_photo(self):
        return self.photos.filter(kind=Photo.Kind.AFTER).exists()


class Photo(models.Model):
    class Kind(models.TextChoices):
        BEFORE = "before", "Before"
        AFTER = "after", "After"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="photos")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    file = models.ImageField(upload_to="photos/%Y/%m/%d/")
    captured_at = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_missing = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} photo for {self.job_id}"
