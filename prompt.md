# ConsentFlow Privacy Shield — Agent Build Prompts

Each prompt is a self-contained instruction to a coding agent.
Run them in order. Each step builds on the output of the previous one.

---

## Step 1 — Scaffold the Extension

```
You are building a Chrome extension called "ConsentFlow Privacy Shield".

Create the project scaffold at `consentflow-extension/` with the following:

1. `manifest.json` — Chrome Manifest V3 with:
   - name: "ConsentFlow Privacy Shield"
   - version: "1.0.0"
   - description: "Masks your PII before it reaches any AI chatbot."
   - permissions: ["storage", "activeTab", "scripting"]
   - host_permissions: ["https://chat.openai.com/*", "https://claude.ai/*"]
   - background service_worker pointing to "dist/serviceWorker.js"
   - content_scripts injecting "dist/content/index.js" on both host URLs at document_idle
   - action popup pointing to "popup/index.html"
   - icons at 16, 48, 128 all pointing to "icons/shield.png"

2. `package.json` with these exact dependencies:
   - react ^18.3.0, react-dom ^18.3.0
   - idb ^7.1.1
   - webextension-polyfill ^0.10.0
   - tailwindcss ^3.4.0, clsx ^2.1.0
   And devDependencies:
   - typescript ^5.4.0, vite ^5.2.0, @crxjs/vite-plugin ^2.0.0
   - @types/chrome ^0.0.268, @types/react ^18.3.0
   - vitest ^1.5.0, @playwright/test ^1.44.0
   Scripts: "dev", "build", "test"

3. `tsconfig.json` — strict TypeScript, target ES2020, module ESNext,
   JSX react-jsx, include src/**/*.ts and src/**/*.tsx

4. `vite.config.ts` — configure @crxjs/vite-plugin with the manifest,
   build output to dist/

5. Empty placeholder files (just a TODO comment each) for every file in
   this tree so the full structure is visible:
   src/content/index.ts
   src/content/interceptor.ts
   src/content/reverseMapper.ts
   src/content/platforms/chatgpt.ts
   src/content/platforms/claude.ts
   src/content/platforms/index.ts
   src/background/serviceWorker.ts
   src/popup/App.tsx
   src/popup/index.html
   src/vault/vault.ts
   src/utils/dummyGenerator.ts

After creating all files, print the full directory tree. Do not implement
any logic yet — placeholders only.
```

---

## Step 2 — PII Detection and Placeholder Substitution (`dummyGenerator.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.
The project scaffold already exists at consentflow-extension/.

Implement `src/utils/dummyGenerator.ts` in full.

Export one function:

  detectAndReplace(text: string, mode: 'placeholder' | 'direct', enabledTypes?: string[])
  : { anonymized: string, mappings: Array<{ original: string; placeholder: string; dummy: string; type: string }> }

  - 'placeholder' mode: replaces each PII value with a token like [PERSON_1].
    dummy field in the mapping is '' — filled in after backend responds.
    These tokens are what get sent to the backend (never real values).
  - 'direct' mode: replaces each PII value immediately with a local dummy.
    Used for offline fallback — no backend call needed.
  - enabledTypes: if provided, skip any type not in this list.

Counter must be global across all types within a single call so tokens are
unique: [IN_AADHAAR_1], [PHONE_NUMBER_2] — not [IN_AADHAAR_1], [PHONE_NUMBER_1].

Apply patterns in this exact order (ordering prevents partial matches):
  1. EMAIL_ADDRESS  /[\w.+-]+@[\w-]+\.[a-z]{2,}/gi       dummy: 'user@example.com'
  2. IN_AADHAAR     /\b\d{4}\s\d{4}\s\d{4}\b/g           dummy: 'XXXX XXXX XXXX'
  3. IN_PAN         /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g         dummy: 'AAAAA0000A'
  4. PHONE_NUMBER   /\b[6-9]\d{9}\b/g                    dummy: '9000000000'
  5. UPI_ID         /\b[\w.\-]+@[\w]+\b/g                dummy: 'user@upi'

Export also: SUPPORTED_TYPES string[] — all five type names in the order above.

