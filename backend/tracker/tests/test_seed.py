from io import StringIO

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings

from tracker.models import Assignment, Job, Photo, Project, User, Visit


@override_settings(
    N8N_WEBHOOK_URL="",
)
class SeedScenarioCommandTests(TestCase):
    def test_seed_loads_bathtub_scenario(self):
        out = StringIO()
        call_command("seed_scenario", stdout=out)

        client = User.objects.get(email="owner@example.com")
        self.assertEqual(client.role, User.Role.CLIENT)

        project = Project.objects.get(name="Bathtub repair")
        self.assertEqual(project.owner, client)
        self.assertIn("bathtub", project.scope.lower())

        assignment = Assignment.objects.get(project=project)
        self.assertEqual(assignment.status, Assignment.Status.ACCEPTED)
        self.assertEqual(assignment.contractor.name, "Alex Contractor")

        bathtub = Job.objects.get(assignment=assignment, label="Bathtub", parent=None)
        self.assertEqual(bathtub.status, Job.Status.COMPLETE)
        self.assertTrue(bathtub.photos.filter(kind=Photo.Kind.BEFORE).exists())
        self.assertTrue(bathtub.photos.filter(kind=Photo.Kind.AFTER).exists())

        found = list(
            Job.objects.filter(assignment=assignment, parent=bathtub).order_by("label")
        )
        labels = [j.label for j in found]
        self.assertEqual(labels, ["Broken pipe", "Drywall crack", "Mold"])
        for issue in found:
            self.assertTrue(issue.photos.filter(kind=Photo.Kind.BEFORE).exists())
            self.assertTrue(issue.photos.filter(kind=Photo.Kind.AFTER).exists())
            self.assertIn(
                issue.status,
                {Job.Status.COMPLETE, Job.Status.APPROVED, Job.Status.DISPUTED},
            )

        # At least one approved job and one disputed job with client comment
        self.assertTrue(
            Job.objects.filter(assignment=assignment, status=Job.Status.APPROVED).exists()
        )
        disputed = Job.objects.filter(
            assignment=assignment, status=Job.Status.DISPUTED
        ).exclude(client_comment="")
        self.assertTrue(disputed.exists())
        self.assertTrue(disputed.first().client_comment)

        visits = Visit.objects.filter(assignment=assignment)
        self.assertGreaterEqual(visits.count(), 3)
        self.assertTrue(visits.filter(status=Visit.Status.APPROVED).exists())
        self.assertTrue(visits.filter(status=Visit.Status.PENDING).exists())

        self.assertIn("seeded", out.getvalue().lower())

    def test_seed_is_idempotent_with_reset(self):
        call_command("seed_scenario", stdout=StringIO())
        first_project_id = Project.objects.get(name="Bathtub repair").id
        first_photo_count = Photo.objects.count()

        call_command("seed_scenario", "--reset", stdout=StringIO())
        project = Project.objects.get(name="Bathtub repair")
        self.assertNotEqual(project.id, first_project_id)
        self.assertEqual(Project.objects.filter(name="Bathtub repair").count(), 1)
        self.assertEqual(Photo.objects.count(), first_photo_count)

    def test_seed_without_reset_skips_when_present(self):
        call_command("seed_scenario", stdout=StringIO())
        project_id = Project.objects.get(name="Bathtub repair").id
        out = StringIO()
        call_command("seed_scenario", stdout=out)
        self.assertEqual(Project.objects.get(name="Bathtub repair").id, project_id)
        self.assertIn("already", out.getvalue().lower())
