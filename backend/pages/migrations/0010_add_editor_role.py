from django.db import migrations, models


def migrate_existing_editors_to_editor_role(apps, schema_editor):
    """Migrate all existing project editors to the 'editor' role for backward compatibility."""
    ProjectEditor = apps.get_model("pages", "ProjectEditor")
    ProjectEditor.objects.all().update(role="editor")


def migrate_pending_invitations_to_editor_role(apps, schema_editor):
    """Migrate all existing pending project invitations to the 'editor' role for backward compatibility."""
    ProjectInvitation = apps.get_model("pages", "ProjectInvitation")
    ProjectInvitation.objects.filter(accepted=False).update(role="editor")


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0009_project_org_members_can_access"),
    ]

    operations = [
        # Add role field to ProjectEditor with default 'viewer'
        migrations.AddField(
            model_name="projecteditor",
            name="role",
            field=models.TextField(
                choices=[("viewer", "Viewer"), ("editor", "Editor")],
                default="viewer",
            ),
        ),
        # Update existing ProjectEditor rows to 'editor' for backward compatibility
        migrations.RunPython(
            migrate_existing_editors_to_editor_role,
            reverse_code=migrations.RunPython.noop,
        ),
        # Add role field to ProjectInvitation with default 'viewer'
        migrations.AddField(
            model_name="projectinvitation",
            name="role",
            field=models.TextField(
                choices=[("viewer", "Viewer"), ("editor", "Editor")],
                default="viewer",
            ),
        ),
        # Update existing pending invitations to 'editor' for backward compatibility
        migrations.RunPython(
            migrate_pending_invitations_to_editor_role,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