Write unit tests in `src/utils/dummyGenerator.test.ts` using vitest covering:
- placeholder mode: anonymized string has no original values
- direct mode: anonymized string has dummy values, not originals
- counter is global across types (e.g. second match regardless of type gets _2)
- EMAIL is matched before UPI_ID for an address like foo@gmail.com
- enabledTypes filter skips disabled types
```

---

## Step 3 — In-Memory Vault (`vault.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/vault/vault.ts` in full.

HARD RULE: Real PII must NEVER be written to IndexedDB. The dummy→real map
lives only in a JavaScript Map in RAM. Tab close wipes it automatically.
IndexedDB is used ONLY for non-sensitive metadata (counts, timestamps).

Part 1 — In-memory reverse map, exported as `vault`:

  vault.store(dummy: string, original: string): void
  vault.applyTo(text: string): string
    — replaces all dummy tokens in text with their originals
    — mappings sorted longest-first to prevent partial replacement bugs
  vault.clear(): void
  vault.count(): number
  vault.getMappings(): Array<{ dummy: string; original: string }>
    — sorted longest-first

Part 2 — IndexedDB metadata, exported as `metaStore`:

  Database: "consentflow-meta" v1, object store "sessions", keyPath "sessionId"

  Interface VaultMetaEntry {
    sessionId: string
    counts: Record<string, number>   // e.g. { PERSON: 2, PHONE_NUMBER: 1 }
    lastUpdatedAt: number
  }

  metaStore.upsertCounts(sessionId: string, type: string, increment: number): Promise<void>
    — merge-upsert: add increment to existing count for that type
  metaStore.getCounts(sessionId: string): Promise<Record<string, number>>
  metaStore.clearSession(sessionId: string): Promise<void>

Use the `idb` package (already in package.json) for IndexedDB access.

Write unit tests in `src/vault/vault.test.ts` using vitest:
- store and applyTo work correctly
- applyTo uses longest-first order
- clear empties the map
- metaStore upsert accumulates counts
- metaStore clearSession removes the entry
```

---

## Step 4 — Platform DOM Selectors

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement three platform files.

--- src/content/platforms/chatgpt.ts ---

Export const CHATGPT:
  inputSelector:     '#prompt-textarea'
  sendButton:        '[data-testid="send-button"]'
  responseContainer: '[data-message-author-role="assistant"]'
  streamingClass:    'result-streaming'
  inputType:         'textarea' as const

Export helpers (works for textarea):
  getInputText(el: HTMLElement): string   — reads el.value
  setInputText(el: HTMLElement, text: string): void
    — sets el.value and dispatches a native 'input' Event

--- src/content/platforms/claude.ts ---

Export const CLAUDE:
  inputSelector:     '[contenteditable="true"].ProseMirror'
  sendButton:        '[aria-label="Send message"]'
  responseContainer: '[data-is-streaming]'
  streamingClass:    'streaming'
  inputType:         'contenteditable' as const

Export helpers (works for contenteditable):
  getInputText(el: HTMLElement): string   — reads el.innerText
  setInputText(el: HTMLElement, text: string): void
    — sets el.innerText and dispatches a synthetic 'input' Event

--- src/content/platforms/index.ts ---

Export a shared PlatformConfig type that both CHATGPT and CLAUDE satisfy.

Export:
  detectPlatform(): 'chatgpt' | 'claude' | null
    — 'chatgpt' if location.hostname includes 'chat.openai.com'
    — 'claude'  if location.hostname includes 'claude.ai'
    — null otherwise

  getPlatformConfig(): PlatformConfig | null
    — returns CHATGPT or CLAUDE based on detectPlatform(), or null
