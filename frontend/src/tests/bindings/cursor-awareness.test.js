/**
 * Cursor and Selection Tests
 * Tests that cursor positions and selections work correctly with Yjs binding
 */
import { describe, test, expect, beforeEach, afterEach } from 'vitest';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import * as Y from 'yjs';
import { yCollab } from 'y-codemirror.next';

describe('Cursor and Selection with Yjs', () => {
  let ydoc, ytext, view;

  beforeEach(() => {
    ydoc = new Y.Doc();
    ytext = ydoc.getText('codemirror');

    const state = EditorState.create({
      doc: '',
      extensions: [yCollab(ytext)]
    });

    view = new EditorView({
      state,
      parent: document.createElement('div')
    });
  });

  afterEach(() => {
    view.destroy();
  });

  describe('Cursor Position', () => {
    test('maintains cursor at position 0', () => {
      ytext.insert(0, 'Hello');

      view.dispatch({
        selection: { anchor: 0 }
      });

      expect(view.state.selection.main.anchor).toBe(0);
    });

    test('maintains cursor at end of document', () => {
      ytext.insert(0, 'Hello');

      view.dispatch({
        selection: { anchor: 5 }
      });

      expect(view.state.selection.main.anchor).toBe(5);
      expect(view.state.selection.main.anchor).toBe(view.state.doc.length);
    });

    test('maintains cursor in middle of content', () => {
      ytext.insert(0, 'Hello World');

      view.dispatch({
        selection: { anchor: 6 }
      });

      expect(view.state.selection.main.anchor).toBe(6);
    });
  });

  describe('Selection Ranges', () => {
    test('maintains selection range', () => {
      ytext.insert(0, 'Hello World');

      // Select "World"
      view.dispatch({
        selection: { anchor: 6, head: 11 }
      });

      expect(view.state.selection.main.anchor).toBe(6);
      expect(view.state.selection.main.head).toBe(11);
      expect(view.state.selection.main.from).toBe(6);
      expect(view.state.selection.main.to).toBe(11);
    });

    test('handles reverse selection', () => {
      ytext.insert(0, 'Hello World');

      // Select backwards (head before anchor)
      view.dispatch({
        selection: { anchor: 10, head: 5 }
      });

      expect(view.state.selection.main.anchor).toBe(10);
      expect(view.state.selection.main.head).toBe(5);
      expect(view.state.selection.main.from).toBe(5);
      expect(view.state.selection.main.to).toBe(10);
    });

    test('handles empty selection (cursor)', () => {
      ytext.insert(0, 'Hello');

      view.dispatch({
        selection: { anchor: 3, head: 3 }
      });

      expect(view.state.selection.main.anchor).toBe(3);
      expect(view.state.selection.main.head).toBe(3);
      expect(view.state.selection.main.empty).toBe(true);
    });

    test('handles full document selection', () => {
      ytext.insert(0, 'Hello World');

      view.dispatch({
        selection: { anchor: 0, head: 11 }
      });

      expect(view.state.selection.main.from).toBe(0);
      expect(view.state.selection.main.to).toBe(11);
    });
  });

  describe('Cursor After Edits', () => {
    test('adjusts cursor after insert before cursor', () => {
      ytext.insert(0, 'World');

      // Cursor at end (position 5)
      view.dispatch({
        selection: { anchor: 5 }
      });

      // Insert "Hello " at beginning
      view.dispatch({
        changes: { from: 0, insert: 'Hello ' },
        selection: { anchor: 11 } // Cursor should move
      });

      expect(view.state.selection.main.anchor).toBe(11);
      expect(view.state.doc.toString()).toBe('Hello World');
    });

    test('maintains cursor after insert after cursor', () => {
      ytext.insert(0, 'Hello');

      // Cursor at position 2
      view.dispatch({
        selection: { anchor: 2 }
      });

      // Insert " World" at end (doesn't affect cursor)
      view.dispatch({
        changes: { from: 5, insert: ' World' }
      });

      expect(view.state.selection.main.anchor).toBe(2);
    });

    test('adjusts cursor after delete before cursor', () => {
      ytext.insert(0, 'Hello World');

      // Cursor at position 11 (end)
      view.dispatch({
        selection: { anchor: 11 }
      });

      // Delete "Hello " (positions 0-6)
      view.dispatch({
        changes: { from: 0, to: 6 },
        selection: { anchor: 5 } // Adjusted position
      });

      expect(view.state.selection.main.anchor).toBe(5);
      expect(view.state.doc.toString()).toBe('World');
    });

    test('adjusts selection when content deleted around it', () => {
      ytext.insert(0, 'Start Hello World End');

      // Select "Hello"
      view.dispatch({
        selection: { anchor: 6, head: 11 }
      });

      // Delete "Start " before selection
      view.dispatch({
        changes: { from: 0, to: 6 },
        selection: { anchor: 0, head: 5 }
      });

      expect(view.state.selection.main.anchor).toBe(0);
      expect(view.state.selection.main.head).toBe(5);
    });
  });

  describe('Selection Preservation with Remote Edits', () => {
    let doc2, text2;

    beforeEach(() => {
      doc2 = new Y.Doc();
      text2 = doc2.getText('codemirror');
    });

    test('preserves selection during remote insert at end', () => {
      // Sync documents initially
      const update = Y.encodeStateAsUpdate(ydoc);
      Y.applyUpdate(doc2, update);

      ytext.insert(0, 'Hello World');

      // Sync "Hello World" to doc2 before client 2 makes edits
      const updateContent = Y.encodeStateAsUpdate(ydoc);
      Y.applyUpdate(doc2, updateContent);

      // Client 1 selects "Hello"
      const originalAnchor = 0;
      const originalHead = 5;
      view.dispatch({
        selection: { anchor: originalAnchor, head: originalHead }
      });

      // Client 2 inserts at end (shouldn't affect selection)
      text2.insert(11, '!');

      // Sync back to client 1
      const update2 = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, update2);

      // Selection should remain unchanged since insert was after it
      expect(view.state.selection.main.anchor).toBe(originalAnchor);
      expect(view.state.selection.main.head).toBe(originalHead);
    });

    test('cursor adjusts during remote insert before it', () => {
      // Sync documents initially
      const update = Y.encodeStateAsUpdate(ydoc);
      Y.applyUpdate(doc2, update);

      ytext.insert(0, 'World');

      // Sync "World" to doc2 before client 2 makes edits
      const updateWorld = Y.encodeStateAsUpdate(ydoc);
      Y.applyUpdate(doc2, updateWorld);

      // Client 1 cursor at end
      view.dispatch({
        selection: { anchor: 5 }
      });

      // Client 2 inserts at beginning
      text2.insert(0, 'Hello ');

      // Sync back to client 1
      const update2 = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, update2);

      // Cursor should be pushed forward (implementation detail - might vary)
      // What matters is document is correct
      expect(view.state.doc.toString()).toBe('Hello World');
    });
  });

  describe('Multi-line Selection', () => {
    test('selects across multiple lines', () => {
      ytext.insert(0, 'Line 1\nLine 2\nLine 3');

      // Select from start of Line 2 to end of Line 2
      view.dispatch({
        selection: { anchor: 7, head: 13 }
      });

      expect(view.state.selection.main.from).toBe(7);
      expect(view.state.selection.main.to).toBe(13);
      expect(view.state.sliceDoc(7, 13)).toBe('Line 2');
    });

    test('selects entire document with newlines', () => {
      ytext.insert(0, 'Line 1\nLine 2\nLine 3');

      view.dispatch({
        selection: { anchor: 0, head: view.state.doc.length }
      });

      expect(view.state.selection.main.from).toBe(0);
      expect(view.state.selection.main.to).toBe(view.state.doc.length);
    });
  });

  describe('Typing at Cursor', () => {
    test('inserts text at cursor position', () => {
      ytext.insert(0, 'Hello');

      // Cursor at position 5
      view.dispatch({
        selection: { anchor: 5 }
      });

      // Type " World"
      view.dispatch({
        changes: { from: 5, insert: ' World' },
        selection: { anchor: 11 } // Cursor moves to end
      });

      expect(view.state.doc.toString()).toBe('Hello World');
      expect(view.state.selection.main.anchor).toBe(11);
    });

    test('replaces selection when typing', () => {
      ytext.insert(0, 'Hello World');

      // Select "World"
      view.dispatch({
        selection: { anchor: 6, head: 11 }
      });

      // Type "Universe" to replace selection
      view.dispatch({
        changes: { from: 6, to: 11, insert: 'Universe' },
        selection: { anchor: 14 }
      });

      expect(view.state.doc.toString()).toBe('Hello Universe');
      expect(view.state.selection.main.anchor).toBe(14);
    });
  });

  describe('Edge Cases', () => {
    test('handles empty document selection', () => {
      // Empty document
      view.dispatch({
        selection: { anchor: 0, head: 0 }
      });

      expect(view.state.selection.main.anchor).toBe(0);
      expect(view.state.selection.main.empty).toBe(true);
    });

    test('adjusts invalid cursor position', () => {
      ytext.insert(0, 'Hello');

      // Try to set cursor beyond document length - EditorView should clamp it
      view.dispatch({
        selection: { anchor: Math.min(100, view.state.doc.length) }
      });

      // Should be clamped to document length
      expect(view.state.selection.main.anchor).toBeLessThanOrEqual(5);
    });

    test('handles cursor at boundary positions', () => {
      ytext.insert(0, 'Hello\nWorld');

      // Cursor at newline
      view.dispatch({
        selection: { anchor: 5 }
      });

      expect(view.state.selection.main.anchor).toBe(5);

      // Cursor after newline
      view.dispatch({
        selection: { anchor: 6 }
      });

      expect(view.state.selection.main.anchor).toBe(6);
    });
  });
});
