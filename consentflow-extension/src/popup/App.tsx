import React, { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { metaStore } from '../vault/vault';
import { SUPPORTED_TYPES } from '../utils/dummyGenerator';

type ConsentProfile = Record<string, boolean>;

interface State {
  sessionId: string;
  counts: Record<string, number>;
  profile: ConsentProfile;
  backendUrl: string;
  isOnline: boolean;
  disabledSites: string[];
  currentHostname: string;
}

const PII_LABELS: Record<string, { label: string; badge: string }> = {
  PERSON: { label: 'Full name', badge: 'PERSON' },
  PHONE_NUMBER: { label: 'Phone number', badge: 'PHONE' },
  IN_AADHAAR: { label: 'Aadhaar', badge: 'IN_AADHAAR' },
  EMAIL_ADDRESS: { label: 'Email address', badge: 'EMAIL' },
  IN_PAN: { label: 'PAN card', badge: 'IN_PAN' },
  UPI_ID: { label: 'UPI ID', badge: 'UPI_ID' },
};

function App() {
  const [state, setState] = useReducer(
    (prev: State, patch: Partial<State>) => ({ ...prev, ...patch }),
    {
      sessionId: '',
      counts: {},
      profile: Object.fromEntries(SUPPORTED_TYPES.map(t => [t, true])),
      backendUrl: 'http://localhost:8000',
      isOnline: true,
      disabledSites: [],
      currentHostname: '',
    }
  );

  const [editingUrl, setEditingUrl] = useState(false);
  const [urlDraft, setUrlDraft] = useState('');
  const [siteDisabled, setSiteDisabled] = useState(false);

  useEffect(() => {
    void (async () => {
      // NOTE: Using a try-catch for chrome APIs so it doesn't fail in non-extension environment
      try {
        const sessionResult = await chrome.storage.session.get(['currentSessionId']);
        const sessionId = sessionResult.currentSessionId ?? '';
        const counts = sessionId ? await metaStore.getCounts(sessionId) : {};
        const local = await chrome.storage.local.get(['backendUrl', 'disabledSites']);
        const backendUrl = local.backendUrl ?? 'http://localhost:8000';
        const disabledSites = local.disabledSites ?? [];
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const currentHostname = tab?.url ? new URL(tab.url).hostname : '';
        let isOnline = false;
        try {
          const controller = new AbortController();
          setTimeout(() => controller.abort(), 2000);
          const res = await fetch(`${backendUrl}/health`, { signal: controller.signal });
          isOnline = res.ok;
        } catch (e) {
          isOnline = false;
        }

        setState({ sessionId, counts, backendUrl, disabledSites, currentHostname, isOnline });
        setUrlDraft(backendUrl);
      } catch (e) {
        // Fallback for development outside extension
        setState({ backendUrl: 'http://localhost:8000', isOnline: false });
        setUrlDraft('http://localhost:8000');
      }
    })();
  }, []);

  const handleToggle = useCallback((type: string) => {
    const newStatus = !state.profile[type];
    setState({ profile: { ...state.profile, [type]: newStatus } });
    
    chrome.runtime.sendMessage({
      type: 'UPDATE_CONSENT',
      userId: '00000000-0000-0000-0000-000000000000', // Need a valid UUID for the backend
      entityType: type,
      enabled: newStatus
    }).catch(() => {});

    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      if (tab?.id) {
        chrome.tabs.sendMessage(tab.id, {
          type: 'CONSENT_UPDATED',
          entityType: type,
          enabled: newStatus
        }).catch(() => {});
      }
    });
  }, [state.profile]);

  const clearVault = () => {
    setState({ counts: {} });
  };

  const saveBackend = async () => {
    let display = urlDraft.trim();
    if (!display.startsWith('http')) {
      display = 'http://' + display;
    }
    setEditingUrl(false);
    
    // Trigger ping logic here
    let isOnline = false;
    try {
      const controller = new AbortController();
      setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${display}/health`, { signal: controller.signal });
      isOnline = res.ok;
    } catch (e) {
      isOnline = false;
    }
    setState({ backendUrl: display, isOnline });
    if (typeof chrome !== 'undefined' && chrome.storage) {
      chrome.storage.local.set({ backendUrl: display }).catch(() => {});
    }
  };

  const totalProtected = Object.values(state.counts).reduce((a, b) => a + b, 0);
  const isEmptySession = Object.keys(state.counts).length === 0;

  return (
    <div className="popup">
      <div className="header">
        <div className="header-left">
          <div className="shield-icon">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L4 6v6c0 5.25 3.5 10.15 8 11.35C16.5 22.15 20 17.25 20 12V6L12 2z" fill="#6366f1"/>
              <path d="M9 12l2 2 4-4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <div className="header-title">ConsentFlow Shield</div>
            <div className="header-sub">Active on this page</div>
          </div>
        </div>
        <div className="status-dot" id="status-indicator">
          <div className={`dot ${state.isOnline ? '' : 'offline'}`} id="status-dot"></div>
          <span id="status-text">{state.isOnline ? 'Backend online' : 'Backend offline'}</span>
        </div>
      </div>

      <div className="section">
        <div className="section-label">PII Masking</div>
        <div id="toggles">
          {SUPPORTED_TYPES.map((type, idx) => {
            const isLast = idx === SUPPORTED_TYPES.length - 1;
            const info = PII_LABELS[type] || { label: type, badge: type };
            return (
              <div className="toggle-row" key={type} style={isLast ? { borderBottom: 'none' } : {}}>
                <div className="toggle-label">
                  <span className="toggle-name">{info.label}</span>
                  <span className="type-badge">{info.badge}</span>
                </div>
                <button 
                  className={`toggle-switch ${state.profile[type] !== false ? '' : 'off'}`} 
                  onClick={() => handleToggle(type)}
                ></button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="section">
        <div className="section-label">This session</div>
        <div className="protected-banner">
          <div className="protected-count">{totalProtected}</div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--cf-accent)' }}>items protected</div>
            <div className="protected-label">across {Object.keys(state.counts).length ? '2' : '0'} messages</div>
          </div>
        </div>
        <div className="session-grid">
          {isEmptySession ? (
            <div style={{ gridColumn: '1/-1' }}>
              <p className="empty-state">Nothing masked yet this session</p>
            </div>
          ) : (
            Object.entries(state.counts).map(([type, count]) => {
              const badge = PII_LABELS[type]?.badge || type;
              return (
                <div className="session-card" key={type}>
                  <div className="session-card-type">{badge}</div>
                  <div className="session-card-count">{count}</div>
                  <div className="session-card-label">masked</div>
                </div>
              );
            })
          )}
        </div>
        <button className="clear-btn" onClick={clearVault}>Clear session vault</button>
      </div>

      <div className="footer">
        <div className="footer-row">
          <button 
            className="disable-btn" 
            onClick={() => setSiteDisabled(!siteDisabled)}
            style={{
              color: siteDisabled ? 'var(--cf-red)' : '',
              borderColor: siteDisabled ? 'rgba(239,68,68,0.3)' : ''
            }}
          >
            {siteDisabled ? 'Re-enable on this site' : 'Disable on this site'}
          </button>
          <div className="backend-row">
            <span className="backend-url">{state.backendUrl}</span>
            <button className="edit-btn" onClick={() => setEditingUrl(true)}>Edit</button>
          </div>
        </div>
        
        {editingUrl && (
          <div id="backend-edit" style={{ display: 'block', marginTop: '6px' }}>
            <input 
              type="text" 
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => { if(e.key === 'Enter') saveBackend(); }}
              style={{
                width: '100%', padding: '7px 10px', background: 'var(--cf-surface)', 
                border: '0.5px solid var(--cf-border)', borderRadius: '8px', 
                color: 'var(--cf-text)', fontSize: '13px', fontFamily: 'var(--font-mono)'
              }}
            />
            <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
              <button 
                onClick={saveBackend} 
                style={{ flex: 1, padding: '7px', background: 'var(--cf-accent)', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '13px', cursor: 'pointer' }}
              >
                Save
              </button>
              <button 
                onClick={() => setEditingUrl(false)} 
                style={{ flex: 1, padding: '7px', background: 'var(--cf-surface)', border: '0.5px solid var(--cf-border)', borderRadius: '8px', color: 'var(--cf-muted)', fontSize: '13px', cursor: 'pointer' }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const root = document.getElementById('root')!;
createRoot(root).render(<App />);