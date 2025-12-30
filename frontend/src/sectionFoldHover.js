import { ViewPlugin } from "@codemirror/view";
import { getSections, findRootSectionAtPos, collectAllLinesInTree } from "./getSections.js";

export const sectionFoldHover = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.view = view;
      this.tree = [];
      this.hoveredLines = new Set();
      this.updateSections();

      this.handleMouseMove = this.handleMouseMove.bind(this);
      this.handleMouseLeave = this.handleMouseLeave.bind(this);

      view.dom.addEventListener("mousemove", this.handleMouseMove);
      view.dom.addEventListener("mouseleave", this.handleMouseLeave);
    }

    update(update) {
      if (update.docChanged) {
        this.updateSections();
        this.updateGutterVisibility();
      }
    }

    updateSections() {
      const { tree } = getSections(this.view.state.doc);
      this.tree = tree;
    }

    handleMouseMove(event) {
      const pos = this.view.posAtCoords({ x: event.clientX, y: event.clientY });
      if (pos === null) {
        this.clearHover();
        return;
      }

      const rootSection = findRootSectionAtPos(this.tree, pos);
      if (!rootSection) {
        this.clearHover();
        return;
      }

      const newHoveredLines = collectAllLinesInTree(rootSection, this.view.state.doc);

      if (this.setsEqual(this.hoveredLines, newHoveredLines)) {
        return;
      }

      this.hoveredLines = newHoveredLines;
      this.updateGutterVisibility();
    }

    handleMouseLeave() {
      this.clearHover();
    }

    clearHover() {
      if (this.hoveredLines.size === 0) return;
      this.hoveredLines = new Set();
      this.updateGutterVisibility();
    }

    updateGutterVisibility() {
      const foldGutter = this.view.dom.querySelector(".cm-gutter.cm-foldGutter");
      if (!foldGutter) return;

      const gutterElements = foldGutter.querySelectorAll(".cm-gutterElement");
      const editorRect = this.view.dom.getBoundingClientRect();
      const scrollTop = this.view.scrollDOM.scrollTop;

      gutterElements.forEach((el) => {
        const elRect = el.getBoundingClientRect();
        const relativeTop = elRect.top - editorRect.top + scrollTop;
        const lineBlock = this.view.lineBlockAtHeight(relativeTop);

        if (lineBlock) {
          try {
            const lineNumber = this.view.state.doc.lineAt(lineBlock.from).number;
            if (this.hoveredLines.has(lineNumber)) {
              el.classList.add("section-hover");
            } else {
              el.classList.remove("section-hover");
            }
          } catch {
            el.classList.remove("section-hover");
          }
        } else {
          el.classList.remove("section-hover");
        }
      });
    }

    setsEqual(a, b) {
      if (a.size !== b.size) return false;
      for (const item of a) {
        if (!b.has(item)) return false;
      }
      return true;
    }

    destroy() {
      this.view.dom.removeEventListener("mousemove", this.handleMouseMove);
      this.view.dom.removeEventListener("mouseleave", this.handleMouseLeave);
    }
  }
);
