import { defaultKeymap, indentWithTab } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { foldGutter, foldService } from "@codemirror/language";
import { EditorState, Prec } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";

import {
  createPage as createPageApi,
  deletePage as deletePageApi,
  fetchPage as fetchPageApi,
  fetchProjectsWithPages,
} from "./api.js";
import { getSession, logout } from "./auth.js";
import { clickToEndPlugin } from "./clickToEndPlugin.js";
import {
  createCollaborationObjects,
  destroyCollaboration,
  setupUnloadHandler,
} from "./collaboration.js";
import { API_BASE_URL, getBrandName, getUserInfo } from "./config.js";
import { csrfFetch } from "./csrf.js";
import { decorateEmails } from "./decorateEmails.js";
import {
  decorateFormatting,
  listKeymap,
  checkboxClickHandler,
  blockquoteKeymap,
} from "./decorateFormatting.js";
import { decorateLinks, linkClickHandler } from "./decorateLinks.js";
import { linkAutocomplete } from "./linkAutocomplete.js";
import { findSectionFold } from "./findSectionFold.js";
import { setupUserAvatar } from "./gravatar.js";
import { confirm, shareProject, createProjectModal, newPageModal } from "./lib/modal.js";
import { showToast } from "./lib/toast.js";
import {
  markdownTableExtension,
  generateTable,
  insertTable,
  formatTable,
  findTables,
} from "./markdownTable.js";
import { setupPresenceUI } from "./presence.js";
import { setCurrentPageId, notifyPageChange, setupSidebar } from "./lib/sidebar.js";
import {
  renderSidenav,
  setNavigateCallback,
  setProjectDeletedHandler,
  setProjectRenamedHandler,
  setupSidenav,
  updateSidenavActive,
} from "./lib/sidenav.js";
import { setupToolbar } from "./toolbar.js";
import { getPageIdFromPath } from "./router.js";

/**
 * Render the main app HTML structure into #app
 */
