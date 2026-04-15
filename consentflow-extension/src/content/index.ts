/**
 * index.ts — Content script entry point for ConsentFlow Privacy Shield.
 *
 * Step 8 of the ConsentFlow Privacy Shield build.
 *
 * Responsibilities:
 *  1. Detect platform (chatgpt / claude). Exit if unknown.
 *  2. Generate a sessionId for this page load.
 *  3. Fetch the user's consent profile from the service worker.
 *  4. Attach interceptor + reverse mapper.
 *  5. Re-attach on SPA navigation (URL change without full reload).
 *  6. Listen for CONSENT_UPDATED from the popup.
 */

import { getPlatformConfig } from './platforms/index';
import { attachInterceptor } from './interceptor';
import { attachReverseMapper } from './reverseMapper';
import { SUPPORTED_TYPES } from '../utils/dummyGenerator';

// ─── Types ────────────────────────────────────────────────────────────────────

type ConsentProfile = Record<string, boolean>;

// ─── Bootstrap ────────────────────────────────────────────────────────────────

const config = getPlatformConfig();

if (!config) {
  console.log('[ConsentFlow] Unknown platform — content script inactive.');
} else {
  void main();
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const platformConfig = getPlatformConfig()!;

  // 2. Per-page-load session ID.
  const sessionId = crypto.randomUUID();
  // Persist so the popup can read it.
  chrome.storage.session?.set({ currentSessionId: sessionId }).catch(() => {/* ignore */});

  // 3. Load consent profile → build activeEnabledTypes Set.
  const activeEnabledTypes = await loadConsentProfile();

  // 4. Attach interceptor and reverse mapper.
  let cleanupInterceptor = await attachAndBind(platformConfig, sessionId, activeEnabledTypes);

  // 5. SPA navigation watch — re-attach after URL changes (debounced 500 ms).
  let lastUrl = location.href;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  const reattach = () => {
    if (debounceTimer !== null) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      if (location.href === lastUrl) return;
      lastUrl = location.href;
      cleanupInterceptor();
      cleanupInterceptor = await attachAndBind(platformConfig, sessionId, activeEnabledTypes);
    }, 500);
  };

  window.addEventListener('popstate', reattach);

  // Also watch body mutations for pushState-based SPAs that don't fire popstate.
  const spaObserver = new MutationObserver(reattach);
  spaObserver.observe(document.body, { childList: true, subtree: false });

  // 6. Listen for CONSENT_UPDATED forwarded from popup.
  //    The interceptor already handles this message via its own listener,
  //    but we also keep activeEnabledTypes in sync here.
  chrome.runtime.onMessage.addListener((message: {
    type: string;
    entityType?: string;
    enabled?: boolean;
  }) => {
    if (message.type !== 'CONSENT_UPDATED') return;
    const { entityType, enabled } = message;
    if (!entityType || enabled === undefined) return;
    if (enabled) {
      activeEnabledTypes.add(entityType);
    } else {
      activeEnabledTypes.delete(entityType);
    }
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Attach the interceptor; on first mask also attach the reverse mapper
 * and update the badge.
 */
async function attachAndBind(
  platformConfig: NonNullable<ReturnType<typeof getPlatformConfig>>,
  sessionId: string,
  activeEnabledTypes: Set<string>,
): Promise<() => void> {
  try {
    const cleanup = await attachInterceptor(platformConfig, (count, sid) => {
      attachReverseMapper(platformConfig, sid);
      chrome.runtime.sendMessage({ type: 'UPDATE_BADGE', count }).catch(() => {/* offline */});
    });
    return cleanup;
  } catch (err) {
    console.warn('[ConsentFlow] Failed to attach interceptor:', err);
    return () => { /* no-op */ };
  }
}

/**
 * Ask the service worker for the user's consent profile.
 * Falls back to all types enabled if the call fails.
 */
async function loadConsentProfile(): Promise<Set<string>> {
  try {
    const response = await new Promise<{ ok: boolean; profile?: ConsentProfile }>(
      (resolve, reject) => {
        chrome.runtime.sendMessage(
          { type: 'GET_CONSENT_PROFILE', userId: '00000000-0000-0000-0000-000000000000' },
          (res) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve(res);
            }
          },
        );
      },
    );

    if (response?.ok && response.profile) {
      // Only include types that are enabled in the profile AND are supported.
      const enabled = new Set<string>();
      for (const type of SUPPORTED_TYPES) {
        if (response.profile[type] !== false) {
          enabled.add(type);
        }
      }
      return enabled;
    }
  } catch {
    // Service worker unreachable — default to all types enabled.
  }

  return new Set(SUPPORTED_TYPES);
}
