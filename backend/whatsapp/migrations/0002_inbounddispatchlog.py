import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("conversations", "0002_message_media_fields"), ("organizations", "0001_initial"), ("whatsapp", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="InboundDispatchLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("engine", models.CharField(max_length=20)),
                ("status", models.CharField(max_length=20)),
                ("detail", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dispatch_logs", to="conversations.message")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inbound_dispatch_logs", to="organizations.organization")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(model_name="inbounddispatchlog", constraint=models.UniqueConstraint(fields=("message", "engine"), name="one_dispatch_per_message_engine")),
    ]