```

---

## Step 5 — Interceptor (`interceptor.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/content/interceptor.ts` in full.

This module intercepts the user's message before it is sent to the AI.

Export:

  attachInterceptor(
    config: PlatformConfig,
    onMasked: (count: number, sessionId: string) => void
  ): Promise<() => void>   — returns cleanup function

Behavior:

1. Poll for the send button every 300ms (max 10s) using MutationObserver +
   document.querySelector. Reject if not found after 10s.

2. Attach a capture-phase 'click' listener on the send button.
   IMPORTANT: never call preventDefault or stopPropagation.

3. On click:
   a. Read input text with getInputText from the platform config.
   b. Call detectAndReplace(text, 'placeholder', activeEnabledTypes).
   c. If mappings.length === 0, do nothing and return.
   d. Generate sessionId = crypto.randomUUID() if not already set this page load.
   e. Send to service worker: { type: 'ANONYMIZE', entityRefs: mappings.map(m => m.placeholder), sessionId }
   f. On response { ok: true, dummies }:
      - For each mapping, call vault.store(dummies[mapping.placeholder], mapping.original)
      - Replace each placeholder in the anonymized string with its dummy
      - Call setInputText with the final anonymized text
      - Update metaStore counts per entity type
      - Call onMasked(mappings.length, sessionId)
   g. On response { ok: false } or timeout (>3s):
      - Offline fallback: call detectAndReplace(text, 'direct', activeEnabledTypes)
      - vault.store each mapping's dummy → original
      - setInputText with the direct-anonymized text
      - console.warn('[ConsentFlow] Backend unreachable — using offline fallback')

4. Listen for chrome.runtime.onMessage type 'CONSENT_UPDATED':
   { type: string, enabled: boolean } — update the local activeEnabledTypes set.

5. Listen for chrome.runtime.onMessage type 'CLEAR_VAULT':
   Call vault.clear().

6. Cleanup function removes all listeners and stops all MutationObservers.
```

---

## Step 6 — Reverse Mapper (`reverseMapper.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/content/reverseMapper.ts` in full.

This module watches the AI's streaming response and swaps dummy values back to
real values as tokens arrive in the DOM.

Export:

  attachReverseMapper(config: PlatformConfig, sessionId: string): () => void

Behavior:

1. Watch document.body with a MutationObserver to detect when the response
   container (config.responseContainer) appears. Once found, begin observing it.

2. Observe the container: { childList: true, subtree: true, characterData: true }

3. On each mutation:
   - For characterData mutations: call replaceInNode(mutation.target)
   - For childList mutations: walk all added nodes, call replaceInNode on each
     TEXT_NODE descendant

4. replaceInNode(node: Node):
   - Skip non-TEXT_NODE nodes
   - newText = vault.applyTo(node.textContent ?? '')
   - Only assign node.textContent = newText if it differs (avoid mutation loops)

5. After streaming ends (config.streamingClass disappears from the container):
   - Do one final pass over all text nodes in the container
   - Use a MutationObserver watching attributes to detect the class change

6. Cleanup: disconnect all MutationObservers.

Write unit tests in `src/content/reverseMapper.test.ts` using vitest + jsdom:
- replaces a dummy token in a text node
- ignores a node with no dummies (no textContent reassignment)
- longest-first ordering: "Alex Smith" replaced before "Alex"
- final pass fires after streaming class is removed from container
```

---

## Step 7 — Service Worker (`serviceWorker.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/background/serviceWorker.ts` in full.

This is the Manifest V3 service worker. It relays messages between content
scripts and the ConsentFlow backend.

Read backend base URL from chrome.storage.local key 'backendUrl',
default to 'http://localhost:8000'.

Handle these message types via chrome.runtime.onMessage (return true for async):

ANONYMIZE
  Payload: { type: 'ANONYMIZE', entityRefs: string[], sessionId: string }
  Action: POST {backendUrl}/api/v1/extension/anonymize
  Body: { entity_refs: entityRefs, session_id: sessionId }
  Timeout: 3000ms via AbortController
  Success: return { ok: true, dummies: data.dummies }
  Failure/timeout: return { ok: false, error: string }

GET_CONSENT_PROFILE
  Payload: { type: 'GET_CONSENT_PROFILE', userId: string }
  Action: GET {backendUrl}/api/v1/extension/consent-profile?user_id={userId}
  Success: return { ok: true, profile: data }
  Failure: return { ok: true, profile: DEFAULT_PII_PROFILE }
  DEFAULT_PII_PROFILE = { PERSON: true, PHONE_NUMBER: true, EMAIL_ADDRESS: true,
                           IN_AADHAAR: true, IN_PAN: true, UPI_ID: true }

UPDATE_CONSENT
  Payload: { type: 'UPDATE_CONSENT', userId: string, entityType: string, enabled: boolean }
  Action: PUT {backendUrl}/api/v1/consent
  Body: { user_id, purpose: 'extension_pii_masking',
          status: enabled ? 'granted' : 'revoked', entity_type: entityType }
  Return { ok: true } or { ok: false, error }

UPDATE_BADGE
  Payload: { type: 'UPDATE_BADGE', count: number }
  Action: chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' })
          chrome.action.setBadgeBackgroundColor({ color: '#6366f1' })
  Return { ok: true }

SET_BACKEND_URL
  Payload: { type: 'SET_BACKEND_URL', url: string }
  Action: chrome.storage.local.set({ backendUrl: url })
  Return { ok: true }
```

