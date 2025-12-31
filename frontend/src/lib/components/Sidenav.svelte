<script>
  import { API_BASE_URL } from "../../config.js";
  import { csrfFetch } from "../../csrf.js";
  import { confirm, prompt, shareProject, changePageType } from "../modal.js";
  import { showToast } from "../toast.js";
  import { validateProjectName } from "../validation.js";
  import {
    getProjects,
    getActivePageId,
    getCurrentProjectId,
    getShowOrgNames,
    setCurrentProject,
    navigateToPage,
    createNewPage,
    updateProjectName,
    notifyProjectDeleted,
  } from "../stores/sidenav.svelte.js";

  // Icons
  const chevronIcon = `<svg class="project-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
  const menuIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>`;
  const shareIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>`;
  const renameIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
  const downloadIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
  const deleteIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
  const changeTypeIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M9 15l2 2 4-4"></path></svg>`;

  // Local state
  let openMenuId = $state(null);
  let openPageMenuId = $state(null);

  // Derived state using getters
  let projects = $derived(getProjects());
  let activePageId = $derived(getActivePageId());
  let currentProjectId = $derived(getCurrentProjectId());
  let showOrgNames = $derived(getShowOrgNames());

  // Small menu icon for pages
  const pageMenuIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>`;

  function handlePageClick(pageId, projectId) {
    closeMobileSidebar();
    navigateToPage(pageId, projectId);
  }

  function handleNewPageClick(e, projectId) {
    e.stopPropagation();
    createNewPage(projectId);
  }

  function handleProjectHeaderClick(projectId, pages) {
    const isCurrentlyExpanded = projectId === currentProjectId;
    if (isCurrentlyExpanded) return;

    setCurrentProject(projectId);

    // Navigate to first page if available
    if (pages?.length > 0) {
      navigateToPage(pages[0].external_id, projectId);
    }
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
  }

  async function handleShare(e, projectId, projectName) {
    e.stopPropagation();
    closeAllMenus();
    shareProject({ projectId, projectName });
  }

  async function handleRename(e, projectId, projectName) {
    e.stopPropagation();
    closeAllMenus();

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
    window.location.href = `${API_BASE_URL}/api/projects/${projectId}/download/`;
  }

  function handlePageDownload(e, pageId) {
    e.stopPropagation();
    closeAllMenus();
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
    changePageType({
      pageId,
      pageTitle: pageTitle || "Untitled",
      currentType: filetype || "md",
    });
  }

  function handleFiletypeClick(e, pageId, pageTitle, filetype) {
    e.stopPropagation();
    changePageType({
      pageId,
      pageTitle: pageTitle || "Untitled",
      currentType: filetype || "md",
    });
  }

  async function handlePageDelete(e, pageId, pageTitle) {
    e.stopPropagation();
    closeAllMenus();

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

  // Close menus when clicking outside
  function handleGlobalClick(e) {
    if (!e.target.closest(".project-menu") && !e.target.closest(".page-menu")) {
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
      {@const isExpanded = project.external_id === currentProjectId}
      <div
        class="sidebar-project"
        class:expanded={isExpanded}
        data-project-id={project.external_id}
      >
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="sidebar-project-header"
          onclick={() => handleProjectHeaderClick(project.external_id, project.pages)}
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
              <button
                class="project-menu-item"
                onclick={(e) => handleShare(e, project.external_id, project.name)}
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
                class="project-menu-item project-menu-delete"
                onclick={(e) => handleDelete(e, project.external_id, project.name)}
              >
                {@html deleteIcon}
                Delete
              </button>
            </div>
          </div>
        </div>
        <div class="sidebar-project-pages">
          {#each project.pages || [] as page (page.external_id)}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="sidebar-item"
              class:active={page.external_id === activePageId}
              onclick={() => handlePageClick(page.external_id, project.external_id)}
            >
              <span class="page-title">{page.title || "Untitled"}</span>
              <button
                class="page-filetype page-filetype-btn"
                title="Change page type"
                onclick={(e) => handleFiletypeClick(e, page.external_id, page.title, page.filetype)}
              >{page.filetype || "md"}</button>
              <div class="page-menu">
                <button
                  class="page-menu-btn"
                  title="Page options"
                  onclick={(e) => handlePageMenuBtnClick(e, page.external_id)}
                >
                  {@html pageMenuIcon}
                </button>
                <div class="page-menu-dropdown" class:open={openPageMenuId === page.external_id}>
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
