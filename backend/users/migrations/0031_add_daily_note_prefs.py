from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0030_drop_profile_access_token"),
        ("pages", "0029_commentreaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="daily_note_project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="pages.project",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="daily_note_template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="pages.page",
            ),
        ),
    ]
