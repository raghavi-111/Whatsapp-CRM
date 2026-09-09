from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0001_initial"),
        ("contacts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="contacts", to="support.tag"),
        ),
    ]
