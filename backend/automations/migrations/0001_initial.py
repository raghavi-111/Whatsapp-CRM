# Generated for Phase 14 automations foundation.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0002_create_default_organizations"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("inbound_message_received", "Inbound message received"),
                            ("conversation_created", "Conversation created"),
                            ("contact_created", "Contact created"),
                            ("tag_added", "Tag added"),
                            ("conversation_status_changed", "Conversation status changed"),
                        ],
                        db_index=True,
                        max_length=60,
                    ),
                ),
                ("conditions_json", models.JSONField(blank=True, default=list)),
                ("actions_json", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_automation_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="automation_rules",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="AutomationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("inbound_message_received", "Inbound message received"),
                            ("conversation_created", "Conversation created"),
                            ("contact_created", "Contact created"),
                            ("tag_added", "Tag added"),
                            ("conversation_status_changed", "Conversation status changed"),
                        ],
                        db_index=True,
                        max_length=60,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                ("context_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="automation_logs",
                        to="organizations.organization",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="automations.automationrule",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="automationrule",
            index=models.Index(fields=["organization", "trigger_type", "is_active"], name="automation__organiz_461d1c_idx"),
        ),
        migrations.AddIndex(
            model_name="automationlog",
            index=models.Index(fields=["organization", "created_at"], name="automation__organiz_7d9a91_idx"),
        ),
        migrations.AddIndex(
            model_name="automationlog",
            index=models.Index(fields=["organization", "status"], name="automation__organiz_6cecff_idx"),
        ),
    ]
