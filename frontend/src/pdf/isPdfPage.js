export const PDF_FILETYPE = "pdf";

export function isPdfPage(page) {
  return page?.details?.filetype === PDF_FILETYPE;
}
