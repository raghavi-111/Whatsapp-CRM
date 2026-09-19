import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contacts", "0001_initial"),
        ("organizations", "0002_create_default_organizations"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "channel",
                    models.CharField(choices=[("whatsapp", "WhatsApp")], default="whatsapp", max_length=30),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("pending", "Pending"),
                            ("resolved", "Resolved"),
                            ("closed", "Closed"),
                        ],
                        db_index=True,
                        default="open",
                        max_length=20,
                    ),
                ),
                ("last_message_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_conversations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversations",
                        to="contacts.contact",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversations",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-last_message_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["organization", "status"], name="conversatio_organiz_35d9cc_idx"),
                    models.Index(fields=["organization", "last_message_at"], name="conversatio_organiz_9abf15_idx"),
                    models.Index(fields=["organization", "created_at"], name="conversatio_organiz_215f25_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "sender_type",
                    models.CharField(
                        choices=[("contact", "Contact"), ("agent", "Agent"), ("system", "System")],
                        max_length=20,
                    ),
                ),
                (
                    "message_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("image", "Image"),
                            ("document", "Document"),
                            ("audio", "Audio"),
                            ("video", "Video"),
                            ("location", "Location"),
                            ("template", "Template"),
                            ("system", "System"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("text", models.TextField(blank=True)),
                (
                    "direction",
                    models.CharField(choices=[("inbound", "Inbound"), ("outbound", "Outbound")], max_length=20),
                ),
                ("external_message_id", models.CharField(blank=True, db_index=True, max_length=255)),
                (
                    "delivery_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("delivered", "Delivered"),
                            ("read", "Read"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("sent_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="conversations.conversation",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["organization", "created_at"], name="conversatio_organiz_76f2a7_idx"),
                    models.Index(fields=["conversation", "created_at"], name="conversatio_convers_4b968d_idx"),
                    models.Index(fields=["external_message_id"], name="conversatio_externa_c7658c_idx"),
                ],
            },
        ),
    ]
