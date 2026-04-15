/**
 * serviceWorker.ts — Manifest V3 background service worker.
 *
 * Step 7 of the ConsentFlow Privacy Shield build.
 *
 * Handles these message types:
 *   ANONYMIZE            — POST to /api/v1/extension/anonymize
 *   GET_CONSENT_PROFILE  — GET /api/v1/extension/consent-profile
 *   UPDATE_CONSENT       — PUT /api/v1/consent
 *   UPDATE_BADGE         — Set the extension action badge
 *   SET_BACKEND_URL      — Persist a new backend URL to chrome.storage.local
 */

// ─── Default consent profile ─────────────────────────────────────────────────

const DEFAULT_PII_PROFILE: Record<string, boolean> = {
  PERSON: true,
  PHONE_NUMBER: true,
  EMAIL_ADDRESS: true,
  IN_AADHAAR: true,
  IN_PAN: true,
  UPI_ID: true,
};

// ─── Backend URL helper ───────────────────────────────────────────────────────

/** Read the backend base URL from storage; default to localhost:8000. */
async function getBackendUrl(): Promise<string> {
  return new Promise(resolve => {
    chrome.storage.local.get(['backendUrl'], result => {
      resolve((result['backendUrl'] as string | undefined) ?? 'http://localhost:8000');
    });
  });
}

// ─── Message types ────────────────────────────────────────────────────────────

interface AnonymizePayload {
  type: 'ANONYMIZE';
  entityRefs: string[];
  sessionId: string;
}

interface GetConsentProfilePayload {
  type: 'GET_CONSENT_PROFILE';
  userId: string;
}

interface UpdateConsentPayload {
  type: 'UPDATE_CONSENT';
  userId: string;
  entityType: string;
  enabled: boolean;
}

interface UpdateBadgePayload {
  type: 'UPDATE_BADGE';
  count: number;
}

interface SetBackendUrlPayload {
  type: 'SET_BACKEND_URL';
  url: string;
}

type IncomingMessage =
  | AnonymizePayload
  | GetConsentProfilePayload
  | UpdateConsentPayload
  | UpdateBadgePayload
  | SetBackendUrlPayload;

// ─── Message handler ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener(
  (message: IncomingMessage, _sender, sendResponse) => {
    // Must return true to keep the message channel open for async responses.
    handleMessage(message).then(sendResponse).catch(err => {
      console.error('[ConsentFlow SW] Unhandled error:', err);
      sendResponse({ ok: false, error: String(err) });
    });
    return true;
  },
);

async function handleMessage(message: IncomingMessage): Promise<object> {
  switch (message.type) {

    // ── ANONYMIZE ────────────────────────────────────────────────────────────
    case 'ANONYMIZE': {
      const { entityRefs, sessionId } = message;
      const backendUrl = await getBackendUrl();
      const controller = new AbortController();
      const timerId = setTimeout(() => controller.abort(), 3_000);

      try {
        const res = await fetch(`${backendUrl}/api/v1/extension/anonymize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ entity_refs: entityRefs, session_id: sessionId }),
          signal: controller.signal,
        });
        clearTimeout(timerId);

        if (!res.ok) {
          const text = await res.text().catch(() => res.statusText);
          return { ok: false, error: `HTTP ${res.status}: ${text}` };
        }

        const data = await res.json() as { dummies: Record<string, string> };
        return { ok: true, dummies: data.dummies };
      } catch (err) {
        clearTimeout(timerId);
        return { ok: false, error: String(err) };
      }
    }

    // ── GET_CONSENT_PROFILE ──────────────────────────────────────────────────
    case 'GET_CONSENT_PROFILE': {
      const { userId } = message;
      const backendUrl = await getBackendUrl();

      try {
        const res = await fetch(
          `${backendUrl}/api/v1/extension/consent-profile?user_id=${encodeURIComponent(userId)}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const profile = await res.json();
        return { ok: true, profile };
      } catch {
        // Fall back to default profile — the popup must still work offline.
        return { ok: true, profile: DEFAULT_PII_PROFILE };
      }
    }

    // ── UPDATE_CONSENT ───────────────────────────────────────────────────────
    case 'UPDATE_CONSENT': {
      const { userId, entityType, enabled } = message;
      const backendUrl = await getBackendUrl();

      try {
        const res = await fetch(`${backendUrl}/consent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            purpose: 'extension_pii_masking',
            status: enabled ? 'granted' : 'revoked',
            data_type: entityType,
          }),
        });
        if (!res.ok) {
          const text = await res.text().catch(() => res.statusText);
          return { ok: false, error: `HTTP ${res.status}: ${text}` };
        }
        return { ok: true };
      } catch (err) {
        return { ok: false, error: String(err) };
      }
    }

    // ── UPDATE_BADGE ─────────────────────────────────────────────────────────
    case 'UPDATE_BADGE': {
      const { count } = message;
      await chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
      await chrome.action.setBadgeBackgroundColor({ color: '#6366f1' });
      return { ok: true };
    }

    // ── SET_BACKEND_URL ──────────────────────────────────────────────────────
    case 'SET_BACKEND_URL': {
      const { url } = message;
      await chrome.storage.local.set({ backendUrl: url });
      return { ok: true };
    }

    default: {
      const _exhaustive: never = message;
      return { ok: false, error: `Unknown message type: ${(_exhaustive as IncomingMessage).type}` };
    }
  }
}
