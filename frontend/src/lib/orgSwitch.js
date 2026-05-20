/**
 * Org-switch controller.
 *
 * Encapsulates the post-switch navigation pipeline:
 *   1. Fetch the new org's projects.
 *   2. Resume on the user's last-viewed page in that org, or pick the
 *      first available page.
 *   3. If the org is empty, auto-create an "Untitled" project+page so
 *      the editor never lands on an empty screen.
 *
 * Used to live inline in main.js. Pulled out as a factory because the
 * pipeline closes over a fair amount of host state (cached projects,
 * current page, sidenav render, page-open) — wiring it explicitly at
 * the call site makes the data flow legible. The module itself owns
 * only two pieces of state: an in-flight Map (coalesces concurrent
 * bootstraps of the same org) and a monotonic switch sequence (drops
 * stale switches when the user rapidly cycles A→B→C).
 */

import { fetchOrgs } from "../api.js";
import { setAvailableOrgs, setOrgChangedHandler } from "./orgContext.js";
import { getLastPageForOrg, clearLastPageForOrg } from "./stores/sidenav.svelte.js";

/**
 * Re-fetch the user's orgs, push them into `orgContext`, and notify
 * listeners via the `hyperclast:orgs-changed` DOM event. Used by both
 * the initial hydration (`hydrateOrgs`) and the post-create flow in
 * `OrgSwitcher` — extracted so the fetch/set/dispatch trio lives in
 * exactly one place. Throws on transport failure; callers decide how
 * to degrade (hydrateOrgs logs, OrgSwitcher appends the new org
 * locally as a fallback).
 */
export async function refreshAvailableOrgs() {
  const orgs = await fetchOrgs();
  setAvailableOrgs(orgs || []);
  window.dispatchEvent(new CustomEvent("hyperclast:orgs-changed"));
  return orgs || [];
}

/**
 * Pick a target page id from `projects` for an org switch. Prefers the
 * user's last-viewed page (if still visible), otherwise the first page
 * of the first project. Returns null when the org has no pages — the
 * caller should auto-create.
 */
export function pickTargetPageForOrg(orgId, projects) {
  const lastViewed = getLastPageForOrg(orgId);
  if (lastViewed) {
    for (const proj of projects || []) {
      if ((proj.pages || []).some((p) => p.external_id === lastViewed)) {
        return lastViewed;
      }
    }
    // Stored entry no longer points at a real page — clear it so we don't
    // keep checking on every switch.
    clearLastPageForOrg(orgId, lastViewed);
  }
  for (const proj of projects || []) {
    if (proj.pages && proj.pages.length > 0) {
      return proj.pages[0].external_id;
    }
  }
  return null;
}

/**
 * Build an org-switch controller bound to the host's mutable state.
 *
 * @param {object} deps
 * @param {() => boolean} deps.isDemoMode
 * @param {() => Array} deps.getCachedProjects - reader for the host's projects cache
 * @param {(projects: Array) => void} deps.setCachedProjects - writer for the host's projects cache
 * @param {() => object|null} deps.getCurrentPage - reader for the open page
 * @param {() => Promise<Array>} deps.fetchProjects - fetch projects for the current org
 * @param {(projects: Array, activePageId: string|null) => void} deps.renderSidenav
 * @param {(pageId: string) => Promise<void>} deps.openPage
 * @param {(orgId: string, name: string) => Promise<object>} deps.createProjectApi
 * @param {(projectId: string, title: string) => Promise<object>} deps.createPageApi
 * @param {(message: string, kind?: string) => void} deps.showToast
 * @param {(orgId: string) => Promise<void>} deps.patchCurrentOrg
 */
export function createOrgSwitchController(deps) {
  // orgId -> Promise<pageId>. Prevents two concurrent bootstraps of the
  // same empty org from creating duplicate Untitled projects/pages.
  const orgBootstrapInFlight = new Map();

  // Monotonic switch token. Each org-changed invocation captures its
  // seq at entry; if it's stale by the time fetchProjects resolves,
  // the handler bails so newer switches' renders aren't clobbered.
  let orgSwitchSeq = 0;

  async function bootstrapEmptyOrg(orgId, projects) {
    const inFlight = orgBootstrapInFlight.get(orgId);
    if (inFlight) return inFlight;
    const promise = (async () => {
      let targetProject = (projects || []).find(() => true) || null;
      if (!targetProject) {
        targetProject = await deps.createProjectApi(orgId, "Untitled");
      }
      const page = await deps.createPageApi(targetProject.external_id, "Untitled");
      return page.external_id;
    })();
    orgBootstrapInFlight.set(orgId, promise);
    try {
      return await promise;
    } finally {
      orgBootstrapInFlight.delete(orgId);
    }
  }

  /**
   * Route the editor to the right page after an org switch. On
   * bootstrap failure, shows a toast and leaves the editor on whatever
   * it was showing — the sidenav-with-no-projects state still surfaces
   * the "+ New Project" CTA.
   */
  async function navigateToOrgEntryPage(orgId) {
    if (!orgId) return;

    let cached = deps.getCachedProjects();
    let targetPageId = pickTargetPageForOrg(orgId, cached);

    if (!targetPageId) {
      try {
        targetPageId = await bootstrapEmptyOrg(orgId, cached);
      } catch (error) {
        console.error("[Org] bootstrapEmptyOrg failed:", error);
        deps.showToast("Couldn't set up that workspace — try creating a project.", "error");
        return;
      }
      cached = await deps.fetchProjects();
      deps.setCachedProjects(cached);
      deps.renderSidenav(cached, targetPageId);
    }

    if (targetPageId && targetPageId !== deps.getCurrentPage()?.external_id) {
      await deps.openPage(targetPageId);
    }
  }

  async function hydrateOrgs() {
    if (deps.isDemoMode()) {
      setAvailableOrgs([]);
      return;
    }
    try {
      await refreshAvailableOrgs();
    } catch (error) {
      console.error("Error fetching orgs:", error);
    }
  }

  function installHandler() {
    setOrgChangedHandler(async (newOrgId) => {
      const seq = ++orgSwitchSeq;

      // Persist to Profile (fire-and-forget — UI updates instantly).
      deps.patchCurrentOrg(newOrgId);

      const projects = await deps.fetchProjects();
      if (seq !== orgSwitchSeq) return; // superseded by a newer switch
      deps.setCachedProjects(projects);
      deps.renderSidenav(projects, deps.getCurrentPage()?.external_id ?? null);

      await navigateToOrgEntryPage(newOrgId);
    });
  }

  return { hydrateOrgs, installHandler, navigateToOrgEntryPage };
}
