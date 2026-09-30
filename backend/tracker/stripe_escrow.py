"""Per-sub-job escrow: manual-capture PaymentIntents + freeze/unfreeze (SPEC2 phase 4)."""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Assignment, Contractor, Escrow, Project, SubJob

logger = logging.getLogger(__name__)

PLATFORM_FEE_RATE = Decimal("0.02")


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def platform_fee_amount(amount: Decimal) -> Decimal:
    fee = (amount * PLATFORM_FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return fee


def amount_to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resolve_destination_contractor(sub_job: SubJob) -> Contractor:
    if sub_job.created_by_contractor_id:
        contractor = sub_job.created_by_contractor
    else:
        assignment = (
            Assignment.objects.filter(
                project_id=sub_job.project_id,
                status=Assignment.Status.ACCEPTED,
            )
            .select_related("contractor")
            .order_by("id")
            .first()
        )
        if assignment is None:
            raise DRFValidationError(
                {"detail": "An accepted contractor assignment is required before funding escrow."}
            )
        contractor = assignment.contractor

    if contractor.connect_status != Contractor.ConnectStatus.COMPLETE:
        raise DRFValidationError(
            {"detail": "Destination contractor must complete Stripe Connect onboarding before funding."}
        )
    if not contractor.stripe_connect_account_id:
        raise DRFValidationError({"detail": "Destination contractor has no Connect account."})
    return contractor


def _create_payment_intent(
    *,
    amount: Decimal,
    fee: Decimal,
    destination_account_id: str,
    metadata: dict,
) -> dict:
    amount_cents = amount_to_cents(amount)
    fee_cents = amount_to_cents(fee)
    if not settings.STRIPE_SECRET_KEY:
        return {
            "id": f"pi_stub_{uuid.uuid4().hex[:24]}",
            "client_secret": f"pi_stub_secret_{uuid.uuid4().hex[:12]}",
            "status": "requires_capture",
            "amount": amount_cents,
        }
    s = _stripe()
    return s.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        capture_method="manual",
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        application_fee_amount=fee_cents,
        transfer_data={"destination": destination_account_id},
        metadata=metadata,
    )


def _cancel_payment_intent(pi_id: str) -> None:
    if not settings.STRIPE_SECRET_KEY or pi_id.startswith("pi_stub_"):
        return
    s = _stripe()
    try:
        s.PaymentIntent.cancel(pi_id)
    except stripe.error.InvalidRequestError as exc:
        logger.info("cancel PI %s: %s", pi_id, exc)


def _capture_payment_intent(pi_id: str) -> dict:
    if not settings.STRIPE_SECRET_KEY or pi_id.startswith("pi_stub_"):
        return {"id": pi_id, "status": "succeeded"}
    s = _stripe()
    return s.PaymentIntent.capture(pi_id)


def hold_days() -> int:
    return int(getattr(settings, "ESCROW_HOLD_DAYS", 7))


@transaction.atomic
def create_escrow_for_subjob(sub_job: SubJob, *, amount: Decimal) -> Escrow:
    """Authorize a manual-capture hold for an open/funded sub-job."""
    if Escrow.objects.filter(sub_job=sub_job).exclude(
        status__in=[Escrow.Status.DETACHED, Escrow.Status.EXPIRED, Escrow.Status.CANCELED]
    ).exists():
        raise DRFValidationError({"detail": "Sub-job already has an active escrow."})

    contractor = resolve_destination_contractor(sub_job)
    fee = platform_fee_amount(amount)
    pi = _create_payment_intent(
        amount=amount,
        fee=fee,
        destination_account_id=contractor.stripe_connect_account_id,
        metadata={
            "sub_job_id": str(sub_job.id),
            "project_id": str(sub_job.project_id),
            "contractor_id": str(contractor.id),
        },
    )
    now = timezone.now()
    pi_status = pi.get("status") if isinstance(pi, dict) else getattr(pi, "status", "")
    escrow_status = (
        Escrow.Status.REQUIRES_CAPTURE
        if pi_status in ("requires_capture", "succeeded")
        else Escrow.Status.REQUIRES_CONFIRMATION
    )
    return Escrow.objects.create(
        sub_job=sub_job,
        destination_contractor=contractor,
        stripe_payment_intent_id=pi["id"] if isinstance(pi, dict) else pi.id,
        client_secret=(pi.get("client_secret") if isinstance(pi, dict) else getattr(pi, "client_secret", ""))
        or "",
        amount=amount,
        platform_fee_amount=fee,
        status=escrow_status,
        authorized_at=now if escrow_status == Escrow.Status.REQUIRES_CAPTURE else None,
        expires_at=now + timedelta(days=hold_days())
        if escrow_status == Escrow.Status.REQUIRES_CAPTURE
        else None,
    )


