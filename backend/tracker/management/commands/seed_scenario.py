from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image

from tracker.models import Assignment, Contractor, Job, Photo, Project, User, Visit

PROJECT_NAME = "Bathtub repair"
CLIENT_EMAIL = "owner@example.com"
CLIENT_PASSWORD = "changeme123"


def _jpeg_content(color: str, name: str) -> ContentFile:
    buffer = BytesIO()
    Image.new("RGB", (640, 480), color=color).save(buffer, format="JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name=name)


def _add_photo(job: Job, kind: str, color: str, captured_at=None) -> Photo:
    photo = Photo(
        job=job,
        kind=kind,
        captured_at=captured_at or timezone.now(),
        location_missing=True,
    )
    photo.file.save(f"{job.id}-{kind}-{color}.jpg", _jpeg_content(color, f"{kind}.jpg"), save=True)
    return photo


class Command(BaseCommand):
    help = "Load the SPEC bathtub repair demo scenario (Phase 5)."

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
            self.stdout.write(self.style.WARNING(f"Scenario already present (project id={existing.id}). Use --reset to recreate."))
            return

        if existing and options["reset"]:
            existing.delete()

        project = Project.objects.create(
            owner=user,
            name=PROJECT_NAME,
            scope="Repair the master bathroom bathtub and address related water damage.",
            budget=Decimal("2500.00"),
        )
        contractor = Contractor.objects.create(
            name="Alex Contractor",
            phone="555-0100",
            email="alex@example.com",
        )
        assignment = Assignment.objects.create(
            project=project,
            contractor=contractor,
            hourly_rate=Decimal("75.00"),
        )

        bathtub = Job.objects.create(
            assignment=assignment,
            label="Bathtub",
            notes="Main bathtub replacement",
            status=Job.Status.OPEN,
        )
        _add_photo(bathtub, Photo.Kind.BEFORE, "steelblue")

        found_specs = [
            ("Broken pipe", "tomato", "coral", Job.Status.APPROVED, None),
            ("Mold", "darkolivegreen", "yellowgreen", Job.Status.DISPUTED, "After photo is too dark — please re-shoot."),
            ("Drywall crack", "sandybrown", "peru", Job.Status.COMPLETE, None),
        ]
        for label, before_color, after_color, status, comment in found_specs:
            issue = Job.objects.create(
                assignment=assignment,
                label=label,
                parent=bathtub,
                notes=f"Found while working on bathtub: {label.lower()}",
                status=Job.Status.OPEN,
            )
            _add_photo(issue, Photo.Kind.BEFORE, before_color)
            _add_photo(issue, Photo.Kind.AFTER, after_color)
            issue.status = status
            issue.client_comment = comment
            issue.save(update_fields=["status", "client_comment", "updated_at"])

        _add_photo(bathtub, Photo.Kind.AFTER, "lightskyblue")
        bathtub.status = Job.Status.COMPLETE
        bathtub.save(update_fields=["status", "updated_at"])

        today = date.today()
        Visit.objects.create(
            assignment=assignment,
            date=today - timedelta(days=5),
            hours=Decimal("3.50"),
            notes="Demo and material estimate",
            status=Visit.Status.APPROVED,
        )
        Visit.objects.create(
            assignment=assignment,
            date=today - timedelta(days=2),
            hours=Decimal("6.00"),
            notes="Removal and rough-in",
            status=Visit.Status.APPROVED,
        )
        Visit.objects.create(
            assignment=assignment,
            date=today - timedelta(days=1),
            hours=Decimal("4.25"),
            notes="Install and found-issue repairs",
            status=Visit.Status.PENDING,
        )
        Visit.objects.create(
            assignment=assignment,
            date=today,
            hours=Decimal("2.00"),
            notes="Touch-up pending client review",
            status=Visit.Status.PENDING,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded '{PROJECT_NAME}' (project id={project.id}). "
                f"Contractor link path: {assignment.link_path}"
            )
        )
