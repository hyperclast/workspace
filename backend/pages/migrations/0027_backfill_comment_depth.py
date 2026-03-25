"""Backfill Comment.depth for existing reply comments."""

from django.db import migrations

# Must match the constant in pages/models/comments.py
_MAX_DEPTH = 8


def backfill_depth(apps, schema_editor):
    Comment = apps.get_model("pages", "Comment")
    # Process all comments ordered by creation time.
    # Root comments already have depth=0 (field default).
    # For replies, compute depth from parent in a single pass.
    # Cap at _MAX_DEPTH - 1 to respect the check constraint added in 0026.
    depths = {}
    for comment_id, parent_id in Comment.objects.order_by("created").values_list("id", "parent_id"):
        if parent_id is None:
            depths[comment_id] = 0
        else:
            depths[comment_id] = min(depths.get(parent_id, 0) + 1, _MAX_DEPTH - 1)

    # Batch update replies that need depth > 0
    to_update = []
    for comment in Comment.objects.filter(parent__isnull=False).only("id", "depth"):
        depth = depths.get(comment.id, 0)
        if depth != comment.depth:
            comment.depth = depth
            to_update.append(comment)

    if to_update:
        Comment.objects.bulk_update(to_update, ["depth"], batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0026_comment_depth_comment_comment_max_depth"),
    ]

    operations = [
        migrations.RunPython(backfill_depth, migrations.RunPython.noop),
    ]
