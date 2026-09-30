"""SPEC2 Phase 3: SubJobs, Submissions, project status, activity feed."""
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
    Project,
    SubJob,
    Submission,
    User,
)


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


@override_settings(N8N_WEBHOOK_URL="")
class Phase3Base(TestCase):
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


class ProjectStatusFlowTests(Phase3Base):
    def test_new_project_starts_created(self):
        self.assertEqual(self.project.status, Project.Status.CREATED)

    def test_accept_moves_to_contractor_assigned(self):
        invited = Assignment.objects.create(
            project=Project.objects.create(owner=self.owner, name="P2", scope="s"),
            contractor=self.contractor,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.INVITED,
        )
        project = invited.project
        self.assertEqual(project.status, Project.Status.CREATED)
        resp = self.c_api.post(f"/api/contractor/assignments/{invited.id}/accept/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.CONTRACTOR_ASSIGNED)

    def test_confirm_in_route(self):
        resp = self.c_api.post(f"/api/contractor/assignments/{self.assignment.id}/in-route/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CONTRACTOR_IN_ROUTE)
        self.assignment.refresh_from_db()
        self.assertIsNotNone(self.assignment.in_route_at)


class SubJobFlowTests(Phase3Base):
    def test_client_creates_subjob_open_with_amount_and_before_photo(self):
        resp = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {
                "label": "Fix bathtub",
                "amount": "400.00",
                "before_photo": make_image("before.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], SubJob.Status.OPEN)
        self.assertEqual(resp.data["created_by"], SubJob.CreatedBy.CLIENT)
        self.assertEqual(Decimal(resp.data["amount"]), Decimal("400.00"))
        self.assertTrue(resp.data["before_photos"])
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.IN_PROGRESS)

    def test_client_create_requires_before_photo_and_amount(self):
        bad = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "No photo", "amount": "100"},
            format="multipart",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contractor_creates_pending_approval(self):
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {
                "label": "Fix mold",
                "before_photo": make_image("mold.jpg", color="green"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], SubJob.Status.PENDING_APPROVAL)
        self.assertIsNone(resp.data["amount"])
        self.assertEqual(resp.data["created_by"], SubJob.CreatedBy.CONTRACTOR)

    def test_client_approve_and_fund_and_deny(self):
        create = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Pipe", "before_photo": make_image()},
            format="multipart",
        )
        sub_id = create.data["id"]
        approve = self.api.post(
            f"/api/sub-jobs/{sub_id}/approve/",
            {"amount": "250.00"},
            format="json",
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(approve.data["status"], SubJob.Status.OPEN)
        self.assertEqual(Decimal(approve.data["amount"]), Decimal("250.00"))

        create2 = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Skip me", "before_photo": make_image("x.jpg", color="red")},
            format="multipart",
        )
        deny = self.api.post(
            f"/api/sub-jobs/{create2.data['id']}/deny/",
            {"reason": "Out of scope"},
            format="json",
        )
        self.assertEqual(deny.status_code, status.HTTP_200_OK)
        self.assertEqual(deny.data["status"], SubJob.Status.DENIED)
        self.assertEqual(deny.data["denial_reason"], "Out of scope")
        self.assertTrue(SubJob.objects.filter(pk=create2.data["id"]).exists())


class SubmissionFlowTests(Phase3Base):
    def _open_subjob(self):
        resp = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {
                "label": "Tub",
                "amount": "300.00",
                "before_photo": make_image("b.jpg"),
            },
            format="multipart",
        )
        return SubJob.objects.get(pk=resp.data["id"])

    def test_submit_blocked_until_open(self):
        pending = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Wait", "before_photo": make_image()},
            format="multipart",
        )
        bad = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{pending.data['id']}/submissions/",
            {
                "hours": "2.5",
                "notes": "done",
                "after_photo": make_image("a.jpg", color="red"),
            },
            format="multipart",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_accept_reject_append_only_and_project_complete(self):
        sub = self._open_subjob()
        first = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
            {
                "hours": "3.00",
                "notes": "attempt 1",
                "after_photo": make_image("a1.jpg", color="red"),
            },
            format="multipart",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["review_status"], Submission.ReviewStatus.PENDING)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubJob.Status.PENDING_REVIEW)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.READY_FOR_EVALUATION)

        reject = self.api.post(
            f"/api/submissions/{first.data['id']}/reject/",
            {"reason": "Blurry after photo"},
            format="json",
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        self.assertEqual(reject.data["review_status"], Submission.ReviewStatus.REJECTED)
        self.assertEqual(Submission.objects.filter(sub_job=sub).count(), 1)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubJob.Status.OPEN)

        second = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sub.id}/submissions/",
            {
                "hours": "3.50",
                "notes": "attempt 2",
                "after_photo": make_image("a2.jpg", color="navy"),
            },
            format="multipart",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        accept = self.api.post(f"/api/submissions/{second.data['id']}/accept/", format="json")
        self.assertEqual(accept.status_code, status.HTTP_200_OK)
        self.assertEqual(Submission.objects.filter(sub_job=sub).count(), 2)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubJob.Status.ACCEPTED)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETE)

    def test_denied_and_pending_do_not_block_completion(self):
        open_sj = self._open_subjob()
        self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Pending forever", "before_photo": make_image("p.jpg")},
            format="multipart",
        )
        denied = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/",
            {"label": "Denied", "before_photo": make_image("d.jpg", color="black")},
            format="multipart",
        )
        self.api.post(
            f"/api/sub-jobs/{denied.data['id']}/deny/",
            {"reason": "no"},
            format="json",
        )
        sub = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{open_sj.id}/submissions/",
            {"hours": "1", "notes": "", "after_photo": make_image("a.jpg", color="red")},
            format="multipart",
        )
        self.api.post(f"/api/submissions/{sub.data['id']}/accept/", format="json")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETE)


class ActivityFeedAndIsolationTests(Phase3Base):
    def test_activity_feed_orders_events(self):
        sj = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "Tub", "amount": "100", "before_photo": make_image()},
            format="multipart",
        )
        sub = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/sub-jobs/{sj.data['id']}/submissions/",
            {"hours": "1", "notes": "n", "after_photo": make_image("a.jpg", color="red")},
            format="multipart",
        )
        self.api.post(
            f"/api/submissions/{sub.data['id']}/reject/",
            {"reason": "redo"},
            format="json",
        )
        feed = self.api.get(f"/api/projects/{self.project.id}/activity/")
        self.assertEqual(feed.status_code, status.HTTP_200_OK)
        types = [e["type"] for e in feed.data]
        self.assertIn("assignment.accepted", types)
        self.assertIn("sub_job.created", types)
        self.assertIn("submission.created", types)
        self.assertIn("submission.rejected", types)
        timestamps = [e["timestamp"] for e in feed.data]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_foreign_client_gets_404_on_subjob_and_feed(self):
        other = client_user(email="other@ex.com")
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        sj = self.api.post(
            f"/api/projects/{self.project.id}/sub-jobs/",
            {"label": "Tub", "amount": "100", "before_photo": make_image()},
            format="multipart",
        )
        self.assertEqual(
            other_api.get(f"/api/projects/{self.project.id}/activity/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            other_api.post(
                f"/api/sub-jobs/{sj.data['id']}/approve/",
                {"amount": "1"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
