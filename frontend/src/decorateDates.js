import { Decoration, MatchDecorator, ViewPlugin } from "@codemirror/view";

const dateRegex = new RegExp(
  [
    // Jan 12th, 2025
    "\\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)",
    "\\s+\\d{1,2}(?:st|nd|rd|th)?(?:,?\\s*\\d{4})?\\b",
    // 06/19/2025 or 6/9/25
    "|\\b\\d{1,2}/\\d{1,2}(?:/\\d{2,4})?\\b",
    // 2025-06-19
    "|\\b\\d{4}-\\d{1,2}-\\d{1,2}\\b",
  ].join(""),
  "gi",
);

const dateMark = Decoration.mark({
  class: "hyper-date",
});

export const decorateDates = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.decorator.createDeco(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.decorator.createDeco(update.view);
      }
    }

    decorator = new MatchDecorator({
      regexp: dateRegex,
      decoration: (match) => dateMark,
    });
  },
  {
    decorations: (v) => v.decorations,
  },
);

/**
 * Setup click handler for date elements.
 * Call this after the editor element has been created.
 */
export function setupDateClickHandler() {
  const editorElement = document.getElementById("editor");
  if (editorElement) {
    editorElement.addEventListener("click", (event) => {
      const target = event.target.closest(".hyper-date");
      if (target) {
        console.log("Clicked date:", target.textContent);
      }
    });
  }
}
