import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateDates } from "../../decorateDates.js";

describe("decorateDates - Date Pattern Recognition", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("decorates full month name with day and year", () => {
    const doc = "Meeting on January 15th, 2025 at noon";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateDates);
    expect(plugin).toBeDefined();
    expect(plugin.decorations.size).toBeGreaterThan(0);

    // Check DOM has the date marked
    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("January 15th, 2025");
  });

  test("decorates abbreviated month name with day", () => {
    const doc = "Due date is Feb 28th";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("Feb 28th");
  });

  test("decorates month with day without ordinal suffix", () => {
    const doc = "Event on March 15 2024";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("March 15 2024");
  });

  test("decorates numeric date MM/DD/YYYY", () => {
    const doc = "Deadline is 06/19/2025";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("06/19/2025");
  });

  test("decorates numeric date M/D/YY (short form)", () => {
    const doc = "Meeting on 6/9/25";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("6/9/25");
  });

  test("decorates numeric date without year M/D", () => {
    const doc = "Next review: 12/15";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("12/15");
  });

  test("decorates ISO format date YYYY-MM-DD", () => {
    const doc = "Published on 2025-06-19";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("2025-06-19");
  });

  test("decorates multiple dates in same document", () => {
    const doc = "Start: January 1st, 2025. End: 12/31/2025. Review: 2025-06-15.";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(3);
    expect(dateElements[0].textContent).toBe("January 1st, 2025");
    expect(dateElements[1].textContent).toBe("12/31/2025");
    expect(dateElements[2].textContent).toBe("2025-06-15");
  });

  test("decorates all month abbreviations", () => {
    const doc = `Jan 1, Feb 2, Mar 3, Apr 4, May 5, Jun 6,
Jul 7, Aug 8, Sep 9, Oct 10, Nov 11, Dec 12`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(12);
  });

  test("decorates September abbreviations (Sep and Sept)", () => {
    const doc = "Sep 1 and Sept 15";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(2);
    expect(dateElements[0].textContent).toBe("Sep 1");
    expect(dateElements[1].textContent).toBe("Sept 15");
  });

  test("does not decorate non-date numbers", () => {
    const doc = "Room 123, page 456, 789 items";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(0);
  });

  test("does not decorate incomplete date patterns", () => {
    const doc = "Just January or just 2025 or just /";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(0);
  });

  test("decorates date at start of document", () => {
    const doc = "2025-01-15 is the start date";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("2025-01-15");
  });

  test("decorates date at end of document", () => {
    const doc = "The end date is December 31st, 2025";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    const dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
    expect(dateElements[0].textContent).toBe("December 31st, 2025");
  });

  test("updates decorations when document changes", () => {
    const initialDoc = "No dates here";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [decorateDates],
      }),
      parent: document.createElement("div"),
    });

    // Initially no decorations
    let dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(0);

    // Add a date
    view.dispatch({
      changes: { from: view.state.doc.length, insert: " January 15th, 2025" },
    });

    // Should now have decorations
    dateElements = view.dom.querySelectorAll(".hyper-date");
    expect(dateElements.length).toBe(1);
  });
});
