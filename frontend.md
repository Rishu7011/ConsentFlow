# ConsentFlow — Frontend Reference

> Next.js 16.2 · React 19 · TypeScript · Framer Motion · GSAP · Tailwind CSS v4 · shadcn/ui · Sonner

---

## Project Layout

```
consentflow-frontend/
├── app/
│   ├── layout.tsx             # Root layout — providers, global font
│   ├── page.tsx               # Main demo dashboard (single-page SPA)
│   ├── globals.css            # CSS custom properties (--cf-* tokens)
│   ├── favicon.ico
│   └── api/
│       ├── audit/route.ts     # Proxy → GET /audit/trail
│       ├── chat/route.ts      # Proxy → POST /chat/message
│       ├── consent/route.ts   # Proxy → POST /consent
│       ├── dashboard-stats/route.ts # Proxy → GET /dashboard/stats
│       ├── health/route.ts    # Proxy → GET /health
│       ├── infer/route.ts     # Proxy → POST /infer/predict
│       ├── policy/route.ts    # Proxy → POST /policy/scan
│       ├── users/route.ts     # Proxy → GET /users
│       └── webhook/route.ts   # Proxy → POST /webhook/consent-revoke
├── components/
│   ├── Sidebar.tsx            # Navigation sidebar (optional)
│   ├── providers.tsx          # TanStack Query + theme providers
│   └── demo/
│       ├── ChatPanel.tsx      # Center panel — chat messages + input
│       ├── MemoryPanel.tsx    # Left panel — RAG memory bank + freeze state
│       └── PipelinePanel.tsx  # Right panel — 8 animated pipeline gates
├── lib/
│   ├── axios.ts               # Axios instance (X-User-ID interceptor)
│   ├── constants.ts           # API base URL constant
│   ├── types.ts               # All TypeScript interfaces
│   └── utils.ts               # GATE_COLORS, PII_ICONS, timeAgo()
├── components/ui/             # shadcn/ui components (badge, button…)
├── public/                    # Static assets
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## Design System

All colors are defined as CSS custom properties in `app/globals.css`:

| Token | Value | Usage |
|-------|-------|-------|
| `--cf-bg` | `#0d0f17` | Page background (deep navy) |
| `--cf-surface` | `#151824` | Panel surfaces |
| `--cf-surface2` | `#1e2235` | Inner cards / chips |
| `--cf-border` | `rgba(255,255,255,0.07)` | Subtle borders |
| `--cf-text` | `#e8eaf6` | Primary text |
| `--cf-muted` | `#6b7280` | Secondary / timestamp text |
| `--cf-purple` | `#7c6dfa` | Brand / user messages |
| `--cf-teal` | `#3ecfb2` | Active / granted / healthy |
| `--cf-coral` | `#fa6d8a` | Revoked / frozen / danger |
| `--cf-amber` | `#f5a623` | Warning / drift flagged |

Typography: **Inter** (Google Fonts via Next.js font optimization)

---

## Main Page (`app/page.tsx`)

The entire demo lives in a single `"use client"` component: `DemoPage`.

### State

| State | Type | Description |
|-------|------|-------------|
| `demoUuid` | `string \| null` | Active user UUID (loaded from `GET /users`) |
| `frozen` | `boolean` | `true` when `consent_status === "revoked"` |
| `memoryState` | `MemoryState \| null` | Latest memory snapshot from polling |
| `messages` | `ChatMessage[]` | Chat history (user + AI pairs) |
| `input` | `string` | Chat input value |
| `sending` | `boolean` | Request in-flight guard |
| `revoking` | `boolean` | Revoke button loading state |
| `gateStates` | `GateStates` | Per-gate label strings |
| `auditEntries` | `AuditEntry[]` | Latest audit events for ticker |
| `typing` | `boolean` | AI typing indicator |

### Gate States

Two preset gate-state maps:

```ts
const DEFAULT_GATES = {
  training: "active", presidio: "active", dataset: "active",
  inference: "active", drift: "active", kafka: "connected",
  mlflow: "active", redis: "cached",
};

const FROZEN_GATES = {
  training: "frozen", presidio: "blocking", dataset: "scrubbed",
  inference: "blocked", drift: "flagged", kafka: "fired",
  mlflow: "quarantined", redis: "cleared",
};
```

### Polling

| Interval | Source | Action |
|----------|--------|--------|
| 2 seconds | `GET /chat/state/{demoUuid}` | Updates `memoryState`, `frozen`, `gateStates` |
| 3 seconds | `GET /audit?limit=6` | Updates `auditEntries` for the ticker |

Frozen state is derived **solely** from `consent_status === "revoked"` (not from the freeze log directly), ensuring correct UI state after a page refresh while revoked.

### Event Handlers

#### `handleSend`

