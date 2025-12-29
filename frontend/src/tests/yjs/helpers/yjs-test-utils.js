/**
 * Test utilities for Yjs CRDT tests
 * Provides helper functions for common testing scenarios
 */
import * as Y from "yjs";

/**
 * Sync two Yjs documents bidirectionally
 * Applies all updates from doc1 to doc2 and vice versa
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 */
export function syncDocs(doc1, doc2) {
  const update1 = Y.encodeStateAsUpdate(doc1);
  const update2 = Y.encodeStateAsUpdate(doc2);
  Y.applyUpdate(doc2, update1);
  Y.applyUpdate(doc1, update2);
}

/**
 * Sync three documents in all directions
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 * @param {Y.Doc} doc3 - Third document
 */
export function syncThreeDocs(doc1, doc2, doc3) {
  syncDocs(doc1, doc2);
  syncDocs(doc2, doc3);
  syncDocs(doc1, doc3);
}

/**
 * Sync multiple documents (variadic)
 * @param {...Y.Doc} docs - Documents to sync
 */
export function syncMultipleDocs(...docs) {
  // Sync each pair of documents
  for (let i = 0; i < docs.length; i++) {
    for (let j = i + 1; j < docs.length; j++) {
      syncDocs(docs[i], docs[j]);
    }
  }
}

/**
 * Create a network partition between two documents
 * Returns an object with a reconnect method
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 * @returns {Object} - Object with reconnect() method
 */
export function createPartition(doc1, doc2) {
  return {
    reconnect: () => syncDocs(doc1, doc2),
  };
}

/**
 * Factory function to create a fresh Yjs document with text type
 * @param {string} textName - Name of the text type (default: 'content')
 * @returns {Object} - { doc, text } tuple
 */
export function createDocWithText(textName = "content") {
  const doc = new Y.Doc();
  const text = doc.getText(textName);
  return { doc, text };
}

/**
 * Apply a series of operations to a text object
 * Operations format: [{ type: 'insert', pos: 0, text: 'foo' }, { type: 'delete', pos: 0, length: 3 }]
 * @param {Y.Text} text - Yjs text object
 * @param {Array} operations - Array of operation objects
 */
export function applyOperations(text, operations) {
  operations.forEach((op) => {
    if (op.type === "insert") {
      text.insert(op.pos, op.text);
    } else if (op.type === "delete") {
      text.delete(op.pos, op.length);
    }
  });
}

/**
 * Simulate typing by inserting characters one at a time
 * @param {Y.Text} text - Yjs text object
 * @param {number} position - Starting position
 * @param {string} content - Content to type
 * @param {Function} onEachChar - Optional callback after each character
 */
export function simulateTyping(text, position, content, onEachChar = null) {
  for (let i = 0; i < content.length; i++) {
    text.insert(position + i, content[i]);
    if (onEachChar) {
      onEachChar(position + i, content[i]);
    }
  }
}

/**
 * Simulate backspace/delete by removing characters one at a time
 * @param {Y.Text} text - Yjs text object
 * @param {number} position - Position to delete from
 * @param {number} count - Number of characters to delete
 * @param {Function} onEachDelete - Optional callback after each delete
 */
export function simulateBackspace(text, position, count, onEachDelete = null) {
  for (let i = 0; i < count; i++) {
    text.delete(position, 1);
    if (onEachDelete) {
      onEachDelete(position);
    }
  }
}

/**
 * Get the state vector of a document (for debugging)
 * @param {Y.Doc} doc - Yjs document
 * @returns {Uint8Array} - State vector
 */
export function getStateVector(doc) {
  return Y.encodeStateVector(doc);
}

/**
 * Calculate the diff between two documents
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 * @returns {Object} - { doc1MissingFromDoc2, doc2MissingFromDoc1 }
 */
export function calculateDiff(doc1, doc2) {
  const stateVector1 = Y.encodeStateVector(doc1);
  const stateVector2 = Y.encodeStateVector(doc2);

  const doc1MissingFromDoc2 = Y.encodeStateAsUpdate(doc2, stateVector1);
  const doc2MissingFromDoc1 = Y.encodeStateAsUpdate(doc1, stateVector2);

  return {
    doc1MissingFromDoc2,
    doc2MissingFromDoc1,
    doc1NeedsSyncFrom2: doc1MissingFromDoc2.length > 2,
    doc2NeedsSyncFrom1: doc2MissingFromDoc1.length > 2,
  };
}

/**
 * Check if two documents are fully synced
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 * @returns {boolean} - True if fully synced
 */
export function areDocsSynced(doc1, doc2) {
  const diff = calculateDiff(doc1, doc2);
  return !diff.doc1NeedsSyncFrom2 && !diff.doc2NeedsSyncFrom1;
}

/**
 * Assert that two documents have converged to the same state
 * Useful for test assertions
 * @param {Y.Doc} doc1 - First document
 * @param {Y.Doc} doc2 - Second document
 * @param {string} textName - Name of text type to compare (default: 'content')
 * @throws {Error} - If documents haven't converged
 */
export function assertConverged(doc1, doc2, textName = "content") {
  const text1 = doc1.getText(textName);
  const text2 = doc2.getText(textName);

  if (text1.toString() !== text2.toString()) {
    throw new Error(
      `Documents have not converged!\n` +
        `Doc1: "${text1.toString()}"\n` +
        `Doc2: "${text2.toString()}"`
    );
  }

  if (!areDocsSynced(doc1, doc2)) {
    throw new Error("Documents have same content but different state vectors");
  }

  return true;
}

/**
 * Create a snapshot of a document's state
 * Useful for rollback testing
 * @param {Y.Doc} doc - Yjs document
 * @returns {Uint8Array} - Encoded snapshot
 */
export function createSnapshot(doc) {
  return Y.encodeStateAsUpdate(doc);
}

/**
 * Restore a document from a snapshot
 * @param {Y.Doc} doc - Yjs document to restore to
 * @param {Uint8Array} snapshot - Snapshot to restore from
 */
export function restoreSnapshot(doc, snapshot) {
  // Create a new clean doc and apply snapshot
  const cleanDoc = new Y.Doc();
  Y.applyUpdate(cleanDoc, snapshot);

  // Get the full state and apply to target doc
  const fullState = Y.encodeStateAsUpdate(cleanDoc);
  Y.applyUpdate(doc, fullState);
}

/**
 * Generate random text of specified length
 * @param {number} length - Length of text to generate
 * @returns {string} - Random text
 */
export function generateRandomText(length) {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Measure operation time in milliseconds
 * @param {Function} operation - Operation to measure
 * @returns {Object} - { result, timeMs }
 */
export function measureTime(operation) {
  const start = performance.now();
  const result = operation();
  const timeMs = performance.now() - start;
  return { result, timeMs };
}
