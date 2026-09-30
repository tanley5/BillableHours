from django.urls import path

from . import views

urlpatterns = [
    # Auth
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/set-password/", views.SetPasswordView.as_view(), name="set-password"),
    # Stripe
    path("stripe/webhook/", views.StripeWebhookView.as_view(), name="stripe-webhook"),
    # Client projects / contractors
    path("projects/", views.ProjectListCreateView.as_view(), name="project-list"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:pk>/assignments/", views.AssignmentCreateView.as_view(), name="assignment-create"),
    path("projects/<int:pk>/jobs/", views.ProjectJobsView.as_view(), name="project-jobs"),
    path("projects/<int:pk>/visits/", views.ProjectVisitsView.as_view(), name="project-visits"),
    path("projects/<int:pk>/export.csv", views.ProjectExportCsvView.as_view(), name="project-export"),
    path("contractors/", views.ContractorListCreateView.as_view(), name="contractor-list"),
    path("contractors/<int:pk>/", views.ContractorDetailView.as_view(), name="contractor-detail"),
    path(
        "contractors/<int:pk>/resend-invite/",
        views.ContractorResendInviteView.as_view(),
        name="contractor-resend-invite",
    ),
    path("assignments/<int:pk>/cancel/", views.AssignmentCancelView.as_view(), name="assignment-cancel"),
    path("jobs/<int:pk>/approve/", views.JobApproveView.as_view(), name="job-approve"),
    path("jobs/<int:pk>/dispute/", views.JobDisputeView.as_view(), name="job-dispute"),
    path("visits/<int:pk>/approve/", views.VisitApproveView.as_view(), name="visit-approve"),
    path("visits/<int:pk>/dispute/", views.VisitDisputeView.as_view(), name="visit-dispute"),
    path("photos/<int:pk>/", views.ClientPhotoDownloadView.as_view(), name="client-photo"),
    # Contractor session namespace
    path("contractor/me/", views.ContractorMeView.as_view(), name="contractor-me"),
    path(
        "contractor/connect/onboard/",
        views.ContractorConnectOnboardView.as_view(),
        name="contractor-connect-onboard",
    ),
    path(
        "contractor/assignments/",
        views.ContractorAssignmentListView.as_view(),
        name="contractor-assignments",
    ),
    path(
        "contractor/assignments/<int:pk>/",
        views.ContractorAssignmentDetailView.as_view(),
        name="contractor-assignment-detail",
    ),
    path(
        "contractor/assignments/<int:pk>/accept/",
        views.ContractorAssignmentAcceptView.as_view(),
        name="contractor-assignment-accept",
    ),
    path(
        "contractor/assignments/<int:pk>/reject/",
        views.ContractorAssignmentRejectView.as_view(),
        name="contractor-assignment-reject",
    ),
    path(
        "contractor/assignments/<int:pk>/jobs/",
        views.ContractorJobListCreateView.as_view(),
        name="contractor-jobs",
    ),
    path(
        "contractor/assignments/<int:pk>/jobs/<int:job_id>/",
        views.ContractorJobDetailView.as_view(),
        name="contractor-job-detail",
    ),
    path(
        "contractor/assignments/<int:pk>/jobs/<int:job_id>/photos/",
        views.ContractorPhotoUploadView.as_view(),
        name="contractor-job-photos",
    ),
    path(
        "contractor/assignments/<int:pk>/jobs/<int:job_id>/resubmit/",
        views.ContractorResubmitJobView.as_view(),
        name="contractor-job-resubmit",
    ),
    path(
        "contractor/assignments/<int:pk>/visits/",
        views.ContractorVisitListCreateView.as_view(),
        name="contractor-visits",
    ),
    path(
        "contractor/assignments/<int:pk>/visits/<int:visit_id>/",
        views.ContractorVisitDetailView.as_view(),
        name="contractor-visit-detail",
    ),
    path(
        "contractor/assignments/<int:pk>/visits/<int:visit_id>/resubmit/",
        views.ContractorResubmitVisitView.as_view(),
        name="contractor-visit-resubmit",
    ),
    path(
        "contractor/assignments/<int:pk>/photos/<int:photo_id>/",
        views.ContractorPhotoDownloadView.as_view(),
        name="contractor-photo",
    ),
]
