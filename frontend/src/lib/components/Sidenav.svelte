<script>
  import { API_BASE_URL } from "../../config.js";
  import { csrfFetch } from "../../csrf.js";
  import { formatFileSize } from "../utils/formatFileSize.js";
  import { confirm, prompt, shareProject, changePageType, sharePage, importModal } from "../modal.js";
  import { showToast } from "../toast.js";
  import { broadcastSidenavChanged } from "../sidenavBroadcast.js";
  import { validateProjectName } from "../validation.js";
  import { isDemoMode } from "../../demo/index.js";
  import { getDemoPage } from "../../demo/demoContent.js";
  import {
    getProjects,
    getActivePageId,
    getShowOrgNames,
    getExpandedProjectIds,
    toggleProjectExpanded,
    navigateToPage,
    createNewPage,
    updateProjectName,
    notifyProjectDeleted,
    updatePageAccessCode,
    getShowFilesSection,
    getExpandedFilesSections,
    toggleFilesSectionExpanded,
    getAllProjectFiles,
    removeFileFromProject,
    addFileToProject,
  } from "../stores/sidenav.svelte.js";
  import { deleteFile, restoreFile, fetchFileReferences } from "../../api.js";
  import { openLightbox } from "../../decorateImagePreviews.js";
  import { openPdfViewer } from "../stores/pdfViewer.svelte.js";

  // File extensions for preview detection
  const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"];
  const PDF_EXTENSION = ".pdf";

  // Check if a file is an image based on filename
  function isImageFile(filename) {
    const lower = (filename || "").toLowerCase();
    return IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext));
  }

  // Icons
  const chevronIcon = `<svg class="project-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
  const menuIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>`;
  const shareIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>`;
  const renameIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
  const downloadIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
  const deleteIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
  const changeTypeIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M9 15l2 2 4-4"></path></svg>`;
  const newPageIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>`;
  const globeIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`;
  const folderIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`;
  const fileIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;
  const smallChevronIcon = `<svg class="files-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
  const importIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>`;
  const copyIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
  const insertIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
  const imageIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`;

  // Local state
  let openMenuId = $state(null);
  let openPageMenuId = $state(null);
  let openFileMenuId = $state(null);

  // Derived state using getters
  let projects = $derived(getProjects());
  let activePageId = $derived(getActivePageId());
  let showOrgNames = $derived(getShowOrgNames());
  let expandedProjectIds = $derived(getExpandedProjectIds());
  let showFilesSection = $derived(getShowFilesSection());
  let expandedFilesSections = $derived(getExpandedFilesSections());
  let projectFiles = $derived(getAllProjectFiles());

  // Small menu icon for pages
  const pageMenuIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>`;

  function handlePageClick(pageId, projectId) {
    closeMobileSidebar();
    navigateToPage(pageId, projectId);
  }

  function handleNewPageClick(e, projectId) {
    e.stopPropagation();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }
    createNewPage(projectId);
  }

  function handleNewPageFromMenu(e, projectId) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }
    createNewPage(projectId);
  }

  function handleProjectHeaderClick(projectId) {
    toggleProjectExpanded(projectId);
  }

  function handleMenuBtnClick(e, projectId) {
    e.stopPropagation();
    openMenuId = openMenuId === projectId ? null : projectId;
    openPageMenuId = null;
  }

  function handlePageMenuBtnClick(e, pageId) {
    e.stopPropagation();
    openPageMenuId = openPageMenuId === pageId ? null : pageId;
    openMenuId = null;
  }

  function closeAllMenus() {
    openMenuId = null;
    openPageMenuId = null;
    openFileMenuId = null;
  }

  async function handleShare(e, project) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }
    shareProject({
      projectId: project.external_id,
      projectName: project.name,
      orgName: project.org?.name || '',
    });
  }

  async function handleRename(e, projectId, projectName) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }

    const newName = await prompt({
      title: "Rename Project",
      label: "Project name",
      value: projectName,
      confirmText: "Save",
      validate: validateProjectName,
    });

    if (!newName || newName === projectName) return;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName }),
      });

      if (response.ok) {
        showToast("Project renamed successfully");
        updateProjectName(projectId, newName);
      } else {
        const data = await response.json().catch(() => ({}));
        showToast(data.message || "Failed to rename project", "error");
      }
    } catch (error) {
      console.error("Error renaming project:", error);
      showToast("Network error. Please try again.", "error");
    }
  }

  async function handleDelete(e, projectId, projectName) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Delete Project",
      message: `Are you sure you want to delete "${projectName}"?`,
      description:
        "This will delete the project and all its pages. This action cannot be undone.",
      confirmText: "Delete Project",
      danger: true,
    });

    if (!confirmed) return;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/`, {
        method: "DELETE",
      });

      if (response.ok || response.status === 204) {
        showToast("Project deleted successfully");
        broadcastSidenavChanged(); // Notify other tabs
        notifyProjectDeleted(projectId);
      } else {
        const data = await response.json().catch(() => ({}));
        showToast(data.message || "Failed to delete project", "error");
      }
    } catch (error) {
      console.error("Error deleting project:", error);
      showToast("Network error. Please try again.", "error");
    }
  }

  function handleDownload(e, projectId) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Project download not available in demo", "error");
      return;
    }
    window.location.href = `${API_BASE_URL}/api/projects/${projectId}/download/`;
  }

  function handleImport(e, projectId, projectName) {
    e.stopPropagation();
    closeAllMenus();
    importModal({
      projectId,
      projectName,
      onimported: () => {
        // Refresh the page to see imported pages
        window.location.reload();
      },
    });
  }

  function handlePageDownload(e, pageId) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      const page = getDemoPage(pageId);
      if (page) {
        const content = page.details?.content || "";
        const filename = `${page.title || "untitled"}.md`;
        const blob = new Blob([content], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
      return;
    }
    window.location.href = `${API_BASE_URL}/api/pages/${pageId}/download/`;
  }

  function handlePageRename(e, pageId) {
    e.stopPropagation();
    closeAllMenus();

    const titleInput = document.getElementById("note-title-input");
    if (titleInput) {
      titleInput.focus();
      titleInput.select();
    }
  }

  function handleChangePageType(e, pageId, pageTitle, filetype) {
    e.stopPropagation();
    closeAllMenus();
    // Get page content for the modal (needed for CSV detection)
    let pageContent = "";
    if (isDemoMode()) {
      const demoPage = getDemoPage(pageId);
      pageContent = demoPage?.details?.content || "";
    }
    changePageType({
      pageId,
      pageTitle: pageTitle || "Untitled",
      currentType: filetype || "md",
      pageContent,
    });
  }

  function handleSharePage(e, pageId, pageTitle) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }

    sharePage({
      pageId: pageId,
      pageTitle: pageTitle || "Untitled",
      onAccessCodeChange: (newAccessCode) => {
        updatePageAccessCode(pageId, newAccessCode);
      },
    });
  }

  async function handlePageDelete(e, pageId, pageTitle) {
    e.stopPropagation();
    closeAllMenus();
    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Delete Page",
      message: `Are you sure you want to delete "${pageTitle || 'Untitled'}"?`,
      description: "This action cannot be undone.",
      confirmText: "Delete Page",
      danger: true,
    });

    if (!confirmed) return;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/pages/${pageId}/`, {
        method: "DELETE",
      });

      if (response.ok || response.status === 204) {
        showToast("Page deleted successfully");
        broadcastSidenavChanged(); // Notify other tabs
        window.location.href = "/";
      } else {
        const data = await response.json().catch(() => ({}));
        showToast(data.message || "Failed to delete page", "error");
      }
    } catch (error) {
      console.error("Error deleting page:", error);
      showToast("Network error. Please try again.", "error");
    }
  }

  function closeMobileSidebar() {
    const sidebar = document.getElementById("note-sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    sidebar?.classList.remove("open");
    overlay?.classList.remove("visible");
  }

  function handleFilesSectionClick(e, projectId) {
    e.stopPropagation();
    toggleFilesSectionExpanded(projectId);
  }

  function handleFileClick(e, file) {
    e.stopPropagation();
    if (!file.link) return;

    const filename = file.filename?.toLowerCase() || "";

    // Preview images in lightbox
    if (IMAGE_EXTENSIONS.some((ext) => filename.endsWith(ext))) {
      openLightbox(file.link, file.filename);
      return;
    }

    // Preview PDFs in viewer
    if (filename.endsWith(PDF_EXTENSION)) {
      openPdfViewer({ url: file.link, filename: file.filename });
      return;
    }

    // Other files: download (open in new tab)
    window.open(file.link, "_blank");
  }

  function getFilesList(projectId) {
    return projectFiles[projectId] || [];
  }

  // Copy/Insert link helpers
  function copyToClipboard(text, successMessage = "Link copied to clipboard") {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMessage);
    }).catch(() => {
      showToast("Failed to copy link", "error");
    });
  }

  function insertIntoEditor(markdown) {
    if (!window.editorView) {
      showToast("No editor available", "error");
      return;
    }
    const view = window.editorView;
    const cursor = view.state.selection.main.head;
    view.dispatch({
      changes: { from: cursor, insert: markdown },
      selection: { anchor: cursor + markdown.length },
      scrollIntoView: true,
    });
    view.focus();
    showToast("Link inserted");
  }

  // Page link actions
  function handlePageCopyLink(e, pageId) {
    e.stopPropagation();
    closeAllMenus();
    const url = `${window.location.origin}/pages/${pageId}/`;
    copyToClipboard(url);
  }

  function handlePageInsertLink(e, pageId, pageTitle) {
    e.stopPropagation();
    closeAllMenus();
    const markdown = `[${pageTitle || "Untitled"}](/pages/${pageId}/)\n`;
    insertIntoEditor(markdown);
  }

  // File menu handlers
  function handleFileMenuBtnClick(e, fileId) {
    e.stopPropagation();
    openFileMenuId = openFileMenuId === fileId ? null : fileId;
    openMenuId = null;
    openPageMenuId = null;
  }

  function handleFileCopyLink(e, file) {
    e.stopPropagation();
    closeAllMenus();
    if (file.link) {
      copyToClipboard(file.link);
    } else {
      showToast("No download link available", "error");
    }
  }

  function handleFileInsertLink(e, file) {
    e.stopPropagation();
    closeAllMenus();
    if (file.link) {
      const markdown = `[${file.filename}](${file.link})\n`;
      insertIntoEditor(markdown);
    } else {
      showToast("No download link available", "error");
    }
  }

  function handleFileInsertPreview(e, file) {
    e.stopPropagation();
    closeAllMenus();
    if (file.link) {
      const markdown = `![${file.filename}](${file.link})\n`;
      insertIntoEditor(markdown);
    } else {
      showToast("No download link available", "error");
    }
  }

  function handleFileDownload(e, file) {
    e.stopPropagation();
    closeAllMenus();
    if (file.link) {
      window.open(file.link, "_blank");
    } else {
      showToast("No download link available", "error");
    }
  }

  async function handleFileDelete(e, file, projectId) {
    e.stopPropagation();
    closeAllMenus();

    if (isDemoMode()) {
      showToast("Not available in demo", "error");
      return;
    }

    // Check for references before deleting
    // 1. Check current editor content (catches unsaved links)
    // 2. Check database via API (catches links in other pages)
    let refWarning = "";
    let hasLocalReference = false;
    let hasRemoteReferences = false;

    // Check current editor for unsaved references to this file
    if (window.editorView) {
      const content = window.editorView.state.doc.toString();
      // Match file links: [text](/files/{project_id}/{file_id}/{token}/)
      const fileIdPattern = new RegExp(`/files/[^/]+/${file.external_id}/`, "g");
      if (fileIdPattern.test(content)) {
        hasLocalReference = true;
      }
    }

    // Check database for saved references in other pages
    try {
      const refs = await fetchFileReferences(file.external_id);
      if (refs.count > 0) {
        hasRemoteReferences = true;
        const names = refs.references.slice(0, 3).map(r => r.page_title).join(", ");
        const more = refs.count > 3 ? ` and ${refs.count - 3} more` : "";
        refWarning = `This file is linked in ${refs.count} page${refs.count > 1 ? "s" : ""}: ${names}${more}.`;
      }
    } catch (err) {
      console.error("Failed to check file references:", err);
    }

    // Show confirmation if there are any references
    if (hasLocalReference || hasRemoteReferences) {
      let description = "";
      if (hasLocalReference && !hasRemoteReferences) {
        description = "This file is linked in the current page.";
      } else if (hasRemoteReferences) {
        description = refWarning;
        if (hasLocalReference) {
          description += " It's also linked in the current page.";
        }
      }
      description += " Those links will break.";

      const confirmed = await confirm({
        title: "Delete File",
        message: `Delete "${file.filename}"?`,
        description,
        confirmText: "Delete",
        danger: true,
      });

      if (!confirmed) return;
    }

    // Delete the file and show toast with undo
    try {
      await deleteFile(file.external_id);
      removeFileFromProject(projectId, file.external_id);
      showToast(`"${file.filename}" deleted`, "success", {
        action: {
          label: "Undo",
          onClick: async () => {
            try {
              await restoreFile(file.external_id);
              addFileToProject(projectId, file);
              showToast(`"${file.filename}" restored`);
            } catch (err) {
              showToast(err.message || "Failed to restore file", "error");
            }
          },
        },
      });
    } catch (error) {
      showToast(error.message || "Failed to delete file", "error");
    }
  }

  // Keyboard handlers for interactive divs (a11y)
  // Only triggers when the event target is the element itself (not a child button)
  // Enter activates on keydown, Space activates on keyup (matching native button behavior)
  function handleKeydown(e, action) {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter") {
      e.preventDefault();
      action();
    } else if (e.key === " ") {
      e.preventDefault(); // Prevent scroll, but don't activate yet
    }
  }

  function handleKeyup(e, action) {
    if (e.target !== e.currentTarget) return;
    if (e.key === " ") {
      e.preventDefault();
      action();
    }
  }


  // Close menus when clicking outside
  function handleGlobalClick(e) {
    if (!e.target.closest(".project-menu") && !e.target.closest(".page-menu") && !e.target.closest(".file-menu")) {
      closeAllMenus();
    }
  }
</script>

<svelte:document onclick={handleGlobalClick} />

<div class="sidebar-list-container">
  {#if projects.length === 0}
    <div class="sidebar-empty">No projects yet</div>
  {:else}
    {#each projects as project (project.external_id)}
      {@const isExpanded = expandedProjectIds.has(project.external_id)}
      <div
        class="sidebar-project"
        class:expanded={isExpanded}
        data-project-id={project.external_id}
      >
        <div
          class="sidebar-project-header"
          role="button"
          tabindex="0"
          aria-expanded={isExpanded}
          aria-controls={"project-panel-" + project.external_id}
          onclick={() => handleProjectHeaderClick(project.external_id)}
          onkeydown={(e) => handleKeydown(e, () => handleProjectHeaderClick(project.external_id))}
          onkeyup={(e) => handleKeyup(e, () => handleProjectHeaderClick(project.external_id))}
        >
          {@html chevronIcon}
          <span class="project-name">{project.name}</span>
          {#if showOrgNames && project.org?.name}
            <span class="project-org">{project.org.name}</span>
          {/if}
          <div class="project-menu">
            <button
              class="project-menu-btn"
              title="Project options"
              onclick={(e) => handleMenuBtnClick(e, project.external_id)}
            >
              {@html menuIcon}
            </button>
            <div class="project-menu-dropdown" class:open={openMenuId === project.external_id}>
              <div class="menu-title">PROJECT</div>
              <button
                class="project-menu-item"
                onclick={(e) => handleNewPageFromMenu(e, project.external_id)}
              >
                {@html newPageIcon}
                New Page
              </button>
              <button
                class="project-menu-item"
                onclick={(e) => handleShare(e, project)}
              >
                {@html shareIcon}
                Share
              </button>
              <button
                class="project-menu-item"
                onclick={(e) => handleRename(e, project.external_id, project.name)}
              >
                {@html renameIcon}
                Rename
              </button>
              <button
                class="project-menu-item"
                onclick={(e) => handleDownload(e, project.external_id)}
              >
                {@html downloadIcon}
                Download
              </button>
              <button
                class="project-menu-item"
                onclick={(e) => handleImport(e, project.external_id, project.name)}
              >
                {@html importIcon}
                Notion &rsaquo; Import
              </button>
              <button
                class="project-menu-item project-menu-delete"
                onclick={(e) => handleDelete(e, project.external_id, project.name)}
              >
                {@html deleteIcon}
                Delete
              </button>
            </div>
          </div>
        </div>
        <div class="sidebar-project-pages" id={"project-panel-" + project.external_id}>
          {#each project.pages || [] as page (page.external_id)}
            <div
              class="sidebar-item"
              class:active={page.external_id === activePageId}
              aria-current={page.external_id === activePageId ? "page" : undefined}
              role="button"
              tabindex="0"
              onclick={() => handlePageClick(page.external_id, project.external_id)}
              onkeydown={(e) => handleKeydown(e, () => handlePageClick(page.external_id, project.external_id))}
              onkeyup={(e) => handleKeyup(e, () => handlePageClick(page.external_id, project.external_id))}
            >
              <span class="page-title">{page.title || "Untitled"}</span>
              <span class="page-filetype">{page.filetype || "md"}</span>
              {#if page.access_code}
                <button
                  class="page-shared-indicator"
                  title="View-only link active"
                  onclick={(e) => handleSharePage(e, page.external_id, page.title)}
                >
                  {@html globeIcon}
                </button>
              {/if}
              <div class="page-menu">
                <button
                  class="page-menu-btn"
                  title="Page options"
                  onclick={(e) => handlePageMenuBtnClick(e, page.external_id)}
                >
                  {@html pageMenuIcon}
                </button>
                <div class="page-menu-dropdown" class:open={openPageMenuId === page.external_id}>
                  <div class="menu-title">PAGE</div>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handlePageRename(e, page.external_id)}
                  >
                    {@html renameIcon}
                    Rename
                  </button>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handlePageDownload(e, page.external_id)}
                  >
                    {@html downloadIcon}
                    Download
                  </button>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handleChangePageType(e, page.external_id, page.title, page.filetype)}
                  >
                    {@html changeTypeIcon}
                    Change type
                  </button>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handleSharePage(e, page.external_id, page.title)}
                  >
                    {@html shareIcon}
                    Share
                  </button>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handlePageCopyLink(e, page.external_id)}
                  >
                    {@html copyIcon}
                    Copy link
                  </button>
                  <button
                    class="page-menu-item"
                    onclick={(e) => handlePageInsertLink(e, page.external_id, page.title)}
                  >
                    {@html insertIcon}
                    Insert link
                  </button>
                  <button
                    class="page-menu-item page-menu-delete"
                    onclick={(e) => handlePageDelete(e, page.external_id, page.title)}
                  >
                    {@html deleteIcon}
                    Delete
                  </button>
                </div>
              </div>
            </div>
          {/each}
          {#if showFilesSection}
            {@const filesExpanded = expandedFilesSections.has(project.external_id)}
            {@const files = getFilesList(project.external_id)}
            <div
              class="sidebar-files-header"
              class:expanded={filesExpanded}
              role="button"
              tabindex="0"
              aria-expanded={filesExpanded}
              aria-controls={"files-panel-" + project.external_id}
              onclick={(e) => handleFilesSectionClick(e, project.external_id)}
              onkeydown={(e) => handleKeydown(e, () => handleFilesSectionClick(e, project.external_id))}
              onkeyup={(e) => handleKeyup(e, () => handleFilesSectionClick(e, project.external_id))}
            >
              {@html smallChevronIcon}
              {@html folderIcon}
              <span class="files-label">Files</span>
              {#if files.length > 0}
                <span class="files-count">{files.length}</span>
              {/if}
            </div>
            {#if filesExpanded}
              <div class="sidebar-files-list" id={"files-panel-" + project.external_id}>
                {#if files.length === 0}
                  <div class="sidebar-files-empty">No files uploaded</div>
                {:else}
                  {#each files as file (file.external_id)}
                    <div
                      class="sidebar-file-item"
                      role="button"
                      tabindex="0"
                      onclick={(e) => handleFileClick(e, file)}
                      onkeydown={(e) => handleKeydown(e, () => handleFileClick(e, file))}
                      onkeyup={(e) => handleKeyup(e, () => handleFileClick(e, file))}
                      title={file.filename}
                    >
                      {@html fileIcon}
                      <span class="file-name">{file.filename}</span>
                      {#if file.size_bytes}
                        <span class="file-size">{formatFileSize(file.size_bytes, { compact: true })}</span>
                      {/if}
                      <div class="file-menu">
                        <button
                          class="file-menu-btn"
                          title="File options"
                          onclick={(e) => handleFileMenuBtnClick(e, file.external_id)}
                        >
                          {@html pageMenuIcon}
                        </button>
                        <div class="file-menu-dropdown" class:open={openFileMenuId === file.external_id}>
                          <div class="menu-title">FILE</div>
                          <button
                            class="file-menu-item"
                            onclick={(e) => handleFileCopyLink(e, file)}
                          >
                            {@html copyIcon}
                            Copy link
                          </button>
                          <button
                            class="file-menu-item"
                            onclick={(e) => handleFileInsertLink(e, file)}
                          >
                            {@html insertIcon}
                            Insert link
                          </button>
                          {#if isImageFile(file.filename)}
                            <button
                              class="file-menu-item"
                              onclick={(e) => handleFileInsertPreview(e, file)}
                            >
                              {@html imageIcon}
                              Insert preview
                            </button>
                          {/if}
                          <button
                            class="file-menu-item"
                            onclick={(e) => handleFileDownload(e, file)}
                          >
                            {@html downloadIcon}
                            Download
                          </button>
                          <button
                            class="file-menu-item file-menu-delete"
                            onclick={(e) => handleFileDelete(e, file, project.external_id)}
                          >
                            {@html deleteIcon}
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  {/each}
                {/if}
              </div>
            {/if}
          {/if}
          <button
            class="sidebar-new-page-btn"
            onclick={(e) => handleNewPageClick(e, project.external_id)}
          >
            + New Page
          </button>
        </div>
      </div>
    {/each}
  {/if}
</div>
