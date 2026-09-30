from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Assignment,
    ClientContractor,
    Contractor,
    PasswordInvite,
    Project,
    User,
    Visit,
    Job,
    Photo,
)
from . import notify as notifications
from .services import validate_parent_job


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        if getattr(user, "role", None) not in (User.Role.CLIENT, User.Role.CONTRACTOR):
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        login(request, validated_data["user"])
        return validated_data["user"]


class SetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        raw = attrs["token"]
        from .models import hash_invite_token

        invite = (
            PasswordInvite.objects.select_related("user")
            .filter(token_hash=hash_invite_token(raw), used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if invite is None or not invite.is_valid(raw):
            raise serializers.ValidationError({"token": "Invalid or expired invite token."})
        attrs["invite"] = invite
        return attrs

    def save(self, **kwargs):
        invite: PasswordInvite = self.validated_data["invite"]
        user = invite.user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        invite.used_at = timezone.now()
        invite.save(update_fields=["used_at"])
        # Invalidate other unused invites for this user
        PasswordInvite.objects.filter(user=user, used_at__isnull=True).exclude(pk=invite.pk).update(
            used_at=timezone.now()
        )
        return user


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "scope", "budget", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectDetailSerializer(ProjectSerializer):
    totals = serializers.SerializerMethodField()
    assignments = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["totals", "assignments"]

    def get_totals(self, obj):
        from .services import project_totals

        totals = project_totals(obj)
        return {k: str(v) for k, v in totals.items()}

    def get_assignments(self, obj):
        return AssignmentSerializer(obj.assignments.select_related("contractor"), many=True).data


class ContractorSerializer(serializers.ModelSerializer):
    activated = serializers.SerializerMethodField()
    accept_rate = serializers.SerializerMethodField()
    rejection_count = serializers.SerializerMethodField()
    assigned_to_this_project = serializers.SerializerMethodField()
    assigned_elsewhere = serializers.SerializerMethodField()

    class Meta:
        model = Contractor
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "connect_status",
            "archived",
            "activated",
            "accept_rate",
            "rejection_count",
            "assigned_to_this_project",
            "assigned_elsewhere",
            "created_at",
        ]
        read_only_fields = fields

    def get_activated(self, obj):
        return obj.user.has_usable_password()

    def get_accept_rate(self, obj):
        from .services import contractor_reliability

        rate = contractor_reliability(obj)["accept_rate"]
        return str(rate) if rate is not None else None

    def get_rejection_count(self, obj):
        from .services import contractor_reliability

        return contractor_reliability(obj)["rejection_count"]

    def get_assigned_to_this_project(self, obj):
        project = self.context.get("project")
        if project is None:
            return False
        from .services import contractor_assignment_markers

        return contractor_assignment_markers(obj, project)["assigned_to_this_project"]

    def get_assigned_elsewhere(self, obj):
        project = self.context.get("project")
        if project is None:
            return False
        from .services import contractor_assignment_markers

        return contractor_assignment_markers(obj, project)["assigned_elsewhere"]


class ContractorCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    email = serializers.EmailField()

    def validate(self, attrs):
        if not attrs.get("phone") and not attrs.get("email"):
            raise serializers.ValidationError("Provide a phone or email.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        client = self.context["request"].user
        email = User.objects.normalize_email(validated_data["email"])
        existing = Contractor.objects.filter(email__iexact=email).first()

        if existing:
            ClientContractor.objects.get_or_create(client=client, contractor=existing)
            # Silent roster add — no invite, no notify
            return existing

        user = User.objects.create_user(
            email=email,
            password=None,
            role=User.Role.CONTRACTOR,
        )
        contractor = Contractor.objects.create(
            user=user,
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            email=email,
        )
        ClientContractor.objects.create(client=client, contractor=contractor)
        _issue_password_invite(user, contractor)
        return contractor


def _issue_password_invite(user: User, contractor: Contractor) -> str:
    # Invalidate prior unused invites
    PasswordInvite.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    invite, raw = PasswordInvite.create_for_user(user)
    origin = getattr(settings, "APP_ORIGIN", "http://localhost").rstrip("/")
    set_password_url = f"{origin}/auth/set-password?token={raw}"
    notifications.notify(
        notifications.EVENT_CONTRACTOR_INVITED,
        {
            "contractor_id": contractor.id,
            "email": contractor.email,
            "name": contractor.name,
            "set_password_url": set_password_url,
            "invite_token": raw,
        },
    )
    return raw


class AssignmentSerializer(serializers.ModelSerializer):
    contractor = ContractorSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id",
            "contractor",
            "hourly_rate",
            "status",
            "invited_at",
            "responded_at",
            "created_at",
            "project",
        ]
        read_only_fields = fields


class AssignmentCreateSerializer(serializers.Serializer):
    contractor_id = serializers.IntegerField()
    hourly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate(self, attrs):
        project: Project = self.context["project"]
        client = project.owner
        try:
            contractor = Contractor.objects.get(pk=attrs["contractor_id"])
        except Contractor.DoesNotExist as exc:
            raise serializers.ValidationError({"contractor_id": "Contractor not found."}) from exc

        if not ClientContractor.objects.filter(
            client=client, contractor=contractor, archived=False
        ).exists():
            raise serializers.ValidationError({"contractor_id": "Contractor not found."})

        if contractor.connect_status != Contractor.ConnectStatus.COMPLETE:
            raise serializers.ValidationError(
                {
                    "contractor_id": (
                        "Contractor must complete Stripe Connect onboarding before assignment."
                    )
                }
            )

        if Assignment.objects.filter(
            project=project,
            contractor=contractor,
            status__in=[Assignment.Status.INVITED, Assignment.Status.ACCEPTED],
        ).exists():
            raise serializers.ValidationError(
                {"contractor_id": "Contractor already has an active assignment on this project."}
            )

        attrs["contractor"] = contractor
        return attrs

    def create(self, validated_data):
        project = self.context["project"]
        assignment = Assignment.objects.create(
            project=project,
            contractor=validated_data["contractor"],
            hourly_rate=validated_data["hourly_rate"],
            status=Assignment.Status.INVITED,
            invited_at=timezone.now(),
        )
        notifications.notify(
            notifications.EVENT_ASSIGNMENT_INVITED,
            {
                "assignment_id": assignment.id,
                "project_id": project.id,
                "project_name": project.name,
                "contractor_id": assignment.contractor_id,
                "contractor_email": assignment.contractor.email,
                "contractor_name": assignment.contractor.name,
                "hourly_rate": str(assignment.hourly_rate),
            },
        )
        return assignment


class PhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "id",
            "kind",
            "url",
            "captured_at",
            "latitude",
            "longitude",
            "location_missing",
            "uploaded_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        assignment_id = self.context.get("assignment_id")
        if assignment_id:
            path = f"/api/contractor/assignments/{assignment_id}/photos/{obj.id}/"
        else:
            path = f"/api/photos/{obj.id}/"
        if request:
            return request.build_absolute_uri(path)
        return path


class JobSerializer(serializers.ModelSerializer):
    photos = PhotoSerializer(many=True, read_only=True)
    found_issues = serializers.SerializerMethodField()
    is_found_issue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "assignment",
            "label",
            "parent",
            "notes",
            "status",
            "client_comment",
            "is_found_issue",
            "photos",
            "found_issues",
            "created_at",
            "updated_at",
            "supersedes",
        ]
        read_only_fields = [
            "id",
            "assignment",
            "status",
            "client_comment",
            "is_found_issue",
            "photos",
            "found_issues",
            "created_at",
            "updated_at",
            "supersedes",
        ]

    def get_found_issues(self, obj):
        if self.context.get("nest_found_issues", True) and obj.parent_id is None:
            children = obj.found_issues.all().prefetch_related("photos")
            return JobSerializer(
                children, many=True, context={**self.context, "nest_found_issues": False}
            ).data
        return []


class JobCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    parent = serializers.IntegerField(required=False, allow_null=True, default=None)

    def create(self, validated_data):
        assignment = self.context["assignment"]
        parent = validate_parent_job(assignment, validated_data.get("parent"))
        return Job.objects.create(
            assignment=assignment,
            label=validated_data["label"],
            notes=validated_data.get("notes", ""),
            parent=parent,
        )


class JobUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class VisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visit
        fields = [
            "id",
            "assignment",
            "date",
            "hours",
            "notes",
            "status",
            "client_comment",
            "created_at",
            "updated_at",
            "supersedes",
        ]
        read_only_fields = [
            "id",
            "assignment",
            "status",
            "client_comment",
            "created_at",
            "updated_at",
            "supersedes",
        ]


class VisitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visit
        fields = ["date", "hours", "notes"]


class VisitUpdateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("16"),
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class DisputeSerializer(serializers.Serializer):
    comment = serializers.CharField()


class PhotoUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Photo.Kind.choices)
    file = serializers.ImageField()
    captured_at = serializers.DateTimeField(required=False)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    location_missing = serializers.BooleanField(required=False, default=False)


class ResubmitJobSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class ResubmitVisitSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("16"),
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
