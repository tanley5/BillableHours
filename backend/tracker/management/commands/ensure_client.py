from django.core.management.base import BaseCommand

from tracker.models import User


class Command(BaseCommand):
    help = "Create or update the local demo client user."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="owner@example.com")
        parser.add_argument("--password", default="changeme123")

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": User.Role.CLIENT},
        )
        user.role = User.Role.CLIENT
        user.set_password(password)
        user.save()
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} client {email}"))