---

## Step 8 — Content Entry Point (`index.ts`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/content/index.ts` in full.

This is the content script entry point. Keep it thin — delegate to modules.

1. Detect platform. If null, log '[ConsentFlow] Unknown platform' and exit.

2. Generate sessionId = crypto.randomUUID() for this page load.

3. Fetch consent profile:
   chrome.runtime.sendMessage({ type: 'GET_CONSENT_PROFILE', userId: 'local' })
   Store the profile's enabled types as a Set<string> named activeEnabledTypes.
   Pass it when calling detectAndReplace (via interceptor).

4. attachInterceptor(config, (count, sid) => {
     attachReverseMapper(config, sid)
     chrome.runtime.sendMessage({ type: 'UPDATE_BADGE', count })
   })

5. Watch for SPA navigation (URL changes without page reload):
   Use a MutationObserver on document.body or a popstate listener.
   When the URL changes, re-run step 4 (debounced 500ms) so the interceptor
   re-attaches after the new page's send button is mounted.

6. Listen for message 'CONSENT_UPDATED' from popup:
   Update activeEnabledTypes. Forward to interceptor via its own message listener
   (interceptor already handles this — just ensure the message reaches it).
```

---

## Step 9 — Popup UI (`App.tsx` + `index.html`)

```
You are continuing work on the ConsentFlow Privacy Shield Chrome extension.

Implement `src/popup/App.tsx` and `src/popup/index.html`.

--- index.html ---
Standard HTML5. Mount React at #root. Include Tailwind via CDN.
Script tag for App.tsx (Vite resolves it).

