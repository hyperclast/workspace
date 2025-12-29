/**
 * Test fixtures for performance testing
 *
 * Provides utilities to generate large documents and realistic test data
 * for Yjs and CodeMirror performance tests.
 */

import * as Y from "yjs";

/**
 * Generate a string with the specified number of lines
 * @param {number} numLines - Number of lines to generate
 * @param {Object} options - Generation options
 * @param {number} options.lineLength - Average characters per line (default: 80)
 * @param {boolean} options.varied - Use varied line lengths (default: false)
 * @returns {string}
 */
export const generateLines = (numLines, options = {}) => {
  const { lineLength = 80, varied = false } = options;
  const lines = [];

  for (let i = 0; i < numLines; i++) {
    const length = varied ? Math.floor(lineLength * (0.5 + Math.random())) : lineLength;

    const line = generateLine(i, length);
    lines.push(line);
  }

  return lines.join("\n");
};

/**
 * Generate a single line of text
 * @param {number} lineNum - Line number (for unique content)
 * @param {number} length - Desired length in characters
 * @returns {string}
 */
const generateLine = (lineNum, length) => {
  const prefix = `Line ${lineNum}: `;
  if (length <= prefix.length) {
    return prefix.substring(0, length);
  }

  const remaining = length - prefix.length;
  const words =
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua".split(
      " "
    );

  let content = prefix;
  while (content.length < length) {
    const word = words[Math.floor(Math.random() * words.length)];
    if (content.length + word.length + 1 <= length) {
      content += word + " ";
    } else {
      break;
    }
  }

  return content.trim();
};

/**
 * Create a Yjs document with text content
 * @param {number} numLines - Number of lines to insert
 * @param {Object} options - Creation options
 * @param {string} options.textType - Text type name (default: 'codemirror')
 * @param {number} options.lineLength - Average characters per line
 * @param {boolean} options.varied - Use varied line lengths
 * @returns {Y.Doc}
 */
export const createYjsDoc = (numLines, options = {}) => {
  const { textType = "codemirror", ...generateOptions } = options;

  const doc = new Y.Doc();
  const text = doc.getText(textType);

  const content = generateLines(numLines, generateOptions);
  text.insert(0, content);

  return doc;
};

/**
 * Create multiple Yjs documents for collaborative testing
 * @param {number} count - Number of documents to create
 * @param {number} numLines - Initial lines per document
 * @param {Object} options - Creation options
 * @returns {Y.Doc[]}
 */
export const createMultipleYjsDocs = (count, numLines = 0, options = {}) => {
  const docs = [];
  for (let i = 0; i < count; i++) {
    docs.push(createYjsDoc(numLines, options));
  }
  return docs;
};

/**
 * Generate a series of updates for a Yjs document
 * @param {Y.Doc} doc - Yjs document
 * @param {number} numUpdates - Number of updates to generate
 * @param {Object} options - Update options
 * @param {string} options.textType - Text type name (default: 'codemirror')
 * @param {string} options.operation - Operation type: 'insert', 'delete', 'mixed' (default: 'insert')
 * @returns {Uint8Array[]} Array of update bytes
 */
export const generateUpdates = (doc, numUpdates, options = {}) => {
  const { textType = "codemirror", operation = "insert" } = options;
  const text = doc.getText(textType);
  const updates = [];

  for (let i = 0; i < numUpdates; i++) {
    const currentLength = text.length;

    if (operation === "insert" || (operation === "mixed" && i % 2 === 0)) {
      // Insert operation
      const position = Math.floor(Math.random() * (currentLength + 1));
      const content = `Update ${i}: ${generateLine(i, 40)}\n`;
      text.insert(position, content);
    } else {
      // Delete operation
      if (currentLength > 0) {
        const position = Math.floor(Math.random() * currentLength);
        const deleteLength = Math.min(10, currentLength - position);
        text.delete(position, deleteLength);
      }
    }

    // Capture the update
    const update = Y.encodeStateAsUpdate(doc);
    updates.push(update);
  }

  return updates;
};

/**
 * Apply updates to a Yjs document
 * @param {Y.Doc} doc - Target document
 * @param {Uint8Array[]} updates - Array of updates to apply
 */
export const applyUpdates = (doc, updates) => {
  for (const update of updates) {
    Y.applyUpdate(doc, update);
  }
};

/**
 * Simulate concurrent edits between multiple documents
 * @param {Y.Doc[]} docs - Array of documents
 * @param {number} editsPerDoc - Number of edits each doc should make
 * @param {Object} options - Simulation options
 * @returns {Object} Simulation results with updates and convergence info
 */
export const simulateConcurrentEdits = (docs, editsPerDoc, options = {}) => {
  const { textType = "codemirror" } = options;
  const allUpdates = [];

  // Each doc makes its edits
  for (let i = 0; i < docs.length; i++) {
    const doc = docs[i];
    const text = doc.getText(textType);

    for (let j = 0; j < editsPerDoc; j++) {
      const position = Math.floor(Math.random() * (text.length + 1));
      const content = `Doc${i}-Edit${j} `;
      text.insert(position, content);

      const update = Y.encodeStateAsUpdate(doc);
      allUpdates.push({ docIndex: i, update });
    }
  }

  // Apply all updates to all docs (simulate synchronization)
  for (const { docIndex, update } of allUpdates) {
    for (let i = 0; i < docs.length; i++) {
      if (i !== docIndex) {
        Y.applyUpdate(docs[i], update);
      }
    }
  }

  // Check convergence - all docs should have same content
  const texts = docs.map((doc) => doc.getText(textType).toString());
  const converged = texts.every((text) => text === texts[0]);

  return {
    converged,
    finalLength: texts[0].length,
    totalUpdates: allUpdates.length,
    updates: allUpdates.map((u) => u.update),
  };
};

/**
 * Create a realistic note-like document
 * @param {number} sectionCount - Number of sections (default: 5)
 * @param {number} linesPerSection - Lines per section (default: 20)
 * @returns {string}
 */
export const createRealisticNote = (sectionCount = 5, linesPerSection = 20) => {
  const sections = [];

  for (let i = 0; i < sectionCount; i++) {
    const header = `\n\n# Section ${i + 1}: ${generateLine(i, 30)}\n\n`;
    const content = generateLines(linesPerSection, { lineLength: 70, varied: true });
    sections.push(header + content);
  }

  return sections.join("");
};
