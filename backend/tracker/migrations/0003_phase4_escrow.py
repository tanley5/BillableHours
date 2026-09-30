# Generated manually for SPEC2 phase 4 escrow

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0002_phase3_subjobs"),
    ]

    operations = [
        migrations.CreateModel(
            name="Escrow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_payment_intent_id", models.CharField(max_length=255, unique=True)),
                ("client_secret", models.CharField(blank=True, default="", max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("platform_fee_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("capture_method", models.CharField(default="manual", max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requires_confirmation", "Requires confirmation"),
                            ("requires_capture", "Authorized (requires capture)"),
                            ("captured", "Captured"),
                            ("canceled", "Canceled"),
                            ("expired", "Expired"),
                            ("detached", "Detached"),
                        ],
                        max_length=32,
                    ),
                ),
                ("authorized_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("detached_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "destination_contractor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="escrows",
                        to="tracker.contractor",
                    ),
                ),
                (
                    "sub_job",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escrow",
                        to="tracker.subjob",
                    ),
                ),
            ],
        ),
    ]
