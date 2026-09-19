from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("flows", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="flowrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("running", "Running"),
                    ("waiting", "Waiting"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="running",
                max_length=20,
            ),
        ),
    ]
