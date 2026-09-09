from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("leads", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="source",
            field=models.CharField(
                choices=[
                    ("whatsapp", "WhatsApp"), ("website", "Website"), ("blog", "Blog"),
                    ("instagram", "Instagram"), ("facebook", "Facebook"), ("linkedin", "LinkedIn"),
                    ("qr_code", "QR Code"), ("marketing_team", "Marketing Team"),
                    ("referral", "Referral"), ("excel_import", "Excel Import"),
                    ("manual_entry", "Manual Entry"), ("lead_collector", "Lead Collector"),
                    ("other", "Other"),
                ],
                default="manual_entry", max_length=30,
            ),
        ),
    ]
