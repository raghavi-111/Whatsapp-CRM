import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0002_create_default_organizations"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppBusinessConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_name", models.CharField(blank=True, max_length=255)),
                ("phone_number", models.CharField(blank=True, max_length=50)),
                ("phone_number_id", models.CharField(max_length=255)),
                ("whatsapp_business_account_id", models.CharField(max_length=255)),
                ("meta_app_id", models.CharField(blank=True, max_length=255)),
                ("meta_app_secret", models.TextField()),
                ("access_token", models.TextField()),
                ("webhook_verify_token", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="whatsapp_config",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "WhatsApp Business Config",
                "verbose_name_plural": "WhatsApp Business Configs",
            },
        ),
    ]
