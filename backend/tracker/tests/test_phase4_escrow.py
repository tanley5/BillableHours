"""SPEC2 Phase 4: per-sub-job escrow, capture, freeze/unfreeze, re-auth."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
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
    Submission,
    User,
)
from tracker import stripe_escrow


def make_image(name="shot.jpg", color="blue"):
    buf = BytesIO()
    Image.new("RGB", (200, 150), color=color).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def client_user(email="owner@example.com"):
    return User.objects.create_user(email=email, password="pass", role=User.Role.CLIENT)


def contractor_user(
    *,
    email="alex@example.com",
    name="Alex",
    connect_status=Contractor.ConnectStatus.COMPLETE,
    stripe_id="acct_alex",
):
    user = User.objects.create_user(email=email, password="pass", role=User.Role.CONTRACTOR)
    return Contractor.objects.create(
        user=user,
        name=name,
        email=email,
        phone="555",
        connect_status=connect_status,
        stripe_connect_account_id=stripe_id,
    )


@override_settings(N8N_WEBHOOK_URL="", STRIPE_SECRET_KEY="")
class Phase4Base(TestCase):
    def setUp(self):
        self.owner = client_user()
        self.api = APIClient()
        self.api.force_authenticate(user=self.owner)
        self.project = Project.objects.create(
            owner=self.owner,
            name="Bathtub",
            scope="Fix tub",
            customer_contact="555-0000",
        )
        self.contractor = contractor_user()
        ClientContractor.objects.create(client=self.owner, contractor=self.contractor)
        self.assignment = Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )
        self.c_api = APIClient()
        self.c_api.force_authenticate(user=self.contractor.user)

    def create_funded_subjob(self, label="Fix tub", amount="400.00"):
        resp = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {
                "label": label,
                "amount": amount,
                "before_photo": make_image("before.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return SubJob.objects.get(pk=resp.data["id"])


class EscrowCreateTests(Phase4Base):
    def test_client_create_subjob_creates_authorized_escrow(self):
        sub = self.create_funded_subjob()
        escrow = Escrow.objects.get(sub_job=sub)
        self.assertEqual(escrow.status, Escrow.Status.REQUIRES_CAPTURE)
        self.assertEqual(escrow.amount, Decimal("400.00"))
        self.assertEqual(escrow.platform_fee_amount, Decimal("8.00"))  # 2%
        self.assertTrue(escrow.stripe_payment_intent_id.startswith("pi_"))
        self.assertEqual(escrow.destination_contractor_id, self.contractor.id)
        self.assertIsNotNone(escrow.expires_at)
        self.assertIn("escrow", self.api.get(f"/api/projects/{self.project.id}/sub-jobs/").data[0])

    def test_approve_contractor_subjob_creates_escrow(self):
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Found leak", "before_photo": make_image("b.jpg")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        sub_id = resp.data["id"]
        self.assertFalse(Escrow.objects.filter(sub_job_id=sub_id).exists())

        resp = self.api.post(f"/api/sub-jobs/{sub_id}/approve/", {"amount": "250.00"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow = Escrow.objects.get(sub_job_id=sub_id)
        self.assertEqual(escrow.amount, Decimal("250.00"))
        self.assertEqual(escrow.platform_fee_amount, Decimal("5.00"))
        self.assertEqual(escrow.destination_contractor_id, self.contractor.id)

    def test_deny_never_creates_escrow(self):
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Nope", "before_photo": make_image("b.jpg")},
            format="multipart",
        )
        sub_id = resp.data["id"]
        self.api.post(f"/api/sub-jobs/{sub_id}/deny/", {"reason": "out of scope"}, format="json")
        self.assertFalse(Escrow.objects.filter(sub_job_id=sub_id).exists())

    def test_cannot_fund_without_connect_complete_destination(self):
        self.contractor.connect_status = Contractor.ConnectStatus.PENDING
        self.contractor.save(update_fields=["connect_status"])
        resp = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {
                "label": "Blocked",
                "amount": "100.00",
                "before_photo": make_image("before.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class EscrowCaptureTests(Phase4Base):
    def test_accept_submission_captures_escrow(self):
        sub = self.create_funded_subjob()
        sub_resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
            {
                "hours": "2.5",
                "notes": "done",
                "after_photo": make_image("after.jpg", "green"),
            },
            format="multipart",
        )
        self.assertEqual(sub_resp.status_code, status.HTTP_201_CREATED)
        submission_id = sub_resp.data["id"]

        resp = self.api.post(f"/api/submissions/{submission_id}/accept/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow = Escrow.objects.get(sub_job=sub)
        self.assertEqual(escrow.status, Escrow.Status.CAPTURED)
        self.assertIsNotNone(escrow.captured_at)

        feed = self.api.get(f"/api/projects/{self.project.id}/activity/").data
        types = [e["type"] for e in feed]
        self.assertIn("escrow.captured", types)

    def test_independent_capture_per_subjob(self):
        a = self.create_funded_subjob("A", "100.00")
        b = self.create_funded_subjob("B", "200.00")
        for sub in (a, b):
            self.c_api.post(
                f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
                {"hours": "1", "after_photo": make_image(f"a{sub.id}.jpg")},
                format="multipart",
            )
        sub_a = Submission.objects.get(sub_job=a)
        self.api.post(f"/api/submissions/{sub_a.id}/accept/", {}, format="json")
        self.assertEqual(Escrow.objects.get(sub_job=a).status, Escrow.Status.CAPTURED)
        self.assertEqual(Escrow.objects.get(sub_job=b).status, Escrow.Status.REQUIRES_CAPTURE)


class EscrowFreezeTests(Phase4Base):
    def test_expiry_detaches_and_freezes_project(self):
        sub = self.create_funded_subjob()
        escrow = Escrow.objects.get(sub_job=sub)
        escrow.expires_at = timezone.now() - timedelta(hours=1)
        escrow.save(update_fields=["expires_at"])

        stripe_escrow.process_expired_holds()
        escrow.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(escrow.status, Escrow.Status.EXPIRED)
        self.assertTrue(self.project.frozen)
        self.assertIn("escrow", self.project.frozen_reason.lower())

        # Frozen blocks new sub-jobs
        resp = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {
                "label": "More",
                "amount": "50.00",
                "before_photo": make_image("x.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reauthorize_unfreezes_when_all_resolved(self):
        sub = self.create_funded_subjob()
        escrow = Escrow.objects.get(sub_job=sub)
        escrow.expires_at = timezone.now() - timedelta(hours=1)
        escrow.save(update_fields=["expires_at"])
        stripe_escrow.process_expired_holds()
        self.project.refresh_from_db()
        self.assertTrue(self.project.frozen)

        resp = self.api.post(f"/api/sub-jobs/{sub.id}/escrow/reauthorize/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow = Escrow.objects.get(sub_job=sub)
        self.assertEqual(escrow.status, Escrow.Status.REQUIRES_CAPTURE)
        self.project.refresh_from_db()
        self.assertFalse(self.project.frozen)
        self.assertEqual(self.project.frozen_reason, "")

    def test_detach_open_unused_escrow_without_freeze(self):
        sub = self.create_funded_subjob()
        resp = self.api.post(f"/api/sub-jobs/{sub.id}/escrow/detach/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow = Escrow.objects.get(sub_job=sub)
        self.assertEqual(escrow.status, Escrow.Status.DETACHED)
        self.project.refresh_from_db()
        self.assertFalse(self.project.frozen)

    def test_cannot_detach_after_submission(self):
        sub = self.create_funded_subjob()
        self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
            {"hours": "1", "after_photo": make_image("a.jpg")},
            format="multipart",
        )
        resp = self.api.post(f"/api/sub-jobs/{sub.id}/escrow/detach/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class EscrowIsolationTests(Phase4Base):
    def test_other_client_escrow_endpoints_404(self):
        sub = self.create_funded_subjob()
        other = client_user("other@example.com")
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        self.assertEqual(
            other_api.post(f"/api/sub-jobs/{sub.id}/escrow/reauthorize/", {}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            other_api.post(f"/api/sub-jobs/{sub.id}/escrow/detach/", {}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )


@override_settings(N8N_WEBHOOK_URL="", STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_test")
class EscrowStripeApiTests(Phase4Base):
    @patch("tracker.stripe_escrow.stripe.PaymentIntent")
    def test_real_create_calls_stripe_with_fee_and_destination(self, mock_pi):
        mock_pi.create.return_value = {
            "id": "pi_live_1",
            "client_secret": "pi_live_1_secret",
            "status": "requires_capture",
            "amount": 40000,
        }
        sub = self.create_funded_subjob()
        mock_pi.create.assert_called_once()
        kwargs = mock_pi.create.call_args.kwargs
        self.assertEqual(kwargs["amount"], 40000)
        self.assertEqual(kwargs["capture_method"], "manual")
        self.assertEqual(kwargs["application_fee_amount"], 800)
        self.assertEqual(kwargs["transfer_data"]["destination"], "acct_alex")
        escrow = Escrow.objects.get(sub_job=sub)
        self.assertEqual(escrow.stripe_payment_intent_id, "pi_live_1")

    @patch("tracker.stripe_escrow.stripe.PaymentIntent")
    def test_capture_calls_stripe(self, mock_pi):
        mock_pi.create.return_value = {
            "id": "pi_cap_1",
            "client_secret": "sec",
            "status": "requires_capture",
            "amount": 40000,
        }
        mock_pi.capture.return_value = {"id": "pi_cap_1", "status": "succeeded"}
        sub = self.create_funded_subjob()
        self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
            {"hours": "1", "after_photo": make_image("a.jpg")},
            format="multipart",
        )
        submission = Submission.objects.get(sub_job=sub)
        self.api.post(f"/api/submissions/{submission.id}/accept/", {}, format="json")
        mock_pi.capture.assert_called_once_with("pi_cap_1")

    @patch("tracker.stripe_connect.stripe.Webhook.construct_event")
    def test_webhook_canceled_expires_and_freezes(self, mock_construct):
        with override_settings(STRIPE_SECRET_KEY=""):
            sub = self.create_funded_subjob()
        escrow = Escrow.objects.get(sub_job=sub)
        event = MagicMock()
        event.type = "payment_intent.canceled"
        event.data.object = {
            "id": escrow.stripe_payment_intent_id,
            "status": "canceled",
        }
        mock_construct.return_value = event
        resp = self.client.post(
            "/api/stripe/webhook/",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(escrow.status, Escrow.Status.EXPIRED)
        self.assertTrue(self.project.frozen)


class PlatformFeeHelperTests(TestCase):
    def test_fee_rounds_half_up_to_cents(self):
        self.assertEqual(stripe_escrow.platform_fee_amount(Decimal("100.00")), Decimal("2.00"))
        self.assertEqual(stripe_escrow.platform_fee_amount(Decimal("10.00")), Decimal("0.20"))
        self.assertEqual(stripe_escrow.platform_fee_amount(Decimal("1.00")), Decimal("0.02"))
