"""SPEC2 Phase 6: client reporting dashboard."""
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from tracker.models import (
    Assignment,
    ClientContractor,
    Contractor,
    Escrow,
    Project,
    SubJob,
    User,
)
from tracker.reporting import client_report


def make_image(name="shot.jpg"):
    buf = BytesIO()
    Image.new("RGB", (100, 80), color="navy").save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(N8N_WEBHOOK_URL="", STRIPE_SECRET_KEY="")
class ReportingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="pass", role=User.Role.CLIENT
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="pass", role=User.Role.CLIENT
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.owner)
        self.project = Project.objects.create(owner=self.owner, name="Mine", scope="s")
        Project.objects.create(owner=self.other, name="Theirs", scope="s", frozen=True)
        c_user = User.objects.create_user(
            email="alex@example.com", password="pass", role=User.Role.CONTRACTOR
        )
        self.contractor = Contractor.objects.create(
            user=c_user,
            name="Alex",
            email="alex@example.com",
            connect_status=Contractor.ConnectStatus.COMPLETE,
            stripe_connect_account_id="acct_alex",
        )
        ClientContractor.objects.create(client=self.owner, contractor=self.contractor)
        Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )

    def test_empty_report_shape(self):
        data = client_report(self.owner)
        self.assertEqual(data["frozen_projects"], 0)
        self.assertEqual(data["sub_jobs_awaiting_approval"], 0)
        self.assertEqual(data["escrow_held_total"], "0.00")
        self.assertIn("created", data["projects_by_status"])

    def test_report_endpoint_aggregates_owned_data_only(self):
        SubJob.objects.create(
            project=self.project,
            label="Pending",
            status=SubJob.Status.PENDING_APPROVAL,
            created_by=SubJob.CreatedBy.CONTRACTOR,
            created_by_contractor=self.contractor,
        )
        funded = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "Funded", "amount": "250.00", "before_photo": make_image()},
            format="multipart",
        )
        self.assertEqual(funded.status_code, status.HTTP_201_CREATED)
        self.project.frozen = True
        self.project.frozen_reason = "test"
        self.project.save(update_fields=["frozen", "frozen_reason"])

        resp = self.api.get("/api/reports/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sub_jobs_awaiting_approval"], 1)
        self.assertEqual(resp.data["frozen_projects"], 1)
        self.assertEqual(Decimal(resp.data["escrow_held_total"]), Decimal("250.00"))
        self.assertEqual(resp.data["escrow_expired_or_detached"], 0)
        self.assertEqual(Decimal(resp.data["platform_fees_captured_total"]), Decimal("0.00"))

        # Other client's frozen project not counted
        other_api = APIClient()
        other_api.force_authenticate(user=self.other)
        other = other_api.get("/api/reports/dashboard/")
        self.assertEqual(other.status_code, status.HTTP_200_OK)
        self.assertEqual(other.data["frozen_projects"], 1)
        self.assertEqual(other.data["escrow_held_total"], "0.00")
        self.assertEqual(other.data["sub_jobs_awaiting_approval"], 0)

    def test_captured_fees_sum(self):
        sub = SubJob.objects.create(
            project=self.project,
            label="Done",
            amount=Decimal("100.00"),
            status=SubJob.Status.ACCEPTED,
            created_by=SubJob.CreatedBy.CLIENT,
        )
        Escrow.objects.create(
            sub_job=sub,
            destination_contractor=self.contractor,
            stripe_payment_intent_id="pi_fee_1",
            amount=Decimal("100.00"),
            platform_fee_amount=Decimal("2.00"),
            status=Escrow.Status.CAPTURED,
        )
        resp = self.api.get("/api/reports/dashboard/")
        self.assertEqual(Decimal(resp.data["platform_fees_captured_total"]), Decimal("2.00"))

    def test_contractor_cannot_access_report(self):
        c_api = APIClient()
        c_api.force_authenticate(user=self.contractor.user)
        resp = c_api.get("/api/reports/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
