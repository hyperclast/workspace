# Generated manually for data migration

from django.db import migrations


def migrate_project_references(apps, schema_editor):
    """Copy project_id from ProjectFile to FileUpload.project."""
    ProjectFile = apps.get_model("pages", "ProjectFile")
    FileUpload = apps.get_model("filehub", "FileUpload")

    for pf in ProjectFile.objects.all():
        FileUpload.objects.filter(id=pf.file_upload_id).update(project_id=pf.project_id)


def reverse_migration(apps, schema_editor):
    """No reverse needed - ProjectFile still exists at this point."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("filehub", "0002_add_project_fk_to_fileupload"),
        ("pages", "0008_projectfile_project_files_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_project_references, reverse_migration),
    ]
