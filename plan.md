# ConsentFlow Privacy Shield — Extension Build Plan
### Using the Existing ConsentFlow Backend

---

## What We Already Have (Don't Rebuild)

The `consentflow-backend` is already running FastAPI with these pieces we plug straight into:

| Already Built | File | What It Does |
|---|---|---|
| PII detection | `consentflow/anonymizer.py` | `anonymize_record()`, `_anonymize_value()`, `_anonymize_text()` — Presidio-powered |
| Consent SDK | `consentflow/sdk.py` | `is_user_consented()` — Redis + Postgres check |
| Consent cache | `consentflow/app/cache.py` | `get_consent_cache()`, `set_consent_cache()`, `invalidate_consent_cache()` |
| Audit log | `consentflow/app/routers/audit.py` | `GET /audit/trail` — already logs events |
| Consent CRUD | `consentflow/app/routers/consent.py` | `POST /consent`, `GET /consent/{user_id}/{purpose}` |
| App entry | `consentflow/app/main.py` | FastAPI lifespan, Postgres pool, Redis, Kafka producer |
| Models | `consentflow/app/models.py` | `ConsentStatus`, `ConsentRecord`, `AuditLogEntry` |
| Webhook | `consentflow/app/routers/webhook.py` | `receive_consent_revoke()` — already handles revocation |

**We only need to add 2 new routes to the existing backend.** Everything else is already there.

---

## Two New Backend Routes to Add

### Route 1 — `POST /api/v1/extension/anonymize`

Add to `consentflow/app/routers/extension.py` (new file):

```python
from consentflow.anonymizer import _anonymize_text   # already exists
from consentflow.app.cache import get_consent_cache   # already exists

@router.post("/api/v1/extension/anonymize")
async def anonymize_for_extension(request: ExtensionAnonymizeRequest):
    """
    Extension sends raw user text.
    We detect PII, replace with dummy values, return both.
    Mappings stored in session — never persisted with real PII.
    """
    anonymized, mappings = _anonymize_text(request.text, request.entities)
    return {
        "anonymized_text": anonymized,
        "mappings": mappings,          # [{ original, dummy, type }]
        "session_id": request.session_id
    }
```

### Route 2 — `GET /api/v1/extension/consent-profile`

```python
@router.get("/api/v1/extension/consent-profile")
async def get_extension_consent_profile(user_id: str):
    """
    Returns which PII types the user has toggled on/off.
    Uses existing consent cache + SDK — no new logic.
    """
    profile = await get_consent_cache(user_id, purpose="extension_pii_masking")
    return profile or DEFAULT_PII_PROFILE
```

**That's it for backend work.** Register `extension.py` in `main.py` and done.

---

## Extension Architecture

```
consentflow-extension/
├── manifest.json                  # Chrome Manifest V3
├── src/
│   ├── content/
│   │   ├── index.ts               # Injected into chatbot pages
│   │   ├── interceptor.ts         # Captures textarea before send
│   │   ├── reverseMapper.ts       # Swaps dummy → real in AI response stream
│   │   └── platforms/
│   │       ├── chatgpt.ts         # ChatGPT DOM selectors
│   │       └── claude.ts          # Claude.ai DOM selectors
│   ├── background/
│   │   └── serviceWorker.ts       # Calls backend /anonymize + coordinates vault
│   ├── popup/
│   │   ├── App.tsx                # React popup UI
│   │   └── index.html
│   ├── vault/
│   │   └── vault.ts               # AES-256-GCM IndexedDB (session-scoped)
│   └── utils/
│       └── dummyGenerator.ts      # Fallback regex-based masking (offline mode)
├── package.json
└── tsconfig.json
```

---

## How the Extension Talks to the Existing Backend

```
User types message in ChatGPT
          ↓
interceptor.ts captures text (before submit fires)
          ↓
serviceWorker.ts → POST /api/v1/extension/anonymize
          ↓
Backend runs _anonymize_text() — already in anonymizer.py
          ↓
Returns { anonymized_text, mappings }
          ↓
vault.ts stores mappings (AES-256, IndexedDB, session only)
          ↓
interceptor.ts replaces textarea value with anonymized_text
          ↓
User hits send → AI only ever sees dummy data
          ↓
AI streams response back
          ↓
reverseMapper.ts watches DOM mutations on response container
          ↓
Looks up each dummy token in vault → replaces with real value
          ↓
User sees their real name/number in the response
```

