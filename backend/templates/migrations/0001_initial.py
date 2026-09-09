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
            name="MessageTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("language", models.CharField(max_length=20)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("marketing", "Marketing"),
                            ("utility", "Utility"),
                            ("authentication", "Authentication"),
                        ],
                        default="utility",
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("paused", "Paused"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "header_type",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("text", "Text"),
                            ("image", "Image"),
                            ("document", "Document"),
                            ("video", "Video"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                ("header_text", models.CharField(blank=True, max_length=255)),
                ("body_text", models.TextField()),
                ("footer_text", models.CharField(blank=True, max_length=255)),
                ("buttons_json", models.JSONField(blank=True, default=list)),
                ("meta_template_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_message_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="message_templates",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddConstraint(
            model_name="messagetemplate",
            constraint=models.UniqueConstraint(
                fields=("organization", "name", "language"),
                name="unique_template_name_language_per_org",
            ),
        ),
    ]
