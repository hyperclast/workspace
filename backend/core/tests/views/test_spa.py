from http import HTTPStatus

from django.test import TestCase, override_settings

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from core.views.home import get_app_config


class TestHomepageUnauthenticated(BaseViewTestCase):
    """Test homepage view for unauthenticated users."""

    def test_unauthenticated_user_gets_landing(self):
        """Unauthenticated user should get landing page."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/landing.html")


class TestHomepageAuthenticated(BaseAuthenticatedViewTestCase):
    """Test homepage view for authenticated users."""

    url_name = "core:home"

    def test_authenticated_user_without_pages_redirects_to_welcome(self):
        """Authenticated user without pages should redirect to welcome page."""
        response = self.client.get("/")

        self.assertRedirects(response, "/welcome/")

    def test_authenticated_user_with_pages_redirects_to_first_page(self):
        """Authenticated user with pages should redirect to first page."""
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.tests.factories import OrgFactory

        org = OrgFactory()
        org.members.add(self.user)
        project = ProjectFactory(org=org, creator=self.user)
        page = PageFactory(project=project, creator=self.user)
        page.editors.add(self.user)

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{page.external_id}/")


class TestHomepageRedirectChain(BaseAuthenticatedViewTestCase):
    """The homepage redirect should land on the page the user themselves
    last opened. Collaborators editing other pages must not change that
    target — `modified` is a per-row "anyone touched this" stamp, not
    "what was I doing." We resolve via the user-written pointers
    `Profile.current_org` and `Profile.org_state[<org>]["last_page_id"]`.
    """

    def setUp(self):
        super().setUp()
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        # Two orgs the user belongs to.
        self.org_a = OrgFactory()
        OrgMember.objects.create(org=self.org_a, user=self.user, role="admin")
        self.project_a = ProjectFactory(org=self.org_a, creator=self.user)

        self.org_b = OrgFactory()
        OrgMember.objects.create(org=self.org_b, user=self.user, role="admin")
        self.project_b = ProjectFactory(org=self.org_b, creator=self.user)

    def _set_current_org(self, org):
        self.user.profile.current_org = org
        self.user.profile.save(update_fields=["current_org", "modified"])

    def _set_last_page(self, org, page):
        org_state = dict(self.user.profile.org_state or {})
        bucket = dict(org_state.get(org.external_id, {}))
        bucket["last_page_id"] = page.external_id if page else None
        org_state[org.external_id] = bucket
        self.user.profile.org_state = org_state
        self.user.profile.save(update_fields=["org_state", "modified"])

    def test_redirects_to_persisted_last_page_in_selected_org_even_when_other_org_is_newer(self):
        """The selected org's last_page wins over a globally-newer page in
        another org. This is the regression for the compliment behaviour
        when collaborators are editing pages in other workspaces."""
        from pages.tests.factories import PageFactory

        # The user's actual last open page (Org A) — older.
        my_page = PageFactory(project=self.project_a, creator=self.user, title="Mine")
        # A page in Org B that the user can access but didn't touch
        # recently. It's the most recently modified accessible page.
        PageFactory(project=self.project_b, creator=self.user, title="Other-org noise")

        self._set_current_org(self.org_a)
        self._set_last_page(self.org_a, my_page)

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{my_page.external_id}/")

    def test_does_not_redirect_to_persisted_last_page_in_a_different_org(self):
        """A stale or malformed bucket can hold a `last_page_id` pointing at
        a page in a different org. The redirect must stay scoped to the
        user's selected org and fall through to Path 2 instead of leaking
        across the workspace boundary."""
        from pages.tests.factories import PageFactory

        in_org_page = PageFactory(project=self.project_a, creator=self.user, title="In-org fallback")
        cross_org_page = PageFactory(project=self.project_b, creator=self.user, title="Cross-org page")

        self._set_current_org(self.org_a)
        # Persist a pointer under Org A that actually resolves to a page
        # in Org B — the regression we're guarding against.
        org_state = {self.org_a.external_id: {"last_page_id": cross_org_page.external_id}}
        self.user.profile.org_state = org_state
        self.user.profile.save(update_fields=["org_state", "modified"])

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{in_org_page.external_id}/")

    def test_falls_back_within_selected_org_when_last_page_is_inaccessible(self):
        """If the persisted last_page id is stale (page deleted / access
        revoked), we still land in the user's selected org — not in a
        different org just because something there is newer."""
        from pages.tests.factories import PageFactory

        in_org_page = PageFactory(project=self.project_a, creator=self.user, title="In-org fallback")
        PageFactory(project=self.project_b, creator=self.user, title="Other-org noise")

        self._set_current_org(self.org_a)
        # Persist a pointer to a never-created external_id — stale.
        org_state = {self.org_a.external_id: {"last_page_id": "does-not-exist"}}
        self.user.profile.org_state = org_state
        self.user.profile.save(update_fields=["org_state", "modified"])

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{in_org_page.external_id}/")

    def test_external_collaborator_persisted_current_org_is_honored(self):
        """A user who is not an `OrgMember` of `Profile.current_org` but
        retains page-level (Tier 3) access to a page in that org must
        still be redirected within their selected workspace. The
        previous read path demanded membership and silently rerouted
        these collaborators to a different org's newest page."""
        from pages.tests.factories import PageFactory
        from users.models import OrgMember

        my_page = PageFactory(project=self.project_a, creator=self.user, title="A")
        PageFactory(project=self.project_b, creator=self.user, title="B-newer")

        # User loses Org A membership but is still an editor on my_page
        # (PageFactory adds creator as editor automatically, so Tier 3
        # access survives the membership delete). Profile.current_org
        # legitimately stays on Org A.
        self._set_current_org(self.org_a)
        OrgMember.objects.filter(user=self.user, org=self.org_a).delete()

        response = self.client.get("/")

        # Path 2: no last_page_id bucket, newest accessible page in
        # the still-honored Org A — not the globally newer Org B page.
        self.assertRedirects(response, f"/pages/{my_page.external_id}/")

    def test_current_org_with_no_access_at_all_falls_back_to_global_newest(self):
        """If `Profile.current_org` points at an org the user has *no*
        access to via any tier (membership, project editor, page
        editor), the read path drops the selection and falls back to
        the cross-org most-recently-modified page. Self-heals on the
        next page open."""
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        # An org the user has zero relationship with.
        unrelated_org = OrgFactory()
        unrelated_project = ProjectFactory(org=unrelated_org, creator=self.user)
        # Page in unrelated_org but user is NOT the creator → no Tier 3.
        from users.tests.factories import UserFactory

        owner = UserFactory()
        OrgMember.objects.create(org=unrelated_org, user=owner, role="admin")
        PageFactory(project=unrelated_project, creator=owner, title="not-mine")

        # Two of the user's own pages in their real orgs.
        PageFactory(project=self.project_a, creator=self.user, title="A")
        newer_b_page = PageFactory(project=self.project_b, creator=self.user, title="B-newer")

        # Stale selection: profile points at an org user can't reach.
        self.user.profile.current_org = unrelated_org
        self.user.profile.save(update_fields=["current_org", "modified"])

        response = self.client.get("/")

        # Path 3: cross-org newest (B-newer in Org B).
        self.assertRedirects(response, f"/pages/{newer_b_page.external_id}/")

    def test_no_current_org_set_uses_global_newest(self):
        """Legacy / fresh account: `Profile.current_org` is None, no
        persisted pointers — original behaviour."""
        from pages.tests.factories import PageFactory

        PageFactory(project=self.project_a, creator=self.user, title="older")
        newer = PageFactory(project=self.project_b, creator=self.user, title="newer")

        self.user.profile.current_org = None
        self.user.profile.org_state = {}
        self.user.profile.save(update_fields=["current_org", "org_state", "modified"])

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{newer.external_id}/")


