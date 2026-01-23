# Generated manually for Phase 4 migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("filehub", "0003_populate_project_fk"),
        ("pages", "0008_projectfile_project_files_and_more"),
    ]

    operations = [
        # Step 1: Make project field non-nullable on FileUpload
        migrations.AlterField(
            model_name="fileupload",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="file_uploads",
                to="pages.project",
            ),
        ),
    ]
