from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from ask.models import PageEmbedding
from ask.tests.factories import PageEmbeddingFactory
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageEmbeddingModel(TestCase):
    def test_page_embedding_creation(self):
        vector = [0.0 for i in range(1536)]
        page = PageFactory()

        embedding = PageEmbedding.objects.create(page=page, embedding=vector, computed=timezone.now())

        self.assertEqual(page, embedding.page)
        self.assertEqual(len(embedding.embedding), 1536)

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_or_create_page_embedding_create(self, mocked_compute):
        values = [0.5 for i in range(1536)]
        content = "Page text"
        page = PageFactory(details={"content": content})
        mocked_compute.return_value = values

        embedding, action = PageEmbedding.objects.update_or_create_page_embedding(page)

        self.assertEqual(action, "created")
        self.assertEqual(embedding.page, page)
        self.assertEqual(embedding.embedding, values)
        self.assertIsInstance(embedding.computed, datetime)
        self.assertIsNotNone(embedding.content_hash)

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_or_create_page_embedding_update(self, mocked_compute):
        values = [0.5 for i in range(1536)]
        content = "Page text"
        page = PageFactory(details={"content": content})
        mocked_compute.return_value = values
        orig_embedding = PageEmbeddingFactory(page=page, content_hash="old_hash")
        orig_values = orig_embedding.embedding

        embedding, action = PageEmbedding.objects.update_or_create_page_embedding(page)

        self.assertEqual(action, "updated")
        self.assertEqual(embedding.page, page)
        self.assertEqual(embedding.embedding, values)
        self.assertNotEqual(orig_values, values)
        self.assertIsInstance(embedding.computed, datetime)
        self.assertNotEqual(embedding.content_hash, "old_hash")
        self.assertEqual(PageEmbedding.objects.filter(page=page).count(), 1)

    @patch("ask.models.embeddings.compute_embedding")
    @patch("ask.models.embeddings.hashify")
    def test_update_or_create_page_embedding_skipped_when_hash_matches(self, mocked_hashify, mocked_compute):
        """Test that embedding computation is skipped when content hash matches existing embedding."""
        values = [0.5 for i in range(1536)]
        content = "Page text"
        page = PageFactory(details={"content": content})

        # Create existing embedding with the same content hash
        content_hash = "abc123hash"
        mocked_hashify.return_value = content_hash
        orig_embedding = PageEmbeddingFactory(page=page, content_hash=content_hash, embedding=values)
        orig_computed = orig_embedding.computed

        embedding, action = PageEmbedding.objects.update_or_create_page_embedding(page)

        self.assertEqual(action, "skipped")
        self.assertEqual(embedding.page, page)
        self.assertEqual(len(embedding.embedding), 1536)
        self.assertEqual(embedding.content_hash, content_hash)
        self.assertEqual(embedding.computed, orig_computed)  # Should not update computed time

        # Verify compute_embedding was NOT called (since hash matched)
        mocked_compute.assert_not_called()

        # Verify only one embedding exists
        self.assertEqual(PageEmbedding.objects.filter(page=page).count(), 1)

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_or_create_page_embedding_without_title_and_content(self, mocked_compute):
        values = [0.5 for i in range(1536)]
        page = PageFactory(title="")
        mocked_compute.return_value = values

        with self.assertRaises(ValueError):
            PageEmbedding.objects.update_or_create_page_embedding(page)
            self.assertFalse(mocked_compute.called)

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_or_create_page_embedding_indexes_pdf_extracted_text(self, mocked_compute):
        """PDF pages contribute extracted_text to the embedding input — not the empty `content` field."""
        values = [0.5 for _ in range(1536)]
        page = PageFactory(
            title="Annual Report",
            details={
                "filetype": "pdf",
                "schema_version": 2,
                "content": "",
                "extracted_text": "Revenue grew 12% year over year.",
                "pdf_file_id": "pdf-1",
            },
        )
        mocked_compute.return_value = values

        embedding, action = PageEmbedding.objects.update_or_create_page_embedding(page)

        self.assertEqual(action, "created")
        self.assertEqual(embedding.page, page)
        # The compute_embedding call should have received the title + extracted_text body.
        called_input = mocked_compute.call_args[0][0]
        self.assertIn("Annual Report", called_input)
        self.assertIn("Revenue grew 12% year over year.", called_input)


