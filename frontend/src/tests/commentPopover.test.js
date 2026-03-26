/**
 * Comment Popover Tests
 *
 * Tests that the comment button tooltip shows at the right time:
 * - Mouse selection: button appears only after mouseup, not during drag
 * - Keyboard selection: button appears after 300ms debounce, not immediately
 * - Debounce resets when keyboard selection keeps extending
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { EditorState, EditorSelection } from "@codemirror/state";
import { EditorView, showTooltip } from "@codemirror/view";
import { commentPopover, _commentButtonController } from "../commentPopover.js";

function createEditor(content = "Hello World\nThis is a test line\nThird line here") {
  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "600px";
  document.body.appendChild(parent);

  const state = EditorState.create({
    doc: content,
    extensions: [commentPopover],
  });

  const view = new EditorView({ state, parent });
  return { view, parent };
}

/** Return non-null tooltips from the showTooltip facet. */
function getActiveTooltips(view) {
  return view.state.facet(showTooltip).filter((t) => t !== null);
}

/** Get the controller plugin instance to simulate mouse state. */
function getController(view) {
  return view.plugin(_commentButtonController);
}

describe("Comment Popover — button timing", () => {
  let view, parent;

  beforeEach(() => {
    vi.useFakeTimers();
    ({ view, parent } = createEditor());
  });

  afterEach(() => {
    view.destroy();
    parent.remove();
    vi.useRealTimers();
  });

  // --- Keyboard selection ---

  describe("Keyboard selection (no mouse involved)", () => {
    test("button does NOT appear immediately when selection changes", () => {
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      expect(getActiveTooltips(view)).toHaveLength(0);
    });

    test("button appears after 300ms debounce", () => {
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      expect(getActiveTooltips(view)).toHaveLength(0);

      vi.advanceTimersByTime(300);

      expect(getActiveTooltips(view)).toHaveLength(1);
      expect(getActiveTooltips(view)[0].above).toBe(false); // button, not form
    });

    test("debounce resets when selection keeps extending", () => {
      // First selection change
      view.dispatch({ selection: EditorSelection.single(0, 5) });

      // 200ms later — still within debounce
      vi.advanceTimersByTime(200);
      expect(getActiveTooltips(view)).toHaveLength(0);

      // Extend selection (simulates another Shift+Right)
      view.dispatch({ selection: EditorSelection.single(0, 10) });

      // 200ms after second change (400ms total) — debounce was reset
      vi.advanceTimersByTime(200);
      expect(getActiveTooltips(view)).toHaveLength(0);

      // 100ms more (300ms after last change)
      vi.advanceTimersByTime(100);
      expect(getActiveTooltips(view)).toHaveLength(1);
    });

    test("button hides immediately when selection is cleared", () => {
      // Show the button
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      vi.advanceTimersByTime(300);
      expect(getActiveTooltips(view)).toHaveLength(1);

      // Clear selection (cursor with no range)
      view.dispatch({ selection: EditorSelection.cursor(0) });
      expect(getActiveTooltips(view)).toHaveLength(0);
    });

    test("button hides when selection changes after being visible", () => {
      // Show the button
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      vi.advanceTimersByTime(300);
      expect(getActiveTooltips(view)).toHaveLength(1);

      // Change selection — button should hide and debounce again
      view.dispatch({ selection: EditorSelection.single(0, 8) });
      expect(getActiveTooltips(view)).toHaveLength(0);

      // After debounce it reappears at the new position
      vi.advanceTimersByTime(300);
      const tooltips = getActiveTooltips(view);
      expect(tooltips).toHaveLength(1);
      expect(tooltips[0].pos).toBe(8);
    });
  });

  // --- Mouse selection ---
  //
  // CM6's built-in mousedown handler calls posAndSideAtCoords() which
  // relies on real layout and crashes in happy-dom. We simulate mouse
  // state by directly setting the controller's mouseIsDown flag.

  describe("Mouse selection", () => {
    test("button does NOT appear during mouse drag", () => {
      const ctrl = getController(view);

      // Simulate mousedown
      ctrl.mouseIsDown = true;

      // Simulate drag by changing selection
      view.dispatch({ selection: EditorSelection.single(0, 5) });

      // No button during drag, even after debounce time
      vi.advanceTimersByTime(500);
      expect(getActiveTooltips(view)).toHaveLength(0);
    });

    test("button appears after mouseup", () => {
      const ctrl = getController(view);

      // Simulate mousedown + drag
      ctrl.mouseIsDown = true;
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      expect(getActiveTooltips(view)).toHaveLength(0);

      // Simulate mouseup (fires on document)
      document.dispatchEvent(new MouseEvent("mouseup"));

      // The controller uses requestAnimationFrame after mouseup
      vi.advanceTimersByTime(16);

      expect(getActiveTooltips(view)).toHaveLength(1);
    });

    test("no button if mouseup with empty selection (just a click)", () => {
      const ctrl = getController(view);

      // Simulate mousedown (no drag — selection stays collapsed)
      ctrl.mouseIsDown = true;

      // Simulate mouseup
      document.dispatchEvent(new MouseEvent("mouseup"));
      vi.advanceTimersByTime(16);

      expect(getActiveTooltips(view)).toHaveLength(0);
    });

    test("button hides when new mouse drag starts", () => {
      // First: show the button via keyboard selection
      view.dispatch({ selection: EditorSelection.single(0, 5) });
      vi.advanceTimersByTime(300);
      expect(getActiveTooltips(view)).toHaveLength(1);

      const ctrl = getController(view);

      // Start a new mouse drag — button should hide
      ctrl.mouseIsDown = true;
      view.dispatch({ selection: EditorSelection.single(2, 8) });
      expect(getActiveTooltips(view)).toHaveLength(0);

      // Still hidden while dragging
      vi.advanceTimersByTime(500);
      expect(getActiveTooltips(view)).toHaveLength(0);

      // Mouseup — button reappears
      document.dispatchEvent(new MouseEvent("mouseup"));
      vi.advanceTimersByTime(16);
      expect(getActiveTooltips(view)).toHaveLength(1);
    });
  });
});
