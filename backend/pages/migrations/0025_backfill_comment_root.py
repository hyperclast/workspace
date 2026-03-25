"""Backfill Comment.root for existing reply comments."""

from django.db import migrations


def backfill_root(apps, schema_editor):
    Comment = apps.get_model("pages", "Comment")
    # Process replies that don't have root set yet.
    # Walk up the parent chain to find the root for each.
    replies = Comment.objects.filter(parent__isnull=False, root__isnull=True)
    for reply in replies:
        current = reply
        while current.parent_id is not None:
            current = Comment.objects.get(id=current.parent_id)
        reply.root = current
        reply.save(update_fields=["root"])


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0024_comment_root_comment_comment_root_created_idx"),
    ]

    operations = [
        migrations.RunPython(backfill_root, migrations.RunPython.noop),
    ]