class TestPageEmbeddingComputeFailures(TestCase):
    """The embedding column is NOT NULL — when compute_embedding fails, the manager
    must propagate (not insert/update with None). Regression tests for the
    IntegrityError observed in production when a user had no AI provider configured.
    """

    @patch("ask.models.embeddings.compute_embedding")
    def test_create_branch_propagates_when_compute_raises(self, mocked_compute):
        """If compute_embedding raises during the create path, the exception must bubble up."""
        page = PageFactory(details={"content": "Page text"})
        mocked_compute.side_effect = ValueError("api_key is required")

        with self.assertRaises(ValueError):
            PageEmbedding.objects.update_or_create_page_embedding(page)

    @patch("ask.models.embeddings.compute_embedding")
    def test_create_branch_does_not_persist_when_compute_raises(self, mocked_compute):
        """No PageEmbedding row should be created when compute_embedding fails."""
        page = PageFactory(details={"content": "Page text"})
        mocked_compute.side_effect = ValueError("api_key is required")

        with self.assertRaises(ValueError):
            PageEmbedding.objects.update_or_create_page_embedding(page)

        self.assertFalse(PageEmbedding.objects.filter(page=page).exists())

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_branch_propagates_when_compute_raises(self, mocked_compute):
        """If compute_embedding raises during the update path, the exception must bubble up."""
        page = PageFactory(details={"content": "New content"})
        PageEmbeddingFactory(page=page, content_hash="stale_hash")
        mocked_compute.side_effect = ValueError("api_key is required")

        with self.assertRaises(ValueError):
            PageEmbedding.objects.update_or_create_page_embedding(page)

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_branch_leaves_existing_row_intact_when_compute_raises(self, mocked_compute):
        """When the update path fails, the previously-stored embedding and hash must be unchanged."""
        page = PageFactory(details={"content": "New content"})
        original_values = [0.5] * 1536
        original_hash = "original_hash"
        original_embedding = PageEmbeddingFactory(
            page=page,
            embedding=original_values,
            content_hash=original_hash,
        )
        original_computed = original_embedding.computed
        mocked_compute.side_effect = ValueError("api_key is required")

        with self.assertRaises(ValueError):
            PageEmbedding.objects.update_or_create_page_embedding(page)

        original_embedding.refresh_from_db()
        self.assertEqual(list(original_embedding.embedding), original_values)
        self.assertEqual(original_embedding.content_hash, original_hash)
        self.assertEqual(original_embedding.computed, original_computed)

    @patch("ask.models.embeddings.compute_embedding")
    def test_create_branch_passes_raise_exception_true(self, mocked_compute):
        """Regression guard: the manager must opt into raise_exception so failures
        propagate instead of compute_embedding swallowing them and returning None."""
        page = PageFactory(details={"content": "Page text"})
        mocked_compute.return_value = [0.5] * 1536

        PageEmbedding.objects.update_or_create_page_embedding(page)

        _, kwargs = mocked_compute.call_args
        self.assertTrue(kwargs.get("raise_exception"))

    @patch("ask.models.embeddings.compute_embedding")
    def test_update_branch_passes_raise_exception_true(self, mocked_compute):
        """Same regression guard for the update path."""
        page = PageFactory(details={"content": "New content"})
        PageEmbeddingFactory(page=page, content_hash="stale_hash")
        mocked_compute.return_value = [0.5] * 1536

        PageEmbedding.objects.update_or_create_page_embedding(page)

        _, kwargs = mocked_compute.call_args
        self.assertTrue(kwargs.get("raise_exception"))


