/**
 * App.tsx — ConsentFlow Privacy Shield popup UI.
 *
 * Step 9 of the ConsentFlow Privacy Shield build.
 *
 * Width: 360 px  |  Theme: dark (#0f172a bg, #6366f1 accent)
 * Styling: Tailwind utility classes only (loaded via CDN in index.html).
 *
 * Sections:
 *   HEADER       — shield icon, title, items-protected count
 *   PII TOGGLES  — per-entity-type on/off switches
 *   SESSION LOG  — per-type masked counts + clear button
 *   FOOTER       — site disable toggle, backend URL editor, online status dot
 */

import React, { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { metaStore } from '../vault/vault';
import { SUPPORTED_TYPES } from '../utils/dummyGenerator';

// ─── Types ────────────────────────────────────────────────────────────────────

type ConsentProfile = Record<string, boolean>;

interface State {
  sessionId: string;
  counts: Record<string, number>;          // per-type masked counts this session
  profile: ConsentProfile;                 // enabled PII types
  backendUrl: string;
  isOnline: boolean;
  disabledSites: string[];
  currentHostname: string;
}

// ─── PII labels ──────────────────────────────────────────────────────────────

const PII_LABELS: Record<string, string> = {
  EMAIL_ADDRESS: 'Email',
  IN_AADHAAR:    'Aadhaar',
  IN_PAN:        'PAN',
  PHONE_NUMBER:  'Phone',
  UPI_ID:        'UPI ID',
  PERSON:        'Full name',
};

// ─── Toggle component ─────────────────────────────────────────────────────────

function Toggle({
  id,
  checked,
  onChange,
}: {
  id: string;
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="relative inline-block w-11 h-6 cursor-pointer select-none">
      <input
        id={id}
        type="checkbox"
        className="toggle-input sr-only"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
      />
      <span className="toggle-track block w-11 h-6 rounded-full bg-slate-600 transition-colors duration-200">
        <span className="toggle-thumb block w-4 h-4 mt-1 ml-1 rounded-full bg-white shadow transition-transform duration-200" />
      </span>
    </label>
  );
}

// ─── Status dot ───────────────────────────────────────────────────────────────

function StatusDot({ online }: { online: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`inline-block w-2 h-2 rounded-full ${online ? 'bg-emerald-400' : 'bg-red-400'}`}
      />
      <span className={online ? 'text-emerald-400' : 'text-red-400'}>
        {online ? 'Backend online' : 'Backend offline'}
      </span>
    </span>
  );
}

// ─── App ─────────────────────────────────────────────────────────────────────

