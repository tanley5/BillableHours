"""Expire escrow authorization holds (SPEC2 phase 4). Run via cron, e.g. hourly."""
from django.core.management.base import BaseCommand

from tracker import stripe_escrow


class Command(BaseCommand):
    help = "Detach expired escrow holds and freeze affected projects."

    def handle(self, *args, **options):
        count = stripe_escrow.process_expired_holds()
        self.stdout.write(self.style.SUCCESS(f"Processed {count} expired escrow hold(s)."))