class TestSPARoutes(BaseViewTestCase):
    """Test explicit SPA routes."""

    def test_login_route(self):
        """/login/ should serve the SPA."""
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_signup_route(self):
        """/signup/ should serve the SPA."""
        response = self.client.get("/signup/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_settings_route(self):
        """/settings/ should serve the SPA."""
        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_pages_route(self):
        """/pages/abc123/ should serve the SPA."""
        response = self.client.get("/pages/abc123/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_pages_route_without_trailing_slash_redirects(self):
        """/pages/abc123 should redirect to /pages/abc123/."""
        response = self.client.get("/pages/abc123")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/pages/abc123/")


class TestTrailingSlashRedirects(BaseViewTestCase):
    """Test APPEND_SLASH redirects for Django routes."""

    def test_admin_without_slash_redirects(self):
        """Requesting /admin should redirect to /admin/."""
        response = self.client.get("/admin")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/admin/")

    def test_pricing_without_slash_redirects(self):
        """Requesting /pricing should redirect to /pricing/."""
        response = self.client.get("/pricing")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/pricing/")

    def test_login_without_slash_redirects(self):
        """Requesting /login should redirect to /login/."""
        response = self.client.get("/login")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/login/")

    def test_unknown_route_returns_404(self):
        """Unknown routes should return 404."""
        response = self.client.get("/unknown-route/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestGetAppConfig(TestCase):
    """Test get_app_config() returns correct configuration values."""

    def test_default_values(self):
        """Returns expected defaults when no env vars override."""
        config = get_app_config()

        self.assertEqual(config["imports"]["pdfMaxFileSize"], 20 * 1024 * 1024)
        self.assertEqual(config["imports"]["maxFileSize"], 104857600)
        self.assertEqual(config["filehub"]["maxFileSize"], 10485760)

    @override_settings(WS_IMPORTS_PDF_MAX_FILE_SIZE_BYTES=50 * 1024 * 1024)
    def test_custom_pdf_max_size(self):
        """Custom PDF max size flows through."""
        config = get_app_config()

        self.assertEqual(config["imports"]["pdfMaxFileSize"], 50 * 1024 * 1024)

    @override_settings(WS_IMPORTS_MAX_FILE_SIZE_BYTES=200 * 1024 * 1024)
    def test_custom_import_max_size(self):
        """Custom import max size flows through."""
        config = get_app_config()

        self.assertEqual(config["imports"]["maxFileSize"], 200 * 1024 * 1024)

    @override_settings(WS_FILEHUB_MAX_FILE_SIZE_BYTES=25 * 1024 * 1024)
    def test_custom_filehub_max_size(self):
        """Custom filehub max size flows through."""
        config = get_app_config()

        self.assertEqual(config["filehub"]["maxFileSize"], 25 * 1024 * 1024)

    def test_structure(self):
        """Config has the expected top-level keys."""
        config = get_app_config()

        self.assertIn("imports", config)
        self.assertIn("filehub", config)
        self.assertIn("reactions", config)
        self.assertIn("pdfMaxFileSize", config["imports"])
        self.assertIn("maxFileSize", config["imports"])
        self.assertIn("maxFileSize", config["filehub"])
        self.assertIn("allowedEmojis", config["reactions"])

    def test_reactions_allowed_emojis_matches_backend(self):
        """reactions.allowedEmojis matches the backend ALLOWED_REACTIONS list."""
        from pages.api.comments import ALLOWED_REACTIONS

        config = get_app_config()

        self.assertEqual(config["reactions"]["allowedEmojis"], list(ALLOWED_REACTIONS))
        self.assertIsInstance(config["reactions"]["allowedEmojis"], list)
        self.assertGreater(len(config["reactions"]["allowedEmojis"]), 0)


class TestSPAAppConfigContext(BaseViewTestCase):
    """Test that app_config is included in SPA template context."""

    def test_spa_includes_app_config(self):
        """SPA view passes app_config to the template."""
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("app_config", response.context)
        self.assertIn("imports", response.context["app_config"])
        self.assertIn("filehub", response.context["app_config"])
        self.assertIn("reactions", response.context["app_config"])

    def test_app_config_rendered_in_html(self):
        """app-config JSON script tag is present in response HTML."""
        response = self.client.get("/login/")

        self.assertContains(response, 'id="app-config"')
        self.assertContains(response, "pdfMaxFileSize")
        self.assertContains(response, "window._appConfig")


class TestGetUserState(BaseAuthenticatedViewTestCase):
    """Test core.views.home.get_user_state() — the SPA-injected user state.

    Validates that stale state (org membership revoked, page access lost)
    is not leaked through the SPA inject, since the frontend trusts these
    values as authoritative on first paint.
    """

    def test_current_org_omitted_when_membership_revoked(self):
        """If the user has no remaining access to Profile.current_org via
        any tier (membership, project editor, page editor), the SPA
        inject must NOT expose that org id. Revoking membership in an
        org with no other access channels is the cleanest case."""
        from core.views.home import get_user_state
        from pages.tests.factories import ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        org = OrgFactory()
        membership = OrgMember.objects.create(org=org, user=self.user, role="admin")
        self.user.profile.current_org = org
        self.user.profile.save(update_fields=["current_org", "modified"])

        # Sanity: while a member, the org is exposed.
        state = get_user_state(self.user)
        self.assertEqual(state["currentOrgId"], str(org.external_id))

        # Revoke membership; the org id should drop from the inject even
        # though Profile.current_org still points at it.
        membership.delete()
        state = get_user_state(self.user)
        self.assertIsNone(state["currentOrgId"])
        # The display-name fallback drops with it.
        self.assertIsNone(state["currentOrgName"])

    def test_current_org_is_injected_for_non_page_routes_of_external_collaborators(self):
        """An external collaborator (project editor, not `OrgMember`)
        who persisted their `current_org` must see that selection
        survive on non-page routes (`/`, `/settings/`). The read path
        previously gated on membership only, which silently dropped
        the inject and forced the SPA to re-derive context from
        whichever page happened to be in `cachedProjects`."""
        from core.views.home import get_user_state
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory, UserFactory

        org = OrgFactory(name="Acme Sharing")
        owner = UserFactory()
        OrgMember.objects.create(org=org, user=owner, role="admin")
        project = ProjectFactory(org=org, creator=owner, org_members_can_access=False)
        PageFactory(project=project, creator=owner, title="anchor")
        # Self gets project-editor access without org membership; this
        # is enough to count as "access to the org" under the aligned
        # read path.
        ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.EDITOR.value)
        self.user.profile.current_org = org
        self.user.profile.save(update_fields=["current_org", "modified"])

        # No `current_page_external_id` — this is the `/` / `/settings/`
        # surface where Priority 2 (Profile.current_org) is the only
        # source of `currentOrgId`.
        state = get_user_state(self.user)

        self.assertEqual(state["currentOrgId"], org.external_id)
        self.assertEqual(state["currentOrgName"], "Acme Sharing")

    def test_current_org_name_is_injected_for_page_routes_of_non_members(self):
        """External collaborators land on a page in a workspace they
        aren't `OrgMember`s of. The inject must carry that org's name
        so the switcher trigger can display it instead of falling back
        to the generic "Organization" placeholder."""
        from core.views.home import get_user_state
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory, UserFactory

        org = OrgFactory(name="Acme Sharing")
        owner = UserFactory()
        OrgMember.objects.create(org=org, user=owner, role="admin")
        project = ProjectFactory(org=org, creator=owner, org_members_can_access=False)
        page = PageFactory(project=project, creator=owner, title="shared")
        # Self gets project-editor access without org membership.
        ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.EDITOR.value)

        state = get_user_state(self.user, current_page_external_id=page.external_id)

        self.assertEqual(state["currentOrgId"], org.external_id)
        self.assertEqual(state["currentOrgName"], "Acme Sharing")

    def test_current_org_drops_when_underlying_org_is_deleted(self):
        """`Profile.current_org` uses `on_delete=SET_NULL` — deleting the
        Org row nulls the FK on the Profile row, but the row stays. The
        inject must treat the resulting `None` like any other "no access"
        case (no `currentOrgId`, no `currentOrgName`), not crash on the
        nulled relation or leak a stale id.

        Pins Priority 2: when no `current_page_external_id` is passed
        (non-page route) and `current_org_id` is NULL post-cascade, the
        function must return `None` for both id and name.
        """
        from core.views.home import get_user_state
        from users.constants import OrgMemberRole
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        org = OrgFactory(name="To Be Deleted")
        OrgMember.objects.create(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)
        self.user.profile.current_org = org
        self.user.profile.save(update_fields=["current_org", "modified"])

        # Sanity: while the Org exists, the inject exposes it.
        state = get_user_state(self.user)
        self.assertEqual(state["currentOrgId"], str(org.external_id))

        # Delete the Org. SET_NULL on the FK clears profile.current_org_id
        # without removing the Profile row.
        org.delete()
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.current_org_id)

        state = get_user_state(self.user)
        self.assertIsNone(state["currentOrgId"])
        self.assertIsNone(state["currentOrgName"])

    def test_last_page_per_org_drops_entries_pointing_to_pages_in_other_orgs(self):
        """A bucket keyed by Org A whose `last_page_id` resolves to a page in
        Org B must not be injected. The SPA would otherwise resume the
        user into the wrong workspace on the next org switch."""
        from core.views.home import get_user_state
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.constants import OrgMemberRole
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        org_a = OrgFactory()
        OrgMember.objects.create(org=org_a, user=self.user, role=OrgMemberRole.ADMIN.value)
        org_b = OrgFactory()
        OrgMember.objects.create(org=org_b, user=self.user, role=OrgMemberRole.ADMIN.value)

        project_a = ProjectFactory(org=org_a, creator=self.user)
        project_b = ProjectFactory(org=org_b, creator=self.user)
        page_a = PageFactory(project=project_a, creator=self.user, title="A")
        page_b = PageFactory(project=project_b, creator=self.user, title="B")

        profile = self.user.profile
        profile.org_state = {
            # Valid: Org A's bucket points at a page in Org A.
            org_a.external_id: {"last_page_id": page_a.external_id},
            # Drift: Org B's bucket points at a page in Org A.
            org_b.external_id: {"last_page_id": page_a.external_id},
        }
        profile.save(update_fields=["org_state", "modified"])

        state = get_user_state(self.user)

        self.assertEqual(state["lastPagePerOrg"].get(str(org_a.external_id)), str(page_a.external_id))
        self.assertNotIn(str(org_b.external_id), state["lastPagePerOrg"])
        # Sanity: page_b is unrelated noise to confirm the test setup.
        self.assertNotIn(page_b.external_id, state["lastPagePerOrg"].values())

    def test_last_page_per_org_filters_inaccessible_pages(self):
        """A page recorded as last_page for an org but no longer accessible
        to the user shouldn't appear in the inject — the frontend would
        otherwise try to resume on an unopenable page on the next switch."""
        from core.views.home import get_user_state
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
        from users.constants import OrgMemberRole
        from users.models import OrgMember
        from users.tests.factories import OrgFactory, UserFactory

        # An org the user is a non-admin member of.
        org = OrgFactory()
        OrgMember.objects.create(org=org, user=self.user, role=OrgMemberRole.MEMBER.value)

        # A locked-down project the user starts with editor access to.
        owner = UserFactory()
        OrgMember.objects.create(org=org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=org, creator=owner, org_members_can_access=False)
        editor = ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.EDITOR.value)
        page = PageFactory(project=project, creator=owner, title="Hello")

        # Seed `Profile.org_state` directly: the inject reads from JSON.
        profile = self.user.profile
        profile.org_state = {org.external_id: {"last_page_id": page.external_id}}
        profile.save(update_fields=["org_state", "modified"])

        # While the user has editor access, the inject exposes it.
        state = get_user_state(self.user)
        self.assertEqual(state["lastPagePerOrg"].get(str(org.external_id)), str(page.external_id))

        # Revoke project access. The page should no longer be exposed
        # (the stale id stays in JSON but the access filter drops it).
        editor.delete()
        state = get_user_state(self.user)
        self.assertNotIn(str(org.external_id), state["lastPagePerOrg"])
