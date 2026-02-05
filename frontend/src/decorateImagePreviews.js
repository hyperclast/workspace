/**
 * Image Preview Decorations
 *
 * Renders inline image previews for markdown image syntax: ![alt](url)
 * Only previews internal file URLs matching /files/{project}/{file}/{token}/
 * Shows raw syntax when cursor is inside the image syntax for editing.
 */

import { Decoration, ViewPlugin, WidgetType, EditorView } from "@codemirror/view";

// Regex to match markdown image syntax: ![alt](url)
const IMAGE_SYNTAX_REGEX = /!\[([^\]]*)\]\(([^)]+)\)/g;

// Pattern for internal file URLs - matches both relative (/files/...) and absolute (http://host/files/...)
// File IDs can contain hyphens (UUIDs like 9ddb7185-cb5c-46c5-89db-bc59f602b0e2)
// Access tokens use secrets.token_urlsafe() which produces base64url chars (alphanumeric plus - and _)
const INTERNAL_FILE_PATTERN =
  /^(https?:\/\/[^/]+)?\/files\/[a-zA-Z0-9]+\/[a-zA-Z0-9-]+\/[a-zA-Z0-9_-]+\/?$/;

/**
 * Widget that renders an image preview
 */
class ImagePreviewWidget extends WidgetType {
  constructor(src, alt, fullMatch) {
    super();
    this.src = src;
    this.alt = alt;
    this.fullMatch = fullMatch;
  }

  eq(other) {
    return other.src === this.src && other.alt === this.alt;
  }

  toDOM() {
    const container = document.createElement("span");
    container.className = "image-preview-container";
    container.setAttribute("data-image-src", this.src);

    const img = document.createElement("img");
    img.src = this.src;
    img.alt = this.alt || "Image preview";
    img.className = "image-preview";
    img.loading = "lazy";
    img.draggable = false;

    // Handle click on image - open lightbox, prevent cursor movement
    const src = this.src;
    const alt = this.alt;
    img.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    img.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openLightbox(src, alt);
    });

    // Error handling for failed loads
    img.onerror = () => {
      container.innerHTML = "";
      const errorDiv = document.createElement("div");
      errorDiv.className = "image-preview-error";
      errorDiv.innerHTML = `<span class="image-preview-error-icon">&#x26A0;</span> Failed to load: ${
        this.alt || "image"
      }`;
      container.appendChild(errorDiv);
    };

    container.appendChild(img);
    return container;
  }

  ignoreEvent(event) {
    // Ignore mouse events on the widget to prevent cursor positioning
    return !/^mouse/.test(event.type);
  }
}

/**
 * ViewPlugin that computes and manages image preview decorations
 */
export const decorateImagePreviews = ViewPlugin.fromClass(
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
          const regex = new RegExp(IMAGE_SYNTAX_REGEX.source, "g");

          while ((match = regex.exec(lineText)) !== null) {
            const start = line.from + match.index;
            const end = start + match[0].length;
            const altText = match[1];
            const url = match[2];

            // Only preview internal file URLs
            if (!INTERNAL_FILE_PATTERN.test(url)) continue;

            const cursorInImage = cursorPos >= start && cursorPos <= end;

            if (cursorInImage) {
              // Show raw syntax with special styling when cursor is inside
              builder.push(
                Decoration.mark({
                  class: "image-syntax-raw",
                }).range(start, end)
              );
            } else {
              // Replace the entire syntax with the image preview widget
              builder.push(
                Decoration.replace({
                  widget: new ImagePreviewWidget(url, altText, match[0]),
                }).range(start, end)
              );
            }
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
 * Click handler for image previews - opens lightbox
 */
export const imageClickHandler = EditorView.domEventHandlers({
  click(event, view) {
    const target = event.target;

    // Check if clicked on an image preview
    if (target.classList.contains("image-preview")) {
      event.preventDefault();
      openLightbox(target.src, target.alt);
      return true;
    }

    // Check if clicked on the container
    const container = target.closest(".image-preview-container");
    if (container) {
      const img = container.querySelector(".image-preview");
      if (img) {
        event.preventDefault();
        openLightbox(img.src, img.alt);
        return true;
      }
    }

    return false;
  },
});

/**
 * Opens a lightbox overlay to view the image at full size
 */
export function openLightbox(src, alt) {
  // Remove existing lightbox if any
  const existingLightbox = document.querySelector(".image-lightbox");
  if (existingLightbox) {
    existingLightbox.remove();
  }

  const lightbox = document.createElement("div");
  lightbox.className = "image-lightbox";
  lightbox.setAttribute("role", "dialog");
  lightbox.setAttribute("aria-label", "Image lightbox");

  const img = document.createElement("img");
  img.src = src;
  img.alt = alt || "Full size image";
  img.className = "image-lightbox-img";

  // Toolbar with download and close buttons
  const toolbar = document.createElement("div");
  toolbar.className = "image-lightbox-toolbar";

  const downloadBtn = document.createElement("button");
  downloadBtn.className = "image-lightbox-btn";
  downloadBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
  downloadBtn.setAttribute("aria-label", "Download image");
  downloadBtn.title = "Download";

  const closeBtn = document.createElement("button");
  closeBtn.className = "image-lightbox-btn image-lightbox-close-btn";
  closeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
  closeBtn.setAttribute("aria-label", "Close lightbox");
  closeBtn.title = "Close (Escape)";

  toolbar.appendChild(downloadBtn);
  toolbar.appendChild(closeBtn);

  // Close on click outside image or on close button
  const closeLightbox = () => {
    lightbox.remove();
    document.removeEventListener("keydown", handleKeydown);
  };

  const handleKeydown = (e) => {
    if (e.key === "Escape") {
      closeLightbox();
    }
  };

  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) {
      closeLightbox();
    }
  });

  closeBtn.addEventListener("click", closeLightbox);
  downloadBtn.addEventListener("click", () => {
    window.open(src, "_blank");
  });
  document.addEventListener("keydown", handleKeydown);

  lightbox.appendChild(toolbar);
  lightbox.appendChild(img);
  document.body.appendChild(lightbox);

  // Focus the close button for accessibility
  closeBtn.focus();
}
