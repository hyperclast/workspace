/**
 * Yjs Network Partition and Offline Scenarios Tests
 * Tests how documents handle network partitions, offline edits, and reconnection
 */
import { describe, test, expect, beforeEach } from 'vitest';
import * as Y from 'yjs';

/**
 * Simulates a network partition by keeping documents separate
 * Returns a function to "reconnect" by syncing them
 */
function createPartition(doc1, doc2) {
  return {
    reconnect: () => {
      const update1 = Y.encodeStateAsUpdate(doc1);
      const update2 = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(doc2, update1);
      Y.applyUpdate(doc1, update2);
    }
  };
}

describe('Yjs Network Partitions and Offline Scenarios', () => {
  let doc1, doc2, text1, text2;

  beforeEach(() => {
    doc1 = new Y.Doc();
    doc2 = new Y.Doc();
    text1 = doc1.getText('content');
    text2 = doc2.getText('content');
  });

  describe('Offline Edits and Reconnection', () => {
    test('client goes offline, makes edits, comes back online', () => {
      // Initial sync
      text1.insert(0, 'Initial content');
      const update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Doc2 goes "offline" - create partition
      const partition = createPartition(doc1, doc2);

      // While offline, doc2 makes edits
      text2.insert(15, ' - edited offline');

      // Doc1 also makes edits (doesn't know about doc2's changes)
      text1.insert(15, ' - edited online');

      // Doc2 comes back online - reconnect
      partition.reconnect();

      // Both should converge
      expect(text1.toString()).toBe(text2.toString());

      // Both edits should be present
      expect(text1.toString()).toContain('edited offline');
      expect(text1.toString()).toContain('edited online');
    });

    test('client offline for extended period with many edits', () => {
      // Initial sync
      text1.insert(0, 'Document\n');
      const update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Doc2 goes offline
      const partition = createPartition(doc1, doc2);

      // Doc2 makes many offline edits
      for (let i = 0; i < 50; i++) {
        text2.insert(text2.length, `Offline edit ${i}\n`);
      }

      // Doc1 also continues working
      for (let i = 0; i < 50; i++) {
        text1.insert(text1.length, `Online edit ${i}\n`);
      }

      // Reconnect
      partition.reconnect();

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // All edits present
      expect(text1.toString()).toContain('Offline edit 0');
      expect(text1.toString()).toContain('Offline edit 49');
      expect(text1.toString()).toContain('Online edit 0');
      expect(text1.toString()).toContain('Online edit 49');
    });

    test('multiple offline/online cycles', () => {
      // Initial state
      text1.insert(0, 'Start');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Cycle 1: Offline
      const partition1 = createPartition(doc1, doc2);
      text2.insert(5, ' Cycle1');
      partition1.reconnect();

      // Cycle 2: Offline again
      const partition2 = createPartition(doc1, doc2);
      text2.insert(text2.length, ' Cycle2');
      text1.insert(text1.length, ' Online');
      partition2.reconnect();

      // Cycle 3: Offline again
      const partition3 = createPartition(doc1, doc2);
      text2.insert(0, 'Prefix ');
      partition3.reconnect();

      // All changes should be present
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toContain('Start');
      expect(text1.toString()).toContain('Cycle1');
      expect(text1.toString()).toContain('Cycle2');
      expect(text1.toString()).toContain('Online');
      expect(text1.toString()).toContain('Prefix');
    });
  });

  describe('Two Clients Offline Simultaneously', () => {
    test('both clients offline, make edits, both reconnect', () => {
      // Initial sync
      text1.insert(0, 'Shared content');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Both go offline (no connection between them)
      // Client 1 makes edits
      text1.insert(0, '[Client1] ');

      // Client 2 makes edits
      text2.insert(0, '[Client2] ');

      // Both reconnect
      const partition = createPartition(doc1, doc2);
      partition.reconnect();

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // Both prefixes present
      expect(text1.toString()).toContain('[Client1]');
      expect(text1.toString()).toContain('[Client2]');
    });

    test('three-way partition and reconnection', () => {
      const doc3 = new Y.Doc();
      const text3 = doc3.getText('content');

      // Initial sync all
      text1.insert(0, 'Initial');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);
      Y.applyUpdate(doc3, update);

      // All three partition (network splits)
      // Each makes independent edits
      text1.insert(7, ' Doc1');
      text2.insert(7, ' Doc2');
      text3.insert(7, ' Doc3');

      // Reconnect all
      const update1 = Y.encodeStateAsUpdate(doc1);
      const update2 = Y.encodeStateAsUpdate(doc2);
      const update3 = Y.encodeStateAsUpdate(doc3);

      Y.applyUpdate(doc1, update2);
      Y.applyUpdate(doc1, update3);
      Y.applyUpdate(doc2, update1);
      Y.applyUpdate(doc2, update3);
      Y.applyUpdate(doc3, update1);
      Y.applyUpdate(doc3, update2);

      // All converge
      expect(text1.toString()).toBe(text2.toString());
      expect(text2.toString()).toBe(text3.toString());

      // All edits present
      expect(text1.toString()).toContain('Doc1');
      expect(text1.toString()).toContain('Doc2');
      expect(text1.toString()).toContain('Doc3');
    });
  });

  describe('Conflicting Deletes During Partition', () => {
    test('both clients delete overlapping content while offline', () => {
      // Initial content
      text1.insert(0, 'Hello Beautiful Wonderful World');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Partition
      const partition = createPartition(doc1, doc2);

      // Client 1 deletes "Beautiful "
      text1.delete(6, 10);

      // Client 2 deletes "Wonderful "
      text2.delete(16, 10);

      // Reconnect
      partition.reconnect();

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // Result should have both deletes applied
      expect(text1.toString()).toBe('Hello World');
    });

    test('delete same content on both clients', () => {
      // Initial content
      text1.insert(0, 'Remove this text please');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Partition
      const partition = createPartition(doc1, doc2);

      // Both delete "this text "
      text1.delete(7, 10);
      text2.delete(7, 10);

      // Reconnect
      partition.reconnect();

      // Should converge (idempotent delete)
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toBe('Remove please');
    });

    test('one deletes, other inserts at same position', () => {
      // Initial content
      text1.insert(0, 'Hello World');
      let update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Partition
      const partition = createPartition(doc1, doc2);

      // Client 1 deletes " World"
      text1.delete(5, 6);

      // Client 2 inserts " Beautiful" at same position
      text2.insert(5, ' Beautiful');

      // Reconnect
      partition.reconnect();

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // Insert should be preserved even though nearby text was deleted
      expect(text1.toString()).toContain('Beautiful');
    });
  });

  describe('State Vector Synchronization', () => {
    test('state vector correctly identifies missing updates', () => {
      // Doc1 has content
      text1.insert(0, 'Content from doc1');

      // Doc2 is behind (doesn't have this update)
      const stateVector2 = Y.encodeStateVector(doc2);

      // Encode only the updates doc2 is missing
      const missingUpdates = Y.encodeStateAsUpdate(doc1, stateVector2);

      // Apply missing updates to doc2
      Y.applyUpdate(doc2, missingUpdates);

      // Should be in sync now
      expect(text2.toString()).toBe('Content from doc1');
    });

    test('differential sync sends only new updates', () => {
      // Initial sync
      text1.insert(0, 'Initial');
      let update1 = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update1);

      // Doc1 makes more edits
      text1.insert(7, ' Edit1');
      text1.insert(13, ' Edit2');

      // Get state vector before new edits
      const stateVectorBefore = Y.encodeStateVector(doc2);

      // Encode only new updates
      const newUpdates = Y.encodeStateAsUpdate(doc1, stateVectorBefore);

      // Apply only new updates
      Y.applyUpdate(doc2, newUpdates);

      // Should have all content
      expect(text2.toString()).toBe('Initial Edit1 Edit2');
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('handles empty state reconnection', () => {
      // Doc1 has content
      text1.insert(0, 'Content');

      // Doc2 is completely empty (never synced)
      const partition = createPartition(doc1, doc2);
      partition.reconnect();

      // Doc2 should get all content
      expect(text2.toString()).toBe('Content');
    });

    test('handles applying same update twice (idempotent)', () => {
      text1.insert(0, 'Content');
      const update = Y.encodeStateAsUpdate(doc1);

      // Apply same update twice
      Y.applyUpdate(doc2, update);
      Y.applyUpdate(doc2, update);

      // Should still be correct
      expect(text2.toString()).toBe('Content');
    });

    test('handles out-of-order update application', () => {
      // Make several updates
      text1.insert(0, 'A');
      const update1 = Y.encodeStateAsUpdate(doc1);

      text1.insert(1, 'B');
      const update2 = Y.encodeStateAsUpdate(doc1);

      text1.insert(2, 'C');
      const update3 = Y.encodeStateAsUpdate(doc1);

      // Apply in different order (Yjs should handle this)
      Y.applyUpdate(doc2, update3);
      Y.applyUpdate(doc2, update1);
      Y.applyUpdate(doc2, update2);

      // Should still converge
      expect(text2.toString()).toBe('ABC');
    });
  });

  describe('Large Offline Edit Batches', () => {
    test('handles very large offline edit batch', () => {
      // Initial sync
      text1.insert(0, 'Start\n');
      const update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Doc2 goes offline and makes 1000 edits
      const partition = createPartition(doc1, doc2);

      for (let i = 0; i < 1000; i++) {
        text2.insert(text2.length, `Line ${i}\n`);
      }

      // Reconnect
      partition.reconnect();

      // Should sync successfully
      expect(text1.toString()).toBe(text2.toString());
      expect(text1.toString()).toContain('Line 0');
      expect(text1.toString()).toContain('Line 999');
    });

    test('handles both clients making large offline batches', () => {
      // Initial sync
      text1.insert(0, 'Document\n');
      const update = Y.encodeStateAsUpdate(doc1);
      Y.applyUpdate(doc2, update);

      // Partition
      const partition = createPartition(doc1, doc2);

      // Both make many edits
      for (let i = 0; i < 100; i++) {
        text1.insert(text1.length, `Client1-${i}\n`);
        text2.insert(text2.length, `Client2-${i}\n`);
      }

      // Reconnect
      partition.reconnect();

      // Should converge
      expect(text1.toString()).toBe(text2.toString());

      // Spot check some content
      expect(text1.toString()).toContain('Client1-0');
      expect(text1.toString()).toContain('Client1-99');
      expect(text1.toString()).toContain('Client2-0');
      expect(text1.toString()).toContain('Client2-99');
    });
  });
});
