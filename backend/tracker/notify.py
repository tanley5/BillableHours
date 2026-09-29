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
