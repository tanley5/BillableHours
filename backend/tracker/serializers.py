from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from rest_framework import serializers

from .models import Assignment, Contractor, Job, Photo, Project, User, Visit
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
        if getattr(user, "role", None) != User.Role.CLIENT:
            raise serializers.ValidationError("Only clients may log in.")
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        login(request, validated_data["user"])
        return validated_data["user"]


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
    class Meta:
        model = Contractor
        fields = ["id", "name", "phone", "email"]

    def validate(self, attrs):
        phone = attrs.get("phone", getattr(self.instance, "phone", ""))
        email = attrs.get("email", getattr(self.instance, "email", ""))
        if not phone and not email:
            raise serializers.ValidationError("Provide a phone or email.")
        return attrs


class AssignmentSerializer(serializers.ModelSerializer):
    contractor = ContractorSerializer(read_only=True)
    link = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ["id", "contractor", "hourly_rate", "token", "revoked", "link", "created_at"]
        read_only_fields = fields

    def get_link(self, obj):
        request = self.context.get("request")
        path = obj.link_path
        if request:
            return request.build_absolute_uri(path)
        return path


class AssignmentCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    hourly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate(self, attrs):
        if not attrs.get("phone") and not attrs.get("email"):
            raise serializers.ValidationError("Provide a phone or email.")
        return attrs

    def create(self, validated_data):
        project = self.context["project"]
        contractor = Contractor.objects.create(
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            email=validated_data.get("email", ""),
        )
        return Assignment.objects.create(
            project=project,
            contractor=contractor,
            hourly_rate=validated_data["hourly_rate"],
        )


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
        # Client photos served via authenticated endpoint
        path = f"/api/photos/{obj.id}/"
        token = self.context.get("contractor_token")
        if token:
            path = f"/api/c/{token}/photos/{obj.id}/"
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
            return JobSerializer(children, many=True, context={**self.context, "nest_found_issues": False}).data
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
