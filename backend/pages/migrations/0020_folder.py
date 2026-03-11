import django.db.models
from django.db import migrations, models

import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0019_alter_rewind_id"),
    ]

    operations = [
        # Step 1: Create Folder table
        migrations.CreateModel(
            name="Folder",
            fields=[
                (
                    "id",
                    models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "created",
                    django.db.models.fields.DateTimeField(auto_now_add=True),
                ),
                (
                    "modified",
                    django.db.models.fields.DateTimeField(auto_now=True),
                ),
                ("external_id", core.fields.UniqueIDTextField(editable=False, unique=True)),
                ("name", models.TextField()),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="folders",
                        to="pages.project",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subfolders",
                        to="pages.folder",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        # Step 2: Add constraints and indexes to Folder
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                fields=("project", "parent", "name"),
                name="unique_folder_name_in_parent",
            ),
        ),
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                condition=models.Q(parent__isnull=True),
                fields=("project", "name"),
                name="unique_root_folder_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                fields=("project", "id"),
                name="folder_project_id_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="folder",
            index=models.Index(fields=["project", "parent"], name="pages_folde_project_b1e7b5_idx"),
        ),
        # Step 3: Add nullable folder FK to Page
        migrations.AddField(
            model_name="page",
            name="folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pages",
                to="pages.folder",
            ),
        ),
        # Step 4: Add composite FK constraints via raw SQL
        migrations.RunSQL(
            sql=[
                # Page.folder must belong to the same project as the page
                """
                ALTER TABLE pages_page
                    ADD CONSTRAINT page_folder_same_project
                    FOREIGN KEY (project_id, folder_id)
                    REFERENCES pages_folder (project_id, id)
                    ON DELETE SET NULL;
                """,
                # Folder.parent must belong to the same project
                """
                ALTER TABLE pages_folder
                    ADD CONSTRAINT folder_parent_same_project
                    FOREIGN KEY (project_id, parent_id)
                    REFERENCES pages_folder (project_id, id)
                    ON DELETE CASCADE;
                """,
            ],
            reverse_sql=[
                "ALTER TABLE pages_page DROP CONSTRAINT IF EXISTS page_folder_same_project;",
                "ALTER TABLE pages_folder DROP CONSTRAINT IF EXISTS folder_parent_same_project;",
            ],
        ),
    ]
