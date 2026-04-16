/**
 * vitest.setup.ts — Global test setup.
 *
 * Polyfills IndexedDB for the jsdom environment using fake-indexeddb,
 * so metaStore tests run without a real browser.
 */
import 'fake-indexeddb/auto';

// Minimal `chrome.storage.local` mock for unit tests (vitest/jsdom).
// We only implement the methods used by the codebase/tests.
const _localStore = new Map<string, unknown>();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).chrome = (globalThis as any).chrome ?? {};
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).chrome.storage = (globalThis as any).chrome.storage ?? {};
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).chrome.storage.local = (globalThis as any).chrome.storage.local ?? {
  get(
    keys: string[] | Record<string, unknown>,
    cb?: (result: Record<string, unknown>) => void,
  ): Promise<Record<string, unknown>> | void {
    const result: Record<string, unknown> = {};
    if (Array.isArray(keys)) {
      for (const k of keys) result[k] = _localStore.get(k);
    } else {
      for (const [k, def] of Object.entries(keys)) {
        result[k] = _localStore.has(k) ? _localStore.get(k) : def;
      }
    }
    if (cb) {
      cb(result);
      return;
    }
    return Promise.resolve(result);
  },
  set(items: Record<string, unknown>, cb?: () => void): Promise<void> | void {
    for (const [k, v] of Object.entries(items)) _localStore.set(k, v);
    if (cb) {
      cb();
      return;
    }
    return Promise.resolve();
  },
  remove(keys: string[], cb?: () => void): Promise<void> | void {
    for (const k of keys) _localStore.delete(k);
    if (cb) {
      cb();
      return;
    }
    return Promise.resolve();
  },
};
