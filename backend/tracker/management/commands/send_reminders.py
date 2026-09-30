"""Scan for overdue actions and emit reminder events to n8n (SPEC2 phase 5)."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import Assignment, Escrow, Project, SubJob, Submission
from tracker import notify as notifications
from tracker import stripe_escrow


def hours_setting(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def send_reminders(*, now=None) -> dict:
    """Emit reminder (and nearing-expiry) events. Idempotent enough for hourly cron."""
    now = now or timezone.now()
    counts = {
        "assignment_invite": 0,
        "in_route": 0,
        "sub_job_pending": 0,
        "submission_review": 0,
        "project_frozen": 0,
        "escrow_nearing_expiry": 0,
        "escrow_expired": 0,
    }

    invite_hours = hours_setting("REMINDER_ASSIGNMENT_INVITE_HOURS", 24)
    for a in Assignment.objects.filter(
        status=Assignment.Status.INVITED,
        invited_at__lte=now - timedelta(hours=invite_hours),
    ).select_related("project", "contractor"):
        notifications.notify(
            notifications.EVENT_REMINDER_ASSIGNMENT_INVITE,
            {
                "assignment_id": a.id,
                "project_id": a.project_id,
                "project_name": a.project.name,
                "contractor_email": a.contractor.email,
                "contractor_name": a.contractor.name,
                "invited_at": a.invited_at.isoformat(),
            },
        )
        counts["assignment_invite"] += 1

    in_route_hours = hours_setting("REMINDER_IN_ROUTE_HOURS", 4)
    for a in Assignment.objects.filter(
        status=Assignment.Status.ACCEPTED,
        in_route_at__isnull=True,
        responded_at__lte=now - timedelta(hours=in_route_hours),
    ).select_related("project", "contractor"):
        notifications.notify(
            notifications.EVENT_REMINDER_IN_ROUTE,
            {
                "assignment_id": a.id,
                "project_id": a.project_id,
                "project_name": a.project.name,
                "contractor_email": a.contractor.email,
                "in_route_url": f"{notifications.app_origin()}/contractor/assignments/{a.id}",
            },
        )
        counts["in_route"] += 1

    pending_hours = hours_setting("REMINDER_SUBJOB_PENDING_HOURS", 24)
    for sj in SubJob.objects.filter(
        status=SubJob.Status.PENDING_APPROVAL,
        created_at__lte=now - timedelta(hours=pending_hours),
    ).select_related("project__owner"):
        notifications.notify(
            notifications.EVENT_REMINDER_SUBJOB_PENDING,
            {
                "sub_job_id": sj.id,
                "label": sj.label,
                "project_id": sj.project_id,
                "project_name": sj.project.name,
                "client_email": sj.project.owner.email,
            },
        )
        counts["sub_job_pending"] += 1

    review_hours = hours_setting("REMINDER_SUBMISSION_REVIEW_HOURS", 24)
    for sub in Submission.objects.filter(
        review_status=Submission.ReviewStatus.PENDING,
        created_at__lte=now - timedelta(hours=review_hours),
    ).select_related("sub_job__project__owner", "contractor"):
        notifications.notify(
            notifications.EVENT_REMINDER_SUBMISSION_REVIEW,
            {
                "submission_id": sub.id,
                "sub_job_id": sub.sub_job_id,
                "project_id": sub.sub_job.project_id,
                "project_name": sub.sub_job.project.name,
                "client_email": sub.sub_job.project.owner.email,
                "contractor_name": sub.contractor.name,
            },
        )
        counts["submission_review"] += 1

    frozen_hours = hours_setting("REMINDER_PROJECT_FROZEN_HOURS", 24)
    for project in Project.objects.filter(
        frozen=True,
        updated_at__lte=now - timedelta(hours=frozen_hours),
    ).select_related("owner"):
        notifications.notify(
            notifications.EVENT_REMINDER_PROJECT_FROZEN,
            {
                "project_id": project.id,
                "project_name": project.name,
                "client_email": project.owner.email,
                "frozen_reason": project.frozen_reason,
            },
        )
        counts["project_frozen"] += 1

    warn_hours = hours_setting("ESCROW_EXPIRY_WARNING_HOURS", 24)
    warn_until = now + timedelta(hours=warn_hours)
    for escrow in Escrow.objects.filter(
        status=Escrow.Status.REQUIRES_CAPTURE,
        expires_at__isnull=False,
        expires_at__lte=warn_until,
        expires_at__gt=now,
    ).select_related("sub_job__project__owner"):
        notifications.notify_escrow_nearing_expiry(escrow)
        counts["escrow_nearing_expiry"] += 1

    counts["escrow_expired"] = stripe_escrow.process_expired_holds()
    return counts


class Command(BaseCommand):
    help = "Send SPEC2 reminder notifications and process escrow expiry warnings/holds."

    def handle(self, *args, **options):
        counts = send_reminders()
        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {counts}"))
