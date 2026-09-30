"""SPEC2 Phase 1: contractor login, roster, Connect gate, isolation, invite."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from tracker.models import (
    Assignment,
    ClientContractor,
    Contractor,
    PasswordInvite,
    Project,
    User,
)
from tracker.stripe_connect import connect_status_from_account


def create_client_user(email="owner@example.com", password="test-pass-123"):
    return User.objects.create_user(email=email, password=password, role=User.Role.CLIENT)


def create_activated_contractor(
    *,
    email="alex@example.com",
    password="contractor-pass",
    name="Alex Contractor",
    phone="555-0100",
    connect_status=Contractor.ConnectStatus.COMPLETE,
    stripe_id="acct_test_alex",
):
    user = User.objects.create_user(email=email, password=password, role=User.Role.CONTRACTOR)
    return Contractor.objects.create(
        user=user,
        name=name,
        email=email,
        phone=phone,
        connect_status=connect_status,
        stripe_connect_account_id=stripe_id,
    )


class InviteSetPasswordTests(TestCase):
    def setUp(self):
        self.client_user = create_client_user()
        self.api = APIClient()
        self.api.force_authenticate(user=self.client_user)

    @patch("tracker.serializers.notifications.notify")
    def test_new_contractor_gets_invite_and_set_password_enables_login(self, mock_notify):
        resp = self.api.post(
            "/api/contractors/",
            {"name": "Alex", "email": "alex@example.com", "phone": "555-0100"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["connect_status"], Contractor.ConnectStatus.NOT_STARTED)
        self.assertFalse(User.objects.get(email="alex@example.com").has_usable_password())

        invite = PasswordInvite.objects.get(user__email="alex@example.com")
        self.assertIsNone(invite.used_at)
        mock_notify.assert_called()
        event = mock_notify.call_args[0][0]
        self.assertEqual(event, "contractor.invited")
        raw_token = mock_notify.call_args[0][1]["invite_token"]

        anon = APIClient()
        set_pw = anon.post(
            "/api/auth/set-password/",
            {"token": raw_token, "password": "new-secure-pass"},
            format="json",
        )
        self.assertEqual(set_pw.status_code, status.HTTP_200_OK)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)

        login = anon.post(
            "/api/auth/login/",
            {"email": "alex@example.com", "password": "new-secure-pass"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(login.data["role"], User.Role.CONTRACTOR)

    @patch("tracker.serializers.notifications.notify")
    def test_existing_email_roster_add_is_silent(self, mock_notify):
        contractor = create_activated_contractor()
        other_client = create_client_user(email="other@example.com")
        ClientContractor.objects.create(client=other_client, contractor=contractor)

        mock_notify.reset_mock()
        resp = self.api.post(
            "/api/contractors/",
            {"name": "Alex", "email": "alex@example.com", "phone": "555-0100"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contractor.objects.filter(email="alex@example.com").count(), 1)
        self.assertTrue(
            ClientContractor.objects.filter(client=self.client_user, contractor=contractor).exists()
        )
        for call in mock_notify.call_args_list:
            self.assertNotEqual(call[0][0], "contractor.invited")

        contractor_api = APIClient()
        contractor_api.force_authenticate(user=contractor.user)
        home = contractor_api.get("/api/contractor/assignments/")
        self.assertEqual(home.status_code, status.HTTP_200_OK)
        self.assertEqual(home.data, [])

    @patch("tracker.serializers.notifications.notify")
    def test_resend_invite_for_never_activated(self, mock_notify):
        create_resp = self.api.post(
            "/api/contractors/",
            {"name": "Alex", "email": "alex@example.com"},
            format="json",
        )
        contractor_id = create_resp.data["id"]
        first_token = mock_notify.call_args[0][1]["invite_token"]
        mock_notify.reset_mock()

        resend = self.api.post(f"/api/contractors/{contractor_id}/resend-invite/", format="json")
        self.assertEqual(resend.status_code, status.HTTP_200_OK)
        second_token = mock_notify.call_args[0][1]["invite_token"]
        self.assertNotEqual(first_token, second_token)

        anon = APIClient()
        bad = anon.post(
            "/api/auth/set-password/",
            {"token": first_token, "password": "new-secure-pass"},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


class ConnectGateAndAssignmentTests(TestCase):
    def setUp(self):
        self.client_user = create_client_user()
        self.api = APIClient()
        self.api.force_authenticate(user=self.client_user)
        self.project = Project.objects.create(
            owner=self.client_user, name="Bathtub", scope="fix"
        )
        self.contractor = create_activated_contractor(
            connect_status=Contractor.ConnectStatus.NOT_STARTED,
            stripe_id="",
        )
        ClientContractor.objects.create(client=self.client_user, contractor=self.contractor)

    def test_assignment_blocked_without_connect_complete(self):
        resp = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"contractor_id": self.contractor.id, "hourly_rate": "75.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("connect", str(resp.data).lower())

    @patch("tracker.serializers.notifications.notify")
    def test_assignment_invite_accept_reject_reinvite(self, mock_notify):
        self.contractor.connect_status = Contractor.ConnectStatus.COMPLETE
        self.contractor.stripe_connect_account_id = "acct_x"
        self.contractor.save()

        create = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"contractor_id": self.contractor.id, "hourly_rate": "75.00"},
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create.data["status"], Assignment.Status.INVITED)
        self.assertNotIn("token", create.data)
        assignment_id = create.data["id"]
        events = [c[0][0] for c in mock_notify.call_args_list]
        self.assertIn("assignment.invited", events)

        c_api = APIClient()
        c_api.force_authenticate(user=self.contractor.user)
        reject = c_api.post(f"/api/contractor/assignments/{assignment_id}/reject/")
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        self.assertEqual(reject.data["status"], Assignment.Status.REJECTED)
        self.assertTrue(Assignment.objects.filter(pk=assignment_id).exists())

        reinvite = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"contractor_id": self.contractor.id, "hourly_rate": "80.00"},
            format="json",
        )
        self.assertEqual(reinvite.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(reinvite.data["id"], assignment_id)

        accept = c_api.post(f"/api/contractor/assignments/{reinvite.data['id']}/accept/")
        self.assertEqual(accept.status_code, status.HTTP_200_OK)
        self.assertEqual(accept.data["status"], Assignment.Status.ACCEPTED)

    def test_client_cancel_invite(self):
        self.contractor.connect_status = Contractor.ConnectStatus.COMPLETE
        self.contractor.stripe_connect_account_id = "acct_x"
        self.contractor.save()
        create = self.api.post(
            f"/api/projects/{self.project.id}/assignments/",
            {"contractor_id": self.contractor.id, "hourly_rate": "75.00"},
            format="json",
        )
        cancel = self.api.post(f"/api/assignments/{create.data['id']}/cancel/")
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data["status"], Assignment.Status.CANCELLED)


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.a = create_client_user(email="a@example.com")
        self.b = create_client_user(email="b@example.com")
        self.contractor = create_activated_contractor()
        ClientContractor.objects.create(client=self.a, contractor=self.contractor)
        self.project_a = Project.objects.create(owner=self.a, name="A", scope="a")
        self.project_b = Project.objects.create(owner=self.b, name="B", scope="b")
        self.api_a = APIClient()
        self.api_a.force_authenticate(user=self.a)
        self.api_b = APIClient()
        self.api_b.force_authenticate(user=self.b)

    def test_client_b_cannot_see_client_a_project_or_contractor(self):
        detail = self.api_b.get(f"/api/projects/{self.project_a.id}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        contractors = self.api_b.get("/api/contractors/")
        self.assertEqual(contractors.status_code, status.HTTP_200_OK)
        self.assertEqual(contractors.data, [])

        foreign = self.api_b.get(f"/api/contractors/{self.contractor.id}/")
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)

    def test_contractor_cannot_see_other_contractor_assignment(self):
        other = create_activated_contractor(
            email="other@example.com", stripe_id="acct_other", name="Other"
        )
        ClientContractor.objects.create(client=self.a, contractor=other)
        assignment = Assignment.objects.create(
            project=self.project_a,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other.user)
        resp = other_api.get(f"/api/contractor/assignments/{assignment.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class StripeConnectStatusTests(TestCase):
    def test_connect_status_from_account_flags(self):
        self.assertEqual(
            connect_status_from_account({"charges_enabled": True, "details_submitted": True}),
            Contractor.ConnectStatus.COMPLETE,
        )
        self.assertEqual(
            connect_status_from_account({"charges_enabled": False, "details_submitted": True}),
            Contractor.ConnectStatus.RESTRICTED,
        )
        self.assertEqual(
            connect_status_from_account({"charges_enabled": False, "details_submitted": False}),
            Contractor.ConnectStatus.PENDING,
        )

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    @patch("tracker.stripe_connect.stripe.Webhook.construct_event")
    def test_webhook_account_updated_and_redelivery(self, mock_construct):
        contractor = create_activated_contractor(
            connect_status=Contractor.ConnectStatus.PENDING,
            stripe_id="acct_webhook",
        )
        account_obj = {
            "id": "acct_webhook",
            "object": "account",
            "charges_enabled": True,
            "details_submitted": True,
        }
        mock_construct.return_value = MagicMock(
            type="account.updated",
            data=MagicMock(object=account_obj),
        )
        # Stripe construct_event returns a StripeObject-like; use a simple namespace
        event = MagicMock()
        event.type = "account.updated"
        event.data.object = account_obj
        mock_construct.return_value = event

        api = APIClient()
        resp = api.post(
            "/api/stripe/webhook/",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        contractor.refresh_from_db()
        self.assertEqual(contractor.connect_status, Contractor.ConnectStatus.COMPLETE)

        # Redelivery recomputes same status
        resp2 = api.post(
            "/api/stripe/webhook/",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        contractor.refresh_from_db()
        self.assertEqual(contractor.connect_status, Contractor.ConnectStatus.COMPLETE)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    @patch("tracker.stripe_connect.stripe.Webhook.construct_event")
    def test_webhook_bad_signature(self, mock_construct):
        import stripe

        mock_construct.side_effect = stripe.error.SignatureVerificationError("bad", "sig")
        api = APIClient()
        resp = api.post(
            "/api/stripe/webhook/",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ContractorSessionJobTests(TestCase):
    def setUp(self):
        self.client_user = create_client_user()
        self.contractor = create_activated_contractor()
        ClientContractor.objects.create(client=self.client_user, contractor=self.contractor)
        self.project = Project.objects.create(owner=self.client_user, name="P", scope="s")
        self.assignment = Assignment.objects.create(
            project=self.project,
            contractor=self.contractor,
            hourly_rate=Decimal("75"),
            status=Assignment.Status.ACCEPTED,
        )
        self.c_api = APIClient()
        self.c_api.force_authenticate(user=self.contractor.user)

    def test_session_job_create_on_accepted_assignment(self):
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/jobs/",
            {"label": "Bathtub"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["label"], "Bathtub")

    def test_invited_assignment_cannot_create_jobs(self):
        self.assignment.status = Assignment.Status.INVITED
        self.assignment.save()
        resp = self.c_api.post(
            f"/api/contractor/assignments/{self.assignment.id}/jobs/",
            {"label": "Bathtub"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_routes_gone(self):
        resp = self.c_api.get("/api/c/some-token/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class LoginRoleTests(TestCase):
    def test_client_and_contractor_login(self):
        create_client_user()
        create_activated_contractor()
        anon = APIClient()

        client_login = anon.post(
            "/api/auth/login/",
            {"email": "owner@example.com", "password": "test-pass-123"},
            format="json",
        )
        self.assertEqual(client_login.data["role"], "client")

        contractor_login = anon.post(
            "/api/auth/login/",
            {"email": "alex@example.com", "password": "contractor-pass"},
            format="json",
        )
        self.assertEqual(contractor_login.status_code, status.HTTP_200_OK)
        self.assertEqual(contractor_login.data["role"], "contractor")

        me = anon.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["role"], "contractor")
