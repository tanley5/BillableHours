import csv

from django.contrib.auth import logout
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ContractorRateThrottle, ContractorTokenAuthentication, IsClient, IsContractorAssignment
from .images import process_uploaded_image
from .models import Assignment, Job, Photo, Project, Visit
from .serializers import (
    AssignmentCreateSerializer,
    AssignmentSerializer,
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
    VisitCreateSerializer,
    VisitSerializer,
    VisitUpdateSerializer,
)
from . import services
from . import notify as notifications


# ---------------------------------------------------------------------------
# Client auth
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
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        return Response({"email": request.user.email, "role": request.user.role})


# ---------------------------------------------------------------------------
# Client project / assignment APIs
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


class AssignmentCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, owner=request.user)
        serializer = AssignmentCreateSerializer(data=request.data, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return Response(
            AssignmentSerializer(assignment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AssignmentRevokeView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, project__owner=request.user)
        assignment.revoked = True
        assignment.save(update_fields=["revoked"])
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
        writer.writerow(["type", "id", "label_or_date", "hours", "status", "notes", "client_comment", "contractor"])

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
# Contractor token namespace
# ---------------------------------------------------------------------------


class ContractorBaseView(APIView):
    authentication_classes = [ContractorTokenAuthentication]
    permission_classes = [IsContractorAssignment]
    throttle_classes = [ContractorRateThrottle]

    def initial(self, request, *args, **kwargs):
        request.contractor_token = kwargs.get("token")
        super().initial(request, *args, **kwargs)

    @property
    def assignment(self) -> Assignment:
        return self.request.auth


class ContractorSummaryView(ContractorBaseView):
    def get(self, request, token):
        assignment = self.assignment
        project = assignment.project
        open_jobs = (
            Job.objects.filter(assignment=assignment, status=Job.Status.OPEN, parent__isnull=True)
            .prefetch_related("photos", "found_issues__photos")
            .order_by("-created_at")
        )
        recent_visits = Visit.objects.filter(assignment=assignment).order_by("-date", "-created_at")[:20]
        disputed_jobs = Job.objects.filter(assignment=assignment, status=Job.Status.DISPUTED)
        disputed_visits = Visit.objects.filter(assignment=assignment, status=Visit.Status.DISPUTED)

        ctx = {"request": request, "contractor_token": token, "nest_found_issues": True}
        return Response(
            {
                "project": {"name": project.name, "scope": project.scope},
                "contractor": {"name": assignment.contractor.name},
                "open_jobs": JobSerializer(open_jobs, many=True, context=ctx).data,
                "recent_visits": VisitSerializer(recent_visits, many=True).data,
                "disputed_jobs": JobSerializer(disputed_jobs, many=True, context={**ctx, "nest_found_issues": False}).data,
                "disputed_visits": VisitSerializer(disputed_visits, many=True).data,
            }
        )


class ContractorJobListCreateView(ContractorBaseView):
    def get(self, request, token):
        jobs = (
            Job.objects.filter(assignment=self.assignment, parent__isnull=True)
            .prefetch_related("photos", "found_issues__photos")
            .order_by("-created_at")
        )
        ctx = {"request": request, "contractor_token": token, "nest_found_issues": True}
        return Response(JobSerializer(jobs, many=True, context=ctx).data)

    def post(self, request, token):
        serializer = JobCreateSerializer(data=request.data, context={"assignment": self.assignment})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        notifications.notify_job_created(job)
        ctx = {"request": request, "contractor_token": token, "nest_found_issues": False}
        return Response(JobSerializer(job, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorJobDetailView(ContractorBaseView):
    def patch(self, request, token, pk):
        job = get_object_or_404(Job, pk=pk, assignment=self.assignment)
        serializer = JobUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        job = services.update_job_if_open(job, **serializer.validated_data)
        ctx = {"request": request, "contractor_token": token, "nest_found_issues": False}
        return Response(JobSerializer(job, context=ctx).data)

    def delete(self, request, token, pk):
        job = get_object_or_404(Job, pk=pk, assignment=self.assignment)
        services.delete_job_if_open(job)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractorPhotoUploadView(ContractorBaseView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, token, pk):
        job = get_object_or_404(Job, pk=pk, assignment=self.assignment)
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
        ctx = {"request": request, "contractor_token": token}
        return Response(PhotoSerializer(photo, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorVisitListCreateView(ContractorBaseView):
    def get(self, request, token):
        visits = Visit.objects.filter(assignment=self.assignment).order_by("-date", "-created_at")
        return Response(VisitSerializer(visits, many=True).data)

    def post(self, request, token):
        serializer = VisitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = Visit.objects.create(assignment=self.assignment, **serializer.validated_data)
        notifications.notify_visit_created(visit)
        return Response(VisitSerializer(visit).data, status=status.HTTP_201_CREATED)


class ContractorVisitDetailView(ContractorBaseView):
    def patch(self, request, token, pk):
        visit = get_object_or_404(Visit, pk=pk, assignment=self.assignment)
        serializer = VisitUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        visit = services.update_visit_if_pending(visit, **serializer.validated_data)
        return Response(VisitSerializer(visit).data)

    def delete(self, request, token, pk):
        visit = get_object_or_404(Visit, pk=pk, assignment=self.assignment)
        services.delete_visit_if_pending(visit)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractorResubmitJobView(ContractorBaseView):
    def post(self, request, token, pk):
        job = get_object_or_404(Job, pk=pk, assignment=self.assignment)
        serializer = ResubmitJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = services.resubmit_job(job, **serializer.validated_data)
        notifications.notify_resubmit(kind="job", original_id=job.id, replacement=replacement)
        ctx = {"request": request, "contractor_token": token, "nest_found_issues": False}
        return Response(JobSerializer(replacement, context=ctx).data, status=status.HTTP_201_CREATED)


class ContractorResubmitVisitView(ContractorBaseView):
    def post(self, request, token, pk):
        visit = get_object_or_404(Visit, pk=pk, assignment=self.assignment)
        serializer = ResubmitVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = services.resubmit_visit(visit, **serializer.validated_data)
        notifications.notify_resubmit(kind="visit", original_id=visit.id, replacement=replacement)
        return Response(VisitSerializer(replacement).data, status=status.HTTP_201_CREATED)


class ContractorPhotoDownloadView(ContractorBaseView):
    def get(self, request, token, pk):
        photo = get_object_or_404(Photo, pk=pk, job__assignment=self.assignment)
        return FileResponse(photo.file.open("rb"), content_type="image/jpeg")
