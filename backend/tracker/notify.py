"""n8n notification helpers (SPEC2 phase 5). Never raises — delivery must not break the API."""
from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

EVENT_JOB_CREATED = "job.created"
EVENT_FOUND_ISSUE = "job.found_issue"
EVENT_VISIT_CREATED = "visit.created"
EVENT_RESUBMIT = "entry.resubmitted"
EVENT_CONTRACTOR_INVITED = "contractor.invited"
EVENT_ASSIGNMENT_INVITED = "assignment.invited"
EVENT_ASSIGNMENT_ACCEPTED = "assignment.accepted"
EVENT_SUBJOB_PENDING_APPROVAL = "sub_job.pending_approval"
EVENT_SUBMISSION_RECEIVED = "submission.received"
EVENT_SUBJOB_PENDING_REVIEW = "sub_job.pending_review"
EVENT_ESCROW_NEARING_EXPIRY = "escrow.nearing_expiry"
EVENT_PROJECT_FROZEN = "project.frozen"
EVENT_PROJECT_UNFROZEN = "project.unfrozen"
EVENT_REMINDER_ASSIGNMENT_INVITE = "reminder.assignment_invite"
EVENT_REMINDER_IN_ROUTE = "reminder.in_route"
EVENT_REMINDER_SUBJOB_PENDING = "reminder.sub_job_pending_approval"
EVENT_REMINDER_SUBMISSION_REVIEW = "reminder.submission_review"
EVENT_REMINDER_PROJECT_FROZEN = "reminder.project_frozen"


def notify(event: str, data: dict | None = None) -> None:
    """POST an event to n8n. Never raises — notifications must not break the API."""
    url = getattr(settings, "N8N_WEBHOOK_URL", "") or ""
    if not url:
        return

    payload = {
        "event": event,
        "data": data or {},
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=getattr(settings, "N8N_WEBHOOK_TIMEOUT", 3)):
            pass
    except (URLError, OSError, TimeoutError) as exc:
        logger.warning("n8n notify failed for %s: %s", event, exc)


def app_origin() -> str:
    return getattr(settings, "APP_ORIGIN", "http://localhost").rstrip("/")


def job_payload(job) -> dict:
    project = job.assignment.project
    return {
        "project_id": project.id,
        "project_name": project.name,
        "assignment_id": job.assignment_id,
        "contractor": job.assignment.contractor.name,
        "job_id": job.id,
        "label": job.label,
        "parent_id": job.parent_id,
        "status": job.status,
        "notes": job.notes,
    }


def visit_payload(visit) -> dict:
    project = visit.assignment.project
    return {
        "project_id": project.id,
        "project_name": project.name,
        "assignment_id": visit.assignment_id,
        "contractor": visit.assignment.contractor.name,
        "visit_id": visit.id,
        "date": visit.date.isoformat(),
        "hours": str(visit.hours),
        "status": visit.status,
        "notes": visit.notes,
    }


def notify_job_created(job) -> None:
    if job.parent_id:
        notify(EVENT_FOUND_ISSUE, job_payload(job))
    else:
        notify(EVENT_JOB_CREATED, job_payload(job))


def notify_visit_created(visit) -> None:
    notify(EVENT_VISIT_CREATED, visit_payload(visit))


def notify_resubmit(*, kind: str, original_id: int, replacement) -> None:
    if kind == "job":
        data = job_payload(replacement)
    else:
        data = visit_payload(replacement)
    data.update({"kind": kind, "original_id": original_id, "replacement_id": replacement.id})
    notify(EVENT_RESUBMIT, data)


def notify_assignment_accepted(assignment) -> None:
    project = assignment.project
    notify(
        EVENT_ASSIGNMENT_ACCEPTED,
        {
            "assignment_id": assignment.id,
            "project_id": project.id,
            "project_name": project.name,
            "contractor_id": assignment.contractor_id,
            "contractor_email": assignment.contractor.email,
            "contractor_name": assignment.contractor.name,
            "in_route_url": f"{app_origin()}/contractor/assignments/{assignment.id}",
        },
    )


def notify_subjob_pending_approval(sub_job) -> None:
    project = sub_job.project
    notify(
        EVENT_SUBJOB_PENDING_APPROVAL,
        {
            "sub_job_id": sub_job.id,
            "label": sub_job.label,
            "project_id": project.id,
            "project_name": project.name,
            "client_email": project.owner.email,
            "contractor_name": (
                sub_job.created_by_contractor.name if sub_job.created_by_contractor_id else None
            ),
            "review_url": f"{app_origin()}/app/projects/{project.id}",
        },
    )


def notify_submission_received(submission) -> None:
    sub_job = submission.sub_job
    project = sub_job.project
    data = {
        "submission_id": submission.id,
        "sub_job_id": sub_job.id,
        "label": sub_job.label,
        "hours": str(submission.hours),
        "project_id": project.id,
        "project_name": project.name,
        "client_email": project.owner.email,
        "contractor_name": submission.contractor.name,
        "review_url": f"{app_origin()}/app/projects/{project.id}",
    }
    notify(EVENT_SUBMISSION_RECEIVED, data)
    notify(EVENT_SUBJOB_PENDING_REVIEW, data)


def notify_escrow_nearing_expiry(escrow) -> None:
    sub_job = escrow.sub_job
    project = sub_job.project
    notify(
        EVENT_ESCROW_NEARING_EXPIRY,
        {
            "escrow_id": escrow.id,
            "sub_job_id": sub_job.id,
            "label": sub_job.label,
            "amount": str(escrow.amount),
            "expires_at": escrow.expires_at.isoformat() if escrow.expires_at else None,
            "project_id": project.id,
            "project_name": project.name,
            "client_email": project.owner.email,
            "reauth_url": f"{app_origin()}/app/projects/{project.id}",
        },
    )


def notify_project_frozen(project, *, reason: str = "") -> None:
    notify(
        EVENT_PROJECT_FROZEN,
        {
            "project_id": project.id,
            "project_name": project.name,
            "client_email": project.owner.email,
            "reason": reason or project.frozen_reason,
            "url": f"{app_origin()}/app/projects/{project.id}",
        },
    )


def notify_project_unfrozen(project) -> None:
    notify(
        EVENT_PROJECT_UNFROZEN,
        {
            "project_id": project.id,
            "project_name": project.name,
            "client_email": project.owner.email,
            "url": f"{app_origin()}/app/projects/{project.id}",
        },
    )
