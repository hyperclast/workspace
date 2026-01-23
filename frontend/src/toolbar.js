/**
 * Toolbar bridge - mounts Svelte toolbar component
 */

import { mount, unmount } from "svelte";
import Toolbar from "./lib/components/Toolbar.svelte";

let toolbarInstance = null;

export function resetToolbar() {
  if (toolbarInstance) {
    unmount(toolbarInstance);
    toolbarInstance = null;
  }
}

/**
 * Setup the toolbar component.
 * @param {EditorView} editorView - CodeMirror editor view
 * @param {Function} onFileUpload - Callback for file upload action
 * @param {boolean} canUploadFiles - Whether the user can upload files (default: true)
 *   Set to false to disable the file upload button (e.g., for viewers or page-only users)
 * @param {boolean} showFileUpload - Whether to show the file upload button (default: true)
 *   Set to false to completely hide the button (e.g., when filehub feature is disabled)
 */
export function setupToolbar(
  editorView,
  onFileUpload = null,
  canUploadFiles = true,
  showFileUpload = true
) {
  console.log(
    "[Toolbar] setupToolbar called with onFileUpload:",
    onFileUpload,
    "canUploadFiles:",
    canUploadFiles,
    "showFileUpload:",
    showFileUpload
  );
  const container = document.getElementById("toolbar-wrapper");
  if (!container) {
    console.error("[Toolbar] Container #toolbar-wrapper not found");
    return;
  }

  // Clean up existing instance
  if (toolbarInstance) {
    unmount(toolbarInstance);
  }

  container.innerHTML = "";
  container.style.display = "block";

  toolbarInstance = mount(Toolbar, {
    target: container,
    props: {
      editorView: editorView,
      tableUtils: window.tableUtils || null,
      onFileUpload: onFileUpload,
      canUploadFiles: canUploadFiles,
      showFileUpload: showFileUpload,
    },
  });

  console.log("[Toolbar] Svelte component mounted with props:", {
    editorView: !!editorView,
    tableUtils: !!window.tableUtils,
    onFileUpload: !!onFileUpload,
    canUploadFiles: canUploadFiles,
    showFileUpload: showFileUpload,
  });
}
