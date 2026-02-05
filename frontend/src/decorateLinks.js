import { Decoration, ViewPlugin, WidgetType, EditorView } from "@codemirror/view";
import { openPdfViewer } from "./lib/stores/pdfViewer.svelte.js";
import { openLightbox } from "./decorateImagePreviews.js";

const MARKDOWN_LINK_REGEX = /\[([^\]]+)\]\(([^)]+)\)/g;
const INTERNAL_LINK_PATTERN = /^\/pages\/([a-zA-Z0-9]+)\/?$/;

// Pattern for internal file URLs - matches /files/{project}/{file}/{token}/
const FILE_LINK_PATTERN =
  /^(https?:\/\/[^/]+)?\/files\/[a-zA-Z0-9]+\/[a-zA-Z0-9-]+\/[a-zA-Z0-9_-]+\/?$/;

// Image extensions that can be previewed
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"];

/**
 * Check if a link points to a PDF file.
 * Detects by filename extension in the link text.
 * @param {string} url - The URL to check
 * @param {string} linkText - The visible link text (often the filename)
 * @returns {boolean}
 */
function isPdfLink(url, linkText) {
  // Only check internal file URLs
  if (!FILE_LINK_PATTERN.test(url)) return false;
  // Check if link text ends with .pdf (case-insensitive)
  return linkText.toLowerCase().endsWith(".pdf");
}

/**
 * Check if a link points to an image file.
 * Detects by filename extension in the link text.
 * @param {string} url - The URL to check
 * @param {string} linkText - The visible link text (often the filename)
 * @returns {boolean}
 */
function isImageLink(url, linkText) {
  // Only check internal file URLs
  if (!FILE_LINK_PATTERN.test(url)) return false;
  // Check if link text ends with an image extension
  const lowerText = linkText.toLowerCase();
  return IMAGE_EXTENSIONS.some((ext) => lowerText.endsWith(ext));
}

class LinkWidget extends WidgetType {
  constructor(isInternal, url) {
    super();
    this.isInternal = isInternal;
    this.url = url;
  }

  eq(other) {
    return other.isInternal === this.isInternal && other.url === this.url;
  }

  toDOM() {
    // Styles are in editor.css (.link-icon, .link-icon-internal, .link-icon-external)
    const icon = document.createElement("span");
    icon.className = this.isInternal
      ? "link-icon link-icon-internal"
      : "link-icon link-icon-external";
    icon.textContent = this.isInternal ? "📄" : "🔗";
    return icon;
  }
}

export const decorateLinks = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.computeDecorations(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged || update.selectionSet) {
        this.decorations = this.computeDecorations(update.view);
      }
    }

    computeDecorations(view) {
      const builder = [];
      const { state } = view;
      const cursorPos = state.selection.main.head;

      for (const { from, to } of view.visibleRanges) {
        const startLine = state.doc.lineAt(from).number;
        const endLine = state.doc.lineAt(to).number;

        for (let lineNum = startLine; lineNum <= endLine; lineNum++) {
          const line = state.doc.line(lineNum);
          const lineText = line.text;

          let match;
          const regex = new RegExp(MARKDOWN_LINK_REGEX.source, "g");

          while ((match = regex.exec(lineText)) !== null) {
            const start = line.from + match.index;
            const end = start + match[0].length;
            const linkText = match[1];
            const url = match[2];

            if (!linkText) continue;

            // Skip image syntax - preceded by ! character
            if (match.index > 0 && lineText[match.index - 1] === "!") continue;

            // Skip @mentions - they use format @[username](@id) where URL starts with @
            if (url.startsWith("@")) continue;

            const cursorInLink = cursorPos >= start && cursorPos <= end;
            const isInternal = INTERNAL_LINK_PATTERN.test(url);

            const bracketStart = start;
            const textStart = start + 1;
            const textEnd = textStart + linkText.length;

            if (!cursorInLink) {
              builder.push(
                Decoration.replace({ widget: new LinkWidget(isInternal, url) }).range(
                  bracketStart,
                  textStart
                )
              );

              builder.push(Decoration.replace({}).range(textEnd, end));
            }

            const linkClass = isInternal
              ? "format-link format-link-internal"
              : "format-link format-link-external";
            builder.push(
              Decoration.mark({
                class: linkClass,
                attributes: {
                  "data-url": url,
                  "data-internal": isInternal ? "true" : "false",
                },
              }).range(textStart, textEnd)
            );
          }
        }
      }

      builder.sort((a, b) => a.from - b.from || a.startSide - b.startSide);

      return Decoration.set(builder, true);
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

/**
 * Helper to extract link info from a click/mousedown target
 */
function getLinkInfo(target) {
  if (!target.classList.contains("format-link") && !target.closest(".format-link")) {
    return null;
  }
  const linkEl = target.classList.contains("format-link") ? target : target.closest(".format-link");
  const url = linkEl.dataset.url;
  if (!url) return null;
  return {
    url,
    isInternal: linkEl.dataset.internal === "true",
    linkText: linkEl.textContent || "",
  };
}

export const linkClickHandler = EditorView.domEventHandlers({
  // Intercept mousedown to prevent cursor positioning for previewable file links
  mousedown(event, view) {
    const linkInfo = getLinkInfo(event.target);
    if (!linkInfo) return false;

    // For PDF and image links, prevent default to stop cursor positioning
    // This keeps the link decorated (not showing raw markdown)
    if (
      isPdfLink(linkInfo.url, linkInfo.linkText) ||
      isImageLink(linkInfo.url, linkInfo.linkText)
    ) {
      event.preventDefault();
      return true;
    }
    return false;
  },

  click(event, view) {
    const linkInfo = getLinkInfo(event.target);
    if (!linkInfo) return false;

    const { url, isInternal, linkText } = linkInfo;

    // Handle PDF links: regular click opens viewer, Cmd/Ctrl+click opens in new tab
    if (isPdfLink(url, linkText)) {
      event.preventDefault();
      if (event.metaKey || event.ctrlKey) {
        // Power-user escape hatch: open PDF in new tab
        window.open(url, "_blank", "noopener,noreferrer");
      } else {
        // Regular click: open in-app PDF viewer
        openPdfViewer({ url, filename: linkText });
      }
      return true;
    }

    // Handle image links: regular click opens lightbox, Cmd/Ctrl+click opens in new tab
    if (isImageLink(url, linkText)) {
      event.preventDefault();
      if (event.metaKey || event.ctrlKey) {
        // Power-user escape hatch: open image in new tab
        window.open(url, "_blank", "noopener,noreferrer");
      } else {
        // Regular click: open in-app lightbox
        openLightbox(url, linkText);
      }
      return true;
    }

    if (event.metaKey || event.ctrlKey) {
      event.preventDefault();

      if (isInternal) {
        const pageIdMatch = url.match(INTERNAL_LINK_PATTERN);
        if (pageIdMatch) {
          const pageId = pageIdMatch[1];
          window.history.pushState({}, "", `/pages/${pageId}/`);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }
      } else {
        window.open(url, "_blank", "noopener,noreferrer");
      }
      return true;
    }
    return false;
  },
});
