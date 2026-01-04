from django.db import migrations, models
import updates.models


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0002_email_logging_and_spam_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="update",
            name="author_name",
            field=models.CharField(blank=True, default=updates.models.get_default_author_name, max_length=100),
        ),
        migrations.AddField(
            model_name="update",
            name="author_picture_url",
            field=models.CharField(blank=True, default=updates.models.get_default_author_picture, max_length=500),
        ),
    ]