---

## Platform DOM Targets

The interceptor needs to know where to hook into each chatbot's UI.

### ChatGPT (`chat.openai.com`)

```typescript
// src/content/platforms/chatgpt.ts
export const CHATGPT = {
  inputSelector:    '#prompt-textarea',
  sendButton:       '[data-testid="send-button"]',
  responseContainer: '[data-message-author-role="assistant"]',
  streamingClass:   'result-streaming',
};
```

### Claude.ai (`claude.ai`)

```typescript
// src/content/platforms/claude.ts
export const CLAUDE = {
  inputSelector:    '[contenteditable="true"].ProseMirror',
  sendButton:       '[aria-label="Send message"]',
  responseContainer: '[data-is-streaming]',
  streamingClass:   'streaming',
};
```

> **Note:** Claude uses a `contenteditable` div, not a `<textarea>`. The interceptor
> needs to read `innerText` and dispatch a synthetic `input` event after replacement.

---

## The Streaming Response Problem (Solved)

AI responses stream token by token. A naive `textContent` replace after the full
response arrives is too late — the user sees the dummy value flash on screen.

**Solution:** Use `MutationObserver` on the response container and replace tokens as
they arrive, chunk by chunk.

```typescript
// src/content/reverseMapper.ts
export function watchAndReplace(container: Element, vault: Vault) {
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === 'characterData' || m.addedNodes.length) {
        replaceInNode(m.target, vault);
      }
    }
  });

  observer.observe(container, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  return observer;
}

function replaceInNode(node: Node, vault: Vault) {
  const mappings = vault.getMappings();          // sorted longest-first to avoid partial matches
  let text = node.textContent || '';
  for (const { dummy, original } of mappings) {
    text = text.replaceAll(dummy, original);
  }
  if (text !== node.textContent) {
    node.textContent = text;
  }
}
```

---

## Local Vault Design

Real PII never goes to the server. The mapping lives entirely in the browser.

```typescript
// src/vault/vault.ts
interface VaultEntry {
  sessionId:  string;
  original:   string;   // Real value — AES-256-GCM encrypted at rest
  dummy:      string;   // Fake value — plaintext (safe to store)
  entityType: string;   // PERSON | PHONE_NUMBER | IN_AADHAAR | EMAIL | etc.
  createdAt:  number;
  expiresAt:  number;   // Tab close = auto-wipe
}

// Key derived from user PIN via PBKDF2 — never stored, never sent
const key = await crypto.subtle.deriveKey(
  { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
  pinKey,
  { name: 'AES-GCM', length: 256 },
  false,
  ['encrypt', 'decrypt']
);
```

---

## Popup UI Features

```
┌─────────────────────────────┐
│  🛡 ConsentFlow Shield       │
│  5 items protected           │
├─────────────────────────────┤
│  PII Masking                 │
│  ✅ Full name    ✅ Phone    │
│  ✅ Aadhaar      ✅ Email   │
│  ✅ Address      ✅ PAN     │
│  ✅ Date of birth            │
├─────────────────────────────┤
│  This session                │
│  Rohan Sharma → Alex Smith  │
│  9876543210   → 1234567890  │
│  [Clear session vault]       │
├─────────────────────────────┤
│  [Disable on this site]      │
└─────────────────────────────┘
```

Consent toggles call `PUT /api/v1/consent` on the existing backend using the
already-built `ConsentStatus` model — no new API work needed.

---

## Offline Fallback (No Backend)

If the backend is unreachable, the extension falls back to regex-based masking
entirely in the browser — no PII ever sent anywhere.

