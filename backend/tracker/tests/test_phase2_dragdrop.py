"""SPEC2 Phase 2: contractor reliability badge + pool markers for drag-drop."""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from tracker.models import Assignment, ClientContractor, Contractor, Project, User


def create_client(email="owner@example.com"):
    return User.objects.create_user(email=email, password="pass", role=User.Role.CLIENT)


def create_contractor(
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


class ReliabilityBadgeTests(TestCase):
    def setUp(self):
        self.client_user = create_client()
        self.api = APIClient()
        self.api.force_authenticate(user=self.client_user)
        self.contractor = create_contractor()
        ClientContractor.objects.create(client=self.client_user, contractor=self.contractor)
        self.project = Project.objects.create(owner=self.client_user, name="P", scope="s")
        other = Project.objects.create(owner=self.client_user, name="Q", scope="s")

        # 2 accepted, 1 rejected → accept_rate 2/3, rejection_count 1
        Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )
        Assignment.objects.create(
            project=other,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )
        Assignment.objects.create(
            project=other,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.REJECTED,
        )

    def test_list_includes_reliability_from_assignment_history(self):
        resp = self.api.get("/api/contractors/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data[0]
        self.assertEqual(row["rejection_count"], 1)
        self.assertAlmostEqual(float(row["accept_rate"]), 2 / 3, places=4)

    def test_new_contractor_has_null_accept_rate_and_zero_rejections(self):
        newbie = create_contractor(email="new@ex.com", name="New", stripe_id="acct_new")
        ClientContractor.objects.create(client=self.client_user, contractor=newbie)
        resp = self.api.get("/api/contractors/")
        row = next(r for r in resp.data if r["email"] == "new@ex.com")
        self.assertIsNone(row["accept_rate"])
        self.assertEqual(row["rejection_count"], 0)


class PoolAssignmentMarkerTests(TestCase):
    def setUp(self):
        self.client_user = create_client()
        self.api = APIClient()
        self.api.force_authenticate(user=self.client_user)
        self.project = Project.objects.create(owner=self.client_user, name="This", scope="s")
        self.other = Project.objects.create(owner=self.client_user, name="Other", scope="s")
        self.on_this = create_contractor(email="here@ex.com", name="Here", stripe_id="acct_here")
        self.elsewhere = create_contractor(email="away@ex.com", name="Away", stripe_id="acct_away")
        self.free = create_contractor(email="free@ex.com", name="Free", stripe_id="acct_free")
        for c in (self.on_this, self.elsewhere, self.free):
            ClientContractor.objects.create(client=self.client_user, contractor=c)
        Assignment.objects.create(
            project=self.project,
            contractor=self.on_this,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.INVITED,
        )
        Assignment.objects.create(
            project=self.other,
            contractor=self.elsewhere,
            hourly_rate=Decimal("50"),
            status=Assignment.Status.ACCEPTED,
        )

    def test_project_scoped_markers(self):
        resp = self.api.get(f"/api/contractors/?project_id={self.project.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_email = {r["email"]: r for r in resp.data}
        self.assertTrue(by_email["here@ex.com"]["assigned_to_this_project"])
        self.assertFalse(by_email["here@ex.com"]["assigned_elsewhere"])
        self.assertFalse(by_email["away@ex.com"]["assigned_to_this_project"])
        self.assertTrue(by_email["away@ex.com"]["assigned_elsewhere"])
        self.assertFalse(by_email["free@ex.com"]["assigned_to_this_project"])
        self.assertFalse(by_email["free@ex.com"]["assigned_elsewhere"])

    def test_foreign_project_id_returns_404(self):
        other_owner = create_client(email="other@ex.com")
        foreign = Project.objects.create(owner=other_owner, name="Nope", scope="x")
        resp = self.api.get(f"/api/contractors/?project_id={foreign.id}")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
