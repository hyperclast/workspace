/**
 * Yjs CRDT Convergence Tests
 * Tests that multiple documents eventually converge to the same state
 * This is the core property of CRDTs - conflict-free replicated data types
 */
import { describe, test, expect, beforeEach } from 'vitest';
import * as Y from 'yjs';

/**
 * Helper function to sync two Yjs documents
 * Applies all updates from doc1 to doc2 and vice versa
 */
function syncDocs(doc1, doc2) {
  const update1 = Y.encodeStateAsUpdate(doc1);
  const update2 = Y.encodeStateAsUpdate(doc2);
  Y.applyUpdate(doc2, update1);
  Y.applyUpdate(doc1, update2);
}

/**
 * Helper to sync three documents
 */
function syncThreeDocs(doc1, doc2, doc3) {
  syncDocs(doc1, doc2);
  syncDocs(doc2, doc3);
  syncDocs(doc1, doc3);
}

describe('Yjs CRDT Convergence', () => {
  let doc1, doc2, text1, text2;

  beforeEach(() => {
    doc1 = new Y.Doc();
    doc2 = new Y.Doc();
    text1 = doc1.getText('content');
    text2 = doc2.getText('content');
  });

  describe('Two-Client Convergence', () => {
    test('two clients inserting at same position converge', () => {
      // Initial sync - both start with empty document
      syncDocs(doc1, doc2);

      // Both clients insert at position 0 (concurrent edits)
      text1.insert(0, 'Alice');
      text2.insert(0, 'Bob');

      // Sync the updates
      syncDocs(doc1, doc2);

      // Both documents should have same content
      expect(text1.toString()).toBe(text2.toString());

      // Content should contain both edits (order is deterministic based on client IDs)
      const finalContent = text1.toString();
      expect(finalContent).toContain('Alice');
      expect(finalContent).toContain('Bob');
    });

    test('one client inserts while other deletes', () => {
      // Start with initial content
      text1.insert(0, 'Hello World');
      syncDocs(doc1, doc2);

      // Client 1 deletes " World"
      text1.delete(5, 6);

      // Client 2 inserts "Beautiful " before "World"
      text2.insert(6, 'Beautiful ');

      // Sync the updates
      syncDocs(doc1, doc2);

      // Both should converge to same state
      expect(text1.toString()).toBe(text2.toString());

      // The insert should be preserved (even though the nearby text was deleted)
      expect(text1.toString()).toContain('Beautiful');
    });

    test('concurrent inserts at different positions', () => {
      // Start with initial content
      text1.insert(0, 'Hello World');
      syncDocs(doc1, doc2);

      // Client 1 inserts at beginning
      text1.insert(0, 'Hey! ');

      // Client 2 inserts at end
      text2.insert(11, '!');

      // Sync
      syncDocs(doc1, doc2);

      // Should converge
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toBe('Hey! Hello World!');
    });

    test('concurrent deletes of same content', () => {
      // Start with content
      text1.insert(0, 'Hello World');
      syncDocs(doc1, doc2);

      // Both delete "Hello "
      text1.delete(0, 6);
      text2.delete(0, 6);

      // Sync
      syncDocs(doc1, doc2);

      // Should converge to "World"
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toBe('World');
    });

    test('concurrent deletes of overlapping content', () => {
      // Start with content
      text1.insert(0, 'Hello Beautiful World');
      syncDocs(doc1, doc2);

      // Client 1 deletes "Hello "
      text1.delete(0, 6);

      // Client 2 deletes " Beautiful"
      text2.delete(5, 10);

      // Sync
      syncDocs(doc1, doc2);

      // Should converge (both deletes applied)
      // Note: The exact result depends on how Yjs resolves concurrent deletes
      // What matters is that both converge to the same state
      expect(text1.toString()).toBe(text2.toString());

      // Both should have "World" at the end, though there may be a leading space
      expect(text1.toString()).toContain('World');
      expect(text1.toString().length).toBeLessThan(10); // Much shorter than original
    });
  });

  describe('Three-Client Convergence', () => {
    let doc3, text3;

    beforeEach(() => {
      doc3 = new Y.Doc();
      text3 = doc3.getText('content');
    });

    test('three clients all insert at same position', () => {
      // Sync all to empty state
      syncThreeDocs(doc1, doc2, doc3);

      // All three insert at position 0
      text1.insert(0, 'Alice');
      text2.insert(0, 'Bob');
      text3.insert(0, 'Charlie');

      // Sync all
      syncThreeDocs(doc1, doc2, doc3);

      // All should converge to same state
      expect(text1.toString()).toBe(text2.toString());
      expect(text2.toString()).toBe(text3.toString());

      // All three names should be present
      const finalContent = text1.toString();
      expect(finalContent).toContain('Alice');
      expect(finalContent).toContain('Bob');
      expect(finalContent).toContain('Charlie');
    });

    test('three clients make different edits', () => {
      // Start with content
      text1.insert(0, 'Document');
      syncThreeDocs(doc1, doc2, doc3);

      // Different edits
      text1.insert(0, 'My '); // "My Document"
      text2.insert(8, ' Title'); // "Document Title"
      text3.insert(8, '!'); // "Document!"

      // Sync all
      syncThreeDocs(doc1, doc2, doc3);

      // All converge
      expect(text1.toString()).toBe(text2.toString());
      expect(text2.toString()).toBe(text3.toString());

      // All edits preserved
      expect(text1.toString()).toContain('My');
      expect(text1.toString()).toContain('Title');
      expect(text1.toString()).toContain('!');
    });
  });

  describe('Complex Concurrent Scenarios', () => {
    test('rapid concurrent edits converge', () => {
      syncDocs(doc1, doc2);

      // Client 1 makes multiple rapid edits
      for (let i = 0; i < 10; i++) {
        text1.insert(text1.length, `A${i} `);
      }

      // Client 2 makes multiple rapid edits
      for (let i = 0; i < 10; i++) {
        text2.insert(0, `B${i} `);
      }

      // Sync
      syncDocs(doc1, doc2);

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // Both clients' edits should be present
      expect(text1.toString()).toContain('A0');
      expect(text1.toString()).toContain('A9');
      expect(text1.toString()).toContain('B0');
      expect(text1.toString()).toContain('B9');
    });

    test('insert, delete, insert sequence converges', () => {
      text1.insert(0, 'Hello World');
      syncDocs(doc1, doc2);

      // Client 1: delete then insert
      text1.delete(6, 5); // Delete "World"
      text1.insert(6, 'Universe');

      // Client 2: insert at beginning
      text2.insert(0, 'Greetings: ');

      // Sync
      syncDocs(doc1, doc2);

      // Should converge
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toBe('Greetings: Hello Universe');
    });

    test('conflicting replacements converge', () => {
      text1.insert(0, 'Original Text');
      syncDocs(doc1, doc2);

      // Client 1 replaces entire text
      text1.delete(0, 13);
      text1.insert(0, 'Client 1 Version');

      // Client 2 replaces entire text
      text2.delete(0, 13);
      text2.insert(0, 'Client 2 Version');

      // Sync
      syncDocs(doc1, doc2);

      // Should converge (one of the versions wins, or they merge)
      expect(text1.toString()).toBe(text2.toString());
    });
  });

  describe('Incremental Sync', () => {
    test('syncs incrementally as edits are made', () => {
      // Initial sync
      syncDocs(doc1, doc2);

      // Edit 1 + sync
      text1.insert(0, 'Hello');
      syncDocs(doc1, doc2);
      expect(text2.toString()).toBe('Hello');

      // Edit 2 + sync
      text2.insert(5, ' World');
      syncDocs(doc1, doc2);
      expect(text1.toString()).toBe('Hello World');

      // Edit 3 + sync
      text1.insert(11, '!');
      syncDocs(doc1, doc2);
      expect(text2.toString()).toBe('Hello World!');

      // Final state
      expect(text1.toString()).toBe(text2.toString());
    });

    test('late sync after multiple edits', () => {
      syncDocs(doc1, doc2);

      // Client 1 makes many edits without syncing
      text1.insert(0, 'Line 1\n');
      text1.insert(7, 'Line 2\n');
      text1.insert(14, 'Line 3\n');

      // Client 2 also makes edits
      text2.insert(0, 'Title\n');
      text2.insert(6, '-----\n');

      // Finally sync
      syncDocs(doc1, doc2);

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // All content present
      expect(text1.toString()).toContain('Line 1');
      expect(text1.toString()).toContain('Line 2');
      expect(text1.toString()).toContain('Line 3');
      expect(text1.toString()).toContain('Title');
      expect(text1.toString()).toContain('-----');
    });
  });

  describe('Document State Consistency', () => {
    test('state vectors are consistent after sync', () => {
      syncDocs(doc1, doc2);

      text1.insert(0, 'Test');
      syncDocs(doc1, doc2);

      // Get state vectors
      const stateVector1 = Y.encodeStateVector(doc1);
      const stateVector2 = Y.encodeStateVector(doc2);

      // They should be equal (both have seen all updates)
      expect(stateVector1).toEqual(stateVector2);
    });

    test('no missing updates after full sync', () => {
      text1.insert(0, 'Content from doc1');
      text2.insert(0, 'Content from doc2');

      syncDocs(doc1, doc2);

      // Calculate missing updates (should be empty)
      const stateVector1 = Y.encodeStateVector(doc1);
      const stateVector2 = Y.encodeStateVector(doc2);

      const missingFromDoc2 = Y.encodeStateAsUpdate(doc1, stateVector2);
      const missingFromDoc1 = Y.encodeStateAsUpdate(doc2, stateVector1);

      // Both should have no missing updates (length indicates header only)
      expect(missingFromDoc2.length).toBeLessThanOrEqual(2);
      expect(missingFromDoc1.length).toBeLessThanOrEqual(2);
    });
  });

  describe('Deterministic Ordering', () => {
    test('concurrent edits converge to same result', () => {
      // Test that concurrent edits always converge, even if order isn't fully deterministic
      // The key property of CRDTs is convergence, not necessarily deterministic ordering

      for (let iteration = 0; iteration < 5; iteration++) {
        const docA1 = new Y.Doc();
        const docA2 = new Y.Doc();
        const textA1 = docA1.getText('content');
        const textA2 = docA2.getText('content');

        // Same concurrent edits
        textA1.insert(0, 'Alice');
        textA2.insert(0, 'Bob');

        syncDocs(docA1, docA2);

        // Both documents should converge to the same state
        expect(textA1.toString()).toBe(textA2.toString());

        // Both names should be present
        expect(textA1.toString()).toContain('Alice');
        expect(textA1.toString()).toContain('Bob');
      }
    });
  });
});
