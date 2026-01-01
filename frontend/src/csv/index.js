/**
 * CSV Module Entry Point
 * This module is lazily loaded only when a CSV page is opened.
 */

import { mount, unmount } from "svelte";
import CsvViewer from "./CsvViewer.svelte";

let csvViewerInstance = null;

export function mountCsvViewer(content, container) {
  if (csvViewerInstance) {
    unmount(csvViewerInstance);
    csvViewerInstance = null;
  }

  container.innerHTML = "";

  csvViewerInstance = mount(CsvViewer, {
    target: container,
    props: { content },
  });

  return csvViewerInstance;
}

export function unmountCsvViewer() {
  if (csvViewerInstance) {
    unmount(csvViewerInstance);
    csvViewerInstance = null;
  }
}
