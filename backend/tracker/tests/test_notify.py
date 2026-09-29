from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from tracker.models import Assignment, Job, Project, User, Visit
from tracker.notify import EVENT_FOUND_ISSUE, EVENT_JOB_CREATED, EVENT_RESUBMIT, EVENT_VISIT_CREATED, notify


class NotifyServiceTests(TestCase):
    @override_settings(N8N_WEBHOOK_URL="")
    def test_noop_when_webhook_unset(self):
        with patch("tracker.notify.urlopen") as urlopen:
            notify(EVENT_VISIT_CREATED, {"id": 1})
            urlopen.assert_not_called()

    @override_settings(N8N_WEBHOOK_URL="http://n8n:5678/webhook/billable-events")
    def test_posts_json_event_payload(self):
        with patch("tracker.notify.urlopen") as urlopen:
            notify(
                EVENT_FOUND_ISSUE,
                {
                    "project_id": 3,
                    "project_name": "Bathtub repair",
                    "job_id": 2,
                    "label": "Broken pipe",
                },
            )
            urlopen.assert_called_once()
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "http://n8n:5678/webhook/billable-events")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.get_header("Content-type"), "application/json")
            body = request.data.decode()
            self.assertIn(EVENT_FOUND_ISSUE, body)
            self.assertIn("Broken pipe", body)

    @override_settings(N8N_WEBHOOK_URL="http://n8n:5678/webhook/billable-events")
    def test_swallows_delivery_errors(self):
        with patch("tracker.notify.urlopen", side_effect=OSError("n8n down")):
            # Must not raise — contractor/client requests still succeed
            notify(EVENT_JOB_CREATED, {"id": 1})


@override_settings(N8N_WEBHOOK_URL="http://n8n:5678/webhook/billable-events")
class NotifyIntegrationTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
            role=User.Role.CLIENT,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.client_user)
        self.project = Project.objects.create(
            owner=self.client_user,
            name="Bathtub repair",
            scope="Fix bathtub",
        )
        assign = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"name": "Alex", "phone": "555", "hourly_rate": "75"},
            format="json",
        )
        self.assignment = Assignment.objects.get(pk=assign.data["id"])
        self.token = self.assignment.token
        self.c_api = APIClient()

    def c_url(self, path=""):
        return f"/api/c/{self.token}/{path.lstrip('/')}" if path else f"/api/c/{self.token}/"

    @patch("tracker.notify.urlopen")
    def test_creating_job_notifies_job_created(self, urlopen):
        resp = self.c_api.post(self.c_url("jobs/"), {"label": "Bathtub"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        urlopen.assert_called()
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_JOB_CREATED, body)
        self.assertIn("Bathtub", body)

    @patch("tracker.notify.urlopen")
    def test_found_issue_notifies_found_issue_event(self, urlopen):
        parent = self.c_api.post(self.c_url("jobs/"), {"label": "Bathtub"}, format="json").data
        urlopen.reset_mock()
        child = self.c_api.post(
            self.c_url("jobs/"),
            {"label": "Mold", "parent": parent["id"]},
            format="json",
        )
        self.assertEqual(child.status_code, status.HTTP_201_CREATED)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_FOUND_ISSUE, body)
        self.assertIn("Mold", body)

    @patch("tracker.notify.urlopen")
    def test_logging_visit_notifies_visit_created(self, urlopen):
        resp = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "2.5", "notes": "demo"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_VISIT_CREATED, body)
        self.assertIn("2.5", body)

    @patch("tracker.notify.urlopen")
    def test_resubmit_notifies_resubmit_event(self, urlopen):
        visit = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "2", "notes": "original"},
            format="json",
        ).data
        self.api.post(
            f"/api/visits/{visit['id']}/dispute/",
            {"comment": "Too high"},
            format="json",
        )
        urlopen.reset_mock()
        resubmit = self.c_api.post(
            self.c_url(f"visits/{visit['id']}/resubmit/"),
            {"hours": "1.5", "notes": "corrected"},
            format="json",
        )
        self.assertEqual(resubmit.status_code, status.HTTP_201_CREATED)
        body = urlopen.call_args.args[0].data.decode()
        self.assertIn(EVENT_RESUBMIT, body)
        self.assertIn("visit", body)


class ExportCsvPhase4Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="x",
            role=User.Role.CLIENT,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.project = Project.objects.create(owner=self.user, name="Export me", scope="s")
        assign = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"name": "Alex", "email": "a@ex.com", "hourly_rate": "50"},
            format="json",
        ).data
        self.assignment = Assignment.objects.get(pk=assign["id"])

    def test_export_includes_header_and_approved_rows_only(self):
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 1),
            hours=Decimal("4.00"),
            status=Visit.Status.APPROVED,
            notes="billable",
        )
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 2),
            hours=Decimal("1.00"),
            status=Visit.Status.PENDING,
        )
        Job.objects.create(
            assignment=self.assignment,
            label="Done job",
            status=Job.Status.APPROVED,
        )

        resp = self.api.get(f"/api/projects/{self.project.id}/export.csv")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "text/csv")
        text = resp.content.decode()
        self.assertIn("type,id,label_or_date,hours,status,notes,client_comment,contractor", text)
        self.assertIn("Done job", text)
        self.assertIn("4.00", text)
        self.assertIn("billable", text)
        self.assertNotIn("1.00", text)
        self.assertIn("Alex", text)