```typescript
// src/utils/dummyGenerator.ts
const PATTERNS = [
  { type: 'IN_AADHAAR',    regex: /\b\d{4}\s\d{4}\s\d{4}\b/g,    dummy: () => 'XXXX XXXX XXXX' },
  { type: 'IN_PAN',        regex: /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g,  dummy: () => 'AAAAA0000A'     },
  { type: 'PHONE_NUMBER',  regex: /\b[6-9]\d{9}\b/g,              dummy: () => '9000000000'     },
  { type: 'UPI_ID',        regex: /\b[\w.\-]+@[\w]+\b/g,          dummy: () => 'user@upi'       },
  { type: 'EMAIL_ADDRESS', regex: /[\w.+-]+@[\w-]+\.[a-z]{2,}/gi, dummy: () => 'user@example.com'},
];
```

Presidio on the backend handles complex cases (names, addresses, context-aware
detection). Regex handles the structured Indian PII formats that patterns cover
reliably without NLP.

---

## npm Setup

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "idb": "^7.1.1",
    "webextension-polyfill": "^0.10.0",
    "tailwindcss": "^3.4.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "@crxjs/vite-plugin": "^2.0.0",
    "@types/chrome": "^0.0.268",
    "@types/react": "^18.3.0",
    "vitest": "^1.5.0",
    "@playwright/test": "^1.44.0"
  }
}
```

---

## Backend Changes Needed (Minimal)

### 1. Add `extension.py` router

```
consentflow-backend/
└── consentflow/
    └── app/
        └── routers/
            └── extension.py      ← NEW (2 routes only)
```

### 2. Register in `main.py` (1 line change)

```python
# consentflow/app/main.py — already has this pattern for other routers
from consentflow.app.routers import extension
app.include_router(extension.router)
```

### 3. Add `ExtensionAnonymizeRequest` to `models.py`

```python
# consentflow/app/models.py — add alongside existing models
class ExtensionAnonymizeRequest(BaseModel):
    text:       str
    session_id: str
    entities:   list[str] = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
                              "IN_AADHAAR", "IN_PAN", "IN_PHONE", "IN_UPI"]
```

### 4. Expose `_anonymize_text` from `anonymizer.py`

The function already exists — just needs the return signature updated to also
return the mappings list alongside the anonymized string.

---

## Build Milestones

| Week | Goal | Uses Existing Backend? |
|------|------|------------------------|
| 1 | Manifest V3 scaffold + ChatGPT DOM hook | No (pure extension) |
| 1 | `interceptor.ts` captures textarea before send | No |
| 2 | Add `extension.py` router — `/anonymize` endpoint | `anonymizer.py` ✅ |
| 2 | `vault.ts` — AES-256 IndexedDB session store | No |
| 3 | `reverseMapper.ts` — MutationObserver streaming fix | No |
| 3 | Claude.ai contenteditable support | No |
| 4 | Popup UI — React toggles wired to `PUT /consent` | `consent.py` ✅ |
| 4 | Popup audit log view | `audit.py` ✅ |
| 5 | Indian PII regex fallback (offline mode) | No |
| 5 | Demo polish — end-to-end flow for judges | Both |

---

## Demo Script for Judges

1. Open **ChatGPT** with extension installed
2. Type: *"My name is Rohan Sharma, Aadhaar 1234 5678 9012, phone 9876543210"*
3. Show extension popup → **3 PII items detected and masked**
4. Open DevTools → Network → find the ChatGPT request body → **only dummy data visible**
5. ChatGPT responds using dummy values naturally
6. Show user screen → **real values swapped back** in the response
7. Open ConsentFlow audit log at `/audit/trail` → **zero real PII in logs**
8. Toggle off "Phone masking" in popup → type again → phone goes through unmasked
9. Toggle back on → privacy restored

**Judge takeaway:** The AI worked perfectly. It never knew who Rohan actually was.
And we didn't build a new backend — we extended an existing consent infrastructure.

---

## Privacy Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| Real PII never reaches the AI | Masked before HTTP request leaves browser |
| Real PII never reaches our backend | Only anonymized text sent to `/anonymize` |
| Vault is local-only | IndexedDB, AES-256-GCM, session-scoped |
| Audit logs contain zero real PII | Existing `audit.py` logs entity type + timestamp only |
| Consent toggles respected | Existing `consent.py` + `cache.py` + `sdk.py` |
| Offline mode available | Regex fallback runs 100% in browser |