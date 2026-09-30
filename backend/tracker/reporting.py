"""Client reporting aggregates (SPEC2 phase 6). Read-only."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from .models import Escrow, Project, SubJob


def client_report(owner) -> dict:
    projects = Project.objects.filter(owner=owner)
    by_status = {
        row["status"]: row["c"]
        for row in projects.values("status").annotate(c=Count("id")).order_by("status")
    }
    # Ensure all known statuses appear (zero-filled)
    for status, _label in Project.Status.choices:
        by_status.setdefault(status, 0)

    frozen_count = projects.filter(frozen=True).count()
    sub_jobs_awaiting_approval = SubJob.objects.filter(
        project__owner=owner,
        status=SubJob.Status.PENDING_APPROVAL,
    ).count()

    held = Escrow.objects.filter(
        sub_job__project__owner=owner,
        status=Escrow.Status.REQUIRES_CAPTURE,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    expired_or_detached = Escrow.objects.filter(
        sub_job__project__owner=owner,
        status__in=[Escrow.Status.EXPIRED, Escrow.Status.DETACHED],
    ).count()

    fees = Escrow.objects.filter(
        sub_job__project__owner=owner,
        status=Escrow.Status.CAPTURED,
    ).aggregate(total=Sum("platform_fee_amount"))["total"] or Decimal("0.00")

    return {
        "projects_by_status": by_status,
        "active_projects": projects.exclude(status=Project.Status.COMPLETE).count(),
        "sub_jobs_awaiting_approval": sub_jobs_awaiting_approval,
        "frozen_projects": frozen_count,
        "escrow_held_total": str(held),
        "escrow_expired_or_detached": expired_or_detached,
        "platform_fees_captured_total": str(fees),
    }
