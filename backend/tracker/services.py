from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from .models import Assignment, Job, Photo, Visit


class LockConflict(DRFValidationError):
    """Raised when approval wins a race against a contractor edit."""

    default_code = "approval_wins"

    def __init__(self, detail=None):
        message = detail or "This entry was approved by the client and can no longer be edited."
        super().__init__(detail={"detail": message}, code=self.default_code)


def assert_assignment_active(assignment: Assignment):
    if assignment.status != Assignment.Status.ACCEPTED:
        raise PermissionDenied("Assignment must be accepted before performing this action.")


def project_totals(project):
    """Roll-up hours and cost for a project (approved vs pending)."""
    visits = Visit.objects.filter(
        assignment__project=project,
        assignment__status=Assignment.Status.ACCEPTED,
    )
    approved = visits.filter(status=Visit.Status.APPROVED)
    pending = visits.filter(status=Visit.Status.PENDING)

    def sum_hours(qs):
        total = qs.aggregate(total=Sum("hours"))["total"] or Decimal("0")
        return Decimal(total).quantize(Decimal("0.01"))

    def cost_for(qs):
        total = Decimal("0")
        for visit in qs.select_related("assignment"):
            total += visit.hours * visit.assignment.hourly_rate
        return total.quantize(Decimal("0.01"))

    return {
        "approved_hours": sum_hours(approved),
        "pending_hours": sum_hours(pending),
        "approved_cost": cost_for(approved),
        "pending_cost": cost_for(pending),
    }


def ensure_job_editable(job: Job):
    job.refresh_from_db()
    if job.status in (Job.Status.APPROVED, Job.Status.DISPUTED, Job.Status.COMPLETE):
        if job.status == Job.Status.APPROVED:
            raise LockConflict()
        if job.status != Job.Status.OPEN:
            raise DRFValidationError(
                {"detail": f"Job is {job.status} and cannot be edited."}
            )


def ensure_visit_editable(visit: Visit):
    visit.refresh_from_db()
    if visit.status == Visit.Status.APPROVED:
        raise LockConflict()
    if visit.status != Visit.Status.PENDING:
        raise DRFValidationError(
            {"detail": f"Visit is {visit.status} and cannot be edited."}
        )


@transaction.atomic
def update_job_if_open(job: Job, **fields):
    locked = Job.objects.select_for_update().get(pk=job.pk)
    if locked.status == Job.Status.APPROVED:
        raise LockConflict()
    if locked.status != Job.Status.OPEN:
        raise DRFValidationError({"detail": f"Job is {locked.status} and cannot be edited."})
    for key, value in fields.items():
        setattr(locked, key, value)
    locked.save()
    return locked


@transaction.atomic
def delete_job_if_open(job: Job):
    locked = Job.objects.select_for_update().get(pk=job.pk)
    if locked.status == Job.Status.APPROVED:
        raise LockConflict()
    if locked.status != Job.Status.OPEN:
        raise DRFValidationError({"detail": f"Job is {locked.status} and cannot be deleted."})
    locked.delete()


@transaction.atomic
def update_visit_if_pending(visit: Visit, **fields):
    locked = Visit.objects.select_for_update().get(pk=visit.pk)
    if locked.status == Visit.Status.APPROVED:
        raise LockConflict()
    if locked.status != Visit.Status.PENDING:
        raise DRFValidationError({"detail": f"Visit is {locked.status} and cannot be edited."})
    for key, value in fields.items():
        setattr(locked, key, value)
    locked.save()
    return locked


@transaction.atomic
def delete_visit_if_pending(visit: Visit):
    locked = Visit.objects.select_for_update().get(pk=visit.pk)
    if locked.status == Visit.Status.APPROVED:
        raise LockConflict()
    if locked.status != Visit.Status.PENDING:
        raise DRFValidationError({"detail": f"Visit is {locked.status} and cannot be deleted."})
    locked.delete()


@transaction.atomic
def approve_job(job: Job):
    locked = Job.objects.select_for_update().get(pk=job.pk)
    if locked.status != Job.Status.COMPLETE:
        raise DRFValidationError({"detail": "Only completed jobs can be approved."})
    locked.status = Job.Status.APPROVED
    locked.client_comment = None
    locked.save(update_fields=["status", "client_comment", "updated_at"])
    return locked


@transaction.atomic
def dispute_job(job: Job, comment: str):
    locked = Job.objects.select_for_update().get(pk=job.pk)
    if locked.status != Job.Status.COMPLETE:
        raise DRFValidationError({"detail": "Only completed jobs can be disputed."})
    if not comment or not comment.strip():
        raise DRFValidationError({"comment": "A comment is required to dispute."})
    locked.status = Job.Status.DISPUTED
    locked.client_comment = comment.strip()
    locked.save(update_fields=["status", "client_comment", "updated_at"])
    return locked


