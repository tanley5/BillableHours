"""SPEC2 Phase 5: n8n notifications and reminders."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from tracker.management.commands.send_reminders import send_reminders
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
from tracker.notify import (
    EVENT_ASSIGNMENT_ACCEPTED,
    EVENT_ESCROW_NEARING_EXPIRY,
    EVENT_PROJECT_FROZEN,
    EVENT_PROJECT_UNFROZEN,
    EVENT_REMINDER_ASSIGNMENT_INVITE,
    EVENT_REMINDER_IN_ROUTE,
    EVENT_SUBJOB_PENDING_APPROVAL,
    EVENT_SUBJOB_PENDING_REVIEW,
    EVENT_SUBMISSION_RECEIVED,
)


def make_image(name="shot.jpg"):
    buf = BytesIO()
    Image.new("RGB", (120, 80), color="blue").save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(N8N_WEBHOOK_URL="http://n8n:5678/webhook/billable-events", STRIPE_SECRET_KEY="")
class Phase5NotifyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="pass", role=User.Role.CLIENT
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.owner)
        self.project = Project.objects.create(owner=self.owner, name="P", scope="s")
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
        self.assignment = Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.INVITED,
        )
        self.c_api = APIClient()
        self.c_api.force_authenticate(user=c_user)

    def _events_from(self, urlopen):
        return [c.args[0].data.decode() for c in urlopen.call_args_list]

    @patch("tracker.notify.urlopen")
    def test_accept_notifies_in_route_link(self, urlopen):
        resp = self.c_api.post(f"/api/contractor/assignments/{self.assignment.id}/accept/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        bodies = self._events_from(urlopen)
        self.assertTrue(any(EVENT_ASSIGNMENT_ACCEPTED in b for b in bodies))
        self.assertTrue(any("in_route_url" in b for b in bodies))

    @patch("tracker.notify.urlopen")
    def test_contractor_subjob_notifies_pending_approval(self, urlopen):
        self.assignment.status = Assignment.Status.ACCEPTED
        self.assignment.save(update_fields=["status"])
        urlopen.reset_mock()
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Leak", "before_photo": make_image()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        bodies = self._events_from(urlopen)
        self.assertTrue(any(EVENT_SUBJOB_PENDING_APPROVAL in b for b in bodies))

    @patch("tracker.notify.urlopen")
    def test_submission_notifies_received_and_pending_review(self, urlopen):
        self.assignment.status = Assignment.Status.ACCEPTED
        self.assignment.save(update_fields=["status"])
        sub = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "Tub", "amount": "100.00", "before_photo": make_image()},
            format="multipart",
        ).data
        urlopen.reset_mock()
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub['id']}/submissions/",
            {"hours": "1", "after_photo": make_image("a.jpg")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        bodies = "\n".join(self._events_from(urlopen))
        self.assertIn(EVENT_SUBMISSION_RECEIVED, bodies)
        self.assertIn(EVENT_SUBJOB_PENDING_REVIEW, bodies)

    @patch("tracker.notify.urlopen")
    def test_freeze_and_unfreeze_notify(self, urlopen):
        self.assignment.status = Assignment.Status.ACCEPTED
        self.assignment.save(update_fields=["status"])
        sub = SubJob.objects.get(
            pk=self.api.post(
                f"/api/projects/{self.project.id}/sub-jobs/",
                {"label": "Tub", "amount": "100.00", "before_photo": make_image()},
                format="multipart",
            ).data["id"]
        )
        escrow = Escrow.objects.get(sub_job=sub)
        escrow.expires_at = timezone.now() - timedelta(hours=1)
        escrow.save(update_fields=["expires_at"])
        urlopen.reset_mock()
        from tracker import stripe_escrow

        stripe_escrow.process_expired_holds()
        bodies = "\n".join(self._events_from(urlopen))
        self.assertIn(EVENT_PROJECT_FROZEN, bodies)

        urlopen.reset_mock()
        self.api.post(f"/api/sub-jobs/{sub.id}/escrow/reauthorize/", {}, format="json")
        bodies = "\n".join(self._events_from(urlopen))
        self.assertIn(EVENT_PROJECT_UNFROZEN, bodies)


@override_settings(N8N_WEBHOOK_URL="http://n8n:5678/webhook/billable-events", STRIPE_SECRET_KEY="")
class Phase5ReminderTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="pass", role=User.Role.CLIENT
        )
        self.project = Project.objects.create(owner=self.owner, name="P", scope="s")
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

    @patch("tracker.notify.urlopen")
    def test_stale_invite_reminder(self, urlopen):
        Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.INVITED,
            invited_at=timezone.now() - timedelta(hours=25),
        )
        counts = send_reminders()
        self.assertEqual(counts["assignment_invite"], 1)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_REMINDER_ASSIGNMENT_INVITE, body)

    @patch("tracker.notify.urlopen")
    def test_in_route_reminder(self, urlopen):
        Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.ACCEPTED,
            responded_at=timezone.now() - timedelta(hours=5),
            in_route_at=None,
        )
        counts = send_reminders()
        self.assertEqual(counts["in_route"], 1)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_REMINDER_IN_ROUTE, body)

    @patch("tracker.notify.urlopen")
    def test_escrow_nearing_expiry_reminder(self, urlopen):
        assignment = Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.ACCEPTED,
        )
        ClientContractor.objects.create(client=self.owner, contractor=self.contractor)
        api = APIClient()
        api.force_authenticate(user=self.owner)
        sub_id = api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "Tub", "amount": "100.00", "before_photo": make_image()},
            format="multipart",
        ).data["id"]
        escrow = Escrow.objects.get(sub_job_id=sub_id)
        escrow.expires_at = timezone.now() + timedelta(hours=12)
        escrow.save(update_fields=["expires_at"])
        urlopen.reset_mock()
        counts = send_reminders()
        self.assertEqual(counts["escrow_nearing_expiry"], 1)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_ESCROW_NEARING_EXPIRY, body)
        # silence unused
        self.assertEqual(assignment.status, Assignment.Status.ACCEPTED)
