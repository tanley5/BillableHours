"""SubJob / Submission / project status machine (SPEC2 phase 3). Escrow capture is phase 4."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Assignment, Project, SubJob, Submission, SubJobPhoto, SubmissionPhoto


def assert_project_writable(project: Project):
    if project.frozen:
        raise DRFValidationError({"detail": "Project is frozen and cannot be modified."})


def recompute_project_status(project: Project) -> Project:
    """
    Derive project status from assignments + sub-jobs.
    Never downgrades COMPLETE. Frozen is independent (phase 4).
    """
    project.refresh_from_db()
    if project.status == Project.Status.COMPLETE:
        return project

    sub_jobs = list(project.sub_jobs.all())
    pipeline = [s for s in sub_jobs if s.is_in_pipeline]
    accepted = [s for s in pipeline if s.status == SubJob.Status.ACCEPTED]
    pending_review = [s for s in pipeline if s.status == SubJob.Status.PENDING_REVIEW]
    open_or_review = [
        s
        for s in pipeline
        if s.status in (SubJob.Status.OPEN, SubJob.Status.PENDING_REVIEW, SubJob.Status.ACCEPTED)
    ]

    assignments = list(project.assignments.all())
    has_accepted = any(a.status == Assignment.Status.ACCEPTED for a in assignments)
    has_in_route = any(a.in_route_at for a in assignments if a.status == Assignment.Status.ACCEPTED)

    new_status = Project.Status.CREATED
    if pipeline and len(accepted) == len(pipeline) and pipeline:
        new_status = Project.Status.COMPLETE
    elif pending_review:
        new_status = Project.Status.READY_FOR_EVALUATION
    elif open_or_review:
        new_status = Project.Status.IN_PROGRESS
    elif has_in_route:
        new_status = Project.Status.CONTRACTOR_IN_ROUTE
    elif has_accepted:
        new_status = Project.Status.CONTRACTOR_ASSIGNED

    if new_status != project.status:
        project.status = new_status
        project.save(update_fields=["status", "updated_at"])
    return project


@transaction.atomic
def create_client_subjob(*, project: Project, label: str, amount: Decimal, before_file) -> SubJob:
    assert_project_writable(project)
    if amount is None or amount <= 0:
        raise DRFValidationError({"amount": "Amount is required for client-created sub-jobs."})
    if before_file is None:
        raise DRFValidationError({"before_photo": "A before photo is required."})
    sub = SubJob.objects.create(
        project=project,
        label=label,
        amount=amount,
        status=SubJob.Status.OPEN,
        created_by=SubJob.CreatedBy.CLIENT,
    )
    SubJobPhoto.objects.create(sub_job=sub, file=before_file)
    recompute_project_status(project)
    return sub


@transaction.atomic
def create_contractor_subjob(*, project: Project, contractor, label: str, before_file) -> SubJob:
    assert_project_writable(project)
    if before_file is None:
        raise DRFValidationError({"before_photo": "A before photo is required."})
    sub = SubJob.objects.create(
        project=project,
        label=label,
        amount=None,
        status=SubJob.Status.PENDING_APPROVAL,
        created_by=SubJob.CreatedBy.CONTRACTOR,
        created_by_contractor=contractor,
    )
    SubJobPhoto.objects.create(sub_job=sub, file=before_file)
    recompute_project_status(project)
    return sub


@transaction.atomic
def approve_and_fund_subjob(sub_job: SubJob, *, amount: Decimal) -> SubJob:
    assert_project_writable(sub_job.project)
    locked = SubJob.objects.select_for_update().get(pk=sub_job.pk)
    if locked.status != SubJob.Status.PENDING_APPROVAL:
        raise DRFValidationError({"detail": "Only pending_approval sub-jobs can be approved."})
    if amount is None or amount <= 0:
        raise DRFValidationError({"amount": "Amount is required."})
    locked.amount = amount
    locked.status = SubJob.Status.OPEN
    locked.save(update_fields=["amount", "status", "updated_at"])
    # Escrow PaymentIntent is phase 4 — amount is recorded now.
    recompute_project_status(locked.project)
    return locked


@transaction.atomic
def deny_subjob(sub_job: SubJob, *, reason: str = "") -> SubJob:
    assert_project_writable(sub_job.project)
    locked = SubJob.objects.select_for_update().get(pk=sub_job.pk)
    if locked.status != SubJob.Status.PENDING_APPROVAL:
        raise DRFValidationError({"detail": "Only pending_approval sub-jobs can be denied."})
    locked.status = SubJob.Status.DENIED
    locked.denial_reason = (reason or "").strip()
    locked.save(update_fields=["status", "denial_reason", "updated_at"])
    recompute_project_status(locked.project)
    return locked


@transaction.atomic
def create_submission(*, sub_job: SubJob, contractor, hours: Decimal, notes: str, after_file) -> Submission:
    assert_project_writable(sub_job.project)
    locked = SubJob.objects.select_for_update().get(pk=sub_job.pk)
    if locked.status != SubJob.Status.OPEN:
        raise DRFValidationError({"detail": "Submissions are only allowed on open sub-jobs."})
    if after_file is None:
        raise DRFValidationError({"after_photo": "An after photo is required."})
    if hours is None or hours <= 0:
        raise DRFValidationError({"hours": "Hours must be greater than zero."})
    submission = Submission.objects.create(
        sub_job=locked,
        contractor=contractor,
        hours=hours,
        notes=notes or "",
        review_status=Submission.ReviewStatus.PENDING,
    )
    SubmissionPhoto.objects.create(
        submission=submission, kind=SubmissionPhoto.Kind.AFTER, file=after_file
    )
    locked.status = SubJob.Status.PENDING_REVIEW
    locked.save(update_fields=["status", "updated_at"])
    recompute_project_status(locked.project)
    return submission


@transaction.atomic
def accept_submission(submission: Submission, *, reviewer) -> Submission:
    assert_project_writable(submission.sub_job.project)
    locked = Submission.objects.select_for_update().select_related("sub_job__project").get(pk=submission.pk)
    if locked.review_status != Submission.ReviewStatus.PENDING:
        raise DRFValidationError({"detail": "Only pending submissions can be accepted."})
    sub = SubJob.objects.select_for_update().get(pk=locked.sub_job_id)
    if sub.status != SubJob.Status.PENDING_REVIEW:
        raise DRFValidationError({"detail": "Sub-job is not pending review."})

    locked.review_status = Submission.ReviewStatus.ACCEPTED
    locked.reviewed_by = reviewer
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["review_status", "reviewed_by", "reviewed_at"])

    sub.status = SubJob.Status.ACCEPTED
    sub.save(update_fields=["status", "updated_at"])
    # Escrow capture is phase 4
    recompute_project_status(sub.project)
    return locked


@transaction.atomic
def reject_submission(submission: Submission, *, reviewer, reason: str) -> Submission:
    assert_project_writable(submission.sub_job.project)
    locked = Submission.objects.select_for_update().select_related("sub_job").get(pk=submission.pk)
    if locked.review_status != Submission.ReviewStatus.PENDING:
        raise DRFValidationError({"detail": "Only pending submissions can be rejected."})
    if not reason or not str(reason).strip():
        raise DRFValidationError({"reason": "A reason is required to reject."})
    sub = SubJob.objects.select_for_update().get(pk=locked.sub_job_id)

    locked.review_status = Submission.ReviewStatus.REJECTED
    locked.reviewed_by = reviewer
    locked.review_reason = str(reason).strip()
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["review_status", "reviewed_by", "review_reason", "reviewed_at"])

    # Re-open for resubmission; rejected record stays
    sub.status = SubJob.Status.OPEN
    sub.save(update_fields=["status", "updated_at"])
    recompute_project_status(sub.project)
    return locked


@transaction.atomic
def confirm_in_route(assignment: Assignment) -> Assignment:
    locked = Assignment.objects.select_for_update().select_related("project").get(pk=assignment.pk)
    if locked.status != Assignment.Status.ACCEPTED:
        raise DRFValidationError({"detail": "Only accepted assignments can confirm in-route."})
    assert_project_writable(locked.project)
    if locked.in_route_at is None:
        locked.in_route_at = timezone.now()
        locked.save(update_fields=["in_route_at"])
    recompute_project_status(locked.project)
    return locked


def project_activity_feed(project: Project) -> list[dict]:
    events: list[dict] = []
    for a in project.assignments.select_related("contractor").all():
        events.append(
            {
                "type": "assignment.invited",
                "timestamp": a.invited_at.isoformat(),
                "actor": a.contractor.name,
                "detail": {"assignment_id": a.id, "status": a.status},
            }
        )
        if a.status == Assignment.Status.ACCEPTED:
            events.append(
                {
                    "type": "assignment.accepted",
                    "timestamp": (a.responded_at or a.created_at).isoformat(),
                    "actor": a.contractor.name,
                    "detail": {"assignment_id": a.id},
                }
            )
        if a.status == Assignment.Status.REJECTED:
            events.append(
                {
                    "type": "assignment.rejected",
                    "timestamp": (a.responded_at or a.created_at).isoformat(),
                    "actor": a.contractor.name,
                    "detail": {"assignment_id": a.id},
                }
            )
        if a.in_route_at:
            events.append(
                {
                    "type": "assignment.in_route",
                    "timestamp": a.in_route_at.isoformat(),
                    "actor": a.contractor.name,
                    "detail": {"assignment_id": a.id},
                }
            )

    for sj in project.sub_jobs.select_related("created_by_contractor").all():
        actor = (
            sj.created_by_contractor.name
            if sj.created_by == SubJob.CreatedBy.CONTRACTOR and sj.created_by_contractor_id
            else "client"
        )
        events.append(
            {
                "type": "sub_job.created",
                "timestamp": sj.created_at.isoformat(),
                "actor": actor,
                "detail": {
                    "sub_job_id": sj.id,
                    "label": sj.label,
                    "status": sj.status,
                    "created_by": sj.created_by,
                },
            }
        )
        if sj.status == SubJob.Status.DENIED:
            events.append(
                {
                    "type": "sub_job.denied",
                    "timestamp": sj.updated_at.isoformat(),
                    "actor": "client",
                    "detail": {
                        "sub_job_id": sj.id,
                        "reason": sj.denial_reason,
                    },
                }
            )
        elif sj.created_by == SubJob.CreatedBy.CONTRACTOR and sj.status in (
            SubJob.Status.OPEN,
            SubJob.Status.PENDING_REVIEW,
            SubJob.Status.ACCEPTED,
        ):
            events.append(
                {
                    "type": "sub_job.approved",
                    "timestamp": sj.updated_at.isoformat(),
                    "actor": "client",
                    "detail": {"sub_job_id": sj.id, "amount": str(sj.amount) if sj.amount else None},
                }
            )

    for sub in Submission.objects.filter(sub_job__project=project).select_related(
        "contractor", "reviewed_by", "sub_job"
    ):
        events.append(
            {
                "type": "submission.created",
                "timestamp": sub.created_at.isoformat(),
                "actor": sub.contractor.name,
                "detail": {
                    "submission_id": sub.id,
                    "sub_job_id": sub.sub_job_id,
                    "hours": str(sub.hours),
                },
            }
        )
        if sub.reviewed_at and sub.review_status == Submission.ReviewStatus.ACCEPTED:
            events.append(
                {
                    "type": "submission.accepted",
                    "timestamp": sub.reviewed_at.isoformat(),
                    "actor": sub.reviewed_by.email if sub.reviewed_by_id else "client",
                    "detail": {"submission_id": sub.id, "sub_job_id": sub.sub_job_id},
                }
            )
        if sub.reviewed_at and sub.review_status == Submission.ReviewStatus.REJECTED:
            events.append(
                {
                    "type": "submission.rejected",
                    "timestamp": sub.reviewed_at.isoformat(),
                    "actor": sub.reviewed_by.email if sub.reviewed_by_id else "client",
                    "detail": {
                        "submission_id": sub.id,
                        "sub_job_id": sub.sub_job_id,
                        "reason": sub.review_reason,
                    },
                }
            )

    events.sort(key=lambda e: e["timestamp"])
    return events