function renderAppHTML() {
  const brandName = getBrandName();
  const app = document.getElementById("app");
  app.innerHTML = `
    <nav>
      <div class="nav-brand">
        <a href="/" class="nav-title" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 0.5rem;">
          <svg class="logo-icon" viewBox="0 0 90 90" width="24" height="24">
            <path d="M 10,80 L 10,70 L 20,70 L 20,80 L 30,80 L 40,80 L 40,70 L 30,70 L 30,60 L 40,60 L 40,50 L 30,50 L 20,50 L 20,60 L 10,60 L 10,50 L 10,40 L 20,40 L 20,30 L 10,30 L 10,20 L 10,10 L 20,10 L 20,20 L 30,20 L 30,10 L 40,10 L 40,20 L 40,30 L 30,30 L 30,40 L 40,40 L 50,40 L 60,40 L 60,30 L 50,30 L 50,20 L 50,10 L 60,10 L 60,20 L 70,20 L 70,10 L 80,10 L 80,20 L 80,30 L 70,30 L 70,40 L 80,40 L 80,50 L 80,60 L 70,60 L 70,50 L 60,50 L 50,50 L 50,60 L 60,60 L 60,70 L 50,70 L 50,80 L 60,80 L 70,80 L 70,70 L 80,70 L 80,80" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          ${brandName}
        </a>
      </div>
      <div class="nav-main">
        <div class="nav-actions">
          <a href="/pricing/" id="upgrade-pill" class="upgrade-pill" style="display: none;">Upgrade</a>
          <a href="/settings/" class="nav-link">Settings</a>
          <div class="user-menu">
            <button id="user-avatar" class="user-avatar" title="Account menu">
              <span id="user-initial"></span>
            </button>
            <div id="user-dropdown" class="user-dropdown">
              <div class="user-dropdown-header">
                <div id="user-email" class="user-dropdown-email"></div>
              </div>
              <div class="user-dropdown-menu">
                <a href="/settings" class="user-dropdown-item">Settings</a>
                <button id="logout-btn" class="user-dropdown-item">Log out</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <div id="note-layout" class="note-layout">
      <div id="sidebar-overlay" class="sidebar-overlay"></div>
      <aside id="note-sidebar" class="note-sidebar">
        <div class="sidebar-header">
          <h2>Projects › Pages</h2>
        </div>
        <div id="sidebar-list" class="sidebar-list">
          <!-- Populated dynamically -->
        </div>
        <button id="sidebar-new-project-btn" class="sidebar-new-btn">+ New Project</button>
      </aside>

      <div id="note-page" class="note-page">
        <div id="note-header">
          <div class="note-header-container">
            <button id="sidebar-toggle" class="sidebar-toggle" title="Open pages list">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <div class="breadcrumb-row" id="breadcrumb-row" style="display: none;">
              <nav id="breadcrumb" class="breadcrumb">
                <span id="breadcrumb-org" class="breadcrumb-item">
                  <span id="breadcrumb-org-name"></span>
                </span>
                <span class="breadcrumb-sep">/</span>
                <span id="breadcrumb-project" class="breadcrumb-item"></span>
                <span class="breadcrumb-sep">/</span>
                <span id="breadcrumb-page" class="breadcrumb-item breadcrumb-page"></span><span id="breadcrumb-filetype" class="breadcrumb-filetype"></span>
              </nav>
              <div class="breadcrumb-actions">
                <div id="presence-indicator" class="presence-indicator" title="Users currently editing">
                  <span id="user-count">1 user editing</span>
                  <div id="presence-popover" class="presence-popover" style="display: none;">
                    <div class="presence-popover-header">Users editing</div>
                    <div id="presence-list" class="presence-list"></div>
                  </div>
                </div>
                <div id="note-actions" class="note-actions">
                  <button id="actions-btn" class="actions-btn" title="More actions">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="1"></circle>
                      <circle cx="12" cy="5" r="1"></circle>
                      <circle cx="12" cy="19" r="1"></circle>
                    </svg>
                  </button>
                  <div id="actions-dropdown" class="actions-dropdown" style="display: none;">
                    <button id="share-project-btn" class="actions-dropdown-item">Share this project</button>
                    <div class="actions-dropdown-divider"></div>
                    <button id="download-page-btn" class="actions-dropdown-item">Download page</button>
                    <div class="actions-dropdown-divider"></div>
                    <button id="delete-note-btn" class="actions-dropdown-item danger">Delete page</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="note-header-actions">
              <button id="chat-toggle-btn" class="chat-toggle-btn" title="Toggle AI chat">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <span>AI</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Toolbar container - mounted by Svelte -->
        <div id="toolbar-wrapper" style="height: 44px; box-sizing: border-box;"></div>

        <div id="editor-container">
          <div id="note-title-area" class="note-title-area">
            <input type="text" id="note-title-input" class="note-title-input" placeholder="Untitled" />
          </div>
          <div id="editor"></div>
        </div>
      </div>

      <!-- Sidebar container - mounted by Svelte -->
      <div id="sidebar-root"></div>
    </div>
  `;
}

/**
 * Check if user is authenticated.
 * Returns user object if authenticated, redirects to login page if not.
 */
async function checkAuthentication() {
  const session = await getSession();

  if (!session.isAuthenticated) {
    const currentPath = window.location.pathname + window.location.search;
    const redirectUrl = encodeURIComponent(currentPath);
    window.location.href = `/login?redirect=${redirectUrl}`;
    return null;
  }

  console.log("Authenticated as:", session.user.email);

  const userEmailElement = document.getElementById("user-email");
  if (userEmailElement) {
    userEmailElement.textContent = session.user.email;
  }

  setupUserAvatar(
    session.user.email,
    document.getElementById("user-avatar"),
    document.getElementById("user-initial")
  );

  return session.user;
}

/**
 * Fetch all projects with their pages.
 */
async function fetchProjects() {
  try {
    const projects = await fetchProjectsWithPages();
    return projects || [];
  } catch (error) {
    console.error("Error fetching projects:", error);
    return [];
  }
}

/**
 * Fetch a specific page by external_id.
 */
