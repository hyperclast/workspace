import { Decoration, ViewPlugin } from "@codemirror/view";
import { getUserInfo } from "./config.js";

// Format: @[username](@user_id) - the @ prefix in ID distinguishes from regular links
const MENTION_REGEX = /@\[([^\]]+)\]\(@([a-zA-Z0-9]+)\)/g;

export const decorateMentions = ViewPlugin.fromClass(
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
      const currentUserExternalId = getUserInfo().user?.externalId;

      for (const { from, to } of view.visibleRanges) {
        const startLine = state.doc.lineAt(from).number;
        const endLine = state.doc.lineAt(to).number;

        for (let lineNum = startLine; lineNum <= endLine; lineNum++) {
          const line = state.doc.line(lineNum);
          const lineText = line.text;

          let match;
          const regex = new RegExp(MENTION_REGEX.source, "g");

          while ((match = regex.exec(lineText)) !== null) {
            const start = line.from + match.index;
            const end = start + match[0].length;
            const username = match[1];
            const userId = match[2];

            if (!username) continue;

            const cursorInMention = cursorPos >= start && cursorPos <= end;
            const isOwn = userId === currentUserExternalId;

            // Position markers for the mention structure: @[username](@id)
            const atPos = start; // @
            const textStart = start + 2; // username start (after @[)
            const textEnd = textStart + username.length; // username end

            if (!cursorInMention) {
              // Hide @[ prefix, show just @ before username
              builder.push(Decoration.replace({}).range(atPos + 1, textStart)); // hide [

              // Hide ](@id)
              builder.push(Decoration.replace({}).range(textEnd, end));
            }

            // Apply highlight to the entire visible mention (@username or full syntax)
            const mentionClass = isOwn ? "mention mention-own" : "mention";
            const highlightStart = cursorInMention ? start : atPos;
            const highlightEnd = cursorInMention ? end : textEnd;
            builder.push(
              Decoration.mark({
                class: mentionClass,
                attributes: {
                  "data-user-id": userId,
                  "data-own": isOwn ? "true" : "false",
                },
              }).range(highlightStart, highlightEnd)
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
