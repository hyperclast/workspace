import { mount, unmount } from "svelte";

import { subscribeToPageEvents } from "../collaboration.js";
import { API_BASE_URL } from "../config.js";
import { csrfFetch } from "../csrf.js";
import { metrics } from "../lib/metrics.js";

export async function loadPdfPage(page, pageLoadSpan, contentLength) {
  pageLoadSpan.addEvent("pdf_viewer_init_start");

  const toolbarWrapper = document.getElementById("toolbar-wrapper");
  if (toolbarWrapper) toolbarWrapper.style.display = "none";

  // PDF pages skip Yjs collab, so setupPresenceUI never runs and the
  // styled #presence-indicator div would otherwise render as an empty
  // pill in the breadcrumb row.
  const presenceIndicator = document.getElementById("presence-indicator");
  if (presenceIndicator) presenceIndicator.style.display = "none";

  // Same reason for the collab-status dot: SPA-navigating from a markdown
  // page leaves #collab-status-wrapper mounted from the prior session, and
  // its last status (often "offline" from the destroyed provider) would
  // otherwise hover-popover "Offline" on a page that has no collab at all.
  const collabStatusWrapper = document.getElementById("collab-status-wrapper");
  if (collabStatusWrapper) collabStatusWrapper.style.display = "none";

  window.editorView = null;

  const editorEl = document.getElementById("editor");
  editorEl.innerHTML = "";
  editorEl.style.padding = "0";

  const pdfFileId = page.details?.pdf_file_id;
  let fileDownloadUrl = "";
  if (pdfFileId) {
    try {
      const fileResp = await csrfFetch(`${API_BASE_URL}/api/v1/files/${pdfFileId}/`);
      if (fileResp.ok) {
        const fileData = await fileResp.json();
        fileDownloadUrl = fileData.link || fileData.download_url || "";
      }
    } catch (err) {
      console.error("[PdfPage] failed to fetch file metadata:", err);
    }
  }

  const { default: PdfPageView } = await import("./PdfPageView.svelte");

  const targetPageId = page.external_id;
  const pageId = page.external_id;
  let pdfSpanEnded = false;
  const onPdfFirstPaint = (event) => {
    const detail = event.detail || {};
    if (detail.pageId !== targetPageId) return;
    if (pdfSpanEnded) return;
    pdfSpanEnded = true;
    window.removeEventListener("pdfFirstPageRendered", onPdfFirstPaint);
    if (detail.status === "error") {
      pageLoadSpan.end({ status: "error", phase: "pdf_load_error" });
      return;
    }
    pageLoadSpan.addEvent("pdf_first_page_rendered");
    pageLoadSpan.end({ status: "success", phase: "pdf_visible" });
    metrics.event("page_visible", { pageId, contentLength, timestamp: Date.now() });
  };
  window.addEventListener("pdfFirstPageRendered", onPdfFirstPaint);

  const pdfApp = mount(PdfPageView, {
    target: editorEl,
    props: { fileDownloadUrl, pageId: targetPageId },
  });

  // PDF pages skip Yjs collaboration, so they need their own thin WebSocket
  // subscription to receive comment / AI-review broadcasts in real time.
  const unsubscribeEvents = subscribeToPageEvents(targetPageId);

  window.pdfPageViewCleanup = () => {
    window.removeEventListener("pdfFirstPageRendered", onPdfFirstPaint);
    try {
      unsubscribeEvents();
    } catch (err) {
      console.warn("[loadPdfPage] subscribeToPageEvents cleanup failed:", err);
    }
    try {
      unmount(pdfApp);
    } catch (err) {
      console.warn("[loadPdfPage] PdfPageView unmount failed:", err);
    }
  };

  pageLoadSpan.addEvent("pdf_viewer_init_complete");
}