async function fetchPage(external_id) {
  try {
    const page = await fetchPageApi(external_id);
    return page;
  } catch (error) {
    console.error("Error fetching page:", error);
    return { error: error.message || "Could not load page at this time" };
  }
}

/**
 * Create a new page via API.
 * @param {string} projectId - External ID of the project
 * @param {string} title - Title of the page
 * @param {string} [copyFrom] - Optional external ID of page to copy content from
 */
async function createPage(projectId, title, copyFrom = null) {
  try {
    const page = await createPageApi(projectId, title || "Untitled", copyFrom);
    return { success: true, page };
  } catch (error) {
    console.error("Error creating page:", error);
    return { success: false, error: error.message || "Could not create page at this time." };
  }
}

/**
 * Delete a page via API.
 */
async function deletePage(external_id) {
  try {
    await deletePageApi(external_id);
    return { success: true };
  } catch (error) {
    console.error("Error deleting page:", error);
    return { success: false, error: error.message || "Could not delete page at this time." };
  }
}

// Store current page data globally for collab and other features
let currentPage = null;

// Store collaboration objects (ydoc, provider, etc.)
let collabObjects = null;

// Store current user globally
let currentUser = null;

// Store presence UI cleanup function
let cleanupPresenceUI = null;

// Store unload handler cleanup function
let cleanupUnloadHandler = null;

// Store projects list for sidebar (with nested pages)
let cachedProjects = [];

// Store the current project ID when creating a new page
let currentProjectId = null;

// Expose cachedProjects for the Dev tab
Object.defineProperty(window, "_cachedProjects", {
  get: () => cachedProjects,
});

// Expose currentProjectId for the Dev tab
Object.defineProperty(window, "_currentProjectId", {
  get: () => currentProjectId,
});

/**
 * Update the page title and page heading.
 */
function setPageTitle(title, filetype = "md") {
  document.title = `${title} - ${getBrandName()}`;
  const titleInput = document.getElementById("note-title-input");
  if (titleInput) {
    titleInput.value = title;
  }
  const breadcrumbPage = document.getElementById("breadcrumb-page");
  if (breadcrumbPage) {
    breadcrumbPage.textContent = title || "Untitled";
  }
  const breadcrumbFiletype = document.getElementById("breadcrumb-filetype");
  if (breadcrumbFiletype) {
    breadcrumbFiletype.textContent = filetype || "md";
  }
}

/**
 * Update the breadcrumb with org and project names.
 */
function updateBreadcrumb(projectId) {
  const breadcrumbRow = document.getElementById("breadcrumb-row");
  const orgNameEl = document.getElementById("breadcrumb-org-name");
  const projectEl = document.getElementById("breadcrumb-project");
  const pageEl = document.getElementById("breadcrumb-page");

  if (!breadcrumbRow || !orgNameEl || !projectEl) return;

  const project = cachedProjects.find((p) => p.external_id === projectId);

  if (!project) {
    breadcrumbRow.style.display = "none";
    return;
  }

  orgNameEl.textContent = project.org?.name || "Personal";
  projectEl.textContent = project.name || "Untitled Project";

  if (pageEl && currentPage) {
    pageEl.textContent = currentPage.title || "Untitled";
  }

  breadcrumbRow.style.display = "flex";
}

/**
 * Update page title via API.
 */
async function updatePageTitle(external_id, newTitle) {
  try {
    const response = await csrfFetch(`${API_BASE_URL}/api/pages/${external_id}/`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ title: newTitle }),
    });

    if (!response.ok) {
      console.error("Failed to update page title");
      return false;
    }

    // Update cached projects - find the page in the nested structure
    for (let i = 0; i < cachedProjects.length; i++) {
      const project = cachedProjects[i];
      const pageIndex = project.pages?.findIndex((p) => p.external_id === external_id);
      if (pageIndex !== -1) {
        // Create new page object to trigger reactivity
        const updatedPage = { ...project.pages[pageIndex], title: newTitle };
        // Create new pages array
        const updatedPages = [...project.pages];
        updatedPages[pageIndex] = updatedPage;
        // Create new project object
        cachedProjects[i] = { ...project, pages: updatedPages };
        renderSidenav(cachedProjects, external_id);
        break;
      }
    }

    return true;
  } catch (error) {
    console.error("Error updating page title:", error);
    return false;
  }
}

