from django.db import migrations, models


def migrate_existing_page_editors_to_editor_role(apps, schema_editor):
    """Migrate all existing page editors to the 'editor' role for backward compatibility."""
    PageEditor = apps.get_model("pages", "PageEditor")
    PageEditor.objects.all().update(role="editor")


def migrate_pending_page_invitations_to_editor_role(apps, schema_editor):
    """Migrate all existing pending page invitations to the 'editor' role for backward compatibility."""
    PageInvitation = apps.get_model("pages", "PageInvitation")
    PageInvitation.objects.filter(accepted=False).update(role="editor")


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0010_add_editor_role"),
    ]

    operations = [
        # Add role field to PageEditor with default 'viewer'
        migrations.AddField(
            model_name="pageeditor",
            name="role",
            field=models.TextField(
                choices=[("viewer", "Viewer"), ("editor", "Editor")],
                default="viewer",
            ),
        ),
        # Update existing PageEditor rows to 'editor' for backward compatibility
        migrations.RunPython(
            migrate_existing_page_editors_to_editor_role,
            reverse_code=migrations.RunPython.noop,
        ),
        # Add role field to PageInvitation with default 'viewer'
        migrations.AddField(
            model_name="pageinvitation",
            name="role",
            field=models.TextField(
                choices=[("viewer", "Viewer"), ("editor", "Editor")],
                default="viewer",
            ),
        ),
        # Update existing pending page invitations to 'editor' for backward compatibility
        migrations.RunPython(
            migrate_pending_page_invitations_to_editor_role,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
