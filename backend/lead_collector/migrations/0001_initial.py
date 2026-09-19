import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import lead_collector.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_organizationinvitation"),
        ("leads", "0002_lead_collector_source"),
    ]
    operations = [
        migrations.CreateModel(
            name="ProviderSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hotel_provider", models.CharField(choices=[("openstreetmap", "OpenStreetMap"), ("geoapify", "Geoapify"), ("google", "Google Places"), ("playwright", "Browser Search")], default="openstreetmap", max_length=20)),
                ("business_providers", models.JSONField(default=lead_collector.models.default_business_providers)),
                ("people_providers", models.JSONField(default=lead_collector.models.default_people_providers)),
                ("apollo_enabled", models.BooleanField(default=False)),
                ("google_api_key_encrypted", models.TextField(blank=True)),
                ("geoapify_api_key_encrypted", models.TextField(blank=True)),
                ("apollo_api_key_encrypted", models.TextField(blank=True)),
                ("zoominfo_api_key_encrypted", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lead_collector_settings", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="DiscoverySearch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("location_name", models.CharField(max_length=300)), ("latitude", models.FloatField()), ("longitude", models.FloatField()),
                ("radius_m", models.PositiveIntegerField()), ("category", models.CharField(max_length=80)),
                ("providers", models.JSONField(default=list)), ("search_depth", models.CharField(default="standard", max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("complete", "Complete"), ("failed", "Failed")], default="pending", max_length=20)),
                ("diagnostics", models.JSONField(blank=True, default=dict)), ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovery_searches", to="organizations.organization")),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DiscoveredBusiness",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identity_key", models.CharField(max_length=500)), ("name", models.CharField(max_length=300)),
                ("phone_normalized", models.CharField(blank=True, max_length=50)), ("website_domain", models.CharField(blank=True, max_length=255)),
                ("provider_place_id", models.CharField(blank=True, max_length=255)), ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovered_businesses", to="organizations.organization")),
                ("search", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="businesses", to="lead_collector.discoverysearch")),
            ], options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="LeadImportRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identity_key", models.CharField(max_length=500)), ("phone_normalized", models.CharField(blank=True, max_length=50)),
                ("whatsapp_normalized", models.CharField(blank=True, max_length=50)), ("website_domain", models.CharField(blank=True, max_length=255)),
                ("provider_place_id", models.CharField(blank=True, max_length=255)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lead_imports", to="lead_collector.discoveredbusiness")),
                ("lead", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="collector_import", to="leads.lead")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_collector_imports", to="organizations.organization")),
            ],
        ),
        migrations.AddIndex(model_name="discoverysearch", index=models.Index(fields=["organization", "-created_at"], name="lead_collec_organiz_b7afc0_idx")),
        migrations.AddConstraint(model_name="discoveredbusiness", constraint=models.UniqueConstraint(fields=("search", "identity_key"), name="unique_business_identity_per_search")),
        migrations.AddIndex(model_name="discoveredbusiness", index=models.Index(fields=["organization", "phone_normalized"], name="lead_collec_organiz_f9cbab_idx")),
        migrations.AddIndex(model_name="discoveredbusiness", index=models.Index(fields=["organization", "website_domain"], name="lead_collec_organiz_ddc9a1_idx")),
        migrations.AddIndex(model_name="discoveredbusiness", index=models.Index(fields=["organization", "provider_place_id"], name="lead_collec_organiz_c6c647_idx")),
        migrations.AddConstraint(model_name="leadimportrecord", constraint=models.UniqueConstraint(fields=("organization", "business"), name="unique_imported_business_per_org")),
        migrations.AddIndex(model_name="leadimportrecord", index=models.Index(fields=["organization", "phone_normalized"], name="lead_collec_organiz_74890e_idx")),
        migrations.AddIndex(model_name="leadimportrecord", index=models.Index(fields=["organization", "whatsapp_normalized"], name="lead_collec_organiz_4833ee_idx")),
        migrations.AddIndex(model_name="leadimportrecord", index=models.Index(fields=["organization", "website_domain"], name="lead_collec_organiz_865623_idx")),
        migrations.AddIndex(model_name="leadimportrecord", index=models.Index(fields=["organization", "provider_place_id"], name="lead_collec_organiz_0303e8_idx")),
    ]