/**
 * Setup AI chat sidebar toggle.
 */

const INVALID_FILENAME_CHARS = /[/\\:*?"<>|]/g;
const INVALID_FILENAME_CHARS_PATTERN = /[/\\:*?"<>|]/;

function sanitizeTitle(title) {
  return title.replace(INVALID_FILENAME_CHARS, "").trim();
}

function isValidTitle(title) {
  return !INVALID_FILENAME_CHARS_PATTERN.test(title);
}

/**
 * Setup title editing functionality.
 */
function setupTitleEditing() {
  const titleInput = document.getElementById("note-title-input");
  if (!titleInput) return;

  let lastSavedTitle = "";

  titleInput.addEventListener("focus", () => {
    lastSavedTitle = titleInput.value;
    // Select all text so user can type over
    setTimeout(() => titleInput.select(), 0);
  });

  titleInput.addEventListener("input", () => {
    if (!isValidTitle(titleInput.value)) {
      titleInput.classList.add("title-invalid");
      titleInput.title = 'Invalid characters: / \\ : * ? " < > |';
    } else {
      titleInput.classList.remove("title-invalid");
      titleInput.title = "";
    }
  });

  titleInput.addEventListener("blur", async () => {
    if (!currentPage) return;
    let newTitle = sanitizeTitle(titleInput.value) || "Untitled";
    titleInput.value = newTitle;
    titleInput.classList.remove("title-invalid");
    titleInput.title = "";

    if (newTitle !== lastSavedTitle) {
      currentPage.title = newTitle;
      document.title = `${newTitle} - ${getBrandName()}`;
      const breadcrumbPage = document.getElementById("breadcrumb-page");
      if (breadcrumbPage) {
        breadcrumbPage.textContent = newTitle;
      }
      await updatePageTitle(currentPage.external_id, newTitle);
    }
  });

  titleInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === "ArrowDown") {
      e.preventDefault();
      if (window.editorView) {
        window.editorView.focus();
        window.editorView.dispatch({
          selection: { anchor: 0 },
        });
      }
    } else if (e.key === "Escape") {
      titleInput.value = lastSavedTitle;
      titleInput.classList.remove("title-invalid");
      titleInput.title = "";
      titleInput.blur();
    }
  });
}

/**
 * Load and display a page (used for both new and existing pages).
 * @param {Object} page - The page object from API (with external_id, title, details, etc.)
 */
async function loadPage(page) {
  currentPage = {
    external_id: page.external_id,
    title: page.title,
    details: page.details,
    created: page.created,
    modified: page.modified,
    updated: page.updated,
    is_owner: page.is_owner,
  };

  // Store the project ID for this page
  currentProjectId = page.project_id || findProjectIdForPage(page.external_id);

  localStorage.setItem("ws-last-page", page.external_id);

  setPageTitle(page.title, page.details?.filetype || "md");
  updateBreadcrumb(currentProjectId);
  setCurrentPageId(page.external_id);
  notifyPageChange(page.external_id);

  // Show/hide actions menu based on ownership
  const pageActions = document.getElementById("note-actions");
  if (pageActions) {
    pageActions.style.display = page.is_owner ? "block" : "none";
  }

  const content = page.details?.content || "";

  // Setup collaboration and wait for initial sync (with timeout fallback)
  // Use getUserInfo() which has username from Django template (session API doesn't include it)
  const userInfo = getUserInfo();
  const displayName = userInfo.user?.username || currentUser?.email || "Anonymous";
  collabObjects = createCollaborationObjects(currentPage.external_id, displayName);

  // Wait for sync to see if server has content
  const syncResult = await collabObjects.syncPromise;

  if (syncResult.synced && !syncResult.ytextHasContent && content) {
    // Sync succeeded but server is empty - safe to insert REST content
    collabObjects.ytext.insert(0, content);
    console.log("Server synced but empty, inserted REST content");
  } else if (!syncResult.synced) {
    // Sync timed out - do NOT insert REST content to avoid duplication
    // Editor will start empty, content appears when WebSocket connects
    console.log("Sync timeout - editor will be empty until WebSocket connects");
  }

  // Always use ytext content - yCollab keeps editor and ytext in sync
  initializeEditor(collabObjects.ytext.toString(), [collabObjects.extension]);

  cleanupPresenceUI = setupPresenceUI(collabObjects.awareness);
  cleanupUnloadHandler = setupUnloadHandler(collabObjects);
  updateSidenavActive(currentPage.external_id);
}

