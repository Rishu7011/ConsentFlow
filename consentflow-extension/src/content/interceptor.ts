/**
 * interceptor.ts — Intercept the user's outbound message before it reaches the AI.
 *
 * Step 5 of the ConsentFlow Privacy Shield build.
 *
 * Flow:
 *   1. Poll for the send button (MutationObserver + querySelector, max 10 s).
 *   2. Attach a capture-phase 'click' listener (never prevents default).
 *   3. On click: detect PII → call backend via service worker → replace with dummies.
 *   4. Offline fallback if the service worker doesn't respond within 3 s.
 *   5. Listen for CONSENT_UPDATED / CLEAR_VAULT runtime messages.
 */

import { detectAndReplace, SUPPORTED_TYPES } from '../utils/dummyGenerator';
import { vault, metaStore } from '../vault/vault';
import type { PlatformConfig } from './platforms/index';

// ─── Module-level state ───────────────────────────────────────────────────────

/** Enabled PII types for this page load (updated via CONSENT_UPDATED messages). */
let activeEnabledTypes: Set<string> = new Set(SUPPORTED_TYPES);

/** Session ID generated once per page load (set on first intercept). */
let sessionId: string | null = null;

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Attach the send-button interceptor for the given platform.
 *
 * @param config    - Platform DOM selectors and input helpers.
 * @param onMasked  - Called after PII has been masked; receives the count and sessionId.
 * @returns         A cleanup function that removes all listeners and observers.
 */
export async function attachInterceptor(
  config: PlatformConfig,
  onMasked: (count: number, sessionId: string) => void,
): Promise<() => void> {
  const cleanupFns: Array<() => void> = [];

  // 1. Wait for the send button to appear in the DOM.
  const sendButton = await waitForElement(config.sendButton, 10_000);

  // 2. Capture-phase click listener — never calls preventDefault/stopPropagation.
  const handleClick = () => void interceptClick(config, onMasked);
  sendButton.addEventListener('click', handleClick, { capture: true });
  cleanupFns.push(() => sendButton.removeEventListener('click', handleClick, { capture: true }));

  // 3. Runtime message listener for CONSENT_UPDATED and CLEAR_VAULT.
  const handleMessage = (
    message: { type: string; entityType?: string; enabled?: boolean },
  ) => {
    if (message.type === 'CONSENT_UPDATED') {
      const { entityType, enabled } = message;
      if (entityType === undefined || enabled === undefined) return;
      if (enabled) {
        activeEnabledTypes.add(entityType);
      } else {
        activeEnabledTypes.delete(entityType);
      }
    } else if (message.type === 'CLEAR_VAULT') {
      vault.clear();
    }
  };

  chrome.runtime.onMessage.addListener(handleMessage);
  cleanupFns.push(() => chrome.runtime.onMessage.removeListener(handleMessage));

  // Return a single cleanup function.
  return () => cleanupFns.forEach(fn => fn());
}

// ─── Core intercept logic ─────────────────────────────────────────────────────

async function interceptClick(
  config: PlatformConfig,
  onMasked: (count: number, sid: string) => void,
): Promise<void> {
  // a. Read current text.
  const inputEl = document.querySelector<HTMLElement>(config.inputSelector);
  if (!inputEl) return;

  const text = config.getInputText(inputEl);
  if (!text.trim()) return;

  // b. Detect PII in placeholder mode.
  const { anonymized, mappings } = detectAndReplace(
    text,
    'placeholder',
    [...activeEnabledTypes],
  );

  // c. No PII found — nothing to do.
  if (mappings.length === 0) return;

  // d. Generate sessionId once per page load.
  if (!sessionId) {
    sessionId = crypto.randomUUID();
  }
  const sid = sessionId;

  // e. Send to service worker with a 3 s timeout race.
  const placeholders = mappings.map(m => m.placeholder);

  try {
    const response = await Promise.race([
      sendToServiceWorker({ type: 'ANONYMIZE', entityRefs: placeholders, sessionId: sid }),
      timeout(3_000),
    ]) as { ok: boolean; dummies?: Record<string, string>; error?: string } | null;

    if (response?.ok && response.dummies) {
      // f. Backend succeeded — swap placeholders for dummies.
      let finalText = anonymized;
      for (const mapping of mappings) {
        const dummy = response.dummies[mapping.placeholder];
        if (dummy) {
          vault.store(dummy, mapping.original);
          finalText = finalText.split(mapping.placeholder).join(dummy);
        }
      }
      config.setInputText(inputEl, finalText);

      // Update per-type counts in IndexedDB metadata (non-PII).
      const typeCounts: Record<string, number> = {};
      for (const m of mappings) {
        typeCounts[m.type] = (typeCounts[m.type] ?? 0) + 1;
      }
      for (const [type, count] of Object.entries(typeCounts)) {
        await metaStore.upsertCounts(sid, type, count);
      }

      onMasked(mappings.length, sid);
    } else {
      // g. Response says not ok — use offline fallback.
      applyOfflineFallback(config, inputEl, text, sid, onMasked);
    }
  } catch {
    // Timeout or any other failure — offline fallback.
    applyOfflineFallback(config, inputEl, text, sid, onMasked);
  }
}

/** Offline fallback: run 'direct' mode locally, store dummy→original in vault. */
async function applyOfflineFallback(
  config: PlatformConfig,
  inputEl: HTMLElement,
  originalText: string,
  sid: string,
  onMasked: (count: number, sid: string) => void,
): Promise<void> {
  console.warn('[ConsentFlow] Backend unreachable — using offline fallback');

  const { anonymized, mappings } = detectAndReplace(
    originalText,
    'direct',
    [...activeEnabledTypes],
  );

  for (const m of mappings) {
    vault.store(m.dummy, m.original);
  }

  config.setInputText(inputEl, anonymized);

  // Update per-type counts (non-PII metadata).
  const typeCounts: Record<string, number> = {};
  for (const m of mappings) {
    typeCounts[m.type] = (typeCounts[m.type] ?? 0) + 1;
  }
  for (const [type, count] of Object.entries(typeCounts)) {
    await metaStore.upsertCounts(sid, type, count);
  }

  onMasked(mappings.length, sid);
}

// ─── Utilities ────────────────────────────────────────────────────────────────

/**
 * Poll for a CSS selector using MutationObserver + querySelector.
 * Resolves with the element when found, rejects after `maxMs`.
 */
function waitForElement(selector: string, maxMs: number): Promise<HTMLElement> {
  return new Promise<HTMLElement>((resolve, reject) => {
    // Check immediately first.
    const existing = document.querySelector<HTMLElement>(selector);
    if (existing) {
      resolve(existing);
      return;
    }

    const timer = setTimeout(() => {
      observer.disconnect();
      reject(new Error(`[ConsentFlow] Element not found within ${maxMs}ms: ${selector}`));
    }, maxMs);

    const observer = new MutationObserver(() => {
      const el = document.querySelector<HTMLElement>(selector);
      if (el) {
        clearTimeout(timer);
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  });
}

/** Send a message to the service worker and return the response. */
function sendToServiceWorker(message: object): Promise<unknown> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

/** Returns a promise that resolves to null after `ms` milliseconds. */
function timeout(ms: number): Promise<null> {
  return new Promise(resolve => setTimeout(() => resolve(null), ms));
}
