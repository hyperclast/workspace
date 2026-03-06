import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0015_version_history"),
    ]

    operations = [
        # 1. Rename models
        migrations.RenameModel("PageVersion", "Rewind"),
        migrations.RenameModel("PageVersionEditorSession", "RewindEditorSession"),
        # 2. Rename fields
        migrations.RenameField(
            model_name="page",
            old_name="current_version_number",
            new_name="current_rewind_number",
        ),
        migrations.RenameField(
            model_name="rewind",
            old_name="version_number",
            new_name="rewind_number",
        ),
        # 3. Update related_name on Rewind.page FK
        migrations.AlterField(
            model_name="rewind",
            name="page",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rewinds",
                to="pages.page",
            ),
        ),
        # 4. Update related_name on RewindEditorSession.page FK
        migrations.AlterField(
            model_name="rewindeditorsession",
            name="page",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rewind_sessions",
                to="pages.page",
            ),
        ),
        # 5. Remove old constraints/indexes
        migrations.RemoveConstraint(
            model_name="rewind",
            name="unique_page_version_number",
        ),
        migrations.RemoveIndex(
            model_name="rewind",
            name="pageversion_page_vnum_idx",
        ),
        migrations.RemoveIndex(
            model_name="rewind",
            name="pageversion_page_created_idx",
        ),
        migrations.RemoveIndex(
            model_name="rewindeditorsession",
            name="editorsession_page_conn_idx",
        ),
        # 6. Add renamed constraints/indexes
        migrations.AddConstraint(
            model_name="rewind",
            constraint=models.UniqueConstraint(
                fields=("page", "rewind_number"),
                name="unique_page_rewind_number",
            ),
        ),
        migrations.AddIndex(
            model_name="rewind",
            index=models.Index(
                fields=["page", "-rewind_number"],
                name="rewind_page_rnum_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="rewind",
            index=models.Index(
                fields=["page", "-created"],
                name="rewind_page_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="rewindeditorsession",
            index=models.Index(
                fields=["page", "-connected_at"],
                name="rewindsession_page_conn_idx",
            ),
        ),
    ]