@transaction.atomic
def capture_escrow(escrow: Escrow) -> Escrow:
    locked = Escrow.objects.select_for_update().get(pk=escrow.pk)
    if locked.status == Escrow.Status.CAPTURED:
        return locked
    if locked.status != Escrow.Status.REQUIRES_CAPTURE:
        raise DRFValidationError(
            {"detail": f"Escrow cannot be captured from status {locked.status}."}
        )
    _capture_payment_intent(locked.stripe_payment_intent_id)
    locked.status = Escrow.Status.CAPTURED
    locked.captured_at = timezone.now()
    locked.save(update_fields=["status", "captured_at", "updated_at"])
    return locked


def freeze_project(project: Project, *, reason: str) -> Project:
    project.frozen = True
    project.frozen_reason = reason
    project.save(update_fields=["frozen", "frozen_reason", "updated_at"])
    return project


def maybe_unfreeze_project(project: Project) -> Project:
    project.refresh_from_db()
    if not project.frozen:
        return project
    if Escrow.objects.filter(sub_job__project=project, status=Escrow.Status.EXPIRED).exists():
        return project
    project.frozen = False
    project.frozen_reason = ""
    project.save(update_fields=["frozen", "frozen_reason", "updated_at"])
    return project


@transaction.atomic
def mark_escrow_expired(escrow: Escrow, *, reason: str = "Escrow authorization hold expired") -> Escrow:
    locked = Escrow.objects.select_for_update().select_related("sub_job__project").get(pk=escrow.pk)
    if locked.status in (
        Escrow.Status.CAPTURED,
        Escrow.Status.EXPIRED,
        Escrow.Status.DETACHED,
        Escrow.Status.CANCELED,
    ):
        return locked
    if locked.stripe_payment_intent_id:
        _cancel_payment_intent(locked.stripe_payment_intent_id)
    now = timezone.now()
    locked.status = Escrow.Status.EXPIRED
    locked.expired_at = now
    locked.detached_at = now
    locked.save(update_fields=["status", "expired_at", "detached_at", "updated_at"])
    freeze_project(locked.sub_job.project, reason=reason)
    return locked


@transaction.atomic
def detach_escrow(escrow: Escrow) -> Escrow:
    """Client-initiated detach: only open sub-job with no submissions, or past expiry."""
    locked = Escrow.objects.select_for_update().select_related("sub_job").get(pk=escrow.pk)
    sub = locked.sub_job
    if locked.status in (Escrow.Status.DETACHED, Escrow.Status.EXPIRED, Escrow.Status.CANCELED):
        return locked
    if locked.status == Escrow.Status.CAPTURED:
        raise DRFValidationError({"detail": "Captured escrow cannot be detached."})

    has_submission = sub.submissions.exists()
    past_expiry = locked.expires_at and timezone.now() >= locked.expires_at
    if has_submission and not past_expiry:
        raise DRFValidationError(
            {"detail": "Escrow can only be detached when open with no submission, or past hold expiry."}
        )
    if sub.status not in (SubJob.Status.OPEN, SubJob.Status.PENDING_REVIEW) and not past_expiry:
        raise DRFValidationError({"detail": "Escrow detach is not allowed in this sub-job state."})

    _cancel_payment_intent(locked.stripe_payment_intent_id)
    now = timezone.now()
    if past_expiry:
        locked.status = Escrow.Status.EXPIRED
        locked.expired_at = now
        locked.detached_at = now
        locked.save(update_fields=["status", "expired_at", "detached_at", "updated_at"])
        freeze_project(sub.project, reason="Escrow hold expired and was detached")
    else:
        locked.status = Escrow.Status.DETACHED
        locked.detached_at = now
        locked.save(update_fields=["status", "detached_at", "updated_at"])
    return locked


