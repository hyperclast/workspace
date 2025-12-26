import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateEmails } from "../../decorateEmails.js";

describe("decorateEmails - Email Pattern Recognition", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("decorates simple email address", () => {
    const doc = "Contact me at user@example.com for details";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateEmails);
    expect(plugin).toBeDefined();
    expect(plugin.decorations.size).toBeGreaterThan(0);

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("user@example.com");
  });

  test("decorates email with numbers in username", () => {
    const doc = "Email: john123@test.org";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("john123@test.org");
  });

  test("decorates email with dots in username", () => {
    const doc = "Send to first.last@company.com";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("first.last@company.com");
  });

  test("decorates email with hyphens in domain", () => {
    const doc = "Support: help@my-company.com";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("help@my-company.com");
  });

  test("decorates email with subdomain", () => {
    const doc = "Admin: admin@mail.example.co.uk";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("admin@mail.example.co.uk");
  });

  test("decorates email with plus sign in username", () => {
    const doc = "Test: user+tag@gmail.com";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("user+tag@gmail.com");
  });

  test("decorates email with underscore in username", () => {
    const doc = "Contact: user_name@test.io";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("user_name@test.io");
  });

  test("decorates multiple emails in same document", () => {
    const doc = "Email alice@example.com or bob@test.org for help";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(2);
    expect(emailElements[0].textContent).toBe("alice@example.com");
    expect(emailElements[1].textContent).toBe("bob@test.org");
  });

  test("decorates email at start of document", () => {
    const doc = "admin@site.com is the contact";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("admin@site.com");
  });

  test("decorates email at end of document", () => {
    const doc = "Contact us at support@company.net";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
    expect(emailElements[0].textContent).toBe("support@company.net");
  });

  test("does not decorate incomplete email (no TLD)", () => {
    const doc = "Invalid: user@localhost";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(0);
  });

  test("does not decorate malformed email patterns", () => {
    const doc = "Not emails: @example.com or user@ or @";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    const emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(0);
  });

  test("updates decorations when document changes", () => {
    const initialDoc = "No emails here";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [decorateEmails],
      }),
      parent: document.createElement("div"),
    });

    // Initially no decorations
    let emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(0);

    // Add an email
    view.dispatch({
      changes: { from: view.state.doc.length, insert: " user@example.com" },
    });

    // Should now have decorations
    emailElements = view.dom.querySelectorAll(".email-highlight");
    expect(emailElements.length).toBe(1);
  });
});
