import csv

import stripe
from django.contrib.auth import logout
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import (
    ContractorRateThrottle,
    IsClient,
    IsContractor,
    assert_assignment_accepted,
    get_contractor,
    get_owned_assignment,
)
from .images import process_uploaded_image
from .models import Assignment, ClientContractor, Contractor, Job, Photo, Project, Visit
from .serializers import (
    AssignmentCreateSerializer,
    AssignmentSerializer,
    ContractorCreateSerializer,
    ContractorSerializer,
    DisputeSerializer,
    JobCreateSerializer,
    JobSerializer,
    JobUpdateSerializer,
    LoginSerializer,
    PhotoSerializer,
    PhotoUploadSerializer,
    ProjectDetailSerializer,
    ProjectSerializer,
    ResubmitJobSerializer,
    ResubmitVisitSerializer,
    SetPasswordSerializer,
    VisitCreateSerializer,
    VisitSerializer,
    VisitUpdateSerializer,
)
from . import notify as notifications
from . import services
from . import stripe_connect
from .serializers import _issue_password_invite


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set"})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"email": user.email, "role": user.role})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"email": request.user.email, "role": request.user.role})


class SetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password set. You can log in."})


# ---------------------------------------------------------------------------
# Client project / contractor APIs
# ---------------------------------------------------------------------------


class ProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProjectDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = ProjectDetailSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user).prefetch_related(
            "assignments__contractor"
        )


class ContractorListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        roster = (
            ClientContractor.objects.filter(client=request.user, archived=False)
            .select_related("contractor", "contractor__user")
            .order_by("contractor__name")
        )
        contractors = [m.contractor for m in roster]
        return Response(ContractorSerializer(contractors, many=True).data)

    def post(self, request):
        serializer = ContractorCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        contractor = serializer.save()
        return Response(ContractorSerializer(contractor).data, status=status.HTTP_201_CREATED)


class ContractorDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def _get(self, request, pk):
        membership = get_object_or_404(
            ClientContractor.objects.select_related("contractor", "contractor__user"),
            client=request.user,
            contractor_id=pk,
            archived=False,
        )
        return membership.contractor

    def get(self, request, pk):
        return Response(ContractorSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        contractor = self._get(request, pk)
        name = request.data.get("name")
        phone = request.data.get("phone")
        if name is not None:
            contractor.name = name
        if phone is not None:
            contractor.phone = phone
        contractor.save()
        return Response(ContractorSerializer(contractor).data)

    def delete(self, request, pk):
        membership = get_object_or_404(
            ClientContractor, client=request.user, contractor_id=pk, archived=False
        )
        if membership.contractor.has_active_assignments:
            return Response(
                {"detail": "Cannot archive contractor with active assignments."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership.archived = True
        membership.save(update_fields=["archived"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractorResendInviteView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        membership = get_object_or_404(
            ClientContractor.objects.select_related("contractor", "contractor__user"),
            client=request.user,
            contractor_id=pk,
            archived=False,
        )
        contractor = membership.contractor
        if contractor.user.has_usable_password():
            return Response(
                {"detail": "Contractor already activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _issue_password_invite(contractor.user, contractor)
        return Response({"detail": "Invite resent."})


class AssignmentCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, owner=request.user)
        serializer = AssignmentCreateSerializer(
            data=request.data, context={"project": project, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return Response(
            AssignmentSerializer(assignment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AssignmentCancelView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, project__owner=request.user)
        if assignment.status != Assignment.Status.INVITED:
            return Response(
                {"detail": "Only invited assignments can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.status = Assignment.Status.CANCELLED
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=["status", "responded_at"])
        return Response(AssignmentSerializer(assignment, context={"request": request}).data)


class ProjectJobsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = JobSerializer

    def get_queryset(self):
        project = get_object_or_404(Project, pk=self.kwargs["pk"], owner=self.request.user)
        return (
            Job.objects.filter(assignment__project=project, parent__isnull=True)
            .prefetch_related("photos", "found_issues__photos")
            .order_by("-created_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["nest_found_issues"] = True
        return ctx


class ProjectVisitsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = VisitSerializer

    def get_queryset(self):
        project = get_object_or_404(Project, pk=self.kwargs["pk"], owner=self.request.user)
        return Visit.objects.filter(assignment__project=project).order_by("-date", "-created_at")


class JobApproveView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, assignment__project__owner=request.user)
        job = services.approve_job(job)
        return Response(JobSerializer(job, context={"request": request, "nest_found_issues": False}).data)


class JobDisputeView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, assignment__project__owner=request.user)
        serializer = DisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = services.dispute_job(job, serializer.validated_data["comment"])
        return Response(JobSerializer(job, context={"request": request, "nest_found_issues": False}).data)


class VisitApproveView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk, assignment__project__owner=request.user)
        visit = services.approve_visit(visit)
        return Response(VisitSerializer(visit).data)


class VisitDisputeView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk, assignment__project__owner=request.user)
        serializer = DisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = services.dispute_visit(visit, serializer.validated_data["comment"])
        return Response(VisitSerializer(visit).data)


class ProjectExportCsvView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, owner=request.user)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="project-{project.id}-export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["type", "id", "label_or_date", "hours", "status", "notes", "client_comment", "contractor"]
        )

        jobs = Job.objects.filter(
            assignment__project=project, status=Job.Status.APPROVED
        ).select_related("assignment__contractor")
        for job in jobs:
            writer.writerow(
                [
                    "job",
                    job.id,
                    job.label,
                    "",
                    job.status,
                    job.notes,
                    job.client_comment or "",
                    job.assignment.contractor.name,
                ]
            )

        visits = Visit.objects.filter(
            assignment__project=project, status=Visit.Status.APPROVED
        ).select_related("assignment__contractor")
        for visit in visits:
            writer.writerow(
                [
                    "visit",
                    visit.id,
                    visit.date.isoformat(),
                    str(visit.hours),
                    visit.status,
                    visit.notes,
                    visit.client_comment or "",
                    visit.assignment.contractor.name,
                ]
            )
        return response


class ClientPhotoDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request, pk):
        photo = get_object_or_404(Photo, pk=pk, job__assignment__project__owner=request.user)
        return FileResponse(photo.file.open("rb"), content_type="image/jpeg")


# ---------------------------------------------------------------------------
# Contractor session namespace
# ---------------------------------------------------------------------------


class ContractorMeView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request):
        c = get_contractor(request)
        return Response(
            {
                "email": request.user.email,
                "role": request.user.role,
                "contractor": ContractorSerializer(c).data,
            }
        )


class ContractorAssignmentListView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request):
        qs = (
            Assignment.objects.filter(contractor=get_contractor(request))
            .exclude(status=Assignment.Status.CANCELLED)
            .select_related("project", "contractor")
            .order_by("-invited_at")
        )
        data = []
        for a in qs:
            row = AssignmentSerializer(a).data
            row["project_name"] = a.project.name
            row["project_scope"] = a.project.scope
            data.append(row)
        return Response(data)


class ContractorAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        open_jobs = (
            Job.objects.filter(assignment=assignment, status=Job.Status.OPEN, parent__isnull=True)
            .prefetch_related("photos", "found_issues__photos")
            .order_by("-created_at")
        )
        recent_visits = Visit.objects.filter(assignment=assignment).order_by("-date", "-created_at")[:20]
        disputed_jobs = Job.objects.filter(assignment=assignment, status=Job.Status.DISPUTED)
        disputed_visits = Visit.objects.filter(assignment=assignment, status=Visit.Status.DISPUTED)
        ctx = {"request": request, "assignment_id": assignment.id, "nest_found_issues": True}
        return Response(
            {
                "assignment": AssignmentSerializer(assignment).data,
                "project": {"name": assignment.project.name, "scope": assignment.project.scope},
                "contractor": {"name": assignment.contractor.name},
                "open_jobs": JobSerializer(open_jobs, many=True, context=ctx).data,
                "recent_visits": VisitSerializer(recent_visits, many=True).data,
                "disputed_jobs": JobSerializer(
                    disputed_jobs, many=True, context={**ctx, "nest_found_issues": False}
                ).data,
                "disputed_visits": VisitSerializer(disputed_visits, many=True).data,
            }
        )


class ContractorAssignmentAcceptView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]

    def post(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        if assignment.status != Assignment.Status.INVITED:
            return Response(
                {"detail": "Only invited assignments can be accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.status = Assignment.Status.ACCEPTED
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=["status", "responded_at"])
        return Response(AssignmentSerializer(assignment).data)


class ContractorAssignmentRejectView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]

    def post(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        if assignment.status != Assignment.Status.INVITED:
            return Response(
                {"detail": "Only invited assignments can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.status = Assignment.Status.REJECTED
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=["status", "responded_at"])
        return Response(AssignmentSerializer(assignment).data)


class ContractorJobListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        jobs = (
            Job.objects.filter(assignment=assignment, parent__isnull=True)
            .prefetch_related("photos", "found_issues__photos")
            .order_by("-created_at")
        )
        ctx = {"request": request, "assignment_id": assignment.id, "nest_found_issues": True}
        return Response(JobSerializer(jobs, many=True, context=ctx).data)

    def post(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        if assignment.status != Assignment.Status.ACCEPTED:
            return Response(
                {"detail": "Assignment must be accepted before creating jobs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = JobCreateSerializer(data=request.data, context={"assignment": assignment})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        notifications.notify_job_created(job)
        ctx = {"request": request, "assignment_id": assignment.id, "nest_found_issues": False}
        return Response(JobSerializer(job, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorJobDetailView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def patch(self, request, pk, job_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        job = get_object_or_404(Job, pk=job_id, assignment=assignment)
        serializer = JobUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        job = services.update_job_if_open(job, **serializer.validated_data)
        ctx = {"request": request, "assignment_id": assignment.id, "nest_found_issues": False}
        return Response(JobSerializer(job, context=ctx).data)

    def delete(self, request, pk, job_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        job = get_object_or_404(Job, pk=job_id, assignment=assignment)
        services.delete_job_if_open(job)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractorPhotoUploadView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk, job_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        job = get_object_or_404(Job, pk=job_id, assignment=assignment)
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        processed = process_uploaded_image(data["file"])
        photo = services.add_photo(
            job,
            kind=data["kind"],
            file=processed,
            captured_at=data.get("captured_at"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            location_missing=data.get("location_missing", False),
        )
        ctx = {"request": request, "assignment_id": assignment.id}
        return Response(PhotoSerializer(photo, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorVisitListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        visits = Visit.objects.filter(assignment=assignment).order_by("-date", "-created_at")
        return Response(VisitSerializer(visits, many=True).data)

    def post(self, request, pk):
        assignment = get_owned_assignment(request, pk)
        if assignment.status != Assignment.Status.ACCEPTED:
            return Response(
                {"detail": "Assignment must be accepted before logging visits."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VisitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = Visit.objects.create(assignment=assignment, **serializer.validated_data)
        notifications.notify_visit_created(visit)
        return Response(VisitSerializer(visit).data, status=status.HTTP_201_CREATED)


class ContractorVisitDetailView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def patch(self, request, pk, visit_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        visit = get_object_or_404(Visit, pk=visit_id, assignment=assignment)
        serializer = VisitUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        visit = services.update_visit_if_pending(visit, **serializer.validated_data)
        return Response(VisitSerializer(visit).data)

    def delete(self, request, pk, visit_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        visit = get_object_or_404(Visit, pk=visit_id, assignment=assignment)
        services.delete_visit_if_pending(visit)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractorResubmitJobView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def post(self, request, pk, job_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        job = get_object_or_404(Job, pk=job_id, assignment=assignment)
        serializer = ResubmitJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = services.resubmit_job(job, **serializer.validated_data)
        notifications.notify_resubmit(kind="job", original_id=job.id, replacement=replacement)
        ctx = {"request": request, "assignment_id": assignment.id, "nest_found_issues": False}
        return Response(JobSerializer(replacement, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorResubmitVisitView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def post(self, request, pk, visit_id):
        assignment = get_owned_assignment(request, pk)
        assert_assignment_accepted(assignment)
        visit = get_object_or_404(Visit, pk=visit_id, assignment=assignment)
        serializer = ResubmitVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = services.resubmit_visit(visit, **serializer.validated_data)
        notifications.notify_resubmit(kind="visit", original_id=visit.id, replacement=replacement)
        return Response(VisitSerializer(replacement).data, status=status.HTTP_201_CREATED)


class ContractorPhotoDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]
    throttle_classes = [ContractorRateThrottle]

    def get(self, request, pk, photo_id):
        assignment = get_owned_assignment(request, pk)
        photo = get_object_or_404(Photo, pk=photo_id, job__assignment=assignment)
        return FileResponse(photo.file.open("rb"), content_type="image/jpeg")


class ContractorConnectOnboardView(APIView):
    permission_classes = [IsAuthenticated, IsContractor]

    def post(self, request):
        contractor = get_contractor(request)
        try:
            url = stripe_connect.create_account_link(contractor)
        except Exception as exc:  # noqa: BLE001 — surface Stripe config errors clearly
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        contractor.refresh_from_db()
        return Response({"url": url, "connect_status": contractor.connect_status})


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe_connect.construct_webhook_event(payload, sig)
        except ValueError:
            return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({"detail": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        if event.type == "account.updated":
            account = event.data.object
            if not isinstance(account, dict):
                account = account.to_dict() if hasattr(account, "to_dict") else dict(account)
            stripe_connect.apply_account_updated(account)

        return Response({"received": True})
