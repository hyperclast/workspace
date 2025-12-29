/**
 * Yjs/CRDT Performance Tests
 *
 * Micro-benchmarks for Yjs CRDT operations to track performance and detect regressions.
 * Tests run in two modes:
 * - Default: Fast, CI-friendly (1k lines, lenient thresholds)
 * - Full: Thorough testing (5k lines, strict thresholds) via PERF_FULL=1
 */

import { describe, test, expect } from "vitest";
import * as Y from "yjs";
import { getConfig, runPerfTest, logPerf, measureSize, formatBytes } from "./helpers/perf-utils.js";
import {
  createYjsDoc,
  generateUpdates,
  applyUpdates,
  createMultipleYjsDocs,
  simulateConcurrentEdits,
} from "./helpers/fixtures.js";

describe("[PERF] Yjs CRDT Micro-benchmarks", () => {
  test("[PERF] apply large batch of updates", async () => {
    // Configuration based on mode
    const numLines = getConfig(1000, 5000); // Default: 1k, Full: 5k
    const numUpdates = 100;
    const threshold = getConfig(500, 200); // Default: 500ms, Full: 200ms

    // Generate updates from a source document
    const sourceDoc = createYjsDoc(numLines);
    const updates = generateUpdates(sourceDoc, numUpdates);

    // Create a fresh target document
    const targetDoc = new Y.Doc();

    // Measure time to apply all updates
    const { duration } = await runPerfTest(
      "apply large batch of updates",
      () => {
        applyUpdates(targetDoc, updates);
      },
      threshold,
      {
        metadata: {
          numLines,
          numUpdates,
          totalUpdateSize: formatBytes(updates.reduce((sum, u) => sum + u.length, 0)),
        },
      }
    );

    // Verify the document was properly reconstructed
    const targetText = targetDoc.getText("codemirror");
    expect(targetText.length).toBeGreaterThan(0);
  });

  test("[PERF] generate updates for large document", async () => {
    const numLines = getConfig(1000, 5000);
    const threshold = getConfig(200, 500);

    // Measure time to create doc and generate update
    const { duration, result } = await runPerfTest(
      "generate updates for large document",
      () => {
        const doc = createYjsDoc(numLines);
        const update = Y.encodeStateAsUpdate(doc);
        return { doc, update };
      },
      threshold
    );

    const { doc, update } = result;
    const updateSize = measureSize(update);

    // Log the update size
    console.log(`[PERF] Update size: ${formatBytes(updateSize)}`);

    // Soft assertion on size (warn if > 2x expected)
    const maxSize = getConfig(
      500 * 1024, // Default: 500 KB for 1k lines
      2 * 1024 * 1024 // Full: 2 MB for 5k lines
    );

    if (updateSize > maxSize) {
      console.warn(
        `⚠️  Update size (${formatBytes(updateSize)}) exceeds expected (${formatBytes(maxSize)})`
      );
    }

    // Hard limit: fail if dramatically oversized (3x)
    expect(updateSize).toBeLessThan(maxSize * 3);

    // Verify doc was created
    expect(doc.getText("codemirror").length).toBeGreaterThan(0);
  });

  test("[PERF] resolve concurrent edits", async () => {
    const numDocs = 3;
    const editsPerDoc = getConfig(100, 500); // Default: 100, Full: 500
    const threshold = getConfig(100, 1000); // Default: 100ms, Full: 1000ms (more edits = more time)

    // Create multiple documents
    const docs = createMultipleYjsDocs(numDocs, 10);

    // Measure time for concurrent edits to converge
    const { duration, result } = await runPerfTest(
      "resolve concurrent edits",
      () => {
        return simulateConcurrentEdits(docs, editsPerDoc);
      },
      threshold,
      {
        metadata: {
          numDocs,
          editsPerDoc,
          totalEdits: numDocs * editsPerDoc,
        },
      }
    );

    // Verify convergence
    expect(result.converged).toBe(true);
    expect(result.totalUpdates).toBe(numDocs * editsPerDoc);

    // All docs should have identical content
    const texts = docs.map((doc) => doc.getText("codemirror").toString());
    expect(texts[0]).toBe(texts[1]);
    expect(texts[1]).toBe(texts[2]);
  });

  test("[PERF] update size for typical operations", () => {
    const doc = new Y.Doc();
    const text = doc.getText("codemirror");

    // Baseline: Insert initial content
    text.insert(0, "Hello World\n".repeat(10));
    const baselineUpdate = Y.encodeStateAsUpdate(doc);
    const baselineSize = measureSize(baselineUpdate);

    console.log(`[PERF] Baseline update size: ${formatBytes(baselineSize)}`);

    // Operation 1: Insert single line
    const doc1 = new Y.Doc();
    Y.applyUpdate(doc1, baselineUpdate);
    const text1 = doc1.getText("codemirror");
    text1.insert(0, "New line\n");
    const insertLineUpdate = Y.encodeStateAsUpdate(doc1);
    const insertLineSize = measureSize(insertLineUpdate) - baselineSize;

    console.log(`[PERF] Insert line size: ${formatBytes(insertLineSize)}`);

    // Operation 2: Delete line
    const doc2 = new Y.Doc();
    Y.applyUpdate(doc2, baselineUpdate);
    const text2 = doc2.getText("codemirror");
    text2.delete(0, 12); // Delete one "Hello World\n"
    const deleteLineUpdate = Y.encodeStateAsUpdate(doc2);
    const deleteLineSize = measureSize(deleteLineUpdate) - baselineSize;

    console.log(`[PERF] Delete line size: ${formatBytes(deleteLineSize)}`);

    // Operation 3: Insert block
    const doc3 = new Y.Doc();
    Y.applyUpdate(doc3, baselineUpdate);
    const text3 = doc3.getText("codemirror");
    text3.insert(0, "Block line\n".repeat(20));
    const insertBlockUpdate = Y.encodeStateAsUpdate(doc3);
    const insertBlockSize = measureSize(insertBlockUpdate) - baselineSize;

    console.log(`[PERF] Insert block size: ${formatBytes(insertBlockSize)}`);

    // Soft assertions: warn if sizes are unexpectedly large
    // These are rough estimates - actual sizes may vary
    const expectedInsertLine = 100; // ~100 bytes
    const expectedDeleteLine = 50; // ~50 bytes
    const expectedInsertBlock = 1000; // ~1 KB

    if (insertLineSize > expectedInsertLine * 2) {
      console.warn(`⚠️  Insert line size (${formatBytes(insertLineSize)}) > 2x expected`);
    }

    if (deleteLineSize > expectedDeleteLine * 2) {
      console.warn(`⚠️  Delete line size (${formatBytes(deleteLineSize)}) > 2x expected`);
    }

    if (insertBlockSize > expectedInsertBlock * 2) {
      console.warn(`⚠️  Insert block size (${formatBytes(insertBlockSize)}) > 2x expected`);
    }

    // Hard limits: fail if dramatically oversized (10x for size tests)
    expect(insertLineSize).toBeLessThan(expectedInsertLine * 10);
    expect(deleteLineSize).toBeLessThan(expectedDeleteLine * 10);
    expect(insertBlockSize).toBeLessThan(expectedInsertBlock * 10);
  });
});
