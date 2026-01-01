/**
 * Log Module Entry Point
 * This module is lazily loaded only when a log page is opened.
 */

import { mount, unmount } from "svelte";
import LogViewer from "./LogViewer.svelte";

let logViewerInstance = null;

export function mountLogViewer(content, container) {
  if (logViewerInstance) {
    unmount(logViewerInstance);
    logViewerInstance = null;
  }

  container.innerHTML = "";

  logViewerInstance = mount(LogViewer, {
    target: container,
    props: { content },
  });

  return logViewerInstance;
}

export function unmountLogViewer() {
  if (logViewerInstance) {
    unmount(logViewerInstance);
    logViewerInstance = null;
  }
}