/**
 * Helper to find the project ID for a given page external_id.
 */
function findProjectIdForPage(pageExternalId) {
  for (const project of cachedProjects) {
    if (project.pages?.some((p) => p.external_id === pageExternalId)) {
      return project.external_id;
    }
  }
  return null;
}

/**
 * Expose current page for debugging and future features.
 */
window.getCurrentPage = () => currentPage;

/**
 * Check if collaboration is synced (for testing).
 * Returns true if WebSocket provider is connected and synced.
 */
window.isCollabSynced = () => {
  return collabObjects?.provider?.synced === true;
};

/**
 * Cleanup page state without navigating (used when switching pages).
 */
function cleanupCurrentPage() {
  if (cleanupUnloadHandler) {
    cleanupUnloadHandler();
    cleanupUnloadHandler = null;
  }

  if (cleanupPresenceUI) {
    cleanupPresenceUI();
    cleanupPresenceUI = null;
  }

  if (collabObjects) {
    destroyCollaboration(collabObjects);
    collabObjects = null;
  }

  if (window.editorView) {
    window.editorView.destroy();
    window.editorView = null;
  }

  document.getElementById("editor").innerHTML = "";

  // Hide breadcrumb row and clear title
  const breadcrumbRow = document.getElementById("breadcrumb-row");
  if (breadcrumbRow) breadcrumbRow.style.display = "none";
  const titleInput = document.getElementById("note-title-input");
  if (titleInput) titleInput.value = "";

  // Clear ask context
  setCurrentPageId(null);
  notifyPageChange(null);

  currentPage = null;
}

/**
 * Close the current page without navigating (for page switching).
 */
function closePageWithoutNavigate() {
  cleanupCurrentPage();
}

/**
 * Close the current page and open another one.
 */
async function closePage() {
  const closedPageId = currentPage?.external_id;
  const closedProjectId = currentProjectId;
  cleanupCurrentPage();

  document.title = getBrandName();

  window.history.pushState({}, "", "/");

  // Refresh projects and find another page to open
  cachedProjects = await fetchProjects();

  // Try to find another page in the same project first
  let nextPage = null;
  const sameProject = cachedProjects.find((p) => p.external_id === closedProjectId);
  if (sameProject?.pages) {
    nextPage = sameProject.pages.find((p) => p.external_id !== closedPageId);
  }

  // If no page in same project, find any page
  if (!nextPage) {
    for (const project of cachedProjects) {
      if (project.pages && project.pages.length > 0) {
        nextPage = project.pages[0];
        break;
      }
    }
  }

  if (nextPage) {
    await openPage(nextPage.external_id);
  } else {
    // No pages exist - need to create one, but we'll handle this in Steps 5-6
    console.log("No pages available - project selector needed");
  }
}

/**
 * Format a date for display in notes list.
 */
function formatDate(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? "s" : ""} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;

  return date.toLocaleDateString();
}

const failedPageIds = new Set();

/**
 * Open an existing page by external_id.
 * @param {string} external_id - The page's external_id
 * @param {boolean} skipPushState - If true, don't push to history (used for popstate handling)
 */
async function openPage(external_id, skipPushState = false) {
  if (failedPageIds.has(external_id)) {
    console.warn(`Skipping page ${external_id} - previously failed to load`);
    return;
  }

  if (cachedProjects.length === 0) {
    cachedProjects = await fetchProjects();
  }
  renderSidenav(cachedProjects, external_id);

  const page = await fetchPage(external_id);

  if (!page || page.error) {
    failedPageIds.add(external_id);
    showError(page?.error || "Page not found");
    await redirectToFirstAvailablePage();
    return;
  }

  await loadPage(page);

  // Only push state if this is a programmatic navigation, not browser back/forward
  if (!skipPushState) {
    window.history.pushState({}, "", `/pages/${external_id}/`);
  }
}

