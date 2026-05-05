/**
 * vitest.setup.ts — Global test setup.
 *
 * Polyfills IndexedDB for the jsdom environment using fake-indexeddb,
 * so metaStore tests run without a real browser.
 */
import 'fake-indexeddb/auto';
