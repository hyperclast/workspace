/**
 * Baseline Performance Tests
 *
 * Measures current performance metrics to establish baselines before
 * viewport-based optimizations. These tests should be run before and
 * after changes to quantify improvements.
 *
 * Run with: npm test -- src/tests/baseline-performance.test.js --run
 * Full mode: PERF_FULL=1 npm test -- src/tests/baseline-performance.test.js --run
 */

import { describe, test, expect, beforeEach, afterEach, beforeAll } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { defaultKeymap } from "@codemirror/commands";

import {
  DOCUMENT_SIZES,
  generateDocumentWithFormatting,
  generateDocumentWithLinks,
  generateMixedDocument,
  approximateByteSize,
} from "./helpers/large-fixtures.js";
import { getConfig, measureTime, logPerf, formatBytes, isFullMode } from "./helpers/perf-utils.js";

const RESULTS = {
  baselines: [],
};

function recordBaseline(name, size, metric, value, unit) {
  RESULTS.baselines.push({ name, size, metric, value, unit, timestamp: Date.now() });
}

function createMinimalEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [keymap.of(defaultKeymap), EditorView.lineWrapping],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "600px";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

describe("[BASELINE] Current Performance Metrics", () => {
  const testSizes = isFullMode()
    ? [
        { name: "small", lines: 100 },
        { name: "medium", lines: 5000 },
        { name: "large", lines: 50000 },
        { name: "xlarge", lines: 200000 },
      ]
    : [
        { name: "small", lines: 100 },
        { name: "medium", lines: 1000 },
        { name: "large", lines: 10000 },
      ];

  describe("Editor Initialization", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name} (${size.lines} lines): editor creation time`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const byteSize = approximateByteSize(content);

        const { duration } = await measureTime(() => {
          const { view, parent } = createMinimalEditor(content);
          view.destroy();
          parent.remove();
        });

        recordBaseline("editor_creation", size.name, "duration_ms", duration, "ms");
        recordBaseline("editor_creation", size.name, "content_bytes", byteSize, "bytes");

        console.log(`[BASELINE] Editor creation (${size.name}):`);
        console.log(`  Lines: ${size.lines}`);
        console.log(`  Size: ${formatBytes(byteSize)}`);
        console.log(`  Duration: ${duration.toFixed(2)}ms`);
        console.log(`  Rate: ${(size.lines / duration).toFixed(2)} lines/ms`);

        expect(duration).toBeGreaterThan(0);
      });
    }
  });

  describe("Keystroke Latency", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name}: single character insert latency`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const { view, parent } = createMinimalEditor(content);

        const iterations = getConfig(10, 50);
        const latencies = [];

        for (let i = 0; i < iterations; i++) {
          const pos = Math.floor(Math.random() * view.state.doc.length);

          const { duration } = await measureTime(() => {
            view.dispatch({
              changes: { from: pos, insert: "x" },
            });
          });

          latencies.push(duration);
        }

        const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;
        const maxLatency = Math.max(...latencies);
        const p95Latency = latencies.sort((a, b) => a - b)[Math.floor(latencies.length * 0.95)];

        recordBaseline("keystroke_latency", size.name, "avg_ms", avgLatency, "ms");
        recordBaseline("keystroke_latency", size.name, "max_ms", maxLatency, "ms");
        recordBaseline("keystroke_latency", size.name, "p95_ms", p95Latency, "ms");

        console.log(`[BASELINE] Keystroke latency (${size.name}):`);
        console.log(`  Avg: ${avgLatency.toFixed(2)}ms`);
        console.log(`  P95: ${p95Latency.toFixed(2)}ms`);
        console.log(`  Max: ${maxLatency.toFixed(2)}ms`);

        view.destroy();
        parent.remove();

        expect(avgLatency).toBeGreaterThan(0);
      });
    }
  });

  describe("Scroll Performance", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name}: viewport scroll time`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const { view, parent } = createMinimalEditor(content);

        const scrolls = getConfig(5, 20);
        const scrollTimes = [];

        for (let i = 0; i < scrolls; i++) {
          const targetLine = Math.floor(Math.random() * (view.state.doc.lines - 1)) + 1;

          const { duration } = await measureTime(() => {
            const line = view.state.doc.line(targetLine);
            view.dispatch({
              effects: EditorView.scrollIntoView(line.from, { y: "center" }),
            });
          });

          scrollTimes.push(duration);
        }

        const avgScrollTime = scrollTimes.reduce((a, b) => a + b, 0) / scrollTimes.length;

        recordBaseline("scroll_time", size.name, "avg_ms", avgScrollTime, "ms");

        console.log(`[BASELINE] Scroll time (${size.name}):`);
        console.log(`  Avg: ${avgScrollTime.toFixed(2)}ms per scroll`);

        view.destroy();
        parent.remove();

        expect(avgScrollTime).toBeGreaterThan(0);
      });
    }
  });

  describe("Document Operations", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name}: doc.toString() time`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const { view, parent } = createMinimalEditor(content);

        const iterations = getConfig(5, 20);
        const times = [];

        for (let i = 0; i < iterations; i++) {
          const { duration } = await measureTime(() => {
            const _ = view.state.doc.toString();
          });
          times.push(duration);
        }

        const avgTime = times.reduce((a, b) => a + b, 0) / times.length;

        recordBaseline("doc_toString", size.name, "avg_ms", avgTime, "ms");

        console.log(`[BASELINE] doc.toString() (${size.name}):`);
        console.log(`  Avg: ${avgTime.toFixed(2)}ms`);
        console.log(`  This is the operation we want to ELIMINATE from hot paths`);

        view.destroy();
        parent.remove();

        expect(avgTime).toBeGreaterThan(0);
      });

      test(`[BASELINE] ${size.name}: line iteration time`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const { view, parent } = createMinimalEditor(content);

        const { duration } = await measureTime(() => {
          for (let i = 1; i <= view.state.doc.lines; i++) {
            const line = view.state.doc.line(i);
            const _ = line.text;
          }
        });

        recordBaseline("line_iteration", size.name, "duration_ms", duration, "ms");
        recordBaseline(
          "line_iteration",
          size.name,
          "ms_per_1000_lines",
          (duration / size.lines) * 1000,
          "ms"
        );

        console.log(`[BASELINE] Full line iteration (${size.name}):`);
        console.log(`  Total: ${duration.toFixed(2)}ms for ${size.lines} lines`);
        console.log(`  Rate: ${((duration / size.lines) * 1000).toFixed(4)}ms per 1000 lines`);
        console.log(`  This is the pattern we want to REPLACE with viewport-only iteration`);

        view.destroy();
        parent.remove();

        expect(duration).toBeGreaterThan(0);
      });
    }
  });

  describe("Regex Matching", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name}: global regex matchAll time`, async () => {
        const content = generateDocumentWithLinks({ lines: size.lines, linksPerChunk: 5 });
        const LINK_REGEX = /\[([^\]]+)\]\(([^)]+)\)/g;

        const { duration } = await measureTime(() => {
          const matches = [...content.matchAll(LINK_REGEX)];
          return matches.length;
        });

        recordBaseline("regex_matchAll", size.name, "duration_ms", duration, "ms");

        console.log(`[BASELINE] Global regex matchAll (${size.name}):`);
        console.log(`  Duration: ${duration.toFixed(2)}ms`);
        console.log(`  This is what happens in decorateLinks with doc.toString().matchAll()`);

        expect(duration).toBeGreaterThan(0);
      });
    }
  });

  describe("Memory Usage", () => {
    for (const size of testSizes) {
      test(`[BASELINE] ${size.name}: memory impact of doc.toString()`, async () => {
        const content = generateMixedDocument({ lines: size.lines });
        const byteSize = approximateByteSize(content);
        const { view, parent } = createMinimalEditor(content);

        const copies = [];
        const copyCount = 5;

        for (let i = 0; i < copyCount; i++) {
          copies.push(view.state.doc.toString());
        }

        const totalAllocated = byteSize * copyCount;

        recordBaseline("memory_allocation", size.name, "per_copy_bytes", byteSize, "bytes");
        recordBaseline("memory_allocation", size.name, "total_copies", copyCount, "count");
        recordBaseline("memory_allocation", size.name, "total_bytes", totalAllocated, "bytes");

        console.log(`[BASELINE] Memory impact (${size.name}):`);
        console.log(`  Single toString(): ${formatBytes(byteSize)}`);
        console.log(`  With ${copyCount} copies: ${formatBytes(totalAllocated)}`);
        console.log(`  In current code, each decoration update creates multiple copies like this`);

        copies.length = 0;
        view.destroy();
        parent.remove();

        expect(byteSize).toBeGreaterThan(0);
      });
    }
  });

  afterAll(() => {
    console.log("\n" + "=".repeat(80));
    console.log("BASELINE SUMMARY");
    console.log("=".repeat(80));

    const grouped = {};
    for (const b of RESULTS.baselines) {
      const key = `${b.name}`;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(b);
    }

    for (const [name, results] of Object.entries(grouped)) {
      console.log(`\n${name}:`);
      for (const r of results) {
        const value =
          typeof r.value === "number"
            ? r.unit === "bytes"
              ? formatBytes(r.value)
              : `${r.value.toFixed(2)}${r.unit}`
            : r.value;
        console.log(`  ${r.size} - ${r.metric}: ${value}`);
      }
    }

    console.log("\n" + "=".repeat(80));
    console.log("These baselines will be compared against post-optimization results.");
    console.log("Target: All hot-path operations should be O(viewport) not O(document).");
    console.log("=".repeat(80) + "\n");
  });
});