class TestPageEmbeddingSimilaritySearch(TestCase):
    """Test the similarity_search manager method."""

    def setUp(self):
        """Set up test data for similarity search tests."""
        # Create users
        self.user1 = PageFactory().creator  # Owner of test pages
        self.user2 = PageFactory().creator  # Different user

        # Create a sample query embedding (all zeros for simplicity)
        self.query_embedding = [0.0] * 1536

        # Create pages owned by user1
        self.page1 = PageFactory(creator=self.user1, title="First Page")
        self.page2 = PageFactory(creator=self.user1, title="Second Page")
        self.page3 = PageFactory(creator=self.user1, title="Third Page")
        self.page4 = PageFactory(creator=self.user1, title="Fourth Page")
        self.page5 = PageFactory(creator=self.user1, title="Fifth Page")
        self.page6 = PageFactory(creator=self.user1, title="Sixth Page")

        # Create embeddings for all pages
        # Use slightly different embeddings to test distance ordering
        self.embedding1 = PageEmbeddingFactory(page=self.page1, embedding=[0.1] + [0.0] * 1535)  # Distance ~0.1
        self.embedding2 = PageEmbeddingFactory(page=self.page2, embedding=[0.2] + [0.0] * 1535)  # Distance ~0.2
        self.embedding3 = PageEmbeddingFactory(page=self.page3, embedding=[0.3] + [0.0] * 1535)  # Distance ~0.3
        self.embedding4 = PageEmbeddingFactory(page=self.page4, embedding=[0.4] + [0.0] * 1535)  # Distance ~0.4
        self.embedding5 = PageEmbeddingFactory(page=self.page5, embedding=[0.5] + [0.0] * 1535)  # Distance ~0.5
        self.embedding6 = PageEmbeddingFactory(page=self.page6, embedding=[0.6] + [0.0] * 1535)  # Distance ~0.6

    def test_similarity_search_returns_pages_user_can_access(self):
        """Test that similarity search returns only pages the user can access."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=5
        )

        # Should return 5 closest pages that user1 can access
        self.assertEqual(results.count(), 5)

        # Verify all returned pages are accessible by user1 via the three-tier model
        accessible_page_ids = set(Page.objects.get_user_accessible_pages(self.user1).values_list("id", flat=True))
        for embedding in results:
            self.assertIn(embedding.page.id, accessible_page_ids)

    def test_similarity_search_excludes_other_users_pages(self):
        """Test that similarity search doesn't return pages from other users."""
        # Create a page owned by user2
        other_page = PageFactory(creator=self.user2, title="Other User Page")
        PageEmbeddingFactory(page=other_page, embedding=[0.05] + [0.0] * 1535)  # Very close distance

        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=10
        )

        # Should not include other_page
        result_page_ids = [emb.page.id for emb in results]
        self.assertNotIn(other_page.id, result_page_ids)

    def test_similarity_search_includes_shared_pages(self):
        """Test that similarity search includes pages shared with the user."""
        # Create a page owned by user2 but shared with user1
        shared_page = PageFactory(creator=self.user2, title="Shared Page")
        shared_page.editors.add(self.user1)  # Share with user1

        shared_embedding = PageEmbeddingFactory(
            page=shared_page, embedding=[0.05] + [0.0] * 1535  # Very close distance
        )

        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=10
        )

        # Should include shared_page
        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(shared_page.id, result_page_ids)

    def test_similarity_search_orders_by_distance(self):
        """Test that results are ordered by cosine distance (closest first)."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=6
        )

        results_list = list(results)

        # Should be ordered: page1, page2, page3, page4, page5, page6
        self.assertEqual(results_list[0].page.id, self.page1.id)
        self.assertEqual(results_list[1].page.id, self.page2.id)
        self.assertEqual(results_list[2].page.id, self.page3.id)
        self.assertEqual(results_list[3].page.id, self.page4.id)
        self.assertEqual(results_list[4].page.id, self.page5.id)
        self.assertEqual(results_list[5].page.id, self.page6.id)

    def test_similarity_search_respects_limit(self):
        """Test that similarity search respects the limit parameter."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=3
        )

        self.assertEqual(results.count(), 3)

    def test_similarity_search_default_limit(self):
        """Test that similarity search uses default limit of 5."""
        results = PageEmbedding.objects.similarity_search(user=self.user1, input_embedding=self.query_embedding)

        self.assertEqual(results.count(), 5)

    def test_similarity_search_with_exclude_pages(self):
        """Test that similarity search excludes specified pages."""
        # Exclude page1 and page2 by external_id
        exclude_ids = [str(self.page1.external_id), str(self.page2.external_id)]

        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, exclude_pages=exclude_ids, limit=5
        )

        result_external_ids = [str(emb.page.external_id) for emb in results]

        # Should not include page1 or page2
        self.assertNotIn(str(self.page1.external_id), result_external_ids)
        self.assertNotIn(str(self.page2.external_id), result_external_ids)

        # Should include page3, page4, page5 (next closest)
        self.assertIn(str(self.page3.external_id), result_external_ids)
        self.assertIn(str(self.page4.external_id), result_external_ids)
        self.assertIn(str(self.page5.external_id), result_external_ids)

    def test_similarity_search_exclude_pages_maintains_limit(self):
        """Test that excluding pages applies before limit (not after)."""
        # Exclude page1 and page2
        exclude_ids = [str(self.page1.external_id), str(self.page2.external_id)]

        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, exclude_pages=exclude_ids, limit=5
        )

        # We have 6 pages total. Excluding 2 leaves 4.
        # With limit=5, we should get all 4 remaining pages.
        # This verifies that exclude happens BEFORE limit (not after)
        self.assertEqual(results.count(), 4)

        # Verify we got the right pages (page3, page4, page5, page6)
        result_page_ids = {emb.page.id for emb in results}
        expected_page_ids = {self.page3.id, self.page4.id, self.page5.id, self.page6.id}
        self.assertEqual(result_page_ids, expected_page_ids)

    def test_similarity_search_with_empty_exclude_list(self):
        """Test that similarity search works with empty exclude list."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, exclude_pages=[], limit=5
        )

        self.assertEqual(results.count(), 5)

    def test_similarity_search_with_none_exclude(self):
        """Test that similarity search works with None exclude parameter."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, exclude_pages=None, limit=5
        )

        self.assertEqual(results.count(), 5)

    def test_similarity_search_select_related_page(self):
        """Test that similarity search uses select_related for efficiency."""
        results = PageEmbedding.objects.similarity_search(
            user=self.user1, input_embedding=self.query_embedding, limit=3
        )

        # First, evaluate the queryset (this will execute 1 query)
        results_list = list(results)

        # Now access page properties without triggering additional queries
        # If select_related works, accessing page.title won't trigger another query
        with self.assertNumQueries(0):
            for embedding in results_list:
                _ = embedding.page.title
                _ = embedding.page.external_id

    def test_similarity_search_no_embeddings_for_user(self):
        """Test similarity search when user has no page embeddings."""
        # Create a new user with no pages
        new_user = PageFactory().creator

        results = PageEmbedding.objects.similarity_search(user=new_user, input_embedding=self.query_embedding, limit=5)

        self.assertEqual(results.count(), 0)

    def test_similarity_search_with_different_embedding_dimensions(self):
        """Test that similarity search works with the expected embedding dimensions."""
        # Create an embedding with different values
        different_embedding = [0.1] * 1536

        results = PageEmbedding.objects.similarity_search(user=self.user1, input_embedding=different_embedding, limit=5)

        self.assertEqual(results.count(), 5)

        # Results should have distance annotations
        for embedding in results:
            self.assertTrue(hasattr(embedding, "distance"))
            self.assertIsNotNone(embedding.distance)


