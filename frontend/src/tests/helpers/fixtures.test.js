/**
 * Tests for test fixtures
 */

import { describe, test, expect } from 'vitest';
import * as Y from 'yjs';
import {
  generateLines,
  createYjsDoc,
  createMultipleYjsDocs,
  generateUpdates,
  applyUpdates,
  simulateConcurrentEdits,
  createRealisticNote,
} from './fixtures.js';

describe('Test Fixtures', () => {
  test('generateLines creates correct number of lines', () => {
    const lines = generateLines(10);
    const lineCount = lines.split('\n').length;
    expect(lineCount).toBe(10);
  });

  test('generateLines respects line length option', () => {
    const lines = generateLines(5, { lineLength: 20 });
    const lineArray = lines.split('\n');

    // Each line should be approximately the requested length
    lineArray.forEach(line => {
      expect(line.length).toBeGreaterThan(0);
      expect(line.length).toBeLessThanOrEqual(30); // Allow some variance
    });
  });

  test('createYjsDoc creates document with content', () => {
    const doc = createYjsDoc(10);
    const text = doc.getText('codemirror');

    expect(text.length).toBeGreaterThan(0);
    expect(text.toString().split('\n').length).toBe(10);
  });

  test('createYjsDoc respects custom text type', () => {
    const doc = createYjsDoc(5, { textType: 'custom' });
    const text = doc.getText('custom');

    expect(text.length).toBeGreaterThan(0);
  });

  test('createMultipleYjsDocs creates correct number of docs', () => {
    const docs = createMultipleYjsDocs(3, 5);

    expect(docs).toHaveLength(3);
    docs.forEach(doc => {
      expect(doc).toBeInstanceOf(Y.Doc);
      const text = doc.getText('codemirror');
      expect(text.length).toBeGreaterThan(0);
    });
  });

  test('generateUpdates creates updates', () => {
    const doc = createYjsDoc(5);
    const updates = generateUpdates(doc, 10);

    expect(updates).toHaveLength(10);
    updates.forEach(update => {
      expect(update).toBeInstanceOf(Uint8Array);
    });
  });

  test('applyUpdates applies updates to document', () => {
    const sourceDoc = createYjsDoc(5);
    const updates = generateUpdates(sourceDoc, 5);

    const targetDoc = new Y.Doc();
    applyUpdates(targetDoc, updates);

    const targetText = targetDoc.getText('codemirror');
    expect(targetText.length).toBeGreaterThan(0);
  });

  test('simulateConcurrentEdits produces convergence', () => {
    const docs = createMultipleYjsDocs(3, 5);
    const result = simulateConcurrentEdits(docs, 10);

    expect(result.converged).toBe(true);
    expect(result.totalUpdates).toBe(30); // 3 docs * 10 edits
    expect(result.updates).toHaveLength(30);

    // All docs should have same final content
    const texts = docs.map(doc => doc.getText('codemirror').toString());
    expect(texts[0]).toBe(texts[1]);
    expect(texts[1]).toBe(texts[2]);
  });

  test('createRealisticNote creates structured content', () => {
    const note = createRealisticNote(3, 10);

    expect(note).toContain('# Section 1:');
    expect(note).toContain('# Section 2:');
    expect(note).toContain('# Section 3:');

    // Should have section delimiters (double blank lines)
    expect(note).toContain('\n\n');
  });
});
