import { Decoration, ViewPlugin, WidgetType, EditorView } from "@codemirror/view";

const MARKDOWN_LINK_REGEX = /\[([^\]]+)\]\(([^)]+)\)/g;
const INTERNAL_LINK_PATTERN = /^\/pages\/([a-zA-Z0-9]+)\/?$/;

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
    const icon = document.createElement("span");
    icon.className = this.isInternal
      ? "link-icon link-icon-internal"
      : "link-icon link-icon-external";
    icon.textContent = this.isInternal ? "📄" : "🔗";
    icon.style.fontSize = "0.85em";
    icon.style.marginRight = "2px";
    icon.style.opacity = "0.7";
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

export const linkClickHandler = EditorView.domEventHandlers({
  click(event, view) {
    const target = event.target;

    if (target.classList.contains("format-link") || target.closest(".format-link")) {
      const linkEl = target.classList.contains("format-link")
        ? target
        : target.closest(".format-link");
      const url = linkEl.dataset.url;
      const isInternal = linkEl.dataset.internal === "true";

      if (!url) return false;

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
    }
    return false;
  },
});
