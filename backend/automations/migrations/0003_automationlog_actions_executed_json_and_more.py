from django.db import migrations, models


TRIGGER_CHOICES = [
    ("inbound_message_received", "Inbound message received"),
    ("conversation_created", "Conversation created"),
    ("contact_created", "Contact created"),
    ("tag_added", "Tag added"),
    ("conversation_status_changed", "Conversation status changed"),
    ("deal_created", "Deal created"),
    ("deal_stage_changed", "Deal stage changed"),
    ("broadcast_completed", "Broadcast completed"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("automations", "0002_rename_automation__organiz_7d9a91_idx_automations_organiz_3c4c55_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="automationlog",
            name="actions_executed_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="automationlog",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="automationlog",
            name="matched_conditions_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="automationrule",
            name="condition_logic",
            field=models.CharField(choices=[("and", "AND"), ("or", "OR")], default="and", max_length=10),
        ),
        migrations.AlterField(
            model_name="automationlog",
            name="trigger_type",
            field=models.CharField(choices=TRIGGER_CHOICES, db_index=True, max_length=60),
        ),
        migrations.AlterField(
            model_name="automationrule",
            name="trigger_type",
            field=models.CharField(choices=TRIGGER_CHOICES, db_index=True, max_length=60),
        ),
    ]