@transaction.atomic
def reauthorize_escrow(sub_job: SubJob) -> Escrow:
    """Client actively re-authorizes a fresh PaymentIntent after expiry (no silent re-charge)."""
    locked = SubJob.objects.select_for_update().select_related("project").get(pk=sub_job.pk)
    if locked.amount is None or locked.amount <= 0:
        raise DRFValidationError({"amount": "Sub-job amount is required to re-authorize."})

    existing = Escrow.objects.filter(sub_job=locked).order_by("-id").first()
    if existing and existing.status == Escrow.Status.REQUIRES_CAPTURE:
        raise DRFValidationError({"detail": "Escrow is already authorized."})
    if existing and existing.status == Escrow.Status.CAPTURED:
        raise DRFValidationError({"detail": "Escrow already captured."})

    # Detach/cancel any prior record identity by creating a replacement row:
    # keep history: mark old expired/detached stay; create new escrow row requires OneToOne —
    # so reuse the same Escrow row and replace the PaymentIntent.
    if existing is None:
        escrow = create_escrow_for_subjob(locked, amount=locked.amount)
    else:
        contractor = resolve_destination_contractor(locked)
        fee = platform_fee_amount(locked.amount)
        if existing.stripe_payment_intent_id and existing.status not in (
            Escrow.Status.EXPIRED,
            Escrow.Status.DETACHED,
            Escrow.Status.CANCELED,
        ):
            _cancel_payment_intent(existing.stripe_payment_intent_id)
        pi = _create_payment_intent(
            amount=locked.amount,
            fee=fee,
            destination_account_id=contractor.stripe_connect_account_id,
            metadata={
                "sub_job_id": str(locked.id),
                "project_id": str(locked.project_id),
                "contractor_id": str(contractor.id),
                "reauth": "1",
            },
        )
        now = timezone.now()
        existing.destination_contractor = contractor
        existing.stripe_payment_intent_id = pi["id"] if isinstance(pi, dict) else pi.id
        existing.client_secret = (
            pi.get("client_secret") if isinstance(pi, dict) else getattr(pi, "client_secret", "")
        ) or ""
        existing.amount = locked.amount
        existing.platform_fee_amount = fee
        existing.status = Escrow.Status.REQUIRES_CAPTURE
        existing.authorized_at = now
        existing.expires_at = now + timedelta(days=hold_days())
        existing.expired_at = None
        existing.detached_at = None
        existing.captured_at = None
        existing.save()
        escrow = existing

    maybe_unfreeze_project(locked.project)
    return escrow


def process_expired_holds() -> int:
    """Detach holds past expires_at and freeze their projects. Returns count processed."""
    now = timezone.now()
    qs = Escrow.objects.filter(
        status=Escrow.Status.REQUIRES_CAPTURE,
        expires_at__lte=now,
    ).select_related("sub_job__project")
    count = 0
    for escrow in qs:
        mark_escrow_expired(escrow)
        count += 1
    return count


def apply_payment_intent_event(pi: dict) -> Escrow | None:
    """Map Stripe PaymentIntent webhook object onto Escrow by stored id."""
    pi_id = pi.get("id") if isinstance(pi, dict) else None
    if not pi_id:
        return None
    try:
        escrow = Escrow.objects.select_related("sub_job__project").get(
            stripe_payment_intent_id=pi_id
        )
    except Escrow.DoesNotExist:
        logger.info("PaymentIntent event for unknown PI %s", pi_id)
        return None

    status_value = pi.get("status", "")
    if status_value == "requires_capture" and escrow.status == Escrow.Status.REQUIRES_CONFIRMATION:
        now = timezone.now()
        escrow.status = Escrow.Status.REQUIRES_CAPTURE
        escrow.authorized_at = now
        escrow.expires_at = now + timedelta(days=hold_days())
        escrow.save(update_fields=["status", "authorized_at", "expires_at", "updated_at"])
        return escrow
    if status_value in ("canceled", "cancelled"):
        return mark_escrow_expired(escrow, reason="PaymentIntent canceled / hold released")
    if status_value == "succeeded" and escrow.status != Escrow.Status.CAPTURED:
        escrow.status = Escrow.Status.CAPTURED
        escrow.captured_at = timezone.now()
        escrow.save(update_fields=["status", "captured_at", "updated_at"])
        return escrow
    return escrow
