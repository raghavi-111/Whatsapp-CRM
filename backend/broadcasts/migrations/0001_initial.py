import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contacts", "0002_contact_tags"),
        ("organizations", "0003_organizationinvitation"),
        ("support", "0002_notes"),
        ("templates", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BroadcastCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                (
                    "audience_type",
                    models.CharField(
                        choices=[
                            ("all", "All contacts"),
                            ("tags", "Contacts by tags"),
                            ("filters", "Contacts by filters"),
                        ],
                        default="all",
                        max_length=20,
                    ),
                ),
                ("contact_status", models.CharField(blank=True, max_length=20)),
                ("contact_source", models.CharField(blank=True, max_length=20)),
                ("template_language", models.CharField(max_length=20)),
                ("variable_mappings", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("scheduled", "Scheduled"),
                            ("queued", "Queued"),
                            ("sending", "Sending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("recipient_count", models.PositiveIntegerField(default=0)),
                ("sent_count", models.PositiveIntegerField(default=0)),
                ("delivered_count", models.PositiveIntegerField(default=0)),
                ("read_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_broadcast_campaigns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="broadcast_campaigns",
                        to="organizations.organization",
                    ),
                ),
                (
                    "selected_tags",
                    models.ManyToManyField(blank=True, related_name="broadcast_campaigns", to="support.tag"),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="broadcast_campaigns",
                        to="templates.messagetemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BroadcastRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("delivered", "Delivered"),
                            ("read", "Read"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("whatsapp_message_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipients",
                        to="broadcasts.broadcastcampaign",
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="broadcast_recipients",
                        to="contacts.contact",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="broadcastcampaign",
            index=models.Index(fields=["organization", "status"], name="broadcasts__organiz_4a7452_idx"),
        ),
        migrations.AddIndex(
            model_name="broadcastcampaign",
            index=models.Index(fields=["organization", "created_at"], name="broadcasts__organiz_f12ced_idx"),
        ),
        migrations.AddConstraint(
            model_name="broadcastrecipient",
            constraint=models.UniqueConstraint(fields=("campaign", "contact"), name="unique_broadcast_contact_per_campaign"),
        ),
    ]
