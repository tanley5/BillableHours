from datetime import date
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from tracker.models import Assignment, Job, Project, User, Visit
from tracker import services


def make_image_file(name="shot.jpg", size=(200, 150), color="blue"):
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class TrackerAPITestCase(TestCase):
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
            scope="Fix bathtub and related damage",
            budget=Decimal("2500.00"),
        )
        assign_resp = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {
                "name": "Alex Contractor",
                "phone": "555-0100",
                "hourly_rate": "75.00",
            },
            format="json",
        )
        self.assertEqual(assign_resp.status_code, status.HTTP_201_CREATED)
        self.assignment = Assignment.objects.get(pk=assign_resp.data["id"])
        self.token = self.assignment.token
        self.c_api = APIClient()

    def c_url(self, path=""):
        return f"/api/c/{self.token}/{path.lstrip('/')}" if path else f"/api/c/{self.token}/"


class AuthAndScopingTests(TrackerAPITestCase):
    def test_client_login_and_me(self):
        anon = APIClient()
        resp = anon.post(
            "/api/auth/login/",
            {"email": "owner@example.com", "password": "test-pass-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        me = anon.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "owner@example.com")

    def test_token_scoped_to_assignment(self):
        other = Project.objects.create(owner=self.client_user, name="Other", scope="x")
        other_assign = self.api.post(
            f"/api/projects/{other.id}/assignments/",
            {"name": "Other Guy", "email": "o@ex.com", "hourly_rate": "50"},
            format="json",
        ).data

        job = self.c_api.post(self.c_url("jobs/"), {"label": "Bathtub"}, format="json")
        self.assertEqual(job.status_code, status.HTTP_201_CREATED)

        other_client = APIClient()
        detail = other_client.patch(
            f"/api/c/{other_assign['token']}/jobs/{job.data['id']}/",
            {"label": "Hacked"},
            format="json",
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        summary = other_client.get(f"/api/c/{other_assign['token']}/")
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data["project"]["name"], "Other")
        self.assertEqual(len(summary.data["open_jobs"]), 0)

    def test_contractor_summary_hides_budget_and_other_contractors(self):
        self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"name": "Second", "email": "s@ex.com", "hourly_rate": "90"},
            format="json",
        )
        summary = self.c_api.get(self.c_url())
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertNotIn("budget", summary.data["project"])
        self.assertEqual(summary.data["contractor"]["name"], "Alex Contractor")
        body = str(summary.data)
        self.assertNotIn("Second", body)
        self.assertNotIn("2500", body)

    def test_revoked_token_returns_403(self):
        revoke = self.api.post(f"/api/assignments/{self.assignment.id}/revoke/")
        self.assertEqual(revoke.status_code, status.HTTP_200_OK)
        resp = self.c_api.get(self.c_url())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class VisitRulesTests(TrackerAPITestCase):
    def test_hours_cap_at_16(self):
        ok = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "16.00", "notes": "full day"},
            format="json",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

        bad = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-02", "hours": "16.01", "notes": "too much"},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_append_only_while_pending(self):
        visit = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "3.5", "notes": "demo"},
            format="json",
        ).data
        patch = self.c_api.patch(
            self.c_url(f"visits/{visit['id']}/"),
            {"hours": "4.0"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(patch.data["hours"]), Decimal("4.00"))

        self.api.post(f"/api/visits/{visit['id']}/approve/")
        locked = self.c_api.patch(
            self.c_url(f"visits/{visit['id']}/"),
            {"hours": "5.0"},
            format="json",
        )
        self.assertEqual(locked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("approved", locked.data["detail"].lower())


class JobCompletionTests(TrackerAPITestCase):
    def test_completion_requires_before_and_after(self):
        job = self.c_api.post(self.c_url("jobs/"), {"label": "Bathtub"}, format="json").data
        self.assertEqual(job["status"], "open")

        bad = self.c_api.post(
            self.c_url(f"jobs/{job['id']}/photos/"),
            {"kind": "after", "file": make_image_file(), "location_missing": True},
            format="multipart",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        before = self.c_api.post(
            self.c_url(f"jobs/{job['id']}/photos/"),
            {"kind": "before", "file": make_image_file("before.jpg"), "location_missing": True},
            format="multipart",
        )
        self.assertEqual(before.status_code, status.HTTP_201_CREATED)
        self.assertTrue(before.data["location_missing"])

        job_still_open = Job.objects.get(pk=job["id"])
        self.assertEqual(job_still_open.status, Job.Status.OPEN)

        after = self.c_api.post(
            self.c_url(f"jobs/{job['id']}/photos/"),
            {
                "kind": "after",
                "file": make_image_file("after.jpg", color="red"),
                "latitude": "40.712800",
                "longitude": "-74.006000",
                "location_missing": False,
            },
            format="multipart",
        )
        self.assertEqual(after.status_code, status.HTTP_201_CREATED)
        job_done = Job.objects.get(pk=job["id"])
        self.assertEqual(job_done.status, Job.Status.COMPLETE)

    def test_found_issue_parent(self):
        parent = self.c_api.post(self.c_url("jobs/"), {"label": "Bathtub"}, format="json").data
        child = self.c_api.post(
            self.c_url("jobs/"),
            {"label": "Broken pipe", "parent": parent["id"], "notes": "leaking"},
            format="json",
        )
        self.assertEqual(child.status_code, status.HTTP_201_CREATED)
        self.assertEqual(child.data["parent"], parent["id"])
        self.assertTrue(child.data["is_found_issue"])


class ApprovalWinsRaceTests(TrackerAPITestCase):
    def test_approval_wins_over_concurrent_edit(self):
        visit = Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 1),
            hours=Decimal("2.00"),
            notes="race",
        )

        services.approve_visit(visit)
        with self.assertRaises(services.LockConflict):
            services.update_visit_if_pending(visit, hours=Decimal("9.00"))

        job = Job.objects.create(assignment=self.assignment, label="Race job")
        job.status = Job.Status.COMPLETE
        job.save(update_fields=["status"])
        services.approve_job(job)
        with self.assertRaises(services.LockConflict):
            services.update_job_if_open(job, label="Nope")

    def test_api_edit_after_approve_returns_clear_message(self):
        visit = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "2", "notes": ""},
            format="json",
        ).data
        self.api.post(f"/api/visits/{visit['id']}/approve/")
        resp = self.c_api.patch(
            self.c_url(f"visits/{visit['id']}/"),
            {"notes": "late edit"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("approved", str(resp.data).lower())


class DisputeResubmitTests(TrackerAPITestCase):
    def test_dispute_and_resubmit_visit(self):
        visit = self.c_api.post(
            self.c_url("visits/"),
            {"date": "2026-09-01", "hours": "2", "notes": "original"},
            format="json",
        ).data
        dispute = self.api.post(
            f"/api/visits/{visit['id']}/dispute/",
            {"comment": "Hours look high"},
            format="json",
        )
        self.assertEqual(dispute.status_code, status.HTTP_200_OK)
        self.assertEqual(dispute.data["status"], "disputed")

        resubmit = self.c_api.post(
            self.c_url(f"visits/{visit['id']}/resubmit/"),
            {"hours": "1.5", "notes": "corrected"},
            format="json",
        )
        self.assertEqual(resubmit.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resubmit.data["status"], "pending")
        self.assertEqual(resubmit.data["supersedes"], visit["id"])
        original = Visit.objects.get(pk=visit["id"])
        self.assertEqual(original.status, Visit.Status.DISPUTED)


class ProjectRollupTests(TrackerAPITestCase):
    def test_project_detail_totals(self):
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 1),
            hours=Decimal("2.00"),
            status=Visit.Status.APPROVED,
        )
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 2),
            hours=Decimal("3.00"),
            status=Visit.Status.PENDING,
        )
        detail = self.api.get(f"/api/projects/{self.project.id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["totals"]["approved_hours"], "2.00")
        self.assertEqual(detail.data["totals"]["pending_hours"], "3.00")
        self.assertEqual(detail.data["totals"]["approved_cost"], "150.00")
        self.assertEqual(detail.data["totals"]["pending_cost"], "225.00")

    def test_export_csv_approved_only(self):
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 1),
            hours=Decimal("2.00"),
            status=Visit.Status.APPROVED,
        )
        Visit.objects.create(
            assignment=self.assignment,
            date=date(2026, 9, 2),
            hours=Decimal("3.00"),
            status=Visit.Status.PENDING,
        )
        job = Job.objects.create(
            assignment=self.assignment, label="Done", status=Job.Status.APPROVED
        )
        Job.objects.create(assignment=self.assignment, label="Open", status=Job.Status.OPEN)

        resp = self.api.get(f"/api/projects/{self.project.id}/export.csv")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content = resp.content.decode()
        self.assertIn("Done", content)
        self.assertNotIn("Open", content)
        self.assertIn("2.00", content)
        self.assertNotIn("3.00", content)
        self.assertIn(str(job.id), content)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class InvalidTokenTests(TestCase):
    def test_bogus_token_rejected(self):
        api = APIClient()
        resp = api.get("/api/c/not-a-real-token/")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
