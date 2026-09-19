from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("contacts", "0002_contact_tags")]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("whatsapp", "WhatsApp"),
                    ("import", "Import"),
                    ("website", "Website"),
                    ("referral", "Referral"),
                    ("walk_in", "Walk-in"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
    ]
