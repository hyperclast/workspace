/**
 * Large Document Editor Initialization Test
 *
 * Directly benchmarks EditorState.create + new EditorView with a ~7MB document
 * to reproduce the 10-second blocking seen in Firefox.
 *
 * Tests two configurations:
 * 1. Full extensions (markdown parser, code fences, folding, decorations)
 * 2. Minimal extensions (what large docs should use after the fix)
 *
 * Run with:
 *   npm test -- src/tests/large-doc-init.test.js --run
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState, Compartment } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, indentWithTab } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { foldGutter, foldService, codeFolding } from "@codemirror/language";
import { codeFenceField, decorateFormatting } from "../decorateFormatting.js";
import { decorateCodeBlocks } from "../decorateCodeBlocks.js";
import { decorateEmails } from "../decorateEmails.js";
import { decorateLinks, linkClickHandler } from "../decorateLinks.js";
import { findSectionFold } from "../findSectionFold.js";
import { sectionFoldHover } from "../sectionFoldHover.js";
import { largeFileModeExtension } from "../largeFileMode.js";
import { LARGE_FILE_BYTES } from "../config/performance.js";
import { generateLines } from "./helpers/fixtures.js";

// Generate a ~7MB document similar to the user's "Jan 18, 2026" page
// ~10K lines with ~700 chars each ≈ 7MB
const LARGE_DOC_LINES = 10_000;
const LARGE_DOC_LINE_LENGTH = 700;

function generateLargeDoc() {
  return generateLines(LARGE_DOC_LINES, { lineLength: LARGE_DOC_LINE_LENGTH });
}

// Full extension set (what initializeEditor uses for normal docs)
function fullExtensions() {
  return [
    largeFileModeExtension,
    EditorView.lineWrapping,
    markdown(),
    codeFenceField,
    decorateFormatting,
    decorateCodeBlocks,
    decorateEmails,
    decorateLinks,
    linkClickHandler,
    foldGutter(),
    codeFolding(),
    foldService.of(findSectionFold),
    sectionFoldHover,
    keymap.of(defaultKeymap),
    keymap.of([indentWithTab]),
  ];
}

// Minimal extension set (what initializeEditor now uses for docs > 1MB)
function minimalExtensions() {
  return [
    largeFileModeExtension,
    EditorView.lineWrapping,
    decorateEmails,
    decorateLinks,
    linkClickHandler,
    keymap.of(defaultKeymap),
    keymap.of([indentWithTab]),
  ];
}

describe("Large document editor initialization", () => {
  let view;
  let content;

  // Generate content once
  content = generateLargeDoc();

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
  });

  test("content is above LARGE_FILE_BYTES threshold", () => {
    console.log(
      `Generated doc: ${(content.length / 1024 / 1024).toFixed(2)} MB, ${
        content.split("\n").length
      } lines`
    );
    expect(content.length).toBeGreaterThan(LARGE_FILE_BYTES);
    expect(content.length).toBeGreaterThan(5_000_000); // >5MB to be realistic
  });

  test("FULL extensions: EditorState.create + new EditorView timing", () => {
    const parent = document.createElement("div");
    document.body.appendChild(parent);

    const t0 = performance.now();
    const state = EditorState.create({
      doc: content,
      extensions: fullExtensions(),
    });
    const t1 = performance.now();

    view = new EditorView({ state, parent });
    const t2 = performance.now();

    const stateTime = t1 - t0;
    const viewTime = t2 - t1;
    const totalTime = t2 - t0;

    console.log(`[FULL] EditorState.create: ${stateTime.toFixed(1)}ms`);
    console.log(`[FULL] new EditorView:     ${viewTime.toFixed(1)}ms`);
    console.log(`[FULL] Total:              ${totalTime.toFixed(1)}ms`);
    console.log(`[FULL] doc.lines=${state.doc.lines}, doc.length=${state.doc.length}`);

    document.body.removeChild(parent);

    // This test documents the timing — it's expected to be slow with full extensions
    // In Chromium (Vitest/jsdom) it may be fast; in Firefox it's 10+ seconds
    expect(totalTime).toBeGreaterThan(0);
  });

  test("MINIMAL extensions: EditorState.create + new EditorView timing", () => {
    const parent = document.createElement("div");
    document.body.appendChild(parent);

    const t0 = performance.now();
    const state = EditorState.create({
      doc: content,
      extensions: minimalExtensions(),
    });
    const t1 = performance.now();

    view = new EditorView({ state, parent });
    const t2 = performance.now();

    const stateTime = t1 - t0;
    const viewTime = t2 - t1;
    const totalTime = t2 - t0;

    console.log(`[MINIMAL] EditorState.create: ${stateTime.toFixed(1)}ms`);
    console.log(`[MINIMAL] new EditorView:     ${viewTime.toFixed(1)}ms`);
    console.log(`[MINIMAL] Total:              ${totalTime.toFixed(1)}ms`);
    console.log(`[MINIMAL] doc.lines=${state.doc.lines}, doc.length=${state.doc.length}`);

    document.body.removeChild(parent);

    // Minimal extensions should be significantly faster
    expect(totalTime).toBeGreaterThan(0);
  });

  test("BARE MINIMUM: just EditorState + EditorView, no extensions", () => {
    const parent = document.createElement("div");
    document.body.appendChild(parent);

    const t0 = performance.now();
    const state = EditorState.create({ doc: content });
    const t1 = performance.now();

    view = new EditorView({ state, parent });
    const t2 = performance.now();

    const stateTime = t1 - t0;
    const viewTime = t2 - t1;
    const totalTime = t2 - t0;

    console.log(`[BARE] EditorState.create: ${stateTime.toFixed(1)}ms`);
    console.log(`[BARE] new EditorView:     ${viewTime.toFixed(1)}ms`);
    console.log(`[BARE] Total:              ${totalTime.toFixed(1)}ms`);

    document.body.removeChild(parent);
    expect(totalTime).toBeGreaterThan(0);
  });

  test("MARKDOWN ONLY: just markdown() parser extension", () => {
    const parent = document.createElement("div");
    document.body.appendChild(parent);

    const t0 = performance.now();
    const state = EditorState.create({
      doc: content,
      extensions: [markdown()],
    });
    const t1 = performance.now();

    view = new EditorView({ state, parent });
    const t2 = performance.now();

    const stateTime = t1 - t0;
    const viewTime = t2 - t1;
    const totalTime = t2 - t0;

    console.log(`[MARKDOWN] EditorState.create: ${stateTime.toFixed(1)}ms`);
    console.log(`[MARKDOWN] new EditorView:     ${viewTime.toFixed(1)}ms`);
    console.log(`[MARKDOWN] Total:              ${totalTime.toFixed(1)}ms`);

    document.body.removeChild(parent);
    expect(totalTime).toBeGreaterThan(0);
  });

  test("DEFERRED COMPARTMENT: empty init then inject markdown after view exists", () => {
    const parent = document.createElement("div");
    document.body.appendChild(parent);

    const mdCompartment = new Compartment();
    const mdExtensions = [markdown()];

    // Step 1: Create editor with empty compartment (fast)
    const t0 = performance.now();
    const state = EditorState.create({
      doc: content,
      extensions: [mdCompartment.of([])],
    });
    const t1 = performance.now();

    view = new EditorView({ state, parent });
    const t2 = performance.now();

    // Step 2: Inject markdown parser now that view exists (parser uses viewport)
    view.dispatch({
      effects: mdCompartment.reconfigure(mdExtensions),
    });
    const t3 = performance.now();

    const initTime = t2 - t0;
    const injectTime = t3 - t2;

    console.log(`[DEFERRED] Init (no markdown):     ${initTime.toFixed(1)}ms`);
    console.log(`[DEFERRED] Inject markdown:         ${injectTime.toFixed(1)}ms`);
    console.log(`[DEFERRED] Total:                   ${(t3 - t0).toFixed(1)}ms`);
    console.log(
      `[DEFERRED] vs FULL sync:            init is ${initTime.toFixed(1)}ms instead of ~330ms`
    );

    document.body.removeChild(parent);

    // Init should be fast (< 50ms) since no markdown parser
    expect(initTime).toBeLessThan(50);
  });
});
