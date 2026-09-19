from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("lead_collector", "0002_whatsappcontactimportrecord")]
    operations = [
        migrations.AlterField(model_name="whatsappcontactimportrecord", name="business", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="whatsapp_contact_imports", to="lead_collector.discoveredbusiness")),
        migrations.AddField(model_name="whatsappcontactimportrecord", name="source", field=models.CharField(default="lead_collector", max_length=30)),
        migrations.AddField(model_name="whatsappcontactimportrecord", name="workbook_filename", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="whatsappcontactimportrecord", name="worksheet_name", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="whatsappcontactimportrecord", name="source_row", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappcontactimportrecord", name="import_key", field=models.CharField(blank=True, max_length=64)),
    ]
