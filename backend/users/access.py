"""Org-level access checks shared between the read and write paths for
`Profile.current_org`.

Persisting a `current_org` and reading it back must agree on what
"having access to an org" means. Before this module existed the write
path (`/api/users/me/` PATCH) accepted any user with three-tier access
to *some* page in the org, while the read paths (`get_user_state`,
`_pick_homepage_target`) gated on `OrgMember` only. The mismatch let
external collaborators persist a selection that then silently
disappeared on the next non-page route load.

`user_has_org_access` is the single source of truth: org membership OR
three-tier page access. Membership is the fast path (covers the vast
majority of users); the page-access fallback covers project- and
page-editor collaborators who legitimately work inside a workspace
without being `OrgMember`s.
"""

from pages.models import Page
from users.models import OrgMember


def user_has_org_access(user, org):
    """True if `user` can use `org` as their current workspace.

    Mirrors the additive three-tier access model: org membership grants
    access regardless of project/page state (an empty org with one
    admin should still resolve), and falling back to the accessible-
    pages queryset covers project- and page-editor collaborators.

    Both checks are single EXISTS queries; the helper stays cheap
    enough to call from request hot paths (`get_user_state`,
    `_pick_homepage_target`).
    """
    if org is None:
        return False
    if OrgMember.objects.filter(user=user, org=org).exists():
        return True
    return Page.objects.get_user_accessible_pages(user).filter(project__org=org).exists()
