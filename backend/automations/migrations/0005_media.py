from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("automations", "0004_automationmedia")]

    operations = [
        migrations.CreateModel(
            name="Media",
            fields=[],
            options={"verbose_name_plural": "media", "proxy": True, "indexes": [], "constraints": []},
            bases=("automations.automationmedia",),
        ),
    ]
