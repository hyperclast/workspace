import { writable } from "svelte/store";

export const PDF_PAGE_CONTEXT = Symbol("pdfPageContext");

export function createPdfPageContext() {
  return {
    pages: writable([]),
    selection: writable(null),
  };
}
