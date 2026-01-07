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
  generateAccessCode,
} from "./api.js";
import { metrics } from "./lib/metrics.js";
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
  codeFenceField,
  listKeymap,
  checkboxClickHandler,
  blockquoteKeymap,
} from "./decorateFormatting.js";
import { decorateLinks, linkClickHandler } from "./decorateLinks.js";
import { linkAutocomplete } from "./linkAutocomplete.js";
import { findSectionFold } from "./findSectionFold.js";
import { largeFileModeExtension } from "./largeFileMode.js";
import { sectionFoldHover } from "./sectionFoldHover.js";
import { foldChangeListener, setCurrentPageIdForFolds } from "./foldChangeListener.js";
import { restoreFoldedRanges } from "./foldPersistence.js";
import { setupUserAvatar } from "./gravatar.js";
import {
  confirm,
  shareProject,
  createProjectModal,
  newPageModal,
  changePageType,
  readonlyLinkModal,
} from "./lib/modal.js";
import { setupCommandPalette } from "./lib/commandPaletteSetup.js";
import { showToast } from "./lib/toast.js";
import {
  markdownTableExtension,
  generateTable,
  insertTable,
  formatTable,
  findTables,
} from "./markdownTable.js";
import { setupPresenceUI } from "./presence.js";
import {
  setCurrentPageId,
  notifyPageChange,
  setupSidebar,
  openSidebar,
  setActiveTab,
} from "./lib/sidebar.js";
import {
  renderSidenav,
  setNavigateCallback,
  setProjectDeletedHandler,
  setProjectRenamedHandler,
  setupSidenav,
  updateSidenavActive,
} from "./lib/sidenav.js";
import { updatePageAccessCode } from "./lib/stores/sidenav.svelte.js";
import { setupToolbar, resetToolbar } from "./toolbar.js";
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
                <span id="breadcrumb-page" class="breadcrumb-item breadcrumb-page"></span><button id="breadcrumb-filetype" class="breadcrumb-filetype" title="Change page type"></button>
              </nav>
              <div class="breadcrumb-actions">
                <div id="readonly-indicator" class="readonly-indicator" style="display: none;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                  <div class="indicator-popover readonly-popover">
                    <div class="indicator-popover-header">View-Only Link</div>
                    <div class="indicator-popover-text">Anyone with the link can view this page without signing in.</div>
                    <button class="indicator-popover-btn" id="readonly-popover-btn">Manage</button>
                  </div>
                </div>
                <div id="presence-indicator" class="presence-indicator" title="Users currently editing">
                  <span id="user-count">1 user editing</span>
                  <div id="presence-popover" class="presence-popover" style="display: none;">
                    <div class="presence-popover-header">Users editing</div>
                    <div id="presence-list" class="presence-list"></div>
                  </div>
                </div>
                <div id="note-actions" class="note-actions">
                  <button id="actions-btn" class="actions-btn" title="Page options">
                    Options <span class="btn-chevron">▾</span>
                  </button>
                  <div id="actions-dropdown" class="actions-dropdown" style="display: none;">
                    <button id="share-project-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>
                      Share project
                    </button>
                    <div class="actions-dropdown-divider"></div>
                    <button id="rename-page-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                      Rename page
                    </button>
                    <button id="download-page-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                      Download page
                    </button>
                    <button id="readonly-link-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                      Get view-only link
                    </button>
                    <button id="change-type-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M9 15l2 2 4-4"></path></svg>
                      Change type
                    </button>
                    <div class="actions-dropdown-divider"></div>
                    <div class="actions-dropdown-label">Tasks</div>
                    <button id="clear-completed-btn" class="actions-dropdown-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="m9 11 3 3L22 4"></path></svg>
                      Clear done
                    </button>
                    <div class="actions-dropdown-divider"></div>
                    <button id="delete-note-btn" class="actions-dropdown-item danger">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                      Delete page
                    </button>
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
 * Update the view-only link indicator visibility based on access_code.
 */
