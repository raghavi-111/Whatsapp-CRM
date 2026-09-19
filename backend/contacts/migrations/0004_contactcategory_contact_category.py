import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("contacts", "0003_alter_contact_source")]
    operations = [
        migrations.CreateModel(
            name="ContactCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contact_categories", to="organizations.organization")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="contactcategory",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="unique_contact_category_per_org"),
        ),
        migrations.AddField(
            model_name="contact", name="category",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="contacts", to="contacts.contactcategory"),
        ),
        migrations.AlterField(
            model_name="contact", name="source",
            field=models.CharField(choices=[("manual", "Manual"), ("whatsapp", "WhatsApp"), ("import", "Import"), ("website", "Website"), ("referral", "Referral"), ("walk_in", "Walk-in"), ("lead_collector", "Lead Collector")], default="manual", max_length=20),
        ),
    ]
