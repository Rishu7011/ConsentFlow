/**
 * vault.test.ts — Unit tests for vault.ts (Step 3).
 *
 * In-memory reverse map:
 *   - store / applyTo work correctly
 *   - applyTo uses longest-first ordering
 *   - clear empties the map
 *
 * IndexedDB metaStore (uses fake-indexeddb via vitest jsdom environment):
 *   - upsert accumulates counts across calls
 *   - clearSession removes the entry
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { vault, metaStore } from './vault';

// ─── In-memory vault ─────────────────────────────────────────────────────────

describe('vault (in-memory map)', () => {
  beforeEach(() => {
    vault.clear();
  });

  it('store and applyTo work correctly', () => {
    vault.store('Alex Smith', 'Rishu Nigam');
    vault.store('9000000000', '9876543210');

    const result = vault.applyTo('Call Alex Smith at 9000000000');
    expect(result).toBe('Call Rishu Nigam at 9876543210');
  });

  it('applyTo leaves text unchanged when no dummies are stored', () => {
    const text = 'Nothing to replace here';
    expect(vault.applyTo(text)).toBe(text);
  });

  it('applyTo replaces all occurrences of the same dummy', () => {
    vault.store('DUMMY', 'REAL');
    expect(vault.applyTo('DUMMY and DUMMY')).toBe('REAL and REAL');
  });

  it('applyTo uses longest-first ordering to prevent partial replacement', () => {
    // "Alex Smith" must be replaced before "Alex" to avoid "Rishu Smith"
    vault.store('Alex', 'Jordan');
    vault.store('Alex Smith', 'Rishu Nigam');

    const result = vault.applyTo('Hello Alex Smith and Alex');
    expect(result).toBe('Hello Rishu Nigam and Jordan');
  });

  it('clear empties the map', () => {
    vault.store('dummy@example.com', 'real@example.com');
    expect(vault.count()).toBe(1);

    vault.clear();
    expect(vault.count()).toBe(0);
    expect(vault.applyTo('dummy@example.com')).toBe('dummy@example.com');
  });

  it('count returns the number of stored mappings', () => {
    expect(vault.count()).toBe(0);
    vault.store('a', 'b');
    vault.store('c', 'd');
    expect(vault.count()).toBe(2);
  });

  it('getMappings returns entries sorted longest-dummy-first', () => {
    vault.store('short', 'A');
    vault.store('much longer dummy', 'B');
    vault.store('medium dummy', 'C');

    const mappings = vault.getMappings();
    expect(mappings[0].dummy).toBe('much longer dummy');
    expect(mappings[1].dummy).toBe('medium dummy');
    expect(mappings[2].dummy).toBe('short');
  });

  it('overwriting the same dummy updates the original', () => {
    vault.store('DUMMY', 'first');
    vault.store('DUMMY', 'second');
    expect(vault.applyTo('DUMMY')).toBe('second');
    expect(vault.count()).toBe(1);
  });
});

// ─── metaStore (IndexedDB) ───────────────────────────────────────────────────

describe('metaStore (IndexedDB)', () => {
  const SESSION = 'test-session-001';

  beforeEach(async () => {
    await metaStore.clearSession(SESSION);
  });

  it('upsertCounts creates a new entry with correct count', async () => {
    await metaStore.upsertCounts(SESSION, 'PHONE_NUMBER', 1);
    const counts = await metaStore.getCounts(SESSION);
    expect(counts['PHONE_NUMBER']).toBe(1);
  });

  it('upsertCounts accumulates counts across multiple calls', async () => {
    await metaStore.upsertCounts(SESSION, 'EMAIL_ADDRESS', 2);
    await metaStore.upsertCounts(SESSION, 'EMAIL_ADDRESS', 3);
    const counts = await metaStore.getCounts(SESSION);
    expect(counts['EMAIL_ADDRESS']).toBe(5);
  });

  it('upsertCounts handles multiple types independently', async () => {
    await metaStore.upsertCounts(SESSION, 'PERSON', 1);
    await metaStore.upsertCounts(SESSION, 'PHONE_NUMBER', 2);
    await metaStore.upsertCounts(SESSION, 'PERSON', 1);

    const counts = await metaStore.getCounts(SESSION);
    expect(counts['PERSON']).toBe(2);
    expect(counts['PHONE_NUMBER']).toBe(2);
  });

  it('getCounts returns empty object for unknown session', async () => {
    const counts = await metaStore.getCounts('nonexistent-session');
    expect(counts).toEqual({});
  });

  it('clearSession removes the entry', async () => {
    await metaStore.upsertCounts(SESSION, 'IN_AADHAAR', 3);
    await metaStore.clearSession(SESSION);
    const counts = await metaStore.getCounts(SESSION);
    expect(counts).toEqual({});
  });
});
