from django.urls import path

from . import views

urlpatterns = [
    # Client auth
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    # Client projects
    path("projects/", views.ProjectListCreateView.as_view(), name="project-list"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:pk>/assignments/", views.AssignmentCreateView.as_view(), name="assignment-create"),
    path("projects/<int:pk>/jobs/", views.ProjectJobsView.as_view(), name="project-jobs"),
    path("projects/<int:pk>/visits/", views.ProjectVisitsView.as_view(), name="project-visits"),
    path("projects/<int:pk>/export.csv", views.ProjectExportCsvView.as_view(), name="project-export"),
    path("assignments/<int:pk>/revoke/", views.AssignmentRevokeView.as_view(), name="assignment-revoke"),
    path("jobs/<int:pk>/approve/", views.JobApproveView.as_view(), name="job-approve"),
    path("jobs/<int:pk>/dispute/", views.JobDisputeView.as_view(), name="job-dispute"),
    path("visits/<int:pk>/approve/", views.VisitApproveView.as_view(), name="visit-approve"),
    path("visits/<int:pk>/dispute/", views.VisitDisputeView.as_view(), name="visit-dispute"),
    path("photos/<int:pk>/", views.ClientPhotoDownloadView.as_view(), name="client-photo"),
    # Contractor token namespace
    path("c/<str:token>/", views.ContractorSummaryView.as_view(), name="contractor-summary"),
    path("c/<str:token>/jobs/", views.ContractorJobListCreateView.as_view(), name="contractor-jobs"),
    path("c/<str:token>/jobs/<int:pk>/", views.ContractorJobDetailView.as_view(), name="contractor-job-detail"),
    path("c/<str:token>/jobs/<int:pk>/photos/", views.ContractorPhotoUploadView.as_view(), name="contractor-job-photos"),
    path("c/<str:token>/jobs/<int:pk>/resubmit/", views.ContractorResubmitJobView.as_view(), name="contractor-job-resubmit"),
    path("c/<str:token>/visits/", views.ContractorVisitListCreateView.as_view(), name="contractor-visits"),
    path("c/<str:token>/visits/<int:pk>/", views.ContractorVisitDetailView.as_view(), name="contractor-visit-detail"),
    path("c/<str:token>/visits/<int:pk>/resubmit/", views.ContractorResubmitVisitView.as_view(), name="contractor-visit-resubmit"),
    path("c/<str:token>/photos/<int:pk>/", views.ContractorPhotoDownloadView.as_view(), name="contractor-photo"),
]
