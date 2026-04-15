/**
 * vault.ts — In-memory PII reverse-map + IndexedDB metadata store.
 *
 * Step 3 of the ConsentFlow Privacy Shield build.
 *
 * HARD RULE: Real PII is NEVER written to IndexedDB.
 * The dummy→original map lives only in a JavaScript Map in RAM.
 * Tab close wipes it automatically.
 * IndexedDB is used ONLY for non-sensitive metadata (counts, timestamps).
 */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

// ─── Part 1 — In-memory reverse map ─────────────────────────────────────────

/**
 * RAM-only map: dummy value → original PII value.
 * Never touches disk. Cleared automatically when the tab/worker is destroyed.
 */
const _map = new Map<string, string>();

/**
 * Return all mappings sorted longest-dummy-first to prevent partial
 * replacement bugs when one dummy is a prefix of another.
 */
function _sortedEntries(): Array<{ dummy: string; original: string }> {
  return [..._map.entries()]
    .map(([dummy, original]) => ({ dummy, original }))
    .sort((a, b) => b.dummy.length - a.dummy.length);
}

export const vault = {
  /**
   * Store a dummy→original mapping in RAM.
   * If the same dummy is stored twice, the newer original wins.
   */
  store(dummy: string, original: string): void {
    _map.set(dummy, original);
  },

  /**
   * Replace all dummy tokens in `text` with their original PII values.
   * Uses longest-first ordering to prevent partial replacement bugs.
   */
  applyTo(text: string): string {
    let result = text;
    for (const { dummy, original } of _sortedEntries()) {
      // Use a simple split-join to replace all occurrences without regex
      result = result.split(dummy).join(original);
    }
    return result;
  },

  /** Wipe the entire in-memory map. */
  clear(): void {
    _map.clear();
  },

  /** Number of dummy→original pairs currently stored. */
  count(): number {
    return _map.size;
  },

  /** All mappings sorted longest-dummy-first. */
  getMappings(): Array<{ dummy: string; original: string }> {
    return _sortedEntries();
  },
};

// ─── Part 2 — IndexedDB metadata store ──────────────────────────────────────

export interface VaultMetaEntry {
  sessionId: string;
  /** e.g. { PERSON: 2, PHONE_NUMBER: 1 } */
  counts: Record<string, number>;
  lastUpdatedAt: number;
}

interface ConsentFlowMetaDB extends DBSchema {
  sessions: {
    key: string;
    value: VaultMetaEntry;
  };
}

let _dbPromise: Promise<IDBPDatabase<ConsentFlowMetaDB>> | null = null;

function getDb(): Promise<IDBPDatabase<ConsentFlowMetaDB>> {
  if (!_dbPromise) {
    _dbPromise = openDB<ConsentFlowMetaDB>('consentflow-meta', 1, {
      upgrade(db) {
        db.createObjectStore('sessions', { keyPath: 'sessionId' });
      },
    });
  }
  return _dbPromise;
}

export const metaStore = {
  /**
   * Merge-upsert: add `increment` to the existing count for `type` in the
   * given session. Creates the session entry if it doesn't exist yet.
   */
  async upsertCounts(
    sessionId: string,
    type: string,
    increment: number,
  ): Promise<void> {
    const db = await getDb();
    const tx = db.transaction('sessions', 'readwrite');
    const store = tx.objectStore('sessions');

    const existing = await store.get(sessionId);
    const counts = existing?.counts ?? {};
    counts[type] = (counts[type] ?? 0) + increment;

    await store.put({ sessionId, counts, lastUpdatedAt: Date.now() });
    await tx.done;
  },

  /**
   * Return the counts record for `sessionId`, or {} if not found.
   */
  async getCounts(sessionId: string): Promise<Record<string, number>> {
    const db = await getDb();
    const entry = await db.get('sessions', sessionId);
    return entry?.counts ?? {};
  },

  /**
   * Delete the session entry entirely.
   */
  async clearSession(sessionId: string): Promise<void> {
    const db = await getDb();
    await db.delete('sessions', sessionId);
  },
};