function App() {
  const [state, setState] = useReducer(
    (prev: State, patch: Partial<State>): State => ({ ...prev, ...patch }),
    {
      sessionId: '',
      counts: {},
      profile: Object.fromEntries(SUPPORTED_TYPES.map(t => [t, true])),
      backendUrl: 'http://localhost:8000',
      isOnline: false,
      disabledSites: [],
      currentHostname: '',
    } satisfies State,
  );

  const [editingUrl, setEditingUrl] = useState(false);
  const [urlDraft, setUrlDraft]     = useState('');
  const urlInputRef = useRef<HTMLInputElement>(null);

  // ── Mount: load all initial state ─────────────────────────────────────────
  useEffect(() => {
    void (async () => {
      // Session ID
      const sessionResult = await chromeStorageGet<{ currentSessionId?: string }>(
        chrome.storage.session,
        ['currentSessionId'],
      );
      const sessionId = sessionResult.currentSessionId ?? '';

      // Counts from IndexedDB (non-PII metadata)
      const counts = sessionId ? await metaStore.getCounts(sessionId) : {};

      // Backend URL + disabled sites
      const local = await chromeStorageGet<{
        backendUrl?: string;
        disabledSites?: string[];
      }>(chrome.storage.local, ['backendUrl', 'disabledSites']);

      const backendUrl    = local.backendUrl    ?? 'http://localhost:8000';
      const disabledSites = local.disabledSites ?? [];

      // Current tab hostname
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const currentHostname = tab?.url ? new URL(tab.url).hostname : '';

      // Consent profile + online status (same message)
      const { profile, isOnline } = await loadProfile(backendUrl);

      setState({ sessionId, counts, profile, backendUrl, disabledSites, currentHostname, isOnline });
      setUrlDraft(backendUrl);
    })();
  }, []);

  // ── PII toggle changed ────────────────────────────────────────────────────
  const handleToggle = useCallback(
    async (entityType: string, enabled: boolean) => {
      setState({ profile: { ...state.profile, [entityType]: enabled } });

      // Persist to service worker → backend
      chrome.runtime.sendMessage({
        type: 'UPDATE_CONSENT',
        userId: 'local',
        entityType,
        enabled,
      }).catch(() => {/* offline */});

      // Forward to active-tab content script
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        chrome.tabs.sendMessage(tab.id, {
          type: 'CONSENT_UPDATED',
          entityType,
          enabled,
        }).catch(() => {/* content script may not be loaded */});
      }
    },
    [state.profile],
  );

  // ── Clear session vault ───────────────────────────────────────────────────
  const handleClearVault = useCallback(async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, { type: 'CLEAR_VAULT' }).catch(() => {});
    }
    if (state.sessionId) {
      await metaStore.clearSession(state.sessionId);
    }
    setState({ counts: {} });
  }, [state.sessionId]);

  // ── Site disable toggle ───────────────────────────────────────────────────
  const isSiteDisabled = state.disabledSites.includes(state.currentHostname);

  const handleSiteToggle = useCallback(async () => {
    const host = state.currentHostname;
    if (!host) return;
    const updated = isSiteDisabled
      ? state.disabledSites.filter(s => s !== host)
      : [...state.disabledSites, host];
    await chrome.storage.local.set({ disabledSites: updated });
    setState({ disabledSites: updated });
  }, [state.currentHostname, state.disabledSites, isSiteDisabled]);

  // ── Backend URL save ─────────────────────────────────────────────────────
  const handleUrlSave = useCallback(async () => {
    const url = urlDraft.trim();
    if (!url) return;
    await chrome.runtime.sendMessage({ type: 'SET_BACKEND_URL', url }).catch(() => {});
    setState({ backendUrl: url });
    setEditingUrl(false);

    // Recheck online status with new URL
    const { isOnline } = await loadProfile(url);
    setState({ isOnline });
  }, [urlDraft]);

  // Total items protected this session
  const totalProtected = Object.values(state.counts).reduce((a, b) => a + b, 0);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-[#0f172a] text-slate-100 font-sans text-sm select-none">

      {/* ── HEADER ─────────────────────────────────────────────────────── */}
      <header className="px-4 pt-4 pb-3 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-2xl" role="img" aria-label="shield">🛡️</span>
          <div>
            <h1 className="font-semibold text-base leading-tight tracking-tight">
              ConsentFlow Shield
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              {totalProtected > 0
                ? <><span className="text-indigo-400 font-medium">{totalProtected}</span> item{totalProtected !== 1 ? 's' : ''} protected this session</>
                : 'No items masked yet'}
            </p>
          </div>
        </div>
      </header>

      {/* ── PII TOGGLES ────────────────────────────────────────────────── */}
      <section className="px-4 py-3 border-b border-slate-700">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
          PII Protection
        </p>
        <ul className="space-y-2">
          {SUPPORTED_TYPES.map(type => (
            <li key={type} className="flex items-center justify-between">
              <span className="text-slate-300">{PII_LABELS[type] ?? type}</span>
              <Toggle
                id={`toggle-${type}`}
                checked={state.profile[type] ?? true}
                onChange={val => void handleToggle(type, val)}
              />
            </li>
          ))}
        </ul>
      </section>

      {/* ── SESSION LOG ────────────────────────────────────────────────── */}
      <section className="px-4 py-3 border-b border-slate-700 flex-1 overflow-y-auto">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
          Session Log
        </p>

        {Object.entries(state.counts).filter(([, n]) => n > 0).length === 0 ? (
          <p className="text-xs text-slate-500 italic">Nothing masked yet this session.</p>
        ) : (
          <ul className="space-y-1 mb-3">
            {Object.entries(state.counts)
              .filter(([, n]) => n > 0)
              .map(([type, n]) => (
                <li key={type} className="flex items-center justify-between">
                  <span className="text-slate-400">
                    {PII_LABELS[type] ?? type}
                  </span>
                  <span className="text-indigo-400 font-medium text-xs">
                    {n} masked
                  </span>
                </li>
              ))}
          </ul>
        )}

        <button
          id="btn-clear-vault"
          onClick={() => void handleClearVault()}
          className="mt-1 w-full py-1.5 rounded-md text-xs font-medium
                     bg-slate-700 hover:bg-slate-600 active:bg-slate-500
                     text-slate-300 transition-colors duration-150"
        >
          Clear session vault
        </button>
      </section>

      {/* ── FOOTER ─────────────────────────────────────────────────────── */}
      <footer className="px-4 py-3 space-y-3">

        {/* Site disable toggle */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">
            {state.currentHostname || 'this site'}
          </span>
          <button
            id="btn-site-toggle"
            onClick={() => void handleSiteToggle()}
            className={`text-xs px-2.5 py-1 rounded font-medium transition-colors duration-150 ${
              isSiteDisabled
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
            }`}
          >
            {isSiteDisabled ? 'Re-enable on this site' : 'Disable on this site'}
          </button>
        </div>

        {/* Backend URL */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">Backend URL</span>
            {!editingUrl && (
              <button
                id="btn-edit-url"
                onClick={() => {
                  setUrlDraft(state.backendUrl);
                  setEditingUrl(true);
                  setTimeout(() => urlInputRef.current?.focus(), 0);
                }}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Edit
              </button>
            )}
          </div>

          {editingUrl ? (
            <div className="flex gap-1">
              <input
                ref={urlInputRef}
                id="input-backend-url"
                type="text"
                value={urlDraft}
                onChange={e => setUrlDraft(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') void handleUrlSave();
                  if (e.key === 'Escape') setEditingUrl(false);
                }}
                className="flex-1 bg-slate-800 border border-slate-600 rounded px-2 py-1
                           text-xs text-slate-200 outline-none focus:border-indigo-500
                           transition-colors"
              />
              <button
                id="btn-save-url"
                onClick={() => void handleUrlSave()}
                className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white
                           text-xs rounded font-medium transition-colors"
              >
                Save
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400 truncate font-mono">{state.backendUrl}</p>
          )}
        </div>

        {/* Online status */}
        <StatusDot online={state.isOnline} />
      </footer>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function chromeStorageGet<T>(
  area: chrome.storage.StorageArea,
  keys: string[],
): Promise<T> {
  return new Promise(resolve => area.get(keys, result => resolve(result as T)));
}

async function loadProfile(backendUrl: string): Promise<{
  profile: ConsentProfile;
  isOnline: boolean;
}> {
  try {
    const res = await new Promise<{ ok: boolean; profile?: ConsentProfile }>(
      (resolve, reject) =>
        chrome.runtime.sendMessage(
          { type: 'GET_CONSENT_PROFILE', userId: 'local' },
          r => (chrome.runtime.lastError ? reject(chrome.runtime.lastError) : resolve(r)),
        ),
    );
    if (res?.ok && res.profile) {
      return { profile: res.profile, isOnline: true };
    }
    return { profile: defaultProfile(), isOnline: false };
  } catch {
    return { profile: defaultProfile(), isOnline: false };
  }
}

function defaultProfile(): ConsentProfile {
  return Object.fromEntries(SUPPORTED_TYPES.map(t => [t, true]));
}

// ─── Mount ───────────────────────────────────────────────────────────────────

const root = document.getElementById('root')!;
createRoot(root).render(<App />);