class TestSimilaritySearchMultiTierAccess(TestCase):
    """Test that similarity_search uses the full three-tier access model."""

    def setUp(self):
        self.query_embedding = [0.0] * 1536
        self.user = UserFactory()

    def test_similarity_search_includes_org_admin_pages(self):
        """Tier 0: Org admins can find pages in their org via similarity search."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role="admin")
        project = ProjectFactory(org=org, creator=UserFactory())
        # Page created by another user in the same org
        page = PageFactory(project=project, creator=project.creator, title="Admin Page")
        PageEmbeddingFactory(page=page, embedding=[0.1] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(page.id, result_page_ids)

    def test_similarity_search_includes_org_member_pages(self):
        """Tier 1: Org members can find pages when org_members_can_access is True."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role="member")
        project = ProjectFactory(org=org, creator=UserFactory(), org_members_can_access=True)
        page = PageFactory(project=project, creator=project.creator, title="Org Member Page")
        PageEmbeddingFactory(page=page, embedding=[0.1] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(page.id, result_page_ids)

    def test_similarity_search_excludes_org_member_pages_when_access_disabled(self):
        """Tier 1: Org members cannot find pages when org_members_can_access is False."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role="member")
        project = ProjectFactory(org=org, creator=UserFactory(), org_members_can_access=False)
        page = PageFactory(project=project, creator=project.creator, title="Restricted Page")
        PageEmbeddingFactory(page=page, embedding=[0.1] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertNotIn(page.id, result_page_ids)

    def test_similarity_search_includes_project_editor_pages(self):
        """Tier 2: Project editors can find pages in their project via similarity search."""
        org = OrgFactory()
        project = ProjectFactory(org=org, creator=UserFactory())
        ProjectEditorFactory(user=self.user, project=project)
        page = PageFactory(project=project, creator=project.creator, title="Project Editor Page")
        PageEmbeddingFactory(page=page, embedding=[0.1] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(page.id, result_page_ids)

    def test_similarity_search_includes_page_editor_pages(self):
        """Tier 3: Direct page editors can find pages via similarity search."""
        page = PageFactory(creator=UserFactory(), title="Shared Page")
        page.editors.add(self.user)
        PageEmbeddingFactory(page=page, embedding=[0.1] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(page.id, result_page_ids)

    def test_similarity_search_excludes_inaccessible_pages(self):
        """Pages not accessible via any tier should not appear in similarity search."""
        # Page in a different org, not shared with user
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, creator=UserFactory())
        page = PageFactory(project=other_project, creator=other_project.creator, title="Inaccessible Page")
        PageEmbeddingFactory(page=page, embedding=[0.05] + [0.0] * 1535)  # Very close distance

        results = PageEmbedding.objects.similarity_search(user=self.user, input_embedding=self.query_embedding, limit=5)

        result_page_ids = [emb.page.id for emb in results]
        self.assertNotIn(page.id, result_page_ids)

    def test_similarity_search_org_filter_excludes_other_org_pages(self):
        """When org_id is supplied, pages in other orgs the user belongs to are filtered out.

        Enforces the cross-org boundary at the retrieval layer: a page in Org
        A must never get a citation from Org B even when the user has access
        to both.
        """
        org_a = OrgFactory()
        OrgMemberFactory(org=org_a, user=self.user, role="admin")
        project_a = ProjectFactory(org=org_a, creator=self.user)
        page_a = PageFactory(project=project_a, creator=self.user, title="Org A Page")
        PageEmbeddingFactory(page=page_a, embedding=[0.1] + [0.0] * 1535)

        org_b = OrgFactory()
        OrgMemberFactory(org=org_b, user=self.user, role="admin")
        project_b = ProjectFactory(org=org_b, creator=self.user)
        page_b = PageFactory(project=project_b, creator=self.user, title="Org B Page")
        # Closer distance — without the boundary, Org B would beat Org A.
        PageEmbeddingFactory(page=page_b, embedding=[0.05] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(
            user=self.user,
            input_embedding=self.query_embedding,
            limit=5,
            org_id=str(org_a.external_id),
        )

        result_page_ids = [emb.page.id for emb in results]
        self.assertIn(page_a.id, result_page_ids)
        self.assertNotIn(page_b.id, result_page_ids)

    def test_similarity_search_org_filter_for_non_member_returns_empty(self):
        """Passing an org_id the user is not a member of yields zero results.

        Membership is enforced by get_user_accessible_pages, so combining
        with org_id never widens access — it can only narrow it.
        """
        outsider = UserFactory()
        outsider_org = OrgFactory()
        OrgMemberFactory(org=outsider_org, user=outsider, role="admin")
        outsider_project = ProjectFactory(org=outsider_org, creator=outsider)
        outsider_page = PageFactory(project=outsider_project, creator=outsider, title="Secret")
        PageEmbeddingFactory(page=outsider_page, embedding=[0.05] + [0.0] * 1535)

        results = PageEmbedding.objects.similarity_search(
            user=self.user,
            input_embedding=self.query_embedding,
            limit=5,
            org_id=str(outsider_org.external_id),
        )

        self.assertEqual(results.count(), 0)
