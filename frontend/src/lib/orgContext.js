/**
 * Org-context module: the canonical home for "which org is the user
 * currently looking at" plus the list of orgs they belong to.
 *
 * This lives outside the Svelte sidenav store on purpose. The current
 * org is application context (consulted by api.js, ask.js, autocomplete,
 * etc.), not UI state — pulling it into a Svelte store made non-UI code
 * import from a `.svelte.js` module just to read a string.
 *
 * Source of truth: the open page. The server picks the right value on
 * every SPA render (page's project.org for /pages/<id>/ routes,
 * Profile.current_org otherwise) and injects it as
 * `window._userState.currentOrgId`. We seed from there on module load.
 * In-session updates happen via `setCurrentOrgId` (driven by loadPage
 * when a different-org page opens, or by the org switcher).
 *
 * Subscribers:
 *   - OrgSwitcher.svelte listens for the `hyperclast:orgs-changed`
 *     DOM CustomEvent to know when the *membership list* changed, and for
 *     `hyperclast:current-org-changed` to know when the *selected org*
 *     changed (e.g. driven by `loadPage` upgrading to a cross-org page).
 *     The two events are kept distinct so a list-only refresh doesn't
 *     re-run unrelated selection-change UI work.
 *   - main.js installs an org-change handler via `setOrgChangedHandler`
 *     to drive the post-switch navigation pipeline. That callback is the
 *     coupled, ordered side-effect channel (fetch projects → render
 *     sidenav → navigate); the DOM event is the decoupled fan-out for
 *     passive UI consumers that just need to re-read the value.
 */

function loadCurrentOrgId() {
  // The open page is canonical: on a /pages/<id>/ route the SPA template
  // injects that page's org as `currentOrgId`. On non-page routes it
  // falls back to Profile.current_org. Either way the server has already
  // picked the right value — no client-side cache to reconcile.
  return window._userState?.currentOrgId || null;
}

function loadCurrentOrgName() {
  // Server-injected name for `currentOrgId`. Used by the org switcher
  // trigger as a display fallback when the current org isn't in the
  // user's membership list (project / page-editor collaborators).
  // Without it the trigger would show "Organization" generic text.
  return window._userState?.currentOrgName || null;
}

let currentOrgId = loadCurrentOrgId();
let currentOrgName = loadCurrentOrgName();
let availableOrgs = [];
let onOrgChanged = null;

export function getCurrentOrgId() {
  return currentOrgId;
}

export function getCurrentOrgName() {
  // Best-effort label for the current org. Prefer the org in
  // `availableOrgs` (its name might be more up-to-date than the
  // server snapshot), and fall back to the SPA-injected name. May
  // return `null` — callers should provide their own generic
  // placeholder.
  if (currentOrgId) {
    const known = availableOrgs.find((o) => o.external_id === currentOrgId);
    if (known?.name) return known.name;
  }
  return currentOrgName;
}

export function setCurrentOrgName(name) {
  currentOrgName = name || null;
}

export function getAvailableOrgs() {
  return availableOrgs;
}

export function setAvailableOrgs(orgs) {
  // `availableOrgs` is the user's membership list — the set of orgs the
  // switcher dropdown can navigate to. It is intentionally NOT the same
  // as "valid contexts for `currentOrgId`": a user can have direct
  // project- or page-editor access to a workspace they aren't an
  // OrgMember of, in which case the open page's org legitimately sits
  // outside this list. Under the page-canonical invariant the open
  // page owns the rune, so this setter does NOT touch `currentOrgId` —
  // doing so would clobber the page-derived value for external
  // collaborators the moment their orgs-fetch resolved.
  availableOrgs = [...orgs];
}

export function setCurrentOrgId(orgId) {
  if (orgId === currentOrgId) return;
  currentOrgId = orgId;
  if (onOrgChanged) {
    onOrgChanged(orgId);
  }
  // Fan out to passive UI consumers (e.g. the OrgSwitcher trigger label)
  // through a dedicated event, separate from `hyperclast:orgs-changed`
  // which signals membership-list changes. Same channel for every code
  // path that calls `setCurrentOrgId` — switcher click, loadPage upgrade,
  // post-create — so subscribers don't need to know who moved the value.
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("hyperclast:current-org-changed", { detail: { orgId } }));
  }
}

export function setOrgChangedHandler(handler) {
  onOrgChanged = handler;
}
