/**
 * Large Document Test Fixtures
 *
 * Generators for creating large documents with specific patterns
 * for testing viewport-based decorations and performance.
 */

/**
 * Document size presets for consistent testing
 */
export const DOCUMENT_SIZES = {
  small: { lines: 100, approxBytes: 5000 },
  medium: { lines: 5000, approxBytes: 250000 },
  large: { lines: 50000, approxBytes: 2500000 }, // ~2.5MB
  xlarge: { lines: 200000, approxBytes: 10000000 }, // ~10MB
  xxlarge: { lines: 2000000, approxBytes: 100000000 }, // ~100MB
};

/**
 * Generate a document with markdown links at specific positions
 * @param {Object} config
 * @param {number} config.lines - Total number of lines
 * @param {number} config.linksPerChunk - Links per chunk of 100 lines
 * @param {boolean} config.internalLinks - Include internal page links
 * @returns {string}
 */
export function generateDocumentWithLinks(config = {}) {
  const { lines = 1000, linksPerChunk = 5, internalLinks = true } = config;
  const result = [];

  for (let i = 0; i < lines; i++) {
    const chunkPosition = i % 100;

    if (chunkPosition < linksPerChunk) {
      const linkType = internalLinks && chunkPosition % 2 === 0;
      if (linkType) {
        result.push(`Line ${i}: Check out [Page Title](/pages/abc123/) for more info.`);
      } else {
        result.push(`Line ${i}: Visit [External Site](https://example.com/path?a=1&b=2) here.`);
      }
    } else {
      result.push(`Line ${i}: This is regular text content without any special formatting.`);
    }
  }

  return result.join("\n");
}

/**
 * Generate a document with various formatting patterns
 * @param {Object} config
 * @param {number} config.lines - Total number of lines
 * @returns {string}
 */
export function generateDocumentWithFormatting(config = {}) {
  const { lines = 1000 } = config;
  const result = [];

  for (let i = 0; i < lines; i++) {
    const pattern = i % 20;

    switch (pattern) {
      case 0:
        result.push(`# Heading Level 1 at line ${i}`);
        break;
      case 1:
        result.push(`## Heading Level 2 at line ${i}`);
        break;
      case 2:
        result.push(`This line has **bold text** in it at line ${i}.`);
        break;
      case 3:
        result.push(`This line has __underlined text__ in it at line ${i}.`);
        break;
      case 4:
        result.push(`This line has \`inline code\` in it at line ${i}.`);
        break;
      case 5:
        result.push(`- Bullet list item at line ${i}`);
        break;
      case 6:
        result.push(`  - Nested bullet at line ${i}`);
        break;
      case 7:
        result.push(`1. Ordered list item at line ${i}`);
        break;
      case 8:
        result.push(`- [ ] Checkbox unchecked at line ${i}`);
        break;
      case 9:
        result.push(`- [x] Checkbox checked at line ${i}`);
        break;
      case 10:
        result.push(`> Blockquote at line ${i}`);
        break;
      case 11:
        result.push("```javascript");
        break;
      case 12:
        result.push(`const line${i} = "code content";`);
        break;
      case 13:
        result.push("```");
        break;
      case 14:
        result.push("---");
        break;
      default:
        result.push(`Line ${i}: Regular paragraph text content here.`);
    }
  }

  return result.join("\n");
}

/**
 * Generate a document with markdown tables
 * @param {Object} config
 * @param {number} config.tables - Number of tables
 * @param {number} config.rowsPerTable - Rows per table
 * @param {number} config.linesBetween - Lines between tables
 * @returns {string}
 */
export function generateDocumentWithTables(config = {}) {
  const { tables = 100, rowsPerTable = 5, linesBetween = 10 } = config;
  const result = [];

  for (let t = 0; t < tables; t++) {
    result.push(`## Table ${t + 1}`);
    result.push("");
    result.push("| Column A | Column B | Column C | Column D |");
    result.push("|----------|----------|----------|----------|");

    for (let r = 0; r < rowsPerTable; r++) {
      result.push(`| Cell ${t}-${r}-A | Cell ${t}-${r}-B | Cell ${t}-${r}-C | Cell ${t}-${r}-D |`);
    }

    result.push("");
    for (let l = 0; l < linesBetween; l++) {
      result.push(`Filler line ${t * linesBetween + l} between tables.`);
    }
  }

  return result.join("\n");
}

/**
 * Generate a document with many checkboxes (todo list style)
 * @param {Object} config
 * @param {number} config.checkboxes - Number of checkboxes
 * @param {number} config.checkedRatio - Ratio of checked boxes (0-1)
 * @returns {string}
 */
export function generateDocumentWithCheckboxes(config = {}) {
  const { checkboxes = 5000, checkedRatio = 0.3 } = config;
  const result = [];

  result.push("# Task List");
  result.push("");

  for (let i = 0; i < checkboxes; i++) {
    const checked = Math.random() < checkedRatio;
    const indent = "  ".repeat(i % 4);
    result.push(`${indent}- [${checked ? "x" : " "}] Task item ${i + 1}: Do something important`);
  }

  return result.join("\n");
}

