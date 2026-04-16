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

export async function attachInterceptor(
  config: PlatformConfig,
  providedSessionId: string,
  onMasked: (count: number, sessionId: string) => void,
): Promise<() => void> {
  sessionId = providedSessionId;
  const cleanupFns: Array<() => void> = [];
  
  let isIntercepting = false;

  const handleEvent = (e: Event) => {
    // Let our programmatic/simulated events pass through naturally to ChatGPT
    if (!e.isTrusted) return;

    const isClick = e.type === 'click' || 
                    e.type === 'mousedown' || e.type === 'mouseup' || 
                    e.type === 'pointerdown' || e.type === 'pointerup';
    const isEnter = (e.type === 'keydown' || e.type === 'keyup' || e.type === 'keypress') && 
                    (e as KeyboardEvent).key === 'Enter' && 
                    !(e as KeyboardEvent).shiftKey;
    
    if (!isClick && !isEnter) return;

    const inputEl = document.querySelector<HTMLElement>(config.inputSelector);
    if (!inputEl) return;
    
    if (isClick) {
      const target = e.target as HTMLElement;
      if (!target.closest(config.sendButton)) return;
    } else if (isEnter) {
      if (!inputEl.contains(e.target as Node) && e.target !== inputEl) return;
    }

    // If we are already busy masking from a previous event (e.g. we caught keydown
    // and this is the subsequent keyup), aggressively block it so ChatGPT doesn't get it!
    if (isIntercepting) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      return;
    }

    const text = config.getInputText(inputEl);
    if (!text.trim()) return;

    const { mappings } = detectAndReplace(text, 'placeholder', [...activeEnabledTypes]);
    if (mappings.length === 0) return;

    // We found PII! Stop this event from reaching ChatGPT synchronously!
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    isIntercepting = true;
    
    const triggerEvent = e.type;

    void interceptClick(config, onMasked, text, mappings, inputEl).then(() => {
      setTimeout(() => {
        const btn = document.querySelector<HTMLElement>(config.sendButton);
        if (btn) {
           if (triggerEvent.includes('down')) {
             btn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
             btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
             btn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true }));
             btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
             btn.click();
           } else {
             btn.click();
           }
        } else {
           const newEvent = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
           inputEl.dispatchEvent(newEvent);
        }
        isIntercepting = false;
      }, 50);
    }).catch((err) => {
      console.error('[ConsentFlow] Intercept failed:', err);
      isIntercepting = false;
    });
  };

  // Attach to window capture phase to guarantee we run BEFORE document/root listeners
  window.addEventListener('click', handleEvent, { capture: true });
  window.addEventListener('mousedown', handleEvent, { capture: true });
  window.addEventListener('mouseup', handleEvent, { capture: true });
  window.addEventListener('pointerdown', handleEvent, { capture: true });
  window.addEventListener('pointerup', handleEvent, { capture: true });
  window.addEventListener('keydown', handleEvent, { capture: true });
  window.addEventListener('keyup', handleEvent, { capture: true });
  window.addEventListener('keypress', handleEvent, { capture: true });
  cleanupFns.push(() => {
    window.removeEventListener('click', handleEvent, { capture: true });
    window.removeEventListener('mousedown', handleEvent, { capture: true });
    window.removeEventListener('mouseup', handleEvent, { capture: true });
    window.removeEventListener('pointerdown', handleEvent, { capture: true });
    window.removeEventListener('pointerup', handleEvent, { capture: true });
    window.removeEventListener('keydown', handleEvent, { capture: true });
    window.removeEventListener('keyup', handleEvent, { capture: true });
    window.removeEventListener('keypress', handleEvent, { capture: true });
  });

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

  return () => cleanupFns.forEach(fn => fn());
}

// ─── Core intercept logic ─────────────────────────────────────────────────────

async function interceptClick(
  config: PlatformConfig,
  onMasked: (count: number, sid: string) => void,
  text: string,
  mappings: ReturnType<typeof detectAndReplace>['mappings'],
  inputEl: HTMLElement,
): Promise<void> {
  if (!sessionId) {
    sessionId = crypto.randomUUID();
  }
  const sid = sessionId;

  const placeholders = mappings.map(m => m.placeholder);

  try {
    const response = await Promise.race([
      sendToServiceWorker({ type: 'ANONYMIZE', entityRefs: placeholders, sessionId: sid }),
      timeout(3_000),
    ]) as { ok: boolean; dummies?: Record<string, string>; error?: string } | null;

    if (response?.ok && response.dummies) {
      const { anonymized } = detectAndReplace(text, 'placeholder', [...activeEnabledTypes]);
      let finalText = anonymized;
      for (const mapping of mappings) {
        const dummy = response.dummies[mapping.placeholder];
        if (dummy) {
          vault.store(dummy, mapping.original);
          finalText = finalText.split(mapping.placeholder).join(dummy);
        }
      }
      config.setInputText(inputEl, finalText);

      const typeCounts: Record<string, number> = {};
      for (const m of mappings) {
        typeCounts[m.type] = (typeCounts[m.type] ?? 0) + 1;
      }
      for (const [type, count] of Object.entries(typeCounts)) {
        await metaStore.upsertCounts(sid, type, count);
      }

      onMasked(mappings.length, sid);
    } else {
      await applyOfflineFallback(config, inputEl, text, sid, onMasked);
    }
  } catch {
    await applyOfflineFallback(config, inputEl, text, sid, onMasked);
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
