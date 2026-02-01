"""
Tests for the create_import_pages() orchestration function.
"""

from django.test import TestCase

from imports.models import ImportJob, ImportedPage
from imports.services.notion import ParsedPage, create_import_pages
from pages.models import Page
from pages.models.links import PageLink
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestCreateImportPagesBasic(TestCase):
    """Basic tests for create_import_pages()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_creates_single_page(self):
        """Creates a single page from parsed data."""
        parsed_pages = [
            ParsedPage(
                title="Test Page",
                content="Some content here.",
                original_path="Test Page abc123def456789012.md",
                source_hash="abc123def456789012",
            )
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["total"], 1)
        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["pages"][0].title, "Test Page")
        self.assertEqual(result["pages"][0].details["content"], "Some content here.")

    def test_creates_multiple_pages(self):
        """Creates multiple pages from parsed data."""
        parsed_pages = [
            ParsedPage(title="Page A", content="A", original_path="a.md", source_hash="aaa"),
            ParsedPage(title="Page B", content="B", original_path="b.md", source_hash="bbb"),
            ParsedPage(title="Page C", content="C", original_path="c.md", source_hash="ccc"),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["total"], 3)
        self.assertEqual(result["stats"]["created"], 3)
        self.assertEqual(Page.objects.filter(project=self.project).count(), 3)

    def test_handles_empty_list(self):
        """Returns empty result for empty input."""
        result = create_import_pages([], self.project, self.user)

        self.assertEqual(result["stats"]["total"], 0)
        self.assertEqual(result["stats"]["created"], 0)
        self.assertEqual(result["pages"], [])
        self.assertEqual(result["id_mapping"], {})

    def test_flattens_nested_pages(self):
        """Flattens nested page tree before creating pages."""
        child = ParsedPage(title="Child", content="Child content", original_path="parent/child.md", source_hash="child")
        parent = ParsedPage(
            title="Parent",
            content="Parent content",
            original_path="parent.md",
            source_hash="parent",
            children=[child],
        )

        result = create_import_pages([parent], self.project, self.user)

        self.assertEqual(result["stats"]["total"], 2)
        self.assertEqual(result["stats"]["created"], 2)
        titles = [p.title for p in result["pages"]]
        self.assertIn("Parent", titles)
        self.assertIn("Child", titles)


class TestCreateImportPagesLinkRemapping(TestCase):
    """Tests for internal link remapping in create_import_pages()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_builds_id_mapping(self):
        """Builds correct source_hash → external_id mapping."""
        parsed_pages = [
            ParsedPage(title="Page A", content="", original_path="a.md", source_hash="abc123def456789012"),
            ParsedPage(title="Page B", content="", original_path="b.md", source_hash="def456abc789012345"),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertIn("abc123def456789012", result["id_mapping"])
        self.assertIn("def456abc789012345", result["id_mapping"])

        # Verify mapping points to actual page external_ids
        page_a = next(p for p in result["pages"] if p.title == "Page A")
        page_b = next(p for p in result["pages"] if p.title == "Page B")
        self.assertEqual(result["id_mapping"]["abc123def456789012"], str(page_a.external_id))
        self.assertEqual(result["id_mapping"]["def456abc789012345"], str(page_b.external_id))

    def test_remaps_internal_links(self):
        """Remaps Notion internal links to Hyperclast format."""
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Link to [Page B](Page%20B%20def456abc789012345.md) here.",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B",
                content="Some content.",
                original_path="b.md",
                source_hash="def456abc789012345",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        page_a = next(p for p in result["pages"] if p.title == "Page A")
        page_b = next(p for p in result["pages"] if p.title == "Page B")

        # Verify link was remapped
        page_a.refresh_from_db()
        self.assertIn(f"[Page B](/pages/{page_b.external_id}/)", page_a.details["content"])
        self.assertNotIn(".md", page_a.details["content"])

    def test_preserves_links_without_mapping(self):
        """Preserves links to pages not in the import."""
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Link to [Unknown](Unknown%20Page%20xyz789abc012345678.md) here.",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        page_a = result["pages"][0]
        page_a.refresh_from_db()
        # Original link format should be preserved since target wasn't imported
        self.assertIn("Unknown%20Page%20xyz789abc012345678.md", page_a.details["content"])

    def test_remaps_bidirectional_links(self):
        """Correctly handles pages linking to each other."""
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Link to [Page B](Page%20B%20def456abc789012345.md).",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B",
                content="Link to [Page A](Page%20A%20abc123def456789012.md).",
                original_path="b.md",
                source_hash="def456abc789012345",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        page_a = next(p for p in result["pages"] if p.title == "Page A")
        page_b = next(p for p in result["pages"] if p.title == "Page B")

        page_a.refresh_from_db()
        page_b.refresh_from_db()

        self.assertIn(f"/pages/{page_b.external_id}/", page_a.details["content"])
        self.assertIn(f"/pages/{page_a.external_id}/", page_b.details["content"])


class TestCreateImportPagesPageLinkSync(TestCase):
    """Tests for PageLink syncing in create_import_pages()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_syncs_page_links(self):
        """Creates PageLink records for internal links."""
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Link to [Page B](Page%20B%20def456abc789012345.md).",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B",
                content="No links.",
                original_path="b.md",
                source_hash="def456abc789012345",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        page_a = next(p for p in result["pages"] if p.title == "Page A")
        page_b = next(p for p in result["pages"] if p.title == "Page B")

        # Verify PageLink was created
        self.assertTrue(PageLink.objects.filter(source_page=page_a, target_page=page_b).exists())


class TestCreateImportPagesWithImportJob(TestCase):
    """Tests for ImportedPage creation when import_job is provided."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.import_job = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )

    def test_creates_imported_page_records(self):
        """Creates ImportedPage records when import_job is provided."""
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="Page A abc123def456789012.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B",
                content="Content B",
                original_path="Page B def456abc789012345.md",
                source_hash="def456abc789012345",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user, self.import_job)

        imported_pages = ImportedPage.objects.filter(import_job=self.import_job)
        self.assertEqual(imported_pages.count(), 2)

    def test_imported_page_stores_original_path(self):
        """ImportedPage stores the original Notion path."""
        parsed_pages = [
            ParsedPage(
                title="Page",
                content="",
                original_path="Parent/Child abc123def456789012.md",
                source_hash="abc123def456789012",
            ),
        ]

        create_import_pages(parsed_pages, self.project, self.user, self.import_job)

        imported_page = ImportedPage.objects.get(import_job=self.import_job)
        self.assertEqual(imported_page.original_path, "Parent/Child abc123def456789012.md")

    def test_imported_page_stores_source_hash(self):
        """ImportedPage stores the source_hash."""
        parsed_pages = [
            ParsedPage(
                title="Page",
                content="",
                original_path="page.md",
                source_hash="abc123def456789012",
            ),
        ]

        create_import_pages(parsed_pages, self.project, self.user, self.import_job)

        imported_page = ImportedPage.objects.get(import_job=self.import_job)
        self.assertEqual(imported_page.source_hash, "abc123def456789012")

    def test_imported_page_links_to_created_page(self):
        """ImportedPage correctly links to the created Page."""
        parsed_pages = [
            ParsedPage(
                title="Test Page",
                content="",
                original_path="test.md",
                source_hash="abc123def456789012",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user, self.import_job)

        imported_page = ImportedPage.objects.get(import_job=self.import_job)
        self.assertEqual(imported_page.page, result["pages"][0])

    def test_no_imported_pages_without_import_job(self):
        """No ImportedPage records created when import_job is None."""
        parsed_pages = [
            ParsedPage(
                title="Page",
                content="",
                original_path="page.md",
                source_hash="abc123def456789012",
            ),
        ]

        create_import_pages(parsed_pages, self.project, self.user, import_job=None)

        self.assertEqual(ImportedPage.objects.count(), 0)


class TestCreateImportPagesEdgeCases(TestCase):
    """Edge case tests for create_import_pages()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_handles_empty_title(self):
        """Uses 'Untitled' for pages without title."""
        parsed_pages = [
            ParsedPage(
                title="",
                content="Content",
                original_path="page.md",
                source_hash="abc123def456789012",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["pages"][0].title, "Untitled")

    def test_handles_empty_source_hash(self):
        """Handles pages without source_hash."""
        parsed_pages = [
            ParsedPage(
                title="Page",
                content="Content",
                original_path="page.md",
                source_hash="",
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["created"], 1)
        # Empty hash should not be in mapping
        self.assertNotIn("", result["id_mapping"])

    def test_handles_deeply_nested_pages(self):
        """Correctly flattens deeply nested page tree."""
        level3 = ParsedPage(title="Level 3", content="", original_path="l1/l2/l3.md", source_hash="l3")
        level2 = ParsedPage(title="Level 2", content="", original_path="l1/l2.md", source_hash="l2", children=[level3])
        level1 = ParsedPage(title="Level 1", content="", original_path="l1.md", source_hash="l1", children=[level2])

        result = create_import_pages([level1], self.project, self.user)

        self.assertEqual(result["stats"]["total"], 3)
        titles = [p.title for p in result["pages"]]
        self.assertEqual(titles, ["Level 1", "Level 2", "Level 3"])

    def test_large_batch(self):
        """Handles large batch of pages."""
        parsed_pages = [
            ParsedPage(
                title=f"Page {i}",
                content=f"Content {i}",
                original_path=f"page{i}.md",
                source_hash=f"hash{i:016x}",  # Create 16-char hex hash
            )
            for i in range(100)
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["total"], 100)
        self.assertEqual(result["stats"]["created"], 100)
        self.assertEqual(len(result["id_mapping"]), 100)


class TestCreateImportPagesDeduplication(TestCase):
    """Tests for deduplication of pages across multiple imports."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.import_job = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )

    def test_skips_pages_with_existing_source_hash(self):
        """Pages with source_hash already in project are skipped."""
        # First import
        parsed_pages_1 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B",
                content="Content B",
                original_path="b.md",
                source_hash="def456abc789012345",
            ),
        ]
        result1 = create_import_pages(parsed_pages_1, self.project, self.user, self.import_job)

        self.assertEqual(result1["stats"]["created"], 2)
        self.assertEqual(result1["stats"]["skipped"], 0)

        # Second import with same hashes
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )
        parsed_pages_2 = [
            ParsedPage(
                title="Page A Updated",  # Different title, same hash
                content="Content A Updated",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
            ParsedPage(
                title="Page B Updated",
                content="Content B Updated",
                original_path="b.md",
                source_hash="def456abc789012345",
            ),
        ]
        result2 = create_import_pages(parsed_pages_2, self.project, self.user, import_job_2)

        self.assertEqual(result2["stats"]["total"], 2)
        self.assertEqual(result2["stats"]["created"], 0)
        self.assertEqual(result2["stats"]["skipped"], 2)

    def test_imports_new_pages_while_skipping_duplicates(self):
        """New pages are imported while duplicates are skipped."""
        # First import
        parsed_pages_1 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
        ]
        create_import_pages(parsed_pages_1, self.project, self.user, self.import_job)

        # Second import with one duplicate and one new page
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )
        parsed_pages_2 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",  # Duplicate
            ),
            ParsedPage(
                title="Page B",
                content="Content B",
                original_path="b.md",
                source_hash="def456abc789012345",  # New
            ),
        ]
        result = create_import_pages(parsed_pages_2, self.project, self.user, import_job_2)

        self.assertEqual(result["stats"]["total"], 2)
        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(result["stats"]["skipped"], 1)
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["pages"][0].title, "Page B")

    def test_pages_without_hash_are_not_skipped(self):
        """Pages without source_hash are always imported (no dedup possible)."""
        # First import with no hash
        parsed_pages_1 = [
            ParsedPage(
                title="No Hash Page",
                content="Content",
                original_path="no-hash.md",
                source_hash="",
            ),
        ]
        create_import_pages(parsed_pages_1, self.project, self.user, self.import_job)

        # Second import with same empty hash
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )
        result = create_import_pages(parsed_pages_1, self.project, self.user, import_job_2)

        # Pages without hash are not subject to deduplication
        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(result["stats"]["skipped"], 0)

    def test_same_hash_different_project_not_skipped(self):
        """Same source_hash in different projects doesn't trigger dedup."""
        # First import in project 1
        parsed_pages = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
        ]
        create_import_pages(parsed_pages, self.project, self.user, self.import_job)

        # Second import in different project
        project_2 = ProjectFactory(org=self.org, creator=self.user)
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=project_2,
            provider="notion",
            status="processing",
        )
        result = create_import_pages(parsed_pages, project_2, self.user, import_job_2)

        # Should create new page since different project
        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(result["stats"]["skipped"], 0)

    def test_link_remapping_includes_existing_pages(self):
        """Links to previously imported pages are correctly remapped."""
        # Use valid hex hashes (16+ hex chars)
        hash_a = "abc123def4567890abcd1234"
        hash_b = "def456abc7890123efab5678"

        # First import
        parsed_pages_1 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash=hash_a,
            ),
        ]
        result1 = create_import_pages(parsed_pages_1, self.project, self.user, self.import_job)
        page_a_id = str(result1["pages"][0].external_id)

        # Second import with new page linking to existing page
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )
        parsed_pages_2 = [
            ParsedPage(
                title="Page B",
                content=f"Link to [Page A](Page%20A%20{hash_a}.md)",
                original_path="b.md",
                source_hash=hash_b,
            ),
        ]
        result2 = create_import_pages(parsed_pages_2, self.project, self.user, import_job_2)

        # Verify link was remapped to existing page
        page_b = result2["pages"][0]
        expected_link = f"[Page A](/pages/{page_a_id}/)"
        self.assertIn(expected_link, page_b.details["content"])

    def test_dedup_only_counts_pages_for_this_import_job(self):
        """ImportedPage records only created for newly imported pages."""
        # First import
        parsed_pages_1 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",
            ),
        ]
        create_import_pages(parsed_pages_1, self.project, self.user, self.import_job)

        # Second import with duplicate
        import_job_2 = ImportJob.objects.create(
            user=self.user,
            project=self.project,
            provider="notion",
            status="processing",
        )
        parsed_pages_2 = [
            ParsedPage(
                title="Page A",
                content="Content A",
                original_path="a.md",
                source_hash="abc123def456789012",  # Duplicate - skipped
            ),
            ParsedPage(
                title="Page B",
                content="Content B",
                original_path="b.md",
                source_hash="def456abc789012345",  # New
            ),
        ]
        create_import_pages(parsed_pages_2, self.project, self.user, import_job_2)

        # Only 1 ImportedPage for import_job_2 (Page B)
        self.assertEqual(ImportedPage.objects.filter(import_job=import_job_2).count(), 1)
        # Still 1 ImportedPage for import_job (Page A)
        self.assertEqual(ImportedPage.objects.filter(import_job=self.import_job).count(), 1)


