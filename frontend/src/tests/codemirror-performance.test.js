/**
 * CodeMirror ↔ Yjs Binding Performance Tests
 *
 * Performance tests for CodeMirror editor integration with Yjs CRDT.
 * Tests run in two modes:
 * - Default: Fast, CI-friendly (smaller datasets, lenient thresholds)
 * - Full: Thorough testing (larger datasets, strict thresholds) via PERF_FULL=1
 */

import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import * as Y from "yjs";
import { yCollab } from "y-codemirror.next";
import { getConfig, runPerfTest, measureTime, calculateOverhead } from "./helpers/perf-utils.js";
import { createYjsDoc, generateLines } from "./helpers/fixtures.js";

describe("[PERF] CodeMirror ↔ Yjs Binding", () => {
  let ydoc, ytext, view;

  beforeEach(() => {
    ydoc = new Y.Doc();
    ytext = ydoc.getText("codemirror");
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
  });

  test("[PERF] initialize editor on large document", async () => {
    const numLines = getConfig(1000, 5000);
    const threshold = getConfig(1000, 500); // Default: 1s, Full: 500ms

    // Pre-populate Yjs document
    const content = generateLines(numLines, { lineLength: 80 });
    ytext.insert(0, content);

    // Measure time to initialize CodeMirror with Yjs binding
    const { duration } = await runPerfTest(
      "initialize editor on large document",
      () => {
        const state = EditorState.create({
          doc: content, // Start with content directly
          extensions: [yCollab(ytext)],
        });

        view = new EditorView({
          state,
          parent: document.createElement("div"),
        });
      },
      threshold,
      {
        metadata: {
          numLines,
          contentLength: content.length,
        },
      }
    );

    // Verify editor was initialized with correct content
    expect(view.state.doc.length).toBeGreaterThan(0);
    expect(view.state.doc.lines).toBe(numLines);
  });

  test("[PERF] Yjs update to editor state reflection", async () => {
    const insertLines = getConfig(50, 100);
    const threshold = getConfig(200, 100); // Default: 200ms, Full: 100ms

    // Initialize editor with small document
    const initialContent = "Initial content\n";
    ytext.insert(0, initialContent);

    const state = EditorState.create({
      doc: initialContent,
      extensions: [yCollab(ytext)],
    });

    view = new EditorView({
      state,
      parent: document.createElement("div"),
    });

    // Measure time for Yjs update to reflect in editor
    const insertContent = generateLines(insertLines, { lineLength: 70 });

    const { duration } = await runPerfTest(
      "Yjs update to editor state reflection",
      () => {
        // Apply update to Yjs document
        ytext.insert(ytext.length, insertContent);

        // The yCollab binding should automatically update the editor state
        // We're measuring the time it takes for the binding to process the update
      },
      threshold,
      {
        metadata: {
          insertLines,
          insertSize: insertContent.length,
        },
      }
    );

    // Verify editor reflects the update
    expect(view.state.doc.length).toBeGreaterThan(initialContent.length);
  });

  test("[PERF] common user actions", async () => {
    const blockSize = getConfig(20, 50);
    const singleLineThreshold = getConfig(50, 30);
    const blockThreshold = getConfig(100, 50);

    // Initialize editor with some content
    const initialContent = generateLines(100, { lineLength: 80 });
    ytext.insert(0, initialContent);

    const state = EditorState.create({
      doc: initialContent,
      extensions: [yCollab(ytext)],
    });

    view = new EditorView({
      state,
      parent: document.createElement("div"),
    });

    // Action 1: Insert single line
    const { duration: singleLineTime } = await measureTime(() => {
      view.dispatch({
        changes: { from: 0, insert: "New line\n" },
      });
    });

    console.log(`[PERF] Insert single line: ${singleLineTime.toFixed(2)}ms`);

    if (singleLineTime > singleLineThreshold * 2) {
      console.warn(
        `⚠️  Insert single line (${singleLineTime.toFixed(
          2
        )}ms) > 2x threshold (${singleLineThreshold}ms)`
      );
    }
    expect(singleLineTime).toBeLessThan(singleLineThreshold * 3);

    // Action 2: Insert block (paste simulation)
    const blockContent = generateLines(blockSize, { lineLength: 70 });
    const currentLength = view.state.doc.length;
    const insertPos = Math.min(100, currentLength); // Insert at position 100 or end

    const { duration: blockInsertTime } = await measureTime(() => {
      view.dispatch({
        changes: { from: insertPos, insert: blockContent },
      });
    });

    console.log(`[PERF] Insert ${blockSize} lines: ${blockInsertTime.toFixed(2)}ms`);

    if (blockInsertTime > blockThreshold * 2) {
      console.warn(
        `⚠️  Insert block (${blockInsertTime.toFixed(2)}ms) > 2x threshold (${blockThreshold}ms)`
      );
    }
    expect(blockInsertTime).toBeLessThan(blockThreshold * 3);

    // Action 3: Delete range
    const deleteThreshold = getConfig(50, 30);
    const deleteEnd = Math.min(500, view.state.doc.length);

    const { duration: deleteTime } = await measureTime(() => {
      view.dispatch({
        changes: { from: 0, to: deleteEnd },
      });
    });

    console.log(`[PERF] Delete range: ${deleteTime.toFixed(2)}ms`);

    if (deleteTime > deleteThreshold * 2) {
      console.warn(
        `⚠️  Delete range (${deleteTime.toFixed(2)}ms) > 2x threshold (${deleteThreshold}ms)`
      );
    }
    expect(deleteTime).toBeLessThan(deleteThreshold * 3);
  });

  test("[PERF] Yjs binding overhead", async () => {
    const numOperations = getConfig(100, 500);
    const content = generateLines(50, { lineLength: 80 });

    // Test 1: Editor WITHOUT Yjs binding (baseline)
    const baselineState = EditorState.create({
      doc: content,
      extensions: [], // No Yjs binding
    });

    const baselineView = new EditorView({
      state: baselineState,
      parent: document.createElement("div"),
    });

    const { duration: baselineDuration } = await measureTime(() => {
      for (let i = 0; i < numOperations; i++) {
        baselineView.dispatch({
          changes: { from: 0, insert: "x" },
        });
      }
    });

    baselineView.destroy();

    console.log(
      `[PERF] Baseline (no Yjs): ${baselineDuration.toFixed(2)}ms for ${numOperations} ops`
    );

    // Test 2: Editor WITH Yjs binding
    ytext.insert(0, content);

    const yjsState = EditorState.create({
      doc: "",
      extensions: [yCollab(ytext)],
    });

    view = new EditorView({
      state: yjsState,
      parent: document.createElement("div"),
    });

    const { duration: yjsDuration } = await measureTime(() => {
      for (let i = 0; i < numOperations; i++) {
        view.dispatch({
          changes: { from: 0, insert: "x" },
        });
      }
    });

    console.log(`[PERF] With Yjs binding: ${yjsDuration.toFixed(2)}ms for ${numOperations} ops`);

    // Calculate overhead
    const overhead = calculateOverhead(yjsDuration, baselineDuration);
    console.log(`[PERF] Yjs binding overhead: ${overhead.toFixed(2)}%`);

    // Warn if overhead > 30%
    if (overhead > 30) {
      console.warn(`⚠️  Yjs binding overhead (${overhead.toFixed(2)}%) > 30%`);
    }

    // Fail if overhead > 50%
    expect(overhead).toBeLessThan(50);
  });
});
