from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("automations", "0003_automationlog_actions_executed_json_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="AutomationMedia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="automation-media/%Y/%m/%d/")),
                ("filename", models.CharField(max_length=255)),
                ("mime_type", models.CharField(max_length=150)),
                ("media_type", models.CharField(max_length=20)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automation_media", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="automationmedia", index=models.Index(fields=["organization", "media_type"], name="automations_organiz_ef7f8e_idx")),
    ]
