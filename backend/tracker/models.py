import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password is None:
            user.set_unusable_password()
        else:
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
        CONTRACTOR = "contractor", "Contractor"

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
    class ConnectStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        RESTRICTED = "restricted", "Restricted"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="contractor_profile")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(unique=True)
    stripe_connect_account_id = models.CharField(max_length=255, blank=True, default="")
    connect_status = models.CharField(
        max_length=20,
        choices=ConnectStatus.choices,
        default=ConnectStatus.NOT_STARTED,
    )
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.phone and not self.email:
            raise ValidationError("Contractor must have a phone or email.")

    def __str__(self):
        return self.name

    @property
    def has_active_assignments(self):
        return self.assignments.filter(
            status__in=[Assignment.Status.INVITED, Assignment.Status.ACCEPTED]
        ).exists()


class ClientContractor(models.Model):
    """Client's contractor pool (roster). Silent — not visible on contractor home."""

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="roster")
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE, related_name="roster_memberships")
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("client", "contractor")]

    def __str__(self):
        return f"{self.client_id}:{self.contractor_id}"


def hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


class PasswordInvite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_invites")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create_for_user(cls, user: User) -> tuple["PasswordInvite", str]:
        raw = generate_invite_token()
        ttl = getattr(settings, "PASSWORD_INVITE_TTL_DAYS", 7)
        invite = cls.objects.create(
            user=user,
            token_hash=hash_invite_token(raw),
            expires_at=timezone.now() + timedelta(days=ttl),
        )
        return invite, raw

    def is_valid(self, raw: str) -> bool:
        if self.used_at is not None:
            return False
        if timezone.now() >= self.expires_at:
            return False
        return secrets.compare_digest(self.token_hash, hash_invite_token(raw))


class Assignment(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assignments")
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE, related_name="assignments")
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)
    invited_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "contractor"],
                condition=Q(status__in=["invited", "accepted"]),
                name="unique_active_assignment_per_project_contractor",
            )
        ]

    def __str__(self):
        return f"{self.contractor} @ {self.project} ({self.status})"

    @property
    def is_active(self):
        return self.status in (self.Status.INVITED, self.Status.ACCEPTED)


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