@transaction.atomic
def approve_visit(visit: Visit):
    locked = Visit.objects.select_for_update().get(pk=visit.pk)
    if locked.status != Visit.Status.PENDING:
        raise DRFValidationError({"detail": "Only pending visits can be approved."})
    locked.status = Visit.Status.APPROVED
    locked.client_comment = None
    locked.save(update_fields=["status", "client_comment", "updated_at"])
    return locked


@transaction.atomic
def dispute_visit(visit: Visit, comment: str):
    locked = Visit.objects.select_for_update().get(pk=visit.pk)
    if locked.status != Visit.Status.PENDING:
        raise DRFValidationError({"detail": "Only pending visits can be disputed."})
    if not comment or not comment.strip():
        raise DRFValidationError({"comment": "A comment is required to dispute."})
    locked.status = Visit.Status.DISPUTED
    locked.client_comment = comment.strip()
    locked.save(update_fields=["status", "client_comment", "updated_at"])
    return locked


@transaction.atomic
def resubmit_job(disputed: Job, *, label=None, notes=None):
    locked = Job.objects.select_for_update().get(pk=disputed.pk)
    if locked.status != Job.Status.DISPUTED:
        raise DRFValidationError({"detail": "Only disputed jobs can be resubmitted."})
    replacement = Job.objects.create(
        assignment=locked.assignment,
        label=label if label is not None else locked.label,
        parent=locked.parent,
        notes=notes if notes is not None else locked.notes,
        status=Job.Status.OPEN,
        supersedes=locked,
    )
    return replacement


@transaction.atomic
def resubmit_visit(disputed: Visit, *, date=None, hours=None, notes=None):
    locked = Visit.objects.select_for_update().get(pk=disputed.pk)
    if locked.status != Visit.Status.DISPUTED:
        raise DRFValidationError({"detail": "Only disputed visits can be resubmitted."})
    replacement = Visit.objects.create(
        assignment=locked.assignment,
        date=date if date is not None else locked.date,
        hours=hours if hours is not None else locked.hours,
        notes=notes if notes is not None else locked.notes,
        status=Visit.Status.PENDING,
        supersedes=locked,
    )
    return replacement


def validate_photo_upload(job: Job, kind: str, file_size: int):
    if job.status not in (Job.Status.OPEN, Job.Status.COMPLETE):
        if job.status == Job.Status.APPROVED:
            raise LockConflict()
        raise DRFValidationError({"detail": f"Cannot add photos to a {job.status} job."})

    if kind == Photo.Kind.AFTER and not job.has_before_photo():
        raise DRFValidationError({"kind": "Add at least one before photo before after photos."})

    count = job.photos.filter(kind=kind).count()
    if count >= settings.PHOTO_MAX_PER_KIND:
        raise DRFValidationError({"file": f"At most {settings.PHOTO_MAX_PER_KIND} {kind} photos allowed."})

    if file_size > settings.PHOTO_MAX_BYTES:
        raise DRFValidationError({"file": f"Photo exceeds max size of {settings.PHOTO_MAX_BYTES} bytes."})


@transaction.atomic
def add_photo(job: Job, *, kind, file, captured_at, latitude=None, longitude=None, location_missing=False):
    locked = Job.objects.select_for_update().get(pk=job.pk)
    if locked.status == Job.Status.APPROVED:
        raise LockConflict()
    if locked.status in (Job.Status.DISPUTED,):
        raise DRFValidationError({"detail": f"Cannot add photos to a {locked.status} job."})

    validate_photo_upload(locked, kind, getattr(file, "size", 0) or 0)

    if location_missing is False and (latitude is None or longitude is None):
        location_missing = True

    photo = Photo.objects.create(
        job=locked,
        kind=kind,
        file=file,
        captured_at=captured_at or timezone.now(),
        latitude=latitude,
        longitude=longitude,
        location_missing=location_missing,
    )

    # Completion signal: first after photo (with before already present) -> complete
    if kind == Photo.Kind.AFTER and locked.status == Job.Status.OPEN and locked.has_before_photo():
        locked.status = Job.Status.COMPLETE
        locked.save(update_fields=["status", "updated_at"])

    return photo


def validate_parent_job(assignment: Assignment, parent_id):
    if parent_id is None:
        return None
    try:
        parent = Job.objects.get(pk=parent_id, assignment=assignment)
    except Job.DoesNotExist as exc:
        raise DRFValidationError({"parent": "Parent job not found on this assignment."}) from exc
    if parent.status not in (Job.Status.OPEN, Job.Status.COMPLETE):
        raise DRFValidationError({"parent": "Found issues can only nest under open or complete jobs."})
    return parent
