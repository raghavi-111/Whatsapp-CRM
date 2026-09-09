import decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contacts", "0002_contact_tags"),
        ("organizations", "0003_organizationinvitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="Deal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("value", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("New", "New"),
                            ("Qualified", "Qualified"),
                            ("Proposal", "Proposal"),
                            ("Won", "Won"),
                        ],
                        default="New",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("won", "Won"), ("lost", "Lost")],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("manual", "Manual"), ("whatsapp", "WhatsApp")],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deals",
                        to="contacts.contact",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deals",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["organization", "stage"], name="pipelines_d_organiz_ba856a_idx"),
                    models.Index(fields=["organization", "status"], name="pipelines_d_organiz_c1bed6_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("contact__isnull", False), ("status", "open")),
                        fields=("organization", "contact"),
                        name="unique_open_deal_per_contact_per_org",
                    )
                ],
            },
        ),
    ]