1. Appends an optimistic user message to `messages`
2. `POST /chat/message` with `{user_id, message}`
3. On success: replaces optimistic with actual + appends AI reply
4. On error: removes optimistic, shows toast

#### `handleRevoke`

1. `POST /webhook` with `{userId, purpose:"model_training", consentStatus:"revoked"}`
2. Sets `frozen = true`
3. Runs **GSAP timeline cascade** (1.4 s total):
   - `0.0s` → training: "frozen"
   - `0.1s` → freezeMemoryPanel() GSAP border animation
   - `0.2s` → presidio: "blocking"
   - `0.4s` → dataset: "scrubbed"
   - `0.5s` → redis: "invalidating"
   - `0.6s` → kafka: "fired"
   - `0.7s` → redis: "cleared"
   - `0.8s` → inference: "blocked"
   - `1.0s` → mlflow: "quarantined"
   - `1.2s` → drift: "flagged"
   - `1.4s` → Sonner toast "✓ Kafka event fired ✓ Redis cleared ✓ 5 gates frozen"

#### `handleRestore`

1. `POST /consent` with `{user_id, data_type:"pii", purpose:"model_training", status:"granted"}`
2. Backend automatically clears `consent_freeze_log` (no separate API call needed)
3. Sets `frozen = false`, restores `DEFAULT_GATES`
4. GSAP border color reset on `.memory-panel`
5. Sonner toast "Memory un-frozen. You can continue chatting!"

**Note:** Chat history is preserved — `messages` state is NOT wiped on restore.

#### `handleReset`

1. `DELETE /chat/state/{demoUuid}` — wipes memory, chat_log, freeze_log, consent_records
2. Resets all local state to initial values

---

## Components

### `MemoryPanel.tsx`

Left panel — shows the user's RAG memory bank.

**Props:** `memoryState: MemoryState | null`, `frozen: boolean`

**Features:**
- **"FROZEN" stamp** — `AnimatePresence` spring animation (scale + fade) when `frozen=true`
- **Badge** — "🔴 FROZEN" or "🟢 LEARNING" with animated transition
- **Memory chips** — each fact rendered as a chip; opacity 0.45 when frozen
- **PII icon badges** — `PII_ICONS` and `PII_COLORS` from `lib/utils.ts` tag fact categories
- **Freeze count** — displays "N facts · frozen at M" when frozen
- **Border color** — `rgba(250,109,138,0.6)` when frozen (coral), CSS transition 500ms
- **PII shield row** — "Presidio: blocking all new PII" when frozen

CSS class `.memory-panel` is targeted by GSAP in `handleRevoke` for border animation.

---

### `ChatPanel.tsx`

Center panel — the chat interface.

**Props:** `messages`, `input`, `setInput`, `sending`, `typing`, `frozen`, `onSend`

**Features:**

**User messages (right-aligned, purple border):**
- When `consent_status === "revoked"` AND `message_redacted !== message`:
  - Escapes HTML (`&`, `<`, `>`) first (XSS protection)
  - Then highlights `<REDACTED>` tokens with `<mark>` (coral background, monospace)
- When PII detected:
  - Consent granted → "🔵 PII detected · stored"
  - Consent revoked → "🔴 PII blocked · ENTITY_TYPE, ..."

**AI messages (left-aligned, surface border):**
- "🟢 Memory updated" (trained) or "🔴 Memory blocked" (not trained)
- "N facts used (frozen)" when memory is frozen
- Timestamp via `timeAgo()`

**Typing indicator:** 3-dot bounce animation while AI is responding

**Input field:**
- Placeholder: "Message as Demo…" or "Demo is chatting (memory frozen)…"
- Enter key submits
- Disabled while `sending`

**Chat header:** Shows "Memory frozen" or "Online · learning" status dot + "🔴 CONSENT REVOKED" badge

---

### `PipelinePanel.tsx`

Right panel — animated pipeline gates status.

**Props:** `frozen: boolean`, `gateStates: GateStates`, `frozenAt: number | null`

**5 animated gate rows** (from `GATES` config):

| Gate | Icon | Active label | Frozen label |
|------|------|-------------|--------------|
| Training Gate | 🤖 | Learning | FROZEN |
| Presidio PII | 🛡 | Scanning | Blocking |
| Dataset Gate | 🗄 | Active | PII Scrubbed |
| Inference Gate | ⚡ | Allowed | Blocked 403 |
| Drift Monitor | 📊 | Monitoring | Flagged |

**3 infrastructure rows** (static):
- **Kafka** (📨) — "🟢 Connected" / "🔴 Event fired" + animated "consent.revoked published" text
- **MLflow** (🧪) — "🟢 Active" / "🔴 Quarantined"
- **Redis** (⚡) — "🟢 Cached" / "🔴 Cleared" with "invalidating…" intermediate state