/**
 * Generate a log-style document (timestamps, levels)
 * @param {Object} config
 * @param {number} config.entries - Number of log entries
 * @returns {string}
 */
export function generateLogDocument(config = {}) {
  const { entries = 100000 } = config;
  const levels = ["INFO", "DEBUG", "WARN", "ERROR"];
  const result = [];

  const baseDate = new Date("2024-01-01T00:00:00Z");

  for (let i = 0; i < entries; i++) {
    const timestamp = new Date(baseDate.getTime() + i * 1000).toISOString();
    const level = levels[i % levels.length];
    const message = `Request processed in ${Math.floor(Math.random() * 1000)}ms for user_${
      i % 100
    }`;
    result.push(`[${timestamp}] ${level}: ${message}`);
  }

  return result.join("\n");
}

/**
 * Generate a mixed content document with all patterns
 * @param {Object} config
 * @param {number} config.lines - Target line count
 * @returns {string}
 */
export function generateMixedDocument(config = {}) {
  const { lines = 10000 } = config;
  const sections = [];
  const linesPerSection = Math.floor(lines / 10);

  sections.push("# Mixed Content Document\n");
  sections.push("This document contains various markdown patterns for testing.\n");

  sections.push("\n## Section: Links\n");
  sections.push(generateDocumentWithLinks({ lines: linesPerSection, linksPerChunk: 10 }));

  sections.push("\n## Section: Formatting\n");
  sections.push(generateDocumentWithFormatting({ lines: linesPerSection }));

  sections.push("\n## Section: Tables\n");
  sections.push(
    generateDocumentWithTables({ tables: Math.floor(linesPerSection / 20), rowsPerTable: 5 })
  );

  sections.push("\n## Section: Tasks\n");
  sections.push(generateDocumentWithCheckboxes({ checkboxes: Math.floor(linesPerSection / 2) }));

  sections.push("\n## Section: Log Output\n");
  sections.push(generateLogDocument({ entries: linesPerSection }));

  return sections.join("\n");
}

/**
 * Generate a document with a specific pattern at known positions
 * Useful for viewport boundary testing
 * @param {Object} config
 * @param {number} config.totalLines - Total lines in document
 * @param {Array} config.patterns - Array of { line, content } to place
 * @returns {string}
 */
export function generateDocumentWithPatternsAt(config = {}) {
  const { totalLines = 1000, patterns = [] } = config;
  const result = [];

  const patternMap = new Map(patterns.map((p) => [p.line, p.content]));

  for (let i = 0; i < totalLines; i++) {
    if (patternMap.has(i)) {
      result.push(patternMap.get(i));
    } else {
      result.push(`Line ${i}: Regular filler content for testing purposes.`);
    }
  }

  return result.join("\n");
}

/**
 * Calculate approximate byte size of a string
 * @param {string} str
 * @returns {number}
 */
export function approximateByteSize(str) {
  return new TextEncoder().encode(str).length;
}

/**
 * Generate a document of approximately N megabytes
 * @param {number} targetMB - Target size in megabytes
 * @returns {string}
 */
export function generateDocumentOfSize(targetMB) {
  const targetBytes = targetMB * 1024 * 1024;
  const avgBytesPerLine = 70;
  const estimatedLines = Math.ceil(targetBytes / avgBytesPerLine);

  let doc = generateMixedDocument({ lines: estimatedLines });
  let currentSize = approximateByteSize(doc);

  while (currentSize < targetBytes) {
    doc += `\nExtra line to reach target size: ${currentSize}`;
    currentSize = approximateByteSize(doc);
  }

  return doc;
}

/**
 * Pre-built fixtures for common test scenarios
 */
export const FIXTURES = {
  small: () => generateMixedDocument({ lines: DOCUMENT_SIZES.small.lines }),
  medium: () => generateMixedDocument({ lines: DOCUMENT_SIZES.medium.lines }),
  large: () => generateMixedDocument({ lines: DOCUMENT_SIZES.large.lines }),
  xlarge: () => generateMixedDocument({ lines: DOCUMENT_SIZES.xlarge.lines }),

  manyLinks: () => generateDocumentWithLinks({ lines: 50000, linksPerChunk: 20 }),
  manyTables: () => generateDocumentWithTables({ tables: 1000, rowsPerTable: 5 }),
  manyCheckboxes: () => generateDocumentWithCheckboxes({ checkboxes: 10000 }),
  manyFormatting: () => generateDocumentWithFormatting({ lines: 50000 }),
  logFile: () => generateLogDocument({ entries: 200000 }),

  oneMB: () => generateDocumentOfSize(1),
  fiveMB: () => generateDocumentOfSize(5),
  tenMB: () => generateDocumentOfSize(10),
};
