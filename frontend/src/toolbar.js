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

export function setupToolbar(editorView) {
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
    },
  });

  console.log("[Toolbar] Svelte component mounted");
}