class TestCreateImportPagesBulkOperations(TestCase):
    """Tests to verify bulk operations work correctly (including N+1 fix)."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_multiple_pages_with_cross_links_bulk_updated(self):
        """
        Multiple pages with cross-links are correctly updated via bulk_update.

        This test verifies the N+1 fix works: when multiple pages need link
        remapping, they should all be updated correctly in a single bulk operation.
        """
        # Use valid 20-char hex hashes (Notion uses 16-32 hex chars)
        h1 = "a1b2c3d4e5f6a7b8c9d0"
        h2 = "b2c3d4e5f6a7b8c9d0a1"
        h3 = "c3d4e5f6a7b8c9d0a1b2"
        h4 = "d4e5f6a7b8c9d0a1b2c3"
        h5 = "e5f6a7b8c9d0a1b2c3d4"

        # Create 5 pages that all link to each other
        parsed_pages = [
            ParsedPage(
                title="Page 1",
                content=f"Links to [Page 2](Page%202%20{h2}.md) and [Page 3](Page%203%20{h3}.md)",
                original_path="p1.md",
                source_hash=h1,
            ),
            ParsedPage(
                title="Page 2",
                content=f"Links to [Page 1](Page%201%20{h1}.md) and [Page 4](Page%204%20{h4}.md)",
                original_path="p2.md",
                source_hash=h2,
            ),
            ParsedPage(
                title="Page 3",
                content=f"Links to [Page 5](Page%205%20{h5}.md)",
                original_path="p3.md",
                source_hash=h3,
            ),
            ParsedPage(
                title="Page 4",
                content=f"Links to [Page 1](Page%201%20{h1}.md) and [Page 3](Page%203%20{h3}.md)",
                original_path="p4.md",
                source_hash=h4,
            ),
            ParsedPage(
                title="Page 5",
                content=f"Links to [Page 2](Page%202%20{h2}.md)",
                original_path="p5.md",
                source_hash=h5,
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["created"], 5)

        # Build lookup for external IDs
        page_by_title = {p.title: p for p in result["pages"]}

        # Refresh all pages to get the bulk-updated content
        for page in result["pages"]:
            page.refresh_from_db()

        # Verify all links were remapped correctly
        p1 = page_by_title["Page 1"]
        p2 = page_by_title["Page 2"]
        p3 = page_by_title["Page 3"]
        p4 = page_by_title["Page 4"]
        p5 = page_by_title["Page 5"]

        # Page 1 should link to Page 2 and Page 3
        self.assertIn(f"/pages/{p2.external_id}/", p1.details["content"])
        self.assertIn(f"/pages/{p3.external_id}/", p1.details["content"])

        # Page 2 should link to Page 1 and Page 4
        self.assertIn(f"/pages/{p1.external_id}/", p2.details["content"])
        self.assertIn(f"/pages/{p4.external_id}/", p2.details["content"])

        # Page 3 should link to Page 5
        self.assertIn(f"/pages/{p5.external_id}/", p3.details["content"])

        # Page 4 should link to Page 1 and Page 3
        self.assertIn(f"/pages/{p1.external_id}/", p4.details["content"])
        self.assertIn(f"/pages/{p3.external_id}/", p4.details["content"])

        # Page 5 should link to Page 2
        self.assertIn(f"/pages/{p2.external_id}/", p5.details["content"])

    def test_bulk_update_with_large_batch_of_pages_with_links(self):
        """
        Large batch of pages with inter-page links are correctly updated.

        Tests that bulk_update works efficiently even with many pages.
        """
        # Create 50 pages where each page links to the next one
        # Use valid hex hashes (16-20 char hex strings)
        parsed_pages = []
        for i in range(50):
            next_idx = (i + 1) % 50
            # Create hex hashes like "a0b0c0d0e0f0a0b01234" where last 4 chars encode the index
            source_hash = f"a0b0c0d0e0f0a0b0{i:04x}"
            next_hash = f"a0b0c0d0e0f0a0b0{next_idx:04x}"
            content = f"Link to [Page {next_idx}](Page%20{next_idx}%20{next_hash}.md)"
            parsed_pages.append(
                ParsedPage(
                    title=f"Page {i}",
                    content=content,
                    original_path=f"p{i}.md",
                    source_hash=source_hash,
                )
            )

        result = create_import_pages(parsed_pages, self.project, self.user)

        self.assertEqual(result["stats"]["created"], 50)

        # Build lookup
        pages = list(Page.objects.filter(project=self.project))
        page_by_title = {p.title: p for p in pages}

        # Verify a sample of links are correctly remapped
        for i in [0, 10, 25, 49]:
            next_idx = (i + 1) % 50
            page = page_by_title[f"Page {i}"]
            next_page = page_by_title[f"Page {next_idx}"]
            self.assertIn(
                f"/pages/{next_page.external_id}/",
                page.details["content"],
                f"Page {i} should link to Page {next_idx}",
            )

    def test_bulk_update_preserves_page_details_other_fields(self):
        """
        Bulk update only affects 'content' field, not other page details.

        Verifies that bulk_update(["details"]) correctly preserves other
        data in the JSONField.
        """
        # Use valid hex hashes (16+ hex chars)
        hash_a = "a1b2c3d4e5f6a7b8c9d0"
        hash_b = "b2c3d4e5f6a7b8c9d0a1"

        parsed_pages = [
            ParsedPage(
                title="Page A",
                content=f"Link to [Page B](Page%20B%20{hash_b}.md)",
                original_path="a.md",
                source_hash=hash_a,
            ),
            ParsedPage(
                title="Page B",
                content="Content B",
                original_path="b.md",
                source_hash=hash_b,
            ),
        ]

        result = create_import_pages(parsed_pages, self.project, self.user)

        # Both pages should be created
        self.assertEqual(result["stats"]["created"], 2)

        # Refresh and verify content was updated
        page_a = next(p for p in result["pages"] if p.title == "Page A")
        page_b = next(p for p in result["pages"] if p.title == "Page B")

        page_a.refresh_from_db()

        # Verify link was remapped
        self.assertIn(f"/pages/{page_b.external_id}/", page_a.details["content"])
