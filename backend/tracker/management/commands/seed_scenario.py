"""Load the SPEC2 bathtub demo: sibling SubJobs + Connect-ready contractor."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import stripe
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image

from tracker.models import (
    Assignment,
    ClientContractor,
    Contractor,
    Project,
    User,
)
from tracker.subjobs import create_client_subjob, create_contractor_subjob

PROJECT_NAME = "Bathtub repair"
CLIENT_EMAIL = "owner@example.com"
CLIENT_PASSWORD = "changeme123"
CONTRACTOR_EMAIL = "alex@example.com"
CONTRACTOR_PASSWORD = "contractor123"

# Offline / empty-key demos when stripe-sim is not contacted
OFFLINE_CONNECT_ACCOUNT_ID = "acct_seed_alex"


def _jpeg_content(color: str, name: str) -> ContentFile:
    buffer = BytesIO()
    Image.new("RGB", (640, 480), color=color).save(buffer, format="JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name=name)


def _ensure_stripe_connect_account(*, email: str) -> str:
    """
    Register a Connect Express account with stripe-sim (or live) when configured.
    Falls back to a stable offline id for unit tests / empty Stripe settings.
    """
    api_base = getattr(settings, "STRIPE_API_BASE", "") or ""
    secret = settings.STRIPE_SECRET_KEY or ""
    if not api_base or not secret:
        return OFFLINE_CONNECT_ACCOUNT_ID

    stripe.api_key = secret
    stripe.api_base = api_base
    account = stripe.Account.create(
        type="express",
        email=email,
        capabilities={"transfers": {"requested": True}},
        metadata={"seed": "bathtub"},
    )
    return account["id"]


class Command(BaseCommand):
    help = "Load the SPEC2 bathtub repair demo (sibling SubJobs + Connect contractor)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete an existing Bathtub repair project and recreate it.",
        )
        parser.add_argument("--email", default=CLIENT_EMAIL)
        parser.add_argument("--password", default=CLIENT_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": User.Role.CLIENT},
        )
        user.role = User.Role.CLIENT
        user.set_password(password)
        user.save()
        if created:
            self.stdout.write(f"Created client {email}")

        existing = Project.objects.filter(owner=user, name=PROJECT_NAME).first()
        if existing and not options["reset"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Scenario already present (project id={existing.id}). Use --reset to recreate."
                )
            )
            return

        if existing and options["reset"]:
            existing.delete()

        project = Project.objects.create(
            owner=user,
            name=PROJECT_NAME,
            scope="Repair the master bathroom bathtub and address related water damage.",
            budget=Decimal("2500.00"),
            customer_contact="homeowner@example.com",
            status=Project.Status.CONTRACTOR_ASSIGNED,
        )

        c_user, _ = User.objects.get_or_create(
            email=CONTRACTOR_EMAIL,
            defaults={"role": User.Role.CONTRACTOR},
        )
        c_user.role = User.Role.CONTRACTOR
        c_user.set_password(CONTRACTOR_PASSWORD)
        c_user.save()

        connect_account_id = _ensure_stripe_connect_account(email=CONTRACTOR_EMAIL)

        contractor, _ = Contractor.objects.update_or_create(
            email=CONTRACTOR_EMAIL,
            defaults={
                "user": c_user,
                "name": "Alex Contractor",
                "phone": "555-0100",
                "connect_status": Contractor.ConnectStatus.COMPLETE,
                "stripe_connect_account_id": connect_account_id,
                "archived": False,
            },
        )
        ClientContractor.objects.get_or_create(client=user, contractor=contractor)

        Assignment.objects.create(
            project=project,
            contractor=contractor,
            hourly_rate=Decimal("75.00"),
            status=Assignment.Status.ACCEPTED,
            responded_at=timezone.now(),
        )

        # Sibling SubJobs (SPEC2) — no Job parent/child tree
        client_siblings = [
            ("Fix bathtub", Decimal("800.00"), "steelblue"),
            ("Fix broken pipe", Decimal("400.00"), "tomato"),
            ("Fix mold", Decimal("350.00"), "darkolivegreen"),
        ]
        for label, amount, color in client_siblings:
            create_client_subjob(
                project=project,
                label=label,
                amount=amount,
                before_file=_jpeg_content(color, f"{label}.jpg"),
            )

        create_contractor_subjob(
            project=project,
            contractor=contractor,
            label="Fix drywall",
            before_file=_jpeg_content("sandybrown", "drywall.jpg"),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded '{PROJECT_NAME}' (project id={project.id}) with sibling SubJobs. "
                f"Client: {email} / {password}. "
                f"Contractor: {CONTRACTOR_EMAIL} / {CONTRACTOR_PASSWORD} "
                f"(Connect {connect_account_id})."
            )
        )
