# Generated manually for Phase 4 migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0008_projectfile_project_files_and_more"),
        ("filehub", "0004_remove_projectfile_and_m2m"),
    ]

    operations = [
        # Step 1: Remove the M2M field from Project
        migrations.RemoveField(
            model_name="project",
            name="files",
        ),
        # Step 2: Delete the ProjectFile through table
        migrations.DeleteModel(
            name="ProjectFile",
        ),
    ]
