from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conversations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="media_file",
            field=models.FileField(blank=True, upload_to="messages/%Y/%m/%d/"),
        ),
        migrations.AddField(
            model_name="message",
            name="media_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="message",
            name="media_mime_type",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="message",
            name="media_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="message",
            name="media_size",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="meta_media_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
    ]
