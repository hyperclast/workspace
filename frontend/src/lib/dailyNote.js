/**
 * Daily Note orchestrator.
 *
 * Single entry point invoked by the sidenav calendar icon and the
 * Cmd/Ctrl+Alt+D keyboard shortcut.
 *
 * Flow:
 *   1. POST /daily-note/today/.
 *   2. If the backend returns `{needsConfig: true}` (HTTP 409), show the
 *      welcome modal. The user either accepts the default (auto-setup via
 *      PATCH /config/ with {auto:true}) or opens the customize wizard.
 *   3. Otherwise navigate to the returned page.
 */

import {
  openDailyNoteToday,
  updateDailyNoteConfig,
  organizeDailyNotes,
  fetchProjectsWithPages,
} from "../api.js";
import { initModals } from "./modal.js";
import {
  openDailyNoteWelcome as _openDailyNoteWelcome,
  openDailyNoteWizard as _openDailyNoteWizard,
} from "./stores/modal.svelte.js";
import { showToast } from "./toast.js";

const DAILY_NOTE_TITLE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Count YYYY-MM-DD pages not already filed under their correct YYYY/MM folder.
 * Shared by detectWelcomeContext() and DailyNoteWizard.
 */
export function countUnorganizedDailyNotes(pages, folders) {
  const foldersById = new Map(folders.map((f) => [f.external_id, f]));
  let count = 0;
  for (const page of pages) {
    if (!DAILY_NOTE_TITLE_RE.test(page.title || "")) continue;
    const [year, month] = page.title.split("-");
    if (isNaN(Number(month))) continue;
    const folder = page.folder_id ? foldersById.get(page.folder_id) : null;
    const parent = folder?.parent_id ? foldersById.get(folder.parent_id) : null;
    if (folder && parent && folder.name === month && parent.name === year && !parent.parent_id) {
      continue;
    }
    count += 1;
  }
  return count;
}

// Registered by main.js at startup so we can do in-place page swaps (same code
// path as sidenav clicks). Falls back to pushState+popstate, which forces the
// router to re-import main.js — correct but visually causes a full-app blink.
let pageNavigator = null;
let sidenavRefresher = null;
let cachedProjectsGetter = null;

/**
 * Register the lightweight page-swap function (typically main.js's `openPage`).
 * Call once during app init.
 */
export function setPageNavigator(fn) {
  pageNavigator = fn;
}

/**
 * Register the sidenav refresh function (re-fetches projects and re-renders).
 * Call once during app init.
 */
export function setSidenavRefresher(fn) {
  sidenavRefresher = fn;
}

/**
 * Register a getter that returns the current cached project list (with pages
 * and folders).  Used by `detectWelcomeContext()` to avoid a redundant network
 * round trip when the sidenav has already fetched the data.
 * Call once during app init.
 */
export function setCachedProjectsGetter(fn) {
  cachedProjectsGetter = fn;
}

async function refreshSidenav() {
  if (!sidenavRefresher) return;
  try {
    await sidenavRefresher();
  } catch (e) {
    console.error("[DailyNote] Sidenav refresh failed", e);
  }
}

function navigateToPage(externalId) {
  if (pageNavigator) {
    pageNavigator(externalId);
    return;
  }
  window.history.pushState({}, "", `/pages/${externalId}/`);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/**
 * Best-effort detection for the welcome modal copy. Counts unorganized daily
 * notes in any visible "Daily Notes" project.
 *
 * Never sets `projectExists: true` because we cannot determine writability
 * client-side — the backend auto-setup may create a new project even when a
 * read-only "Daily Notes" project is visible.
 */
async function detectWelcomeContext() {
  let projects = cachedProjectsGetter?.();
  if (!projects || projects.length === 0) {
    try {
      projects = await fetchProjectsWithPages();
    } catch {
      return { projectName: "Daily Notes", projectExists: false, unorganizedCount: 0 };
    }
  }

  const existing = projects.find((p) => (p.name || "").toLowerCase() === "daily notes");
  if (!existing) {
    return { projectName: "Daily Notes", projectExists: false, unorganizedCount: 0 };
  }

  const unorganizedCount = countUnorganizedDailyNotes(existing.pages || [], existing.folders || []);

  return {
    projectName: "Daily Notes",
    projectExists: false,
    unorganizedCount,
  };
}

async function handleAutoSetup(unorganizedCount) {
  try {
    await updateDailyNoteConfig({ auto: true });
    if (unorganizedCount > 0) {
      try {
        await organizeDailyNotes(false);
      } catch (e) {
        showToast("Saved, but could not organize existing notes", "error");
      }
    }
    await refreshSidenav();
    await openDailyNote();
  } catch (e) {
    showToast(e.message || "Failed to set up daily notes", "error");
  }
}

function showWelcome(ctx) {
  initModals();
  _openDailyNoteWelcome({
    projectName: ctx.projectName,
    projectExists: ctx.projectExists,
    unorganizedCount: ctx.unorganizedCount,
    onproceed: () => handleAutoSetup(ctx.unorganizedCount),
    oncustomize: () => {
      _openDailyNoteWizard({
        onconfigured: async () => {
          await refreshSidenav();
          await openDailyNote();
        },
      });
    },
  });
}

/**
 * Open today's daily note. Handles the first-run and configured cases.
 * Called from the sidenav calendar icon and the Mod-Alt-d shortcut.
 */
export async function openDailyNote() {
  let result;
  try {
    result = await openDailyNoteToday();
  } catch (err) {
    console.error("[DailyNote] Failed to open today's note", err);
    showToast("Failed to open today's note", "error");
    return;
  }

  if (result && result.needsConfig) {
    const ctx = await detectWelcomeContext();
    showWelcome(ctx);
    return;
  }

  if (result && result.external_id) {
    // Refresh sidenav first so the newly-created daily note is in cachedProjects
    // before openPage runs — otherwise findProjectIdForPage returns null and the
    // breadcrumb row gets hidden until the user navigates away and back.
    await refreshSidenav();
    navigateToPage(result.external_id);
  }
}

/**
 * Open the customization wizard directly (used from Settings).
 */
export function openDailyNoteWizard(options = {}) {
  initModals();
  _openDailyNoteWizard({
    onconfigured: async (...args) => {
      await refreshSidenav();
      if (options.onconfigured) {
        await options.onconfigured(...args);
      }
    },
  });
}