/**
 * Redirect to the first available page, or show empty state if none exist.
 */
async function redirectToFirstAvailablePage() {
  if (cachedProjects.length === 0) {
    cachedProjects = await fetchProjects();
  }

  for (const project of cachedProjects) {
    if (project.pages && project.pages.length > 0) {
      const availablePage = project.pages.find((p) => !failedPageIds.has(p.external_id));
      if (availablePage) {
        window.history.replaceState({}, "", `/pages/${availablePage.external_id}/`);
        await openPage(availablePage.external_id);
        return;
      }
    }
  }

  window.history.replaceState({}, "", "/");
  renderSidenav(cachedProjects, null);
}

function showError(message) {
  console.error("Error:", message);
  showToast(message, "error");
}

/**
 * Initialize the editor with page content.
 * @param {string} pageContent - Initial content (only used if not using collaboration)
 * @param {Array} additionalExtensions - Extra CodeMirror extensions (e.g., Yjs collab)
 */
function initializeEditor(pageContent = "", additionalExtensions = []) {
  // Create a simple theme to ensure text is visible
  // Using EditorView.theme() instead of baseTheme() to override any defaults
  const simpleTheme = EditorView.theme(
    {
      "&": {
        color: "black",
        backgroundColor: "white",
      },
      ".cm-content": {
        caretColor: "black",
        color: "black",
      },
      ".cm-line": {
        color: "black",
      },
      "&.cm-focused .cm-cursor": {
        borderLeftColor: "black",
        borderLeftWidth: "2px",
      },
      ".cm-cursor": {
        borderLeftColor: "black",
        borderLeftWidth: "2px",
      },
      "&.cm-focused .cm-selectionBackground, ::selection": {
        backgroundColor: "#6fa8dc",
      },
      ".cm-selectionBackground": {
        backgroundColor: "#b3d7ff",
      },
    },
    { dark: false }
  );

  const titleNavigationKeymap = Prec.high(
    keymap.of([
      {
        key: "ArrowUp",
        run: (view) => {
          const pos = view.state.selection.main.head;
          const firstLine = view.state.doc.line(1);
          if (pos <= firstLine.to) {
            const titleInput = document.getElementById("note-title-input");
            if (titleInput) {
              titleInput.focus();
              // Text will be selected by the focus handler
              return true;
            }
          }
          return false;
        },
      },
    ])
  );

  let contentChangeRAF = null;
  const contentChangeNotifier = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      if (contentChangeRAF) cancelAnimationFrame(contentChangeRAF);
      contentChangeRAF = requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent("editorContentChanged"));
        contentChangeRAF = null;
      });
    }
  });

  const enterKeyTrigger = keymap.of([
    {
      key: "Enter",
      run: () => {
        window.dispatchEvent(new CustomEvent("editorEnterPressed"));
        return false;
      },
    },
  ]);

  // Build the base extensions
  const baseExtensions = [
    simpleTheme,
    EditorView.lineWrapping,
    markdown(),
    markdownTableExtension,
    titleNavigationKeymap,
    listKeymap,
    blockquoteKeymap,
    checkboxClickHandler,
    decorateFormatting,
    decorateEmails,
    decorateLinks,
    linkClickHandler,
    linkAutocomplete,
    foldGutter(),
    foldService.of(findSectionFold),
    keymap.of(defaultKeymap),
    keymap.of([indentWithTab]),
    clickToEndPlugin,
    contentChangeNotifier,
    enterKeyTrigger,
  ];

  // Combine with any additional extensions (e.g., Yjs collaboration)
  const allExtensions = [...baseExtensions, ...additionalExtensions];

  // User is authenticated, initialize editor
  const view = new EditorView({
    parent: document.getElementById("editor"),
    state: EditorState.create({
      doc: pageContent || "", // Use empty string if no content provided
      extensions: allExtensions,
    }),
  });

  window.tableUtils = { generateTable, insertTable, formatTable, findTables };
  setupToolbar(view);

  // Expose view for debugging
  window.editorView = view;

  // Position cursor at end of document and focus editor
  view.dispatch({
    selection: { anchor: view.state.doc.length },
  });
  view.focus();

  return view;
}

