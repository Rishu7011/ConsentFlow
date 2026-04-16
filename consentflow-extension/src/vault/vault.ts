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

// ─── Part 2 — Metadata store (chrome.storage.local) ─────────────────────────

export const metaStore = {
  /**
   * Merge-upsert: add `increment` to the existing count for `type` in the
   * given session.
   */
  async upsertCounts(
    sessionId: string,
    type: string,
    increment: number,
  ): Promise<void> {
    const key = `metrics_${sessionId}`;
    const result = await chrome.storage.local.get([key]);
    const counts = result[key] || {};
    counts[type] = (counts[type] || 0) + increment;
    await chrome.storage.local.set({ [key]: counts });
  },

  /**
   * Return the counts record for `sessionId`, or {} if not found.
   */
  async getCounts(sessionId: string): Promise<Record<string, number>> {
    const key = `metrics_${sessionId}`;
    const result = await chrome.storage.local.get([key]);
    return result[key] || {};
  },

  /**
   * Delete the session entry entirely.
   */
  async clearSession(sessionId: string): Promise<void> {
    const key = `metrics_${sessionId}`;
    await chrome.storage.local.remove([key]);
  },
};