Training Gate shows "frozen at N facts" sub-label when frozen.

Each badge transitions with Framer Motion `AnimatePresence mode="wait"` for smooth label swaps.

---

## TypeScript Types (`lib/types.ts`)

```ts
interface MemoryState {
  user_id: string;
  memories: string[];
  memory_count: number;
  frozen: boolean;
  frozen_at_count: number | null;
}

interface ChatMessage {
  id: string;
  event_time: string;
  user_id: string;           // "ai" for AI responses
  message: string;
  message_redacted: string;
  reply: string;
  trained: boolean;
  memory_used: string[];
  pii_detected: string[];
  consent_status: "granted" | "revoked";
}

interface ChatResponse {
  reply: string;
  trained_on_message: boolean;
  consent_status: string;
  pii_detected: string[];
  message_redacted: string;
  memories_used: string[];
  memory_state: MemoryState;
}

interface AuditEntry {
  id: string;
  event_time: string;
  user_id: string;
  gate_name: string;
  action_taken: string;
  consent_status: string;
  purpose: string | null;
  metadata: Record<string, unknown> | null;
  trace_id: string | null;
}

interface DashboardStats {
  users: number;
  granted: number;
  blocked: number;
  checks_24h_total: number;
  checks_24h_blocked: number;
  checks_sparkline: number[];
  policy_scans_total: number;
  policy_scans_critical: number;
}

interface PolicyFinding {
  id: string;
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  clause_excerpt: string;
  explanation: string;
  article_reference: string;
}

interface PolicyScanResult {
  scan_id: string;
  integration_name: string;
  overall_risk_level: "low" | "medium" | "high" | "critical";
  findings: PolicyFinding[];
  findings_count: number;
  raw_summary: string;
  scanned_at: string;
  policy_url?: string;
}
```

---

## Axios Client (`lib/axios.ts`)

```ts
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

// Request interceptor: attach active user ID header
api.interceptors.request.use((config) => {
  const userId = sessionStorage.getItem("active_user_id");
  if (userId) config.headers["X-User-ID"] = userId;
  return config;
});
```

The active user ID is stored in `sessionStorage` under `active_user_id` when the demo user is loaded. This ensures the `ConsentMiddleware` can identify the user for inference gate checks.

---

## Utility Functions (`lib/utils.ts`)

```ts
// Gate badge colors for audit ticker
export const GATE_COLORS: Record<string, string> = {
  training_gate: "#3ecfb2",
  policy_auditor: "#7c6dfa",
  // ...
};

// PII category icons for memory chips
export const PII_ICONS: Record<string, string> = {
  name: "👤", location: "📍", age: "🎂",
  salary: "💰", phone: "📱", medical: "🏥", ...
};

// PII category colors
export const PII_COLORS: Record<string, string> = { ... };

// Relative time formatting
export function timeAgo(isoString: string): string { ... }
```

---

## Dependencies

```json
{
  "next": "16.2.4",
  "react": "19.2.4",
  "framer-motion": "^12.38.0",
  "gsap": "^3.15.0",
  "@gsap/react": "^2.1.2",
  "axios": "^1.15.2",
  "@tanstack/react-query": "^5.100.6",
  "sonner": "^2.0.7",
  "lucide-react": "^1.14.0",
  "shadcn": "^4.6.0",
  "tailwindcss": "^4",
  "date-fns": "^4.1.0",
  "next-themes": "^0.4.6"
}
```

---

## Running Locally

```bash
cd consentflow-frontend

npm install

# Development server (hot reload)
npm run dev       # → http://localhost:3000

# Production build
npm run build
npm start

# Linting
npm run lint
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## Key Implementation Notes

1. **Freeze state source of truth** — `frozen` is set from `consent_status === "revoked"` (from polling `GET /chat/state`), NOT from the freeze log field. This ensures page-refresh correctness.

2. **XSS protection in redacted messages** — Raw HTML is escaped (`&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`) before `<REDACTED>` tokens are replaced with `<mark>` elements. Never inserts unsanitized user content into `dangerouslySetInnerHTML`.

3. **Chat history preserved on restore** — `handleRestore` does not wipe `messages` state. Only `handleReset` (DELETE endpoint) clears the chat.

4. **Gate animation uses GSAP timeline** — `gsap.timeline()` with `.call()` steps provides precise timing for the cascading freeze effect. Gate state updates are React state changes triggered by GSAP callbacks.

5. **Optimistic UI** — Chat messages are added immediately on send with a provisional `trained=false` / `consent_status` state, then replaced with the real server response.

6. **Memory polling** — `GET /chat/state/{user_id}` is polled every 2 seconds. The memory state updates after every message in the main `handleSend` flow as well (from `data.memory_state`).