/**
 * Open create new page dialog using Svelte new page modal.
 */
function openCreatePageDialog(projectId) {
  if (!projectId) {
    showToast("No project selected. Please create a project first.", "error");
    return;
  }

  const project = cachedProjects.find((p) => p.external_id === projectId);
  const pages = project?.pages || [];

  newPageModal({
    projectId,
    pages,
    oncreated: async ({ title, copyFrom }) => {
      const result = await createPage(projectId, title, copyFrom);

      if (result.success) {
        if (currentPage) {
          closePageWithoutNavigate();
        }

        if (project) {
          if (!project.pages) project.pages = [];
          project.pages.unshift(result.page);
        }

        renderSidenav(cachedProjects, result.page.external_id);
        await loadPage(result.page);
        window.history.pushState({}, "", `/pages/${result.page.external_id}/`);
      } else {
        console.error("Failed to create page:", result.error);
        showToast("Failed to create page", "error");
      }
    },
  });
}

/**
 * Setup note actions dropdown (delete, etc.)
 */
function setupNoteActions() {
  const actionsBtn = document.getElementById("actions-btn");
  const actionsDropdown = document.getElementById("actions-dropdown");
  const deleteNoteBtn = document.getElementById("delete-note-btn");
  const shareProjectBtn = document.getElementById("share-project-btn");
  const downloadPageBtn = document.getElementById("download-page-btn");

  if (!actionsBtn || !actionsDropdown) return;

  actionsBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    actionsDropdown.style.display = actionsDropdown.style.display === "none" ? "block" : "none";
  });

  document.addEventListener("click", () => {
    actionsDropdown.style.display = "none";
  });

  if (shareProjectBtn) {
    shareProjectBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      if (!currentPage || !currentProjectId) return;
      const project = cachedProjects.find((p) => p.external_id === currentProjectId);
      shareProject({
        projectId: currentProjectId,
        projectName: project?.name || "Project",
      });
    });
  }

  if (downloadPageBtn) {
    downloadPageBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      if (!currentPage) return;
      window.location.href = `${API_BASE_URL}/api/pages/${currentPage.external_id}/download/`;
    });
  }

  if (deleteNoteBtn) {
    deleteNoteBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      if (!currentPage) return;
      openDeleteModal();
    });
  }
}

/**
 * Open delete confirmation dialog using Svelte confirm modal.
 */
async function openDeleteModal() {
  if (!currentPage) return;

  const confirmed = await confirm({
    title: "Delete Page",
    message: `Are you sure you want to delete "${currentPage.title}"?`,
    description:
      "This will permanently delete the page and all its collaboration data. This action cannot be undone.",
    confirmText: "Delete Page",
    danger: true,
  });

  if (!confirmed) return;

  const result = await deletePage(currentPage.external_id);

  if (result.success) {
    for (const project of cachedProjects) {
      if (project.pages) {
        project.pages = project.pages.filter((p) => p.external_id !== currentPage.external_id);
      }
    }
    await closePage();
  } else {
    showToast(result.error || "Failed to delete page", "error");
  }
}

/**
 * Setup project creation button handler.
 */
function setupCreateProjectButton() {
  const newProjectBtn = document.getElementById("sidebar-new-project-btn");
  newProjectBtn?.addEventListener("click", () => {
    createProjectModal({
      oncreated: async (newProject) => {
        // Create a default page under the new project
        const result = await createPage(newProject.external_id, "Untitled");
        if (result.success && result.page) {
          newProject.pages = [result.page];
        }

        cachedProjects.unshift(newProject);
        renderSidenav(cachedProjects, result.page?.external_id);

        // Navigate to the new page
        if (result.page) {
          window.location.href = `/pages/${result.page.external_id}/`;
        }
      },
    });
  });
}