--- App.tsx ---
React functional component. Popup is 360px wide, dark theme (#0f172a bg, #6366f1 accent).

Sections:

HEADER
  Shield emoji + "ConsentFlow Shield" title
  Subtitle: "{N} items protected this session" (N from vault.count via message)

PII TOGGLE SECTION  (label | toggle switch for each)
  Full name (PERSON), Phone (PHONE_NUMBER), Aadhaar (IN_AADHAAR),
  Email (EMAIL_ADDRESS), PAN (IN_PAN), UPI ID (UPI_ID)

SESSION LOG SECTION
  List: "{TYPE} — {count} masked" for each type with count > 0
  Empty state: "Nothing masked yet this session"
  "Clear session vault" button → sends CLEAR_VAULT to active tab content script
  + calls metaStore.clearSession(sessionId)

FOOTER
  "Disable on this site" / "Re-enable on this site" toggle button
    → reads current tab hostname, adds/removes from chrome.storage.local 'disabledSites'
  Backend URL display + [Edit] inline input
    → on save sends SET_BACKEND_URL to service worker
  Status dot: green "Backend online" / red "Backend offline"
    → determined by whether GET_CONSENT_PROFILE returns ok: true

State on mount:
  - Read sessionId from chrome.storage.session key 'currentSessionId'
  - Load counts: chrome.runtime.sendMessage GET_CONSENT_PROFILE to check online status
  - Load counts from metaStore.getCounts(sessionId) for session display
  - Load consent profile to populate toggle initial state
  - Load 'disabledSites' from chrome.storage.local for site toggle state

On toggle change:
  - chrome.runtime.sendMessage UPDATE_CONSENT
  - chrome.tabs.sendMessage to active tab: { type: 'CONSENT_UPDATED', entityType, enabled }

Use Tailwind utility classes only. No separate CSS file.
```

---

## Step 10 — Backend: New Router (`extension.py`)

```
You are adding one new file to the existing ConsentFlow FastAPI backend.
Do NOT touch any other backend file in this step.

Create `consentflow/app/routers/extension.py`.

This router never receives, logs, or stores real PII. It only processes
entity-type placeholder tokens like "[PERSON_1]".

Imports from existing codebase (already available, do not rewrite):
  from consentflow.app.cache import get_consent_cache
  from consentflow.app.models import ExtensionAnonymizePlaceholderRequest

Private helper: _generate_dummy(entity_ref: str) -> str
  Extract entity type from the placeholder (e.g. "[PERSON_1]" → "PERSON")
  Return a random realistic dummy per type:
    PERSON        → random.choice(["Alex Smith", "Jordan Lee", "Sam Taylor",
                      "Morgan Davis", "Casey Brown", "Riley Wilson"])
    PHONE_NUMBER  → "9" + f"{random.randint(100000000, 999999999)}"
    IN_AADHAAR    → f"{random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
    IN_PAN        → 5 random uppercase letters + 4 random digits + 1 random uppercase letter
    EMAIL_ADDRESS → f"user{random.randint(1000,9999)}@example.com"
    UPI_ID        → f"user{random.randint(1000,9999)}@okaxis"
    Default       → f"DUMMY_{entity_ref}"

DEFAULT_PII_PROFILE = {
  "PERSON": True, "PHONE_NUMBER": True, "EMAIL_ADDRESS": True,
  "IN_AADHAAR": True, "IN_PAN": True, "UPI_ID": True
}

POST /api/v1/extension/anonymize
  Request: ExtensionAnonymizePlaceholderRequest
  Response: { dummies: { "[PERSON_1]": "Alex Smith", ... }, session_id: str }
  Log at INFO: number of placeholders and session_id (not the refs themselves)

GET /api/v1/extension/consent-profile
  Query param: user_id: str
  Response: await get_consent_cache(user_id, purpose="extension_pii_masking")
            or DEFAULT_PII_PROFILE if cache returns None

Router setup:
  router = APIRouter(prefix="/api/v1/extension", tags=["extension"])
  Add CORSMiddleware-compatible headers to responses (allow chrome-extension://* origins)
  via a response header dependency or middleware on just this router.
```

---

## Step 11 — Backend: Wire Up the New Router

```
You are making the final two small backend changes. Do not change anything else.

Change 1 — `consentflow/app/models.py`
Add this class at the very bottom of the file, after all existing models:

  class ExtensionAnonymizePlaceholderRequest(BaseModel):
      """
      Sent by the browser extension. entity_refs are placeholder tokens
      like "[PERSON_1]" — NOT real PII values.
      """
      entity_refs: list[str]
      session_id:  str

Change 2 — `consentflow/app/main.py`
In the block where other routers are registered with app.include_router(), add:

  from consentflow.app.routers import extension
  app.include_router(extension.router)

Do not change any other line in either file.

After both changes, print a diff-style summary showing exactly which lines
were added and at what line numbers.
```

---

## Step 12 — Integration Audit + README

```
You are doing the final integration pass on the ConsentFlow Privacy Shield project.

Task 1 — Cross-file consistency audit. Check and fix any mismatches:

  Message types: verify every type string sent by a file is handled in its receiver
    ANONYMIZE            interceptor.ts → serviceWorker.ts
    GET_CONSENT_PROFILE  index.ts + App.tsx → serviceWorker.ts
    UPDATE_CONSENT       App.tsx → serviceWorker.ts
    CONSENT_UPDATED      App.tsx → index.ts (content script)
    CLEAR_VAULT          App.tsx → index.ts (content script)
    UPDATE_BADGE         index.ts → serviceWorker.ts
    SET_BACKEND_URL      App.tsx → serviceWorker.ts

  Vault usage: vault.store / vault.applyTo / vault.getMappings called correctly
    by interceptor.ts and reverseMapper.ts

  SUPPORTED_TYPES in dummyGenerator.ts matches entity types handled by
    _generate_dummy in extension.py

  PlatformConfig type used consistently across platforms/index.ts,
    interceptor.ts, and reverseMapper.ts

List every fix applied. If nothing needs fixing, say so explicitly.

Task 2 — Write `consentflow-extension/README.md` (max 60 lines):
  - What it does (2 sentences)
  - Privacy guarantees (bullet list, plain English)
  - Dev setup: npm install → npm run build → load dist/ in chrome://extensions
  - How to configure the backend URL in the popup
  - How to run tests: npm test
  - Which backend files to add/modify and where
  - Offline mode behaviour
```