function updateReadonlyIndicator(accessCode) {
  const indicator = document.getElementById("readonly-indicator");
  if (indicator) {
    indicator.style.display = accessCode ? "flex" : "none";
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
 *
 * Architecture: Show content IMMEDIATELY from REST API, then enhance with real-time
 * collaboration. WebSocket is an enhancement, not a requirement.
 *
 * Strategy to avoid content duplication:
 * 1. Show REST content in editor WITHOUT yCollab initially
 * 2. Wait for sync in background
 * 3. After sync, rebuild editor WITH yCollab using correct content source
 *
 * @param {Object} page - The page object from API (with external_id, title, details, etc.)
 */
async function loadPage(page) {
  const pageId = page.external_id;
  const contentLength = page.details?.content?.length || 0;

  // Start comprehensive metrics span for entire page load
  const pageLoadSpan = metrics.startSpan("page_load", {
    pageId,
    contentLength,
    hasContent: contentLength > 0,
    filetype: page.details?.filetype || "md",
  });

  // Clean up any existing page state first
  pageLoadSpan.addEvent("cleanup_start");
  cleanupCurrentPage();
  pageLoadSpan.addEvent("cleanup_complete");

  currentPage = {
    external_id: page.external_id,
    title: page.title,
    details: page.details,
    created: page.created,
    modified: page.modified,
    updated: page.updated,
    is_owner: page.is_owner,
    access_code: page.access_code,
  };

  // Update the view-only link indicator
  updateReadonlyIndicator(page.access_code);

  // Store the project ID for this page
  currentProjectId = page.project_id || findProjectIdForPage(page.external_id);

  localStorage.setItem("ws-last-page", page.external_id);

  setPageTitle(page.title, page.details?.filetype || "md");
  updateBreadcrumb(currentProjectId);
  setCurrentPageId(page.external_id);
  notifyPageChange(page.external_id);

  // Disable delete button for non-owners with explanation
  const deleteNoteBtn = document.getElementById("delete-note-btn");
  if (deleteNoteBtn) {
    if (page.is_owner) {
      deleteNoteBtn.disabled = false;
      deleteNoteBtn.title = "Delete page";
      deleteNoteBtn.classList.remove("disabled");
    } else {
      deleteNoteBtn.disabled = true;
      deleteNoteBtn.title = "Only the page creator can delete this page";
      deleteNoteBtn.classList.add("disabled");
    }
  }

  const content = page.details?.content || "";
  const filetype = page.details?.filetype || "md";
  pageLoadSpan.addEvent("setup_complete");

  // CSV pages use a different viewer (read-only, needs Yjs sync for content)
  if (filetype === "csv") {
    pageLoadSpan.addEvent("csv_viewer_init_start");
    resetToolbar();
    const toolbarWrapper = document.getElementById("toolbar-wrapper");
    if (toolbarWrapper) toolbarWrapper.style.display = "none";

    const { mountCsvViewer, unmountCsvViewer } = await import("./csv/index.js");

    const editorEl = document.getElementById("editor");
    editorEl.style.paddingLeft = "16px";

    // Show loading state with REST content (likely empty)
    mountCsvViewer(content, editorEl);
    window.csvViewerCleanup = unmountCsvViewer;

    // Sync with Yjs to get the actual content
    const userInfo = getUserInfo();
    const displayName = userInfo.user?.username || currentUser?.email || "Anonymous";
    const csvCollabObjects = createCollaborationObjects(pageId, displayName);

    pageLoadSpan.addEvent("csv_yjs_sync_start");
    const syncResult = await csvCollabObjects.syncPromise;

    if (syncResult.synced && syncResult.ytextHasContent) {
      const ytextContent = csvCollabObjects.ytext.toString();
      mountCsvViewer(ytextContent, document.getElementById("editor"));
      pageLoadSpan.addEvent("csv_yjs_sync_complete", { contentLength: ytextContent.length });
    }

    // Disconnect from Yjs - CSV view is read-only
    destroyCollaboration(csvCollabObjects);

    pageLoadSpan.addEvent("csv_viewer_init_complete");
    pageLoadSpan.end({ status: "success", phase: "csv_visible" });

    metrics.event("page_visible", { pageId, contentLength, timestamp: Date.now() });
    updateSidenavActive(currentPage.external_id);
    return;
  }

  // Log pages use a different viewer (read-only, needs Yjs sync for content)
  if (filetype === "log") {
    pageLoadSpan.addEvent("log_viewer_init_start");
    resetToolbar();
    const toolbarWrapper = document.getElementById("toolbar-wrapper");
    if (toolbarWrapper) toolbarWrapper.style.display = "none";

    const { mountLogViewer, unmountLogViewer } = await import("./log/index.js");

    const editorEl = document.getElementById("editor");

    // Show loading state with REST content (likely empty)
    mountLogViewer(content, editorEl);
    window.logViewerCleanup = unmountLogViewer;

    // Sync with Yjs to get the actual content
    const userInfo = getUserInfo();
    const displayName = userInfo.user?.username || currentUser?.email || "Anonymous";
    const logCollabObjects = createCollaborationObjects(pageId, displayName);

    pageLoadSpan.addEvent("log_yjs_sync_start");
    const syncResult = await logCollabObjects.syncPromise;

    if (syncResult.synced && syncResult.ytextHasContent) {
      const ytextContent = logCollabObjects.ytext.toString();
      mountLogViewer(ytextContent, document.getElementById("editor"));
      pageLoadSpan.addEvent("log_yjs_sync_complete", { contentLength: ytextContent.length });
    }

    // Disconnect from Yjs - Log view is read-only
    destroyCollaboration(logCollabObjects);

    pageLoadSpan.addEvent("log_viewer_init_complete");
    pageLoadSpan.end({ status: "success", phase: "log_visible" });

    metrics.event("page_visible", { pageId, contentLength, timestamp: Date.now() });
    updateSidenavActive(currentPage.external_id);
    return;
  }

  // STEP 1: Show REST content immediately WITHOUT collaboration
  // This ensures instant page load - user sees content in <100ms
  const toolbarWrapper = document.getElementById("toolbar-wrapper");
  if (toolbarWrapper) toolbarWrapper.style.display = "block";

  pageLoadSpan.addEvent("editor_init_start");
  initializeEditor(content, [], filetype);
  pageLoadSpan.addEvent("editor_init_complete", { editorContentLength: content.length });

  // End page load span - user can now see content
  pageLoadSpan.end({
    status: "success",
    phase: "rest_content_visible",
  });

  metrics.event("page_visible", {
    pageId,
    contentLength,
    timestamp: Date.now(),
  });

  // Restore fold state
  setCurrentPageIdForFolds(currentPage.external_id);
  if (window.editorView && window.editorView.state.doc.length > 0) {
    restoreFoldedRanges(window.editorView, currentPage.external_id);
  }

  updateSidenavActive(currentPage.external_id);

  // STEP 2: Setup collaboration in background and upgrade editor when ready
  // This is tracked separately from page_load since it's async
  setupCollaborationAsync(page, content, filetype);
}

/**
 * Setup collaboration asynchronously and upgrade the editor when sync completes.
 * This runs after the page is already visible with REST content.
 */
async function setupCollaborationAsync(page, restContent, filetype) {
  const pageId = page.external_id;

  // Start collaboration span - tracks entire async collab setup
  const collabSpan = metrics.startSpan("collab_setup", {
    pageId,
    restContentLength: restContent?.length || 0,
    filetype,
  });

  updateCollabStatus("connecting");

  // Create collaboration objects
  const userInfo = getUserInfo();
  const displayName = userInfo.user?.username || currentUser?.email || "Anonymous";

  collabSpan.addEvent("create_collab_objects_start");
  collabObjects = createCollaborationObjects(pageId, displayName);
  window.undoManager = collabObjects.undoManager;
  collabSpan.addEvent("create_collab_objects_complete");

  // If collaboration is not available (access denied from cache), stay in REST-only mode
  if (!collabObjects.provider) {
    collabSpan.end({
      status: "skipped",
      reason: "access_denied_cached",
    });
    metrics.event("collab_skipped", { pageId, reason: "access_denied_cached" });
    updateCollabStatus("denied");
    return;
  }

  // Setup unload handler early
  cleanupUnloadHandler = setupUnloadHandler(collabObjects);
  collabSpan.addEvent("ws_connect_start");

  try {
    // Wait for sync to complete - this is the critical async operation
    const syncSpan = metrics.startSpan("ws_sync", { pageId });
    const syncResult = await collabObjects.syncPromise;

    const syncStatus = syncResult.synced
      ? "synced"
      : syncResult.accessDenied
      ? "denied"
      : "timeout";
    syncSpan.end({
      status: syncStatus,
      serverHasContent: syncResult.ytextHasContent,
      ytextLength: collabObjects.ytext?.length || 0,
    });

    collabSpan.addEvent("ws_sync_complete", {
      synced: syncResult.synced,
      serverHasContent: syncResult.ytextHasContent,
    });

    // Guard: Check if user navigated away while we were waiting
    if (currentPage?.external_id !== pageId) {
      collabSpan.end({
        status: "aborted",
        reason: "page_changed_during_sync",
        newPageId: currentPage?.external_id,
      });
      metrics.event("collab_aborted", {
        pageId,
        reason: "page_changed",
        newPageId: currentPage?.external_id,
      });
      return;
    }

    if (syncResult.accessDenied) {
      collabSpan.end({
        status: "error",
        reason: "access_denied",
      });
      metrics.event("collab_access_denied", { pageId });
      updateCollabStatus("denied");
      return;
    }

    if (syncResult.synced) {
      // Determine which content to use
      let contentSource = "server";
      if (!syncResult.ytextHasContent && restContent) {
        // Server is empty - insert REST content into ytext
        collabSpan.addEvent("insert_rest_content", { length: restContent.length });
        collabObjects.ytext.insert(0, restContent);
        contentSource = "rest_api";
      }

      // Now upgrade the editor to collaborative mode
      collabSpan.addEvent("editor_upgrade_start");
      const upgradeSpan = metrics.startSpan("editor_upgrade", { pageId, contentSource });
      upgradeEditorToCollaborative(collabObjects, filetype);
      upgradeSpan.end({ status: "success" });
      collabSpan.addEvent("editor_upgrade_complete");

      updateCollabStatus("connected");

      // Setup presence UI now that we have awareness
      if (collabObjects.awareness) {
        cleanupPresenceUI = setupPresenceUI(collabObjects.awareness);
      }

      collabSpan.end({
        status: "success",
        contentSource,
        finalYtextLength: collabObjects.ytext?.length || 0,
      });

      metrics.event("collab_connected", {
        pageId,
        contentSource,
        ytextLength: collabObjects.ytext?.length || 0,
      });
    } else {
      // Sync timed out - stay in REST-only mode, editor already has content
      collabSpan.end({
        status: "timeout",
        reason: "ws_sync_timeout",
      });
      metrics.event("collab_timeout", { pageId });
      updateCollabStatus("offline");
    }
  } catch (error) {
    collabSpan.end({
      status: "error",
      error: error.message,
    });
    metrics.error("collab_error", error, { pageId });
    updateCollabStatus("error");
  }
}

/**
 * Upgrade the editor to collaborative mode by adding yCollab extension.
 * Preserves cursor position and scroll state.
 */
function upgradeEditorToCollaborative(collabObjects, filetype) {
  if (!window.editorView || !collabObjects) return;

  // Save current state
  const currentSelection = window.editorView.state.selection;
  const scrollTop = window.editorView.scrollDOM.scrollTop;

  // Get content from ytext (which now has the correct content)
  const ytextContent = collabObjects.ytext.toString();

  // Destroy old editor
  window.editorView.destroy();
  window.editorView = null;

  // Reinitialize with yCollab extension
  initializeEditor(ytextContent, [collabObjects.extension], filetype);

  // Restore cursor position (if valid)
  if (window.editorView && currentSelection) {
    try {
      const docLength = window.editorView.state.doc.length;
      const anchor = Math.min(currentSelection.main.anchor, docLength);
      const head = Math.min(currentSelection.main.head, docLength);

      window.editorView.dispatch({
        selection: { anchor, head },
        scrollIntoView: false,
      });
    } catch (e) {
      // Selection restore failed, that's ok
    }
  }

  // Restore scroll position
  if (window.editorView) {
    window.editorView.scrollDOM.scrollTop = scrollTop;
  }

  console.log("[Collab] Editor upgraded to collaborative mode");
}

/**
 * Update the collaboration status indicator in the UI.
 * Shows users the current state of real-time collaboration.
 */
function updateCollabStatus(status) {
  // Find or create the status indicator wrapper
  let wrapper = document.getElementById("collab-status-wrapper");
  let indicator = document.getElementById("collab-status");
  let popover = document.getElementById("collab-popover");

  if (!wrapper) {
    // Create the wrapper with indicator and popover
    const presenceIndicator = document.getElementById("presence-indicator");
    if (presenceIndicator?.parentElement) {
      wrapper = document.createElement("div");
      wrapper.id = "collab-status-wrapper";
      wrapper.className = "collab-status-wrapper";

      indicator = document.createElement("span");
      indicator.id = "collab-status";
      indicator.className = "collab-status";

      popover = document.createElement("div");
      popover.id = "collab-popover";
      popover.className = "indicator-popover collab-popover";
      popover.innerHTML = `
        <div class="indicator-popover-header" id="collab-popover-header">Connection</div>
        <div class="indicator-popover-text" id="collab-popover-text"></div>
      `;

      wrapper.appendChild(indicator);
      wrapper.appendChild(popover);
      presenceIndicator.parentElement.insertBefore(wrapper, presenceIndicator);

      // Setup hover handlers
      setupIndicatorPopover(wrapper, popover);
    }
  }

  if (!indicator) return;

  // Update based on status
  const statusConfig = {
    connecting: {
      icon: "◌",
      header: "Connecting",
      text: "Establishing connection to sync server...",
      class: "connecting",
    },
    connected: {
      icon: "●",
      header: "Connected",
      text: "Changes sync instantly with other editors.",
      class: "connected",
    },
    offline: {
      icon: "●",
      header: "Offline",
      text: "Changes are saved locally. They will sync when you reconnect.",
      class: "offline",
    },
    denied: {
      icon: "⊘",
      header: "Unavailable",
      text: "Real-time collaboration is not available for this page.",
      class: "denied",
    },
    error: {
      icon: "!",
      header: "Connection Lost",
      text: "Attempting to reconnect...",
      class: "error",
    },
  };

  const config = statusConfig[status] || statusConfig.offline;
  indicator.textContent = config.icon;
  indicator.className = `collab-status ${config.class}`;

  // Update popover content
  const headerEl = document.getElementById("collab-popover-header");
  const textEl = document.getElementById("collab-popover-text");
  if (headerEl) headerEl.textContent = config.header;
  if (textEl) textEl.textContent = config.text;
}

/**
 * Setup hover handlers for indicator popovers
 */
function setupIndicatorPopover(wrapper, popover) {
  let hideTimeout;

  wrapper.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
    popover.style.display = "block";
  });

  wrapper.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      popover.style.display = "none";
    }, 200);
  });

  popover.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
  });

  popover.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      popover.style.display = "none";
    }, 200);
  });
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
    window.undoManager = null;
  }

  if (window.editorView) {
    window.editorView.destroy();
    window.editorView = null;
  }

  if (window.csvViewerCleanup) {
    window.csvViewerCleanup();
    window.csvViewerCleanup = null;
    document.getElementById("editor").style.paddingLeft = "";
  }

  if (window.logViewerCleanup) {
    window.logViewerCleanup();
    window.logViewerCleanup = null;
    document.getElementById("editor").style.paddingLeft = "";
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
  const navSpan = metrics.startSpan("page_navigation", {
    pageId: external_id,
    source: skipPushState ? "browser_history" : "programmatic",
  });

  if (failedPageIds.has(external_id)) {
    navSpan.end({ status: "skipped", reason: "previously_failed" });
    return;
  }

  if (cachedProjects.length === 0) {
    navSpan.addEvent("fetch_projects_start");
    cachedProjects = await fetchProjects();
    navSpan.addEvent("fetch_projects_complete", { projectCount: cachedProjects.length });
  }
  renderSidenav(cachedProjects, external_id);

  navSpan.addEvent("fetch_page_start");
  const fetchSpan = metrics.startSpan("rest_fetch", { pageId: external_id, endpoint: "page" });
  const page = await fetchPage(external_id);
  fetchSpan.end({
    status: page?.error ? "error" : "success",
    contentLength: page?.details?.content?.length || 0,
  });
  navSpan.addEvent("fetch_page_complete", {
    hasContent: !!page?.details?.content,
    contentLength: page?.details?.content?.length || 0,
  });

  if (!page || page.error) {
    failedPageIds.add(external_id);
    navSpan.end({ status: "error", reason: page?.error || "not_found" });
    showError(page?.error || "Page not found");
    await redirectToFirstAvailablePage();
    return;
  }

  navSpan.addEvent("load_page_start");
  await loadPage(page);
  navSpan.addEvent("load_page_complete");

  // Only push state if this is a programmatic navigation, not browser back/forward
  if (!skipPushState) {
    window.history.pushState({}, "", `/pages/${external_id}/`);
  }

  navSpan.end({
    status: "success",
    title: page.title,
    contentLength: page.details?.content?.length || 0,
  });
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
 * @param {string} filetype - The page filetype (md, txt, csv)
 */
function initializeEditor(pageContent = "", additionalExtensions = [], filetype = "md") {
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

  // Monospace theme for txt files - treat content literally without styling
  const monospaceTheme = EditorView.theme({
    ".cm-content": {
      fontFamily: '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace',
      fontSize: "14px",
      lineHeight: "1.5",
    },
    ".cm-line": {
      fontFamily: '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace',
    },
  });

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
  // For txt files: use monospace font and skip markdown-specific extensions
  const isTxt = filetype === "txt";

  const baseExtensions = [
    largeFileModeExtension,
    simpleTheme,
    ...(isTxt ? [monospaceTheme] : []),
    EditorView.lineWrapping,
    ...(isTxt ? [] : [markdown(), markdownTableExtension]),
    titleNavigationKeymap,
    ...(isTxt
      ? []
      : [codeFenceField, listKeymap, blockquoteKeymap, checkboxClickHandler, decorateFormatting]),
    decorateEmails,
    decorateLinks,
    linkClickHandler,
    linkAutocomplete,
    foldGutter(),
    foldService.of(findSectionFold),
    sectionFoldHover,
    foldChangeListener,
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

function clearCompletedTasks() {
  const view = window.editorView;
  if (!view) return;

  const doc = view.state.doc;
  const checkedPattern = /^\s*- \[[xX]\]/;
  const linesToDelete = [];

  for (let i = 1; i <= doc.lines; i++) {
    const line = doc.line(i);
    if (checkedPattern.test(line.text)) {
      linesToDelete.push({ from: line.from, to: line.to });
    }
  }

  if (linesToDelete.length === 0) {
    showToast("No completed tasks to clear", "info");
    return;
  }

  const changes = [];
  for (let i = linesToDelete.length - 1; i >= 0; i--) {
    const { from, to } = linesToDelete[i];
    const deleteFrom = from;
    const deleteTo = to < doc.length ? to + 1 : to;
    if (from > 0 && deleteTo === doc.length) {
      changes.push({ from: from - 1, to: to });
    } else {
      changes.push({ from: deleteFrom, to: deleteTo });
    }
  }

  view.dispatch({ changes });
  showToast(
    `Cleared ${linesToDelete.length} completed task${linesToDelete.length === 1 ? "" : "s"}`,
    "success"
  );
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
  const renamePageBtn = document.getElementById("rename-page-btn");
  const changeTypeBtn = document.getElementById("change-type-btn");
  const breadcrumbFiletype = document.getElementById("breadcrumb-filetype");

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

  if (renamePageBtn) {
    renamePageBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      const titleInput = document.getElementById("note-title-input");
      if (titleInput) {
        titleInput.focus();
        titleInput.select();
      }
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
      if (deleteNoteBtn.disabled) return;
      actionsDropdown.style.display = "none";
      if (!currentPage) return;
      openDeleteModal();
    });
  }

  if (changeTypeBtn) {
    changeTypeBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      if (!currentPage) return;
      changePageType({
        pageId: currentPage.external_id,
        pageTitle: currentPage.title || "Untitled",
        currentType: currentPage.details?.filetype || "md",
        pageContent: currentPage.details?.content || "",
      });
    });
  }

  const readonlyLinkBtn = document.getElementById("readonly-link-btn");
  if (readonlyLinkBtn) {
    readonlyLinkBtn.addEventListener("click", async () => {
      actionsDropdown.style.display = "none";
      if (!currentPage) return;
      try {
        const { access_code } = await generateAccessCode(currentPage.external_id);
        readonlyLinkModal({
          pageExternalId: currentPage.external_id,
          pageTitle: currentPage.title || "Untitled",
          accessCode: access_code,
          onremove: () => {
            // Update the cached page to remove access_code
            currentPage.access_code = null;
            updatePageAccessCode(currentPage.external_id, null);
            updateReadonlyIndicator(null);
          },
        });
        // Update the cached page with the access_code
        currentPage.access_code = access_code;
        updatePageAccessCode(currentPage.external_id, access_code);
        updateReadonlyIndicator(access_code);
      } catch (err) {
        console.error("Error generating access code:", err);
        showToast("Failed to create view-only link", "error");
      }
    });
  }

  // Setup hover popover for the view-only link indicator
  const readonlyIndicator = document.getElementById("readonly-indicator");
  const readonlyPopover = readonlyIndicator?.querySelector(".readonly-popover");
  const readonlyPopoverBtn = document.getElementById("readonly-popover-btn");

  if (readonlyIndicator && readonlyPopover) {
    setupIndicatorPopover(readonlyIndicator, readonlyPopover);
  }

  // Click handler for "Manage link" button in popover
  if (readonlyPopoverBtn) {
    readonlyPopoverBtn.addEventListener("click", () => {
      if (!currentPage?.access_code) return;
      readonlyPopover.style.display = "none";
      readonlyLinkModal({
        pageExternalId: currentPage.external_id,
        pageTitle: currentPage.title || "Untitled",
        accessCode: currentPage.access_code,
        onremove: () => {
          currentPage.access_code = null;
          updatePageAccessCode(currentPage.external_id, null);
          updateReadonlyIndicator(null);
        },
      });
    });
  }

  const clearCompletedBtn = document.getElementById("clear-completed-btn");
  if (clearCompletedBtn) {
    clearCompletedBtn.addEventListener("click", () => {
      actionsDropdown.style.display = "none";
      clearCompletedTasks();
    });
  }

  if (breadcrumbFiletype) {
    breadcrumbFiletype.addEventListener("click", () => {
      if (!currentPage) return;
      changePageType({
        pageId: currentPage.external_id,
        pageTitle: currentPage.title || "Untitled",
        currentType: currentPage.details?.filetype || "md",
        pageContent: currentPage.details?.content || "",
      });
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
  console.time("[PERF] initializePageView total");
  console.time("[PERF] initializePageView fetchProjects");
  cachedProjects = await fetchProjects();
  console.timeEnd("[PERF] initializePageView fetchProjects");

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
  const appSpan = metrics.startSpan("app_startup", {
    url: window.location.pathname,
    timestamp: Date.now(),
  });

  renderAppHTML();
  appSpan.addEvent("html_rendered");

  // Expose openPage for sidebar components to navigate between pages
  window.openPage = openPage;

  appSpan.addEvent("auth_check_start");
  const user = await checkAuthentication();
  appSpan.addEvent("auth_check_complete", { authenticated: !!user });

  if (!user) {
    appSpan.end({ status: "redirect", reason: "not_authenticated" });
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

  // Setup command palette (Cmd+K / Ctrl+K)
  setupCommandPalette({
    getProjects: () => cachedProjects,
    getCurrentPageId: () => currentPage?.external_id,
    getCurrentProjectId: () => currentProjectId,
    onNavigate: async (pageId) => {
      if (currentPage) {
        closePageWithoutNavigate();
      }
      await openPage(pageId);
    },
    onCreatePage: () => {
      if (currentProjectId) {
        openCreatePageDialog(currentProjectId);
      } else {
        showToast("No project selected", "error");
      }
    },
    onCreateProject: () => {
      createProjectModal({
        oncreated: async (newProject) => {
          const result = await createPage(newProject.external_id, "Untitled");
          if (result.success && result.page) {
            newProject.pages = [result.page];
          }
          cachedProjects.unshift(newProject);
          renderSidenav(cachedProjects, result.page?.external_id);
          if (result.page) {
            window.location.href = `/pages/${result.page.external_id}/`;
          }
        },
      });
    },
    onDeletePage: () => {
      if (currentPage?.is_owner) {
        openDeleteModal();
      } else if (currentPage) {
        showToast("Only the page creator can delete this page", "error");
      }
    },
    onAsk: () => {
      openSidebar();
      setActiveTab("ask");
    },
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

  // Listen for collaboration errors (access denied, rate limited, etc.)
  window.addEventListener("collabError", (event) => {
    const { pageId, code, message } = event.detail;
    console.warn("Collaboration error:", code, message, "for page:", pageId);

    // Update the status indicator
    if (currentPage && currentPage.external_id === pageId) {
      if (code === "access_denied") {
        updateCollabStatus("denied");
      } else if (code === "rate_limited") {
        updateCollabStatus("error");
        // Show a toast notification for rate limiting
        showToast("Connection limited - please close some tabs and refresh", "warning");
      } else {
        updateCollabStatus("error");
      }
    }
  });

  // Listen for collaboration status changes (connected, disconnected, etc.)
  window.addEventListener("collabStatus", (event) => {
    const { pageId, status } = event.detail;
    // Only update if we're still on the same page
    if (currentPage && currentPage.external_id === pageId) {
      updateCollabStatus(status);
    }
  });

  // Initialize page view (open last page or create one)
  appSpan.addEvent("page_view_init_start");
  await initializePageView();
  appSpan.addEvent("page_view_init_complete");

  // Show upgrade pill if user has any free (non-Pro) orgs
  const hasFreePlan = cachedProjects.some((p) => !p.org?.is_pro);
  const upgradePill = document.getElementById("upgrade-pill");
  if (upgradePill && hasFreePlan) {
    upgradePill.style.display = "inline-flex";
  }

  appSpan.end({
    status: "success",
    projectCount: cachedProjects.length,
    pageCount: cachedProjects.reduce((sum, p) => sum + (p.pages?.length || 0), 0),
  });

  // Log startup summary
  metrics.event("app_ready", {
    projectCount: cachedProjects.length,
    pageCount: cachedProjects.reduce((sum, p) => sum + (p.pages?.length || 0), 0),
    currentPageId: currentPage?.external_id,
  });
}

/**
 * Default export for router integration.
 * When imported by the router, this function initializes the main app.
 */
export default function init() {
  startApp();
}