/**
 * Initialize the page view - open appropriate page on startup.
 */
async function initializePageView() {
  cachedProjects = await fetchProjects();

  const pageIdFromUrl = getPageIdFromPath();

  if (pageIdFromUrl) {
    // URL already has page ID - don't push state (handles popstate and direct navigation)
    await openPage(pageIdFromUrl, true);
    return;
  }

  const lastPageId = localStorage.getItem("ws-last-page");
  if (lastPageId) {
    // Check if the last page exists in any project
    let foundPage = false;
    for (const project of cachedProjects) {
      if (project.pages?.some((p) => p.external_id === lastPageId)) {
        foundPage = true;
        break;
      }
    }
    if (foundPage) {
      await openPage(lastPageId);
      return;
    }
  }

  // Find first available page
  for (const project of cachedProjects) {
    if (project.pages && project.pages.length > 0) {
      await openPage(project.pages[0].external_id);
      return;
    }
  }

  // No pages exist - will be handled by project selector in Steps 5-6
  console.log("No pages found - project selector needed to create first page");
  renderSidenav(cachedProjects, null);
}

/**
 * Start the application.
 */
async function startApp() {
  renderAppHTML();

  // Expose openPage for sidebar components to navigate between pages
  window.openPage = openPage;

  const user = await checkAuthentication();
  if (!user) {
    return;
  }

  // Setup user menu dropdown
  const userAvatar = document.getElementById("user-avatar");
  const userDropdown = document.getElementById("user-dropdown");

  if (userAvatar && userDropdown) {
    userAvatar.addEventListener("click", (e) => {
      e.stopPropagation();
      userDropdown.classList.toggle("open");
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!userDropdown.contains(e.target) && !userAvatar.contains(e.target)) {
        userDropdown.classList.remove("open");
      }
    });
  }

  // Setup logout handler
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      const success = await logout();
      if (success) {
        window.location.href = "/login";
      } else {
        console.error("Logout failed");
        window.location.href = "/login";
      }
    });
  }

  // Store user globally for collaboration
  currentUser = user;

  // Setup modals and UI
  setupCreateProjectButton();
  setupTitleEditing();

  // Setup right sidebar (AI chat, links)
  setupSidebar();

  // Setup left sidenav (pages list)
  setNavigateCallback(async (externalId) => {
    if (externalId !== currentPage?.external_id) {
      if (currentPage) {
        closePageWithoutNavigate();
      }
      await openPage(externalId);
    }
  });

  setupSidenav(async (projectId) => {
    currentProjectId = projectId;
    openCreatePageDialog(projectId);
  });

  setProjectDeletedHandler(() => {
    window.location.href = "/";
  });

  setProjectRenamedHandler((projectId, newName) => {
    // Update cachedProjects
    const project = cachedProjects.find((p) => p.external_id === projectId);
    if (project) {
      project.name = newName;
    }
    // Update breadcrumb if this is the current project
    if (projectId === currentProjectId) {
      updateBreadcrumb(projectId);
    }
  });

  // Setup note actions dropdown
  setupNoteActions();

  // Listen for access revocation events from WebSocket
  window.addEventListener("pageAccessRevoked", (event) => {
    const { pageId, message } = event.detail;
    console.warn("Access revoked event received:", pageId, message);

    // Close the page immediately
    if (currentPage && currentPage.external_id === pageId) {
      closePage();

      // Show error message to user
      showError(message || "Your access to this page has been revoked");
    }
  });

  // Initialize page view (open last page or create one)
  await initializePageView();

  // Show upgrade pill if user has any free (non-Pro) orgs
  const hasFreePlan = cachedProjects.some((p) => !p.org?.is_pro);
  const upgradePill = document.getElementById("upgrade-pill");
  if (upgradePill && hasFreePlan) {
    upgradePill.style.display = "inline-flex";
  }
}

/**
 * Default export for router integration.
 * When imported by the router, this function initializes the main app.
 */
export default function init() {
  startApp();
}
