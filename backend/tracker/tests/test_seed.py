from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from tracker.models import (
    Assignment,
    Contractor,
    Escrow,
    Job,
    Project,
    SubJob,
    SubJobPhoto,
    User,
    Visit,
)


@override_settings(N8N_WEBHOOK_URL="", STRIPE_SECRET_KEY="", STRIPE_API_BASE="")
class SeedScenarioCommandTests(TestCase):
    def test_seed_loads_spec2_sibling_subjobs(self):
        out = StringIO()
        call_command("seed_scenario", stdout=out)

        client = User.objects.get(email="owner@example.com")
        self.assertEqual(client.role, User.Role.CLIENT)

        project = Project.objects.get(name="Bathtub repair")
        self.assertEqual(project.owner, client)

        assignment = Assignment.objects.get(project=project)
        self.assertEqual(assignment.status, Assignment.Status.ACCEPTED)
        contractor = assignment.contractor
        self.assertEqual(contractor.name, "Alex Contractor")
        self.assertEqual(contractor.connect_status, Contractor.ConnectStatus.COMPLETE)
        self.assertTrue(contractor.stripe_connect_account_id)

        labels = list(
            SubJob.objects.filter(project=project).order_by("label").values_list("label", flat=True)
        )
        self.assertEqual(
            labels,
            ["Fix bathtub", "Fix broken pipe", "Fix drywall", "Fix mold"],
        )
        # Flat siblings — no legacy Job parent tree
        self.assertEqual(Job.objects.filter(assignment=assignment).count(), 0)
        self.assertEqual(Visit.objects.filter(assignment=assignment).count(), 0)

        for sub in SubJob.objects.filter(project=project):
            self.assertTrue(sub.before_photos.exists())

        open_funded = SubJob.objects.filter(project=project, status=SubJob.Status.OPEN)
        self.assertGreaterEqual(open_funded.count(), 3)
        for sub in open_funded:
            escrow = Escrow.objects.get(sub_job=sub)
            self.assertEqual(escrow.status, Escrow.Status.REQUIRES_CAPTURE)

        pending = SubJob.objects.get(project=project, label="Fix drywall")
        self.assertEqual(pending.status, SubJob.Status.PENDING_APPROVAL)
        self.assertEqual(pending.created_by, SubJob.CreatedBy.CONTRACTOR)

        self.assertIn("seeded", out.getvalue().lower())

    def test_seed_is_idempotent_with_reset(self):
        call_command("seed_scenario", stdout=StringIO())
        first_project_id = Project.objects.get(name="Bathtub repair").id
        first_photo_count = SubJobPhoto.objects.count()

        call_command("seed_scenario", "--reset", stdout=StringIO())
        project = Project.objects.get(name="Bathtub repair")
        self.assertNotEqual(project.id, first_project_id)
        self.assertEqual(Project.objects.filter(name="Bathtub repair").count(), 1)
        self.assertEqual(SubJobPhoto.objects.count(), first_photo_count)

    def test_seed_without_reset_skips_when_present(self):
        call_command("seed_scenario", stdout=StringIO())
        project_id = Project.objects.get(name="Bathtub repair").id
        out = StringIO()
        call_command("seed_scenario", stdout=out)
        self.assertEqual(Project.objects.get(name="Bathtub repair").id, project_id)
        self.assertIn("already", out.getvalue().lower())

    @override_settings(STRIPE_SECRET_KEY="sk_test_sim", STRIPE_API_BASE="http://stripe-sim:12111")
    def test_seed_registers_connect_account_via_stripe_api_base(self):
        fake_account = {"id": "acct_from_sim_xyz", "charges_enabled": True, "details_submitted": True}

        def fake_pi(**kwargs):
            n = fake_pi.n
            fake_pi.n += 1
            return {
                "id": f"pi_seed_{n}",
                "client_secret": f"pi_seed_{n}_secret",
                "status": "requires_capture",
                "amount": kwargs.get("amount", 0),
            }

        fake_pi.n = 1

        with (
            patch("tracker.management.commands.seed_scenario.stripe.Account.create") as create,
            patch("tracker.stripe_escrow.stripe.PaymentIntent.create", side_effect=fake_pi),
        ):
            create.return_value = fake_account
            call_command("seed_scenario", "--reset", stdout=StringIO())

        create.assert_called_once()
        contractor = Contractor.objects.get(email="alex@example.com")
        self.assertEqual(contractor.stripe_connect_account_id, "acct_from_sim_xyz")
        self.assertEqual(contractor.connect_status, Contractor.ConnectStatus.COMPLETE)
