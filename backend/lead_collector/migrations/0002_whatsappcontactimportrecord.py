import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("contacts", "0004_contactcategory_contact_category"), ("lead_collector", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="WhatsAppContactImportRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("normalized_number", models.CharField(max_length=50)),
                ("evidence_type", models.CharField(blank=True, max_length=100)),
                ("evidence_url", models.URLField(blank=True, max_length=1000)),
                ("status", models.CharField(default="CONFIRMED_PUBLIC", max_length=30)),
                ("provider_source", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="whatsapp_contact_imports", to="lead_collector.discoveredbusiness")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_collector_imports", to="contacts.contact")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_collector_contact_imports", to="organizations.organization")),
            ],
        ),
        migrations.AddConstraint(model_name="whatsappcontactimportrecord", constraint=models.UniqueConstraint(fields=("organization", "business", "normalized_number"), name="unique_whatsapp_import_evidence_per_org")),
        migrations.AddIndex(model_name="whatsappcontactimportrecord", index=models.Index(fields=["organization", "normalized_number"], name="lead_collec_organiz_65fbad_idx")),
    ]
