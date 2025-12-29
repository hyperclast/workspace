import { Decoration, ViewPlugin, MatchDecorator } from "@codemirror/view";

const emailRegex = /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}\b/g;

export const decorateEmails = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.computeDecorations(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.computeDecorations(update.view);
      }
    }

    computeDecorations(view) {
      const emailMark = Decoration.mark({ class: "email-highlight" });
      const emailDecorator = new MatchDecorator({
        regexp: emailRegex,
        decoration: () => emailMark,
      });

      return emailDecorator.createDeco(view);
    }

    destroy() {}
  },
  {
    decorations: (v) => v.decorations,
  }
);
