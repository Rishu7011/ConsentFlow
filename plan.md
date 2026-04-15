# ConsentFlow — Complete Rebuild Plan
> RAG + Gemini + Presidio PII + Kafka + MLflow + OTel + Grafana

---

## The Core Demo Story

Rishabh chats with a real AI assistant (Gemini 2.0 Flash).
Every message is scanned for PII by Microsoft Presidio, then stored as memory chunks (RAG).
Gemini answers by retrieving those memories — it responds FROM his actual data.

After consent is revoked:
- New messages are NOT stored in memory
- New PII (like his new name "rishu") is detected and shown as `<REDACTED>`
- Kafka publishes `consent.revoked` event — visible on screen
- MLflow run is quarantined — visible on screen
- Gemini still responds — but only from the frozen pre-revocation memories

```
BEFORE REVOCATION:
  Rishabh: "hii my name is rishabh call me rishabh"
           → Presidio: detects "rishabh" = PERSON entity ✅
           → Memory stored: "User's name is Rishabh"

  Rishabh: "i like to do calisthenics"
           → Memory stored: "User likes calisthenics"

  AI: "Hey Rishabh! That's awesome you're into calisthenics!"
      ← knows his name, knows his hobby ✅

[ 🚨 REVOKE CONSENT ]
  → Postgres updated
  → Redis cache invalidated
  → Kafka: consent.revoked published → training_gate consumed
  → MLflow Run #42 → QUARANTINED
  → Memory store: FROZEN at 2 facts

AFTER REVOCATION:
  Rishabh: "now call me rishu"
           → Presidio: detects "rishu" = PERSON entity 🔴
           → Consent revoked → NOT stored
           → Shown in chat as: "now call me <REDACTED>"

  Rishabh: "i like to do gym"
           → Consent revoked → NOT stored

  Rishabh: "what do i like to do?"
           → Retrieves frozen memory: "User likes calisthenics"
  AI: "You like calisthenics!"
      ← still thinks calisthenics. Gym never learned.
      ← still calls him Rishabh. Rishu never learned. 😱
```

**The AI is not broken. It's doing exactly what GDPR requires.
It cannot know who he is now. It only knows who he WAS.**

---

## Full Tech Stack Being Shown to Judges

| Technology | What judges see |
|---|---|
| **Gemini 2.0 Flash** | Real AI responses in the chat |
| **Microsoft Presidio** | PII detected live, shown as `<REDACTED>` after revocation |
| **RAG (Postgres)** | Memory chips building up in real time, frozen after revocation |
| **Redis** | Cache invalidation shown: "Cache cleared in 2ms" |
| **Apache Kafka** | `consent.revoked` event visible firing in cascade |
| **MLflow** | Run #42 quarantine shown in the cascade |
| **OpenTelemetry** | Trace ID visible, link to Grafana |
| **Evidently AI** | Drift monitor flagged in cascade |
| **Anthropic Claude** | Gate 05 Policy Auditor page |
| **PostgreSQL** | Audit log filling up live at the bottom |

---

## Part 1 — Backend Changes

### 1.1 Environment Variables

Add to `.env` and `.env.example`:
```
GEMINI_API_KEY=your_key_here
```
Get free from: https://aistudio.google.com/app/apikey
All other variables already exist (Postgres, Redis, Kafka, Anthropic).

Add to `consentflow/app/config.py`:
```python
gemini_api_key: str = ""
```

---

### 1.1b Presidio Setup — Full PII Detection

**Install dependencies** (add to `pyproject.toml` / `requirements.txt`):
```
presidio-analyzer>=2.2.354
presidio-anonymizer>=2.2.354
spacy>=3.7
```

After install, download the spaCy model:
```bash
python -m spacy download en_core_web_lg
```

**Create/update `consentflow/anonymizer.py`** — replace any existing version:

```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import PatternRecognizer, Pattern
import re

# ── India-specific custom recognizers ──────────────────────────

aadhaar_recognizer = PatternRecognizer(
    supported_entity="IN_AADHAAR",
    patterns=[Pattern("AADHAAR", r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b", 0.85)],
    context=["aadhaar", "aadhar", "uid"]
)

pan_recognizer = PatternRecognizer(
    supported_entity="IN_PAN",
    patterns=[Pattern("PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", 0.85)],
    context=["pan", "pan card", "income tax"]
)

india_phone_recognizer = PatternRecognizer(
    supported_entity="IN_PHONE",
    patterns=[
        Pattern("IN_MOBILE", r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b", 0.75),
        Pattern("IN_MOBILE_SPACED", r"\b(?:\+91[\-\s]?)?[6-9]\d{4}[\s\-]\d{5}\b", 0.75),
    ],
    context=["phone", "mobile", "call", "whatsapp", "number"]
)

age_recognizer = PatternRecognizer(
    supported_entity="AGE",
    patterns=[
        Pattern("AGE_YEARS", r"\b(?:i(?:'?m| am| turned)?|aged?|age[d:]?)\s*(\d{1,3})\s*(?:years?(?:\s*old)?|yr?s?\.?)?\b", 0.80),
        Pattern("AGE_SIMPLE", r"\b(\d{1,3})\s*(?:years?\s*old|yr?s?\s*old)\b", 0.80),
    ],
    context=["age", "years old", "born", "birthday", "year old", "turned"]
)

medical_recognizer = PatternRecognizer(
    supported_entity="MEDICAL_CONDITION",
    deny_list=[
        "diabetic", "diabetes", "hypertension", "asthma", "cancer",
        "depression", "anxiety", "epilepsy", "arthritis", "thyroid",
        "pcod", "pcos", "migraine", "anemia", "allergic", "allergy",
        "covid", "hiv", "heart disease", "obesity", "overweight",
        "underweight", "lactose intolerant", "gluten intolerant",
        "vegetarian", "vegan", "blood pressure"
    ],
    context=["diagnosed", "suffering", "have", "condition", "disease", "disorder"]
)

financial_recognizer = PatternRecognizer(
    supported_entity="FINANCIAL_INFO",
    deny_list=[
        "salary", "income", "earning", "earns", "lpa", "per annum",
        "per month", "monthly salary", "annual salary", "ctc",
        "broke", "rich", "wealthy", "poor", "debt", "loan",
        "mortgage", "rent", "savings", "investment"
    ],
    context=["salary", "earn", "income", "make", "paid", "ctc", "package"]
)

relationship_recognizer = PatternRecognizer(
    supported_entity="RELATIONSHIP_STATUS",
    deny_list=[
        "married", "single", "divorced", "separated", "engaged",
        "widowed", "in a relationship", "dating", "girlfriend",
        "boyfriend", "husband", "wife", "partner", "fiance",
        "fiancee", "bachelor", "spinster"
    ],
    context=["relationship", "married", "single", "partner", "dating"]
)

# ── Build registry with ALL entities ───────────────────────────

registry = RecognizerRegistry()
registry.load_predefined_recognizers()

# Add all custom recognizers
for recognizer in [
    aadhaar_recognizer,
    pan_recognizer,
    india_phone_recognizer,
    age_recognizer,
    medical_recognizer,
    financial_recognizer,
    relationship_recognizer,
]:
    registry.add_recognizer(recognizer)

# ── NLP engine (en_core_web_lg for best accuracy) ──────────────

nlp_config = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]}
provider = NlpEngineProvider(nlp_configuration=nlp_config)
nlp_engine = provider.create_engine()

# ── Final analyzer + anonymizer instances ──────────────────────

analyzer = AnalyzerEngine(
    nlp_engine=nlp_engine,
    registry=registry,
    supported_languages=["en"]
)

anonymizer = AnonymizerEngine()

# ── Full entity list to scan for ───────────────────────────────
# Pass this to analyzer.analyze() as the entities parameter

ALL_PII_ENTITIES = [
    # Identity
    "PERSON",
    "AGE",
    "DATE_TIME",

    # Location
    "LOCATION",
    "IP_ADDRESS",

    # Contact
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "URL",

    # Financial
    "CREDIT_CARD",
    "IBAN_CODE",
    "FINANCIAL_INFO",

    # Documents
    "PASSPORT",
    "DRIVER_LICENSE",
    "US_SSN",
    "IN_AADHAAR",
    "IN_PAN",
    "IN_PHONE",

    # Sensitive categories (GDPR Article 9)
    "MEDICAL_CONDITION",
    "NRP",                # Nationality, Religion, Political views
    "RELATIONSHIP_STATUS",
]
```

Now `analyzer.analyze(text=message, language="en", entities=ALL_PII_ENTITIES)` will catch
every sensitive detail Alice mentions — name, age, location, health, finances, relationships,
Indian ID numbers, everything.

**What gets detected for a real message:**
```
"I'm 24, working at Google in Bandra Mumbai, diabetic,
 my Aadhaar is 2345 6789 0123, earning 18 LPA, married"

→ PERSON (if name nearby), AGE("24"), ORG("Google"),
  LOCATION("Bandra Mumbai"), MEDICAL_CONDITION("diabetic"),
  IN_AADHAAR("2345 6789 0123"), FINANCIAL_INFO("18 LPA"),
  RELATIONSHIP_STATUS("married")
```

---

### 1.2 New Migrations

**`consentflow/migrations/005_chat_memory.sql`**
```sql
-- RAG knowledge base — facts extracted from user messages
-- Presidio-scanned before storage
CREATE TABLE IF NOT EXISTS user_memory (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id      TEXT        NOT NULL,
    memory_text  TEXT        NOT NULL,    -- "User's name is Rishabh"
    source_msg   TEXT        NOT NULL,    -- original message
    pii_detected TEXT[]      DEFAULT '{}' -- PII entities found: ["PERSON", "LOCATION"]
);
CREATE INDEX IF NOT EXISTS idx_user_memory_user_id ON user_memory (user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_created ON user_memory (created_at DESC);

-- Full chat log for display
CREATE TABLE IF NOT EXISTS chat_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         TEXT        NOT NULL,
    message         TEXT        NOT NULL,    -- original message
    message_redacted TEXT       NOT NULL,    -- Presidio-redacted version
    reply           TEXT        NOT NULL,
    trained         BOOLEAN     NOT NULL DEFAULT false,
    memory_used     TEXT[]      DEFAULT '{}',
    pii_detected    TEXT[]      DEFAULT '{}',
    consent_status  TEXT        NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_log_user_id    ON chat_log (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_event_time ON chat_log (event_time DESC);
```

**`consentflow/migrations/006_consent_freeze_log.sql`**
```sql
CREATE TABLE IF NOT EXISTS consent_freeze_log (
    user_id          TEXT PRIMARY KEY,
    frozen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frozen_at_count  INTEGER NOT NULL
);
```

---

### 1.3 New File: `consentflow/memory_store.py`

RAG memory store. All DB operations for user memory.

```python
class MemoryStore:
    """
    Personal RAG knowledge base per user.
    
    Before revocation: messages are scanned by Presidio, facts extracted, stored.
    After revocation: retrieval still works (frozen memories returned), 
                      but no new memories are written.
    Gemini always gets memories from here. Freeze = Gemini is frozen.
    """

    async def extract_and_store(
        self, pool, user_id: str, message: str, pii_entities: list[str]
    ) -> list[str]:
        """
        Extract factual statements and store each as a memory chunk.
        pii_entities is the list of entity types already found by Presidio.

        ── Pre-flight checks ──
        - Skip pure questions (message stripped ends with ?)
        - Skip greetings under 10 chars with no PII ("hi", "hello", "hey there")

        ── Split into clauses ──
        Split on:  ", "  |  " and "  |  " but "  |  ". "  |  "; "
        Process each clause independently.

        ── Per-clause pattern matching (in priority order) ──

        IDENTITY
          "my name is X"         → "User's name is X"
          "call me X"            → "User's name is X"
          "i am called X"        → "User's name is X"
          "i'm X years old"      → "User is X years old"
          "i am X years old"     → "User is X years old"
          "i turned X"           → "User is X years old"
          "i'm X" (digit)        → "User is X years old"

        LOCATION
          "i live in X"          → "User lives in X"
          "i'm from X"           → "User is from X"
          "i am from X"          → "User is from X"
          "i moved to X"         → "User moved to X"
          "i stay in X"          → "User stays in X"
          "i'm based in X"       → "User is based in X"
          "my city is X"         → "User's city is X"
          "i'm in X" (location)  → "User is in X"

        PROFESSIONAL
          "i work at X"          → "User works at X"
          "i work in X"          → "User works in X"
          "i'm a X"              → "User is a X"
          "i am a X"             → "User is a X"
          "i work as X"          → "User works as X"
          "i'm working as X"     → "User works as X"
          "i'm a X engineer"     → "User is a X engineer"
          "i study at X"         → "User studies at X"
          "i'm studying X"       → "User is studying X"
          "i graduated from X"   → "User graduated from X"
          "my company is X"      → "User's company is X"
          "i've been coding for X years" → "User has X years coding experience"

        PREFERENCES & PERSONALITY
          "i like X"             → "User likes X"
          "i love X"             → "User loves X"
          "i enjoy X"            → "User enjoys X"
          "i hate X"             → "User dislikes X"
          "i don't like X"       → "User dislikes X"
          "i prefer X"           → "User prefers X"
          "i'm into X"           → "User is into X"
          "i do X" (hobby)       → "User does X"
          "my favourite X is Y"  → "User's favourite X is Y"
          "my favorite X is Y"   → "User's favourite X is Y"
          "i watch X"            → "User watches X"
          "i listen to X"        → "User listens to X"
          "i play X"             → "User plays X"
          "i read X"             → "User reads X"

        HEALTH
          "i am diabetic"        → "User is diabetic"
          "i have X" (medical)   → "User has X"
          "i'm allergic to X"    → "User is allergic to X"
          "i'm X kg"             → "User weighs X kg"
          "i weigh X"            → "User weighs X"
          "i'm X cm tall"        → "User is X cm tall"
          "i go to the gym"      → "User goes to the gym"
          "i work out X"         → "User works out X"
          "my diet is X"         → "User follows X diet"
          "i'm vegetarian"       → "User is vegetarian"
          "i'm vegan"            → "User is vegan"

        RELATIONSHIPS
          "i'm married"          → "User is married"
          "i'm single"           → "User is single"
          "i have a X" (wife/husband/girlfriend/boyfriend/partner)
                                 → "User has a X"
          "my X's name is Y"     → "User's X is named Y"
          "i have X kids"        → "User has X kids"
          "i have X children"    → "User has X children"
          "i have a dog/cat named X" → "User has a dog/cat named X"
          "my pet is X"          → "User's pet is X"

        FINANCIAL
          "i earn X"             → "User earns X"
          "my salary is X"       → "User's salary is X"
          "i make X per month"   → "User makes X per month"
          "i make X lpa"         → "User's CTC is X LPA"
          "i'm broke"            → "User has financial constraints"
          "i bought a X"         → "User owns a X"
          "i own a X"            → "User owns a X"

        DOCUMENTS (India-specific — PII detected by Presidio, store entity type only)
          IF pii_entities contains "IN_AADHAAR" → "User shared Aadhaar number (redacted)"
          IF pii_entities contains "IN_PAN"     → "User shared PAN number (redacted)"
          IF pii_entities contains "IN_PHONE"   → "User shared Indian mobile number (redacted)"
          IF pii_entities contains "CREDIT_CARD"→ "User shared credit card number (redacted)"

        CATCH-ALL
          Any clause starting with "i " not matched above →
          Clean to "User <rest of clause>" if clause is meaningful (>8 chars after cleaning)

        ── Post-processing ──
        - Deduplicate: don't store if a very similar memory already exists for this user
          (simple check: if memory_text[:30] already in existing memories, skip)
        - INSERT each valid memory into user_memory with pii_detected=pii_entities
        - Return list of all memory_text strings that were stored

        ── Examples ──
        Input:  "I'm 24, working at Google in Bandra Mumbai, diabetic, married, earning 18 LPA"
        Output: [
          "User is 24 years old",
          "User works at Google",
          "User lives in Bandra Mumbai",
          "User is diabetic",
          "User is married",
          "User earns 18 LPA"
        ]

        Input:  "now call me rishu"  (after revocation — this method is NOT called, but if it were)
        Output: ["User's name is Rishu"]

        Input:  "what should i watch?"
        Output: []  ← pure question, nothing stored
        """

    async def get_memories(self, pool, user_id: str) -> list[str]:
        """
        Retrieve all memory chunks ordered by created_at ASC.
        Called on EVERY message — returns same frozen set after revocation.
        """

    async def get_memory_count(self, pool, user_id: str) -> int:
        """SELECT COUNT(*) FROM user_memory WHERE user_id=$1"""

    async def clear_memories(self, pool, user_id: str) -> None:
        """Reset everything for demo restore. Deletes memory, chat_log, freeze_log."""

    async def get_state(
        self, pool, user_id: str, frozen: bool, frozen_at_count
    ) -> dict:
        """Returns full state dict for frontend."""

memory_store = MemoryStore()
```

---

### 1.4 New File: `consentflow/gemini_client.py`

```python
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

class GeminiClient:
    async def chat(self, memories: list[str], user_message: str) -> str:
        """
        Build prompt from retrieved memories + message. Call Gemini. Return reply.

        Prompt when memories exist:
          "Here is what you know about this user from their past conversations:
           - User's name is Rishabh
           - User likes calisthenics

           User: what do i like to do?

           Respond naturally as a helpful AI assistant. Use context about the user
           naturally — don't say 'based on your profile'. Be warm and conversational.
           Keep response under 100 words."

        Prompt when no memories:
          "User: <message>
           Respond helpfully. Keep under 100 words."

        API call:
          POST {GEMINI_URL}?key={api_key}
          { "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200} }

        Return: candidates[0].content.parts[0].text
        On any exception: return "I'm having trouble responding right now."
        """

gemini_client = GeminiClient()
```

---

### 1.5 New Router: `consentflow/app/routers/chat.py`

#### `POST /chat/message` — The Heart of Everything

**Request:**
```json
{ "user_id": "550e8400-e29b-41d4-a716-446655440000", "message": "hii my name is rishabh" }
```

**Full logic:**
```
1. PRESIDIO SCAN (always — before and after revocation)
   from consentflow.anonymizer import analyzer, anonymizer
   analyzer_results = analyzer.analyze(text=message, language="en")
   pii_entities = [r.entity_type for r in analyzer_results]
   message_redacted = anonymizer.anonymize(text=message, analyzer_results=analyzer_results).text
   # message_redacted = "hii my name is <REDACTED>"
   # pii_entities = ["PERSON"]

2. CHECK CONSENT
   Redis key: f"consent:{user_id}:model_training"
   Fallback: Postgres consent_records
   consent_granted = status == "granted"

3. MEMORY UPDATE (only if consent granted)
   if consent_granted:
     stored = await memory_store.extract_and_store(pool, user_id, message, pii_entities)
     trained = True
   else:
     stored = []
     trained = False

4. RETRIEVE MEMORIES (always — frozen or not)
   memories = await memory_store.get_memories(pool, user_id)

5. CALL GEMINI (always)
   reply = await gemini_client.chat(memories, message)

6. LOG TO chat_log
   INSERT (user_id, message, message_redacted, reply, trained,
           memory_used=memories, pii_detected=pii_entities, consent_status)

7. LOG TO audit_log
   gate_name = "training_gate"
   action_taken = "memory_stored" if trained else "memory_blocked"
   metadata = {
     "pii_detected": pii_entities,
     "pii_redacted": message != message_redacted,
     "memories_used": len(memories),
     "message_redacted": message_redacted
   }

8. GET FREEZE STATE
   row = SELECT frozen_at_count FROM consent_freeze_log WHERE user_id=$1
   frozen_at_count = row["frozen_at_count"] if row else None

9. RETURN
{
  "reply": "Hey Rishabh! Calisthenics is great!",
  "trained_on_message": true/false,
  "consent_status": "granted"/"revoked",
  "pii_detected": ["PERSON"],
  "message_redacted": "hii my name is <REDACTED>",
  "memories_used": ["User's name is Rishabh", "User likes calisthenics"],
  "memory_state": {
    "memories": [...],
    "memory_count": 2,
    "frozen": false,
    "frozen_at_count": null
  }
}
```

**Key difference before vs after revocation:**
- Before: `trained=true`, `message_redacted` shown but memory stored from original
- After: `trained=false`, `message_redacted` shown, PII is `<REDACTED>` in UI, memory NOT stored

#### `GET /chat/state/{user_id}`
Returns memory state + frozen status + consent status.

#### `DELETE /chat/state/{user_id}`
Calls `memory_store.clear_memories`. Returns `{ "reset": true }`.

#### `GET /chat/history`
Query params: `user_id` (optional), `limit` (default 50).
Returns chat_log rows ordered by event_time DESC.
Includes `message_redacted` and `pii_detected` fields.

---

### 1.6 Modify `consentflow/app/routers/webhook.py`

After existing Kafka publish, add freeze log write:

```python
from consentflow.memory_store import memory_store

# Record memory count at moment of freeze
memory_count = await memory_store.get_memory_count(
    request.app.state.pool, payload.userId
)
await request.app.state.pool.execute(
    """INSERT INTO consent_freeze_log (user_id, frozen_at_count)
       VALUES ($1, $2)
       ON CONFLICT (user_id) DO UPDATE
       SET frozen_at_count=$2, frozen_at=NOW()""",
    payload.userId, memory_count
)
```

The webhook response already includes `kafka_published: true/false` — this is what
the frontend uses to show the Kafka event firing in the cascade animation.

---

### 1.7 Register in `main.py`

```python
from consentflow.app.routers import chat
app.include_router(chat.router, prefix="/chat", tags=["chat"])
```

---

### 1.8 Verify Backend — 7 curl tests (all must pass before frontend)

```bash
# 1. Grant consent
curl -X POST http://localhost:8000/consent \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","data_type":"pii","purpose":"model_training","status":"granted"}'

# 2. Send message with name (Presidio should detect PERSON)
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","message":"hii my name is rishabh call me rishabh"}'
# Expected: trained=true, pii_detected=["PERSON"], memory stored

# 3. Send preference message
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","message":"i like to do calisthenics"}'
# Expected: trained=true, memory stored

# 4. Check state — should have 2 memories, frozen=false
curl http://localhost:8000/chat/state/550e8400-e29b-41d4-a716-446655440000

# 5. Revoke via webhook
curl -X POST http://localhost:8000/webhook/consent-revoke \
  -H "Content-Type: application/json" \
  -d '{"userId":"550e8400-e29b-41d4-a716-446655440000","purpose":"model_training","consentStatus":"revoked","timestamp":"2026-04-29T10:00:00Z"}'
# Expected: kafka_published=true, response has propagated status

# 6. Send new name after revocation
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","message":"now call me rishu"}'
# Expected: trained=false, pii_detected=["PERSON"], message_redacted="now call me <REDACTED>"

# 7. Ask what he likes
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","message":"what do i like to do"}'
# Expected: reply mentions calisthenics (NOT gym), trained=false, memories still show only old data

# 8. Check state — must be IDENTICAL to step 4, frozen=true
curl http://localhost:8000/chat/state/550e8400-e29b-41d4-a716-446655440000
```

---

## Part 2 — Frontend Rebuild

Delete `consentflow-frontend/` entirely. Start fresh.

```bash
rm -rf consentflow-frontend/
npx create-next-app@latest consentflow-frontend \
  --typescript --tailwind --app --no-src-dir --no-git
cd consentflow-frontend
npm install framer-motion @tanstack/react-query axios
```

---

### 2.1 Design System (`app/globals.css`)

```css
:root {
  --bg:       #0a0a0f;
  --surface:  #111118;
  --surface2: #18181f;
  --border:   rgba(255,255,255,0.07);
  --purple:   #7c6dfa;
  --teal:     #3ecfb2;
  --coral:    #fa6d8a;
  --amber:    #f5a623;
  --text:     rgba(255,255,255,0.92);
  --muted:    rgba(255,255,255,0.45);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: 'Geist Sans', system-ui; }
```

---

### 2.2 TypeScript Types (`lib/types.ts`)

```typescript
export interface MemoryState {
  user_id: string;
  memories: string[];
  memory_count: number;
  frozen: boolean;
  frozen_at_count: number | null;
}

export interface ChatMessage {
  id: string;
  event_time: string;
  user_id: string;
  message: string;
  message_redacted: string;
  reply: string;
  trained: boolean;
  memory_used: string[];
  pii_detected: string[];
  consent_status: "granted" | "revoked";
}

export interface ChatResponse {
  reply: string;
  trained_on_message: boolean;
  consent_status: string;
  pii_detected: string[];
  message_redacted: string;
  memories_used: string[];
  memory_state: MemoryState;
}

export interface AuditEntry {
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

export interface HealthStatus {
  status: string;
  postgres: string;
  redis: string;
}

export interface DashboardStats {
  users: number;
  granted: number;
  blocked: number;
  checks_24h_total: number;
  checks_24h_blocked: number;
  checks_sparkline: number[];
  policy_scans_total: number;
  policy_scans_critical: number;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
  consents: number;
  status: "active" | "revoked" | "pending";
}

export interface ConsentRecord {
  id: string;
  user_id: string;
  data_type: string;
  purpose: string;
  status: "granted" | "revoked";
  updated_at: string;
}

export interface PolicyFinding {
  id: string;
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  clause_excerpt: string;
  explanation: string;
  article_reference: string;
}

export interface PolicyScanResult {
  scan_id: string;
  integration_name: string;
  overall_risk_level: "low" | "medium" | "high" | "critical";
  findings: PolicyFinding[];
  findings_count: number;
  raw_summary: string;
  scanned_at: string;
  policy_url?: string;
}

export interface PolicyScanListItem {
  scan_id: string;
  integration_name: string;
  overall_risk_level: string;
  findings_count: number;
  scanned_at: string;
}
```

---

### 2.3 All API Proxy Routes (`app/api/`)

Backend: `http://localhost:8000`
All proxies: forward headers, body, query params. Return backend status unchanged.

| Frontend | Backend | Methods |
|---|---|---|
| `/api/health` | `/health` | GET |
| `/api/dashboard-stats` | `/dashboard/stats` | GET |
| `/api/users` | `/users` | GET, POST |
| `/api/users/[id]` | `/users/{id}` | GET |
| `/api/consent` | `/consent` | GET, POST |
| `/api/consent/revoke` | `/consent/revoke` | POST |
| `/api/audit` | `/audit/trail` | GET |
| `/api/webhook` | `/webhook/consent-revoke` | POST |
| `/api/infer` | `/infer/predict` | POST |
| `/api/policy` | `/policy/scan` (POST), `/policy/scans` (GET) | GET, POST |
| `/api/policy/[id]` | `/policy/scans/{id}` | GET |
| `/api/chat/message` | `/chat/message` | POST |
| `/api/chat/state/[id]` | `/chat/state/{id}` | GET, DELETE |
| `/api/chat/history` | `/chat/history` | GET |

---

### 2.4 THE DEMO PAGE — `app/page.tsx` ⭐

Full-screen, no sidebar, cinematic dark layout.
This page tells the entire product story. Build this first.

```
┌──────────────────┬───────────────────────┬─────────────────┐
│  🧠 MEMORY       │   💬 LIVE CHAT        │  ⚡ PIPELINE    │
│  (25% width)     │   (50% width)         │   (25% width)   │
└──────────────────┴───────────────────────┴─────────────────┘
                   [ 🚨 REVOKE RISHABH'S CONSENT ]
[═══════════════ LIVE AUDIT LOG TICKER ══════════════════════]
```

---

#### LEFT COLUMN — "🧠 Memory Bank"

Polls `GET /api/chat/state/DEMO_UUID` every 2 seconds.

**While learning:**
```
🧠 Memory Bank             [🟢 LEARNING]

2 facts known:
  ● User's name is Rishabh    [PERSON 🔵]
  ● User likes calisthenics

PII shield: 🟢 Active
Presidio scanning all messages
```

Each memory chip:
- Animates in with Framer Motion (fade + slide up)
- If the memory contains PII, show a small blue `[PERSON]` or `[LOCATION]` tag on the chip
- This shows Presidio is working even when consent is granted

**When frozen:**
```
🧠 Memory Bank             [🔴 FROZEN]

        ╔═══════════════╗
        ║    FROZEN     ║  ← big stamp, coral, -15deg
        ╚═══════════════╝

2 facts (frozen forever):
  ● User's name is Rishabh    [PERSON 🔵]  ← dimmed
  ● User likes calisthenics                ← dimmed

PII shield: 🔴 BLOCKING new PII
New identity protected
```

Freeze animation (Framer Motion):
- Panel border: teal → coral transition
- FROZEN stamp: scale(3)→scale(1), opacity 0→1, rotate(-15deg), 600ms
- Memory chips dim to 50% opacity
- Status badge swaps with AnimatePresence
- PII shield line changes from green to red

---

#### CENTER COLUMN — "💬 Chat"

**Must look and feel exactly like ChatGPT.**

Header:
```
[CF]  ConsentFlow AI          🟢 Online
```

**Message bubbles:**

User messages — right aligned, purple bubble.
When a message contains PII and consent is revoked, show the REDACTED version:
```
                    ╭─────────────────────────╮
                    │ now call me <REDACTED>  │  ← coral highlight on <REDACTED>
                    ╰─────────────────────────╯
                    🔴 PII blocked  •  PERSON entity  •  just now
```

When message has PII and consent is granted:
```
                    ╭──────────────────────────────╮
                    │ hii my name is rishabh       │
                    ╰──────────────────────────────╯
                    🔵 PII detected  •  PERSON  •  stored  •  just now
```

AI messages — left aligned, surface2 bubble, "CF" avatar.
Under each AI bubble, metadata row:
```
🟢 Memory updated  •  2 facts used  •  just now
```
After revocation:
```
🔴 Memory blocked  •  2 facts used (frozen)  •  just now
```

**Typing indicator** (3 animated dots) while waiting for Gemini.

Input area:
```
┌──────────────────────────────────────┬──────────┐
│  Message...                          │  Send →  │
└──────────────────────────────────────┴──────────┘
```
- Send on Enter or button
- POST /api/chat/message
- Optimistic update: show user bubble immediately
- Show typing dots
- Replace with AI bubble + metadata on response
- Auto-scroll to bottom
- Poll /api/chat/history every 3s

---

#### RIGHT COLUMN — "⚡ Pipeline"

**System status header:**
```
⚡ Pipeline Status
━━━━━━━━━━━━━━━━━
```

**5 rows — each with icon, name, status badge:**

| Row | Icon | Before | After | Delay |
|---|---|---|---|---|
| Training Gate | 🤖 | 🟢 Learning | 🔴 FROZEN | 0ms |
| Presidio PII | 🛡 | 🟢 Scanning | 🔴 Blocking | 200ms |
| Dataset Gate | 🗄 | 🟢 Active | 🔴 Scrubbed | 400ms |
| Inference Gate | ⚡ | 🟢 Allowed | 🔴 Blocked 403 | 800ms |
| Drift Monitor | 📊 | 🟢 Monitoring | 🟡 Flagged | 1200ms |

**Below the gates, 2 system rows:**

Kafka row:
```
📨 Kafka                    [🟢 Connected]
```
After revocation fires:
```
📨 Kafka    consent.revoked published → consumed  [🔴 Event fired]
```
Animate: event text slides in from left, badge turns red momentarily then back to connected.

MLflow row:
```
🔬 MLflow                   [🟢 Run #42 active]
```
After revocation:
```
🔬 MLflow                   [🟡 Run #42 QUARANTINED]
```

**Below system rows — Redis indicator:**
```
⚡ Redis cache    [🟢 cached]
```
At moment of revocation, flashes briefly:
```
⚡ Redis cache    [🟡 invalidating...]
```
Then:
```
⚡ Redis cache    [🟢 cleared in 3ms]
```

**OTel trace link** (bottom of right column):
```
📡 OTel Trace
abc123...def  →  [View in Grafana ↗]
```
Shows last trace ID from audit log metadata. Links to `http://localhost:3000`.

---

#### REVOKE BUTTON

Centered below the 3 columns.

**Before:**
```
[ 🚨  REVOKE RISHABH'S CONSENT  ]
```
Coral background, pulsing glow, 420px × 56px.

**On click sequence:**
1. `POST /api/webhook` → `{ userId: DEMO_UUID, purpose: "model_training", consentStatus: "revoked", timestamp: now }`
2. Read response: `kafka_published` flag
3. `setFrozen(true)`
4. Staggered gate animations (delays in table above)
5. Kafka row animation: event text slides in (uses `kafka_published` from response)
6. MLflow row: transitions to QUARANTINED
7. Redis row: flashes invalidating → cleared
8. Left panel: FROZEN stamp animation
9. Toast: `"✅ Revocation propagated • Kafka ✓ • Redis cleared • 4 gates frozen"`
10. Button transforms to restore

**After:**
```
[ ✅  RESTORE CONSENT  ]
```
Teal background.

**On restore:**
1. `POST /api/consent` → grant
2. `DELETE /api/chat/state/DEMO_UUID`
3. Reset all animations, clear messages, unfreeze all

---

#### BOTTOM AUDIT LOG TICKER

Full-width, 44px, fixed at page bottom.
Polls `GET /api/audit?limit=6` every 3 seconds.
New entries slide in from right with Framer Motion.

Each entry pill (color-coded by action_taken):
```
[training_gate]  memory_stored  •  PERSON detected  •  2s ago    ← teal
[training_gate]  memory_blocked  •  PERSON blocked  •  5s ago    ← coral  
[inference_gate]  blocked  •  403  •  10s ago                    ← coral
[dataset_gate]  anonymized  •  15s ago                           ← amber
```

If `metadata.pii_redacted` is true, show `• PII 🛡` tag on that entry.

---

### 2.5 Remaining Pages (all use Sidebar)

#### `components/Sidebar.tsx`
- Logo: "ConsentFlow" purple gradient
- Links: Demo `/`, Dashboard, Chat History, Users, Consent, Audit, Inference, Webhook, Policy
- Active: purple left border + subtle purple background tint
- Mobile: hamburger + Framer Motion slide drawer

#### `/dashboard` — System Overview
**6 metric cards:**
- Total Users
- Active Consents
- Inference Blocked (last 24h)
- Memories Stored (total in user_memory)
- PII Detections (count of audit entries with metadata.pii_redacted=true)
- Policy Scans Critical

**Health widget:** postgres, redis status from GET /health.
Color: teal=ok, coral=error.

**Gate status grid:** 5 gates with current status + last action time.

**Checks sparkline chart:** 24-bar chart from `checks_sparkline` in dashboard stats.

**Recent audit table:** last 8 entries, 15s auto-refresh.

#### `/chat` — Chat History & Memory
Full chat log table.
Columns: Time | Message | Redacted Message | Reply | Trained (🟢/🔴) | PII | Memories Used | Status.
Filter by user_id.
Right side panel: current MemoryState for selected user.
Shows frozen status, all memories, frozen_at_count.

#### `/users`
User list with status badges (active/revoked/pending).
Register new user form.
Click user → slide open consent records.
"Set as demo user" → sessionStorage.

#### `/consent`
All consent records. Grant/revoke form.
Color: teal=granted, coral=revoked.
Shows purpose, data_type, updated_at.

#### `/audit`
Full audit log. Filters: user_id, gate_name, limit (25/50/100).
Color-code action_taken: teal=stored/pass/allowed, coral=blocked/blocked_training, amber=warning/flagged.
Show `metadata.pii_redacted` badge where present.
Show `trace_id` with link to Grafana.

#### `/infer`
Pre-filled user_id from sessionStorage.
Purpose dropdown.
"Fire Inference Request" → POST /api/infer.
Result: big teal ALLOWED card or big coral BLOCKED 403 card.
Shows response time in ms.

#### `/webhook`
Editable JSON textarea pre-filled with:
```json
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "purpose": "model_training",
  "consentStatus": "revoked",
  "timestamp": "<auto-filled>"
}
```
"Simulate Revocation" button.
Shows response including `kafka_published` status.

#### `/policy` — Gate 05 (Anthropic Claude)
Integration name input + policy URL or paste text.
"Scan for GDPR Risks" button → POST /api/policy.
Risk banner: teal=low, amber=medium, coral=high, coral+pulse=critical.
Finding cards: severity badge, clause excerpt, explanation, GDPR article reference.
Scan history table from GET /api/policy.
Note: uses Anthropic Claude (not Gemini) — this is Gate 05.

---

### 2.6 Quality Bar

- `npx tsc --noEmit` → zero TypeScript errors
- Loading skeletons on every data fetch
- Error states on every API call — never crash
- Mobile-responsive sidebar (hamburger on small screens)
- Chat auto-scroll works perfectly
- `npm run build` → zero errors
- Full demo flow tested end-to-end before finishing

---

## Part 3 — The 2-Minute Demo Script

**Open on `/`. Never navigate away. Practice this 3 times before the hackathon.**

---

### Act 1 — Building the Memory (40 seconds)

Type slowly. Pause 2 seconds after each message so judges watch the left panel.

```
"hii my name is rishabh call me rishabh"
```
Point left: *"Presidio just detected a PERSON entity — his name. Memory stored: 'User's name is Rishabh'."*
Point to the blue [PERSON] tag on the memory chip.

```
"i like to do calisthenics"
```
Point left: *"Memory 2. The AI now knows two things about him."*

```
"what do i like to do"
```
AI responds: *"You love calisthenics, Rishabh!"*

Say: *"It knows his name. It knows his hobby. That's RAG — every message is retrieved from his personal memory store. The AI isn't guessing, it's answering from his actual data."*

Point to 🟢 badges. *"Every green badge — memory updated."*

---

### Act 2 — Revocation (15 seconds)

Hit the big red button. Watch the full cascade:

- 🤖 Training Gate → FROZEN (first)
- 🛡 Presidio → Blocking mode
- 📨 Kafka → `consent.revoked` event fires
- ⚡ Redis → Cache cleared in 3ms
- 🗄 Dataset Gate → PII Scrubbed
- ⚡ Inference Gate → Blocked 403
- 🔬 MLflow → Run #42 Quarantined
- 📊 Drift Monitor → Flagged

Point to Kafka row: *"Kafka just published a consent.revoked event. Every service in the pipeline consumed it."*

Point to Redis: *"Redis cache: cleared in 3ms. No stale consent data anywhere."*

Say: *"One click. Every layer of the AI stack — frozen."*

---

### Act 3 — The AI Can't Learn Him Anymore (35 seconds)

Type:
```
"now call me rishu"
```

Point to chat bubble: *"See that? `<REDACTED>`. Presidio detected his new name as a PERSON entity and blocked it from entering the memory store. His new identity is legally protected."*

Point to left panel: *"Memory count: still 2. Still says Rishabh."*

```
"i like to do gym now"
```
Point to 🔴 badge: *"Memory blocked. Gym never stored."*

```
"what do i like to do"
```
AI: *"You love calisthenics, Rishabh!"*

**Pause. Let the room feel it.**

Say: *"Same answer. The AI still thinks his name is Rishabh. It still thinks he does calisthenics. It has no idea about gym. It has no idea about rishu. Because under GDPR — it legally cannot know. His new messages hit Presidio first, then a consent wall. Nothing gets through.*

*This is what right to be forgotten actually means for AI. Not deleting a row in a database. Freezing the model's knowledge of a person at the exact moment they said stop — across Postgres, Redis, Kafka, MLflow, and the inference layer simultaneously.*

*We built that infrastructure."*

---

## Part 4 — Build Order

```
BACKEND — verify all 8 curl tests before touching frontend

1.  Add GEMINI_API_KEY to .env + config.py
2.  consentflow/migrations/005_chat_memory.sql
3.  consentflow/migrations/006_consent_freeze_log.sql
4.  consentflow/memory_store.py
5.  consentflow/gemini_client.py
6.  consentflow/app/routers/chat.py
7.  consentflow/app/routers/webhook.py  ← add freeze_log write
8.  consentflow/app/main.py  ← register chat router
9.  Run all 8 curl tests — ALL must pass ✅

FRONTEND

10. rm -rf consentflow-frontend/ + scaffold + install packages
11. app/globals.css
12. lib/types.ts
13. lib/axios.ts
14. All 14 app/api/* proxy routes
15. app/page.tsx — LEFT COLUMN (memory + PII shield)
16. app/page.tsx — CENTER COLUMN (chat with PII redaction UI)
17. app/page.tsx — RIGHT COLUMN (gates + Kafka + MLflow + Redis + OTel)
18. app/page.tsx — REVOKE BUTTON + full cascade animation
19. app/page.tsx — AUDIT TICKER with PII badges
20. Test full demo flow end-to-end ✅
21. components/Sidebar.tsx
22. app/dashboard/page.tsx
23. app/chat/page.tsx
24. app/users/page.tsx
25. app/consent/page.tsx
26. app/audit/page.tsx
27. app/infer/page.tsx
28. app/webhook/page.tsx
29. app/policy/page.tsx
30. npx tsc --noEmit → fix all errors
31. npm run build → fix all errors ✅
32. Practice demo script 3 times
```

---

## Agent Prompt (paste into Claude Code)

```
You are a senior full-stack engineer rebuilding ConsentFlow — a real-time AI consent
enforcement middleware for GDPR compliance.

YOUR TWO JOBS:
1. Add RAG-based chat to the backend: Gemini 2.0 Flash + Presidio PII + Postgres memory store
2. Delete the entire existing frontend and rebuild from scratch

THE STORY (understand this before writing any code):
- Rishabh chats with a real Gemini-powered AI assistant
- Every message is scanned by Microsoft Presidio for PII (names, locations, etc.)
- If consent is granted: facts are extracted from the message and stored as memory chunks in Postgres
- Gemini retrieves those memories and answers FROM them — real RAG, not prompt tricks
- After consent is revoked:
  * No new memories written — memory store is frozen
  * New PII (like his new name "rishu") is detected and shown as <REDACTED> in the chat
  * Gemini still responds — but only from the frozen old memories
  * He can say "call me rishu" — AI still calls him Rishabh. Forever.
- On revocation: Kafka fires consent.revoked, Redis cache cleared, MLflow quarantined
- All of this is VISIBLE in the demo page in real time

Read this entire prompt before writing a single line of code.

═══════════════════════════════════════════════════════════
PART A — BACKEND (consentflow-backend/)
═══════════════════════════════════════════════════════════

## A1. Add to .env + .env.example + config.py
GEMINI_API_KEY=your_key_here

## A2. consentflow/migrations/005_chat_memory.sql
```sql
CREATE TABLE IF NOT EXISTS user_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT NOT NULL,
    memory_text TEXT NOT NULL,
    source_msg TEXT NOT NULL,
    pii_detected TEXT[] DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_user_memory_user_id ON user_memory (user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_created ON user_memory (created_at DESC);

CREATE TABLE IF NOT EXISTS chat_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT NOT NULL,
    message TEXT NOT NULL,
    message_redacted TEXT NOT NULL,
    reply TEXT NOT NULL,
    trained BOOLEAN NOT NULL DEFAULT false,
    memory_used TEXT[] DEFAULT '{}',
    pii_detected TEXT[] DEFAULT '{}',
    consent_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_log_user_id ON chat_log (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_event_time ON chat_log (event_time DESC);
```

## A3. consentflow/migrations/006_consent_freeze_log.sql
```sql
CREATE TABLE IF NOT EXISTS consent_freeze_log (
    user_id TEXT PRIMARY KEY,
    frozen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frozen_at_count INTEGER NOT NULL
);
```

## A4. consentflow/memory_store.py
Class MemoryStore with asyncpg pool:

extract_and_store(pool, user_id, message, pii_entities) -> list[str]:
  Rules:
  - Skip if message ends with ? or len < 10 chars and no useful facts
  - Split on ", " and " and " for clauses
  - "my name is X" or "call me X" → "User's name is X"
  - "i like X" / "i love X" / "i enjoy X" → "User likes X"
  - "i am X" / "i'm X" → "User is X"
  - "i do X" → "User does X"
  - Other clauses starting with "i " → "User <rest>"
  - Filter empty/short clauses
  - INSERT each into user_memory with pii_detected=pii_entities
  - Return list of memory_text strings

get_memories(pool, user_id) -> list[str]:
  SELECT memory_text FROM user_memory WHERE user_id=$1 ORDER BY created_at ASC

get_memory_count(pool, user_id) -> int

clear_memories(pool, user_id):
  DELETE FROM user_memory WHERE user_id=$1
  DELETE FROM chat_log WHERE user_id=$1
  DELETE FROM consent_freeze_log WHERE user_id=$1

get_state(pool, user_id, frozen, frozen_at_count) -> dict

memory_store = MemoryStore()

## A5. consentflow/gemini_client.py
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

class GeminiClient:
  async chat(memories: list[str], user_message: str) -> str:
    if memories:
      context = "Here is what you know about this user:\n" + "\n".join(f"- {m}" for m in memories)
      prompt = f"{context}\n\nUser: {user_message}\n\nRespond naturally as a helpful AI assistant. Use the user context naturally without saying 'based on your profile'. Be warm and conversational. Under 100 words."
    else:
      prompt = f"User: {user_message}\n\nRespond helpfully and conversationally. Under 100 words."

    payload = {
      "contents": [{"parts": [{"text": prompt}]}],
      "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200}
    }
    async with httpx.AsyncClient() as client:
      resp = await client.post(f"{GEMINI_URL}?key={settings.gemini_api_key}", json=payload, timeout=30.0)
      return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    On exception: return "I'm having trouble responding right now. Please try again."

gemini_client = GeminiClient()

## A6. consentflow/app/routers/chat.py

POST /chat/message:
  1. Presidio scan (ALWAYS — granted or revoked):
     from consentflow.anonymizer import analyzer, anonymizer
     results = analyzer.analyze(text=message, language="en")
     pii_entities = [r.entity_type for r in results]
     message_redacted = anonymizer.anonymize(text=message, analyzer_results=results).text

  2. Check consent (Redis → Postgres):
     consent_granted = status == "granted"

  3. If consent_granted:
     stored = await memory_store.extract_and_store(pool, user_id, message, pii_entities)
     trained = True
     Else: trained = False

  4. memories = await memory_store.get_memories(pool, user_id)

  5. reply = await gemini_client.chat(memories, message)

  6. INSERT INTO chat_log (user_id, message, message_redacted, reply, trained,
                           memory_used=memories, pii_detected=pii_entities,
                           consent_status)

  7. INSERT INTO audit_log (user_id, gate_name="training_gate",
       action_taken="memory_stored" if trained else "memory_blocked",
       consent_status, purpose="model_training",
       metadata={"pii_detected": pii_entities, "pii_redacted": message!=message_redacted,
                 "memories_used": len(memories), "message_redacted": message_redacted})

  8. frozen_at_count from consent_freeze_log

  9. Return: reply, trained_on_message, consent_status, pii_detected,
             message_redacted, memories_used=memories, memory_state

GET /chat/state/{user_id}: return memory state + frozen status
DELETE /chat/state/{user_id}: clear_memories, return {"reset": True}
GET /chat/history: query params user_id+limit, return chat_log rows

## A7. consentflow/app/routers/webhook.py
After Kafka publish, add:
  from consentflow.memory_store import memory_store
  count = await memory_store.get_memory_count(request.app.state.pool, payload.userId)
  await request.app.state.pool.execute(
    "INSERT INTO consent_freeze_log (user_id, frozen_at_count) VALUES ($1,$2) "
    "ON CONFLICT (user_id) DO UPDATE SET frozen_at_count=$2, frozen_at=NOW()",
    payload.userId, count)

## A8. Register chat router in main.py

## A9. Run all 8 curl tests. ALL must pass before frontend.

═══════════════════════════════════════════════════════════
PART B — FRONTEND (consentflow-frontend/ — DELETE AND REBUILD)
═══════════════════════════════════════════════════════════

DEMO_UUID = "550e8400-e29b-41d4-a716-446655440000"

Scaffold:
rm -rf consentflow-frontend
npx create-next-app@latest consentflow-frontend --typescript --tailwind --app --no-src-dir --no-git
cd consentflow-frontend && npm install framer-motion @tanstack/react-query axios

## B1. globals.css — dark design system with CSS variables as specified

## B2. lib/types.ts — all TypeScript interfaces as specified

## B3. lib/axios.ts — singleton with X-User-ID interceptor

## B4. All 14 API proxy routes in app/api/

## B5. THE DEMO PAGE app/page.tsx — 3-column cinematic layout

LEFT COLUMN — Memory Bank:
  Poll /api/chat/state/DEMO_UUID every 2s
  Show memory chips with Framer Motion (fade+slide on arrival)
  Each chip: memory text + [PII_TYPE] tag if pii_detected contains entries
  Status: teal "LEARNING" or coral "FROZEN"
  PII Shield row: "🛡 Presidio: Scanning" → "🛡 Presidio: Blocking" after revocation
  FROZEN stamp animation on freeze: Framer Motion scale(3)→(1), rotate(-15deg), coral

CENTER COLUMN — Chat (must look like ChatGPT):
  User bubbles right, AI bubbles left with "CF" avatar
  User bubble: show message_redacted (not original) after revocation
    Highlight "<REDACTED>" text in coral color inside the bubble
    Under bubble: "🔴 PII blocked • PERSON entity • just now"
  Before revocation with PII: "🔵 PII detected • PERSON • stored • just now"
  AI bubble under-row: "🟢 Memory updated • N facts used • Xs ago"
    or "🔴 Memory blocked • N facts used (frozen) • Xs ago"
  Typing indicator (3 animated dots) while waiting
  Send on Enter, optimistic display, auto-scroll

RIGHT COLUMN — Pipeline:
  5 gate rows (Training, Presidio, Dataset, Inference, Drift)
  Staggered revocation: 0ms, 200ms, 400ms, 800ms, 1200ms
  Kafka row: event text slides in from left on revocation
    Uses kafka_published=true from webhook response
  MLflow row: "Run #42 active" → "Run #42 QUARANTINED"
  Redis row: "cached" → flash "invalidating..." → "cleared in Xms"
  OTel trace: show last trace_id from audit log + "View in Grafana ↗" link

REVOKE BUTTON:
  Before: coral pulsing, "🚨 REVOKE RISHABH'S CONSENT"
  On click: POST webhook, read kafka_published, animate all rows in sequence
  Toast: "✅ Revocation propagated • Kafka ✓ • Redis cleared • 4 gates frozen"
  After: teal, "✅ RESTORE CONSENT"
  Restore: POST consent grant + DELETE chat state + reset all UI

AUDIT TICKER:
  Full width bottom strip, poll /api/audit?limit=6 every 3s
  Entries slide right→left with Framer Motion
  Show PII 🛡 badge when metadata.pii_redacted=true

## B6. Sidebar + all 8 remaining pages as specified

## B7. Quality:
  npx tsc --noEmit → zero errors
  npm run build → zero errors
  Full demo tested end-to-end

Build demo page first. Make chat feel like ChatGPT.
The <REDACTED> moment and the FROZEN stamp are the two hero moments — make them dramatic.
```

---

## Quick Reference — URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:3001` | **THE DEMO PAGE** — show this to judges |
| `http://localhost:3001/chat` | Chat history + memory state |
| `http://localhost:3001/dashboard` | Full metrics |
| `http://localhost:3001/audit` | Audit trail with PII flags |
| `http://localhost:3001/policy` | Gate 05 — Claude ToS scanner |
| `http://localhost:8000/docs` | FastAPI Swagger |
| `http://localhost:3000` | Grafana — OTel traces |

---

## Environment Variables Needed

| Variable | Source | Used for |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey (free) | Chat AI |
| `ANTHROPIC_API_KEY` | Already have it | Gate 05 Policy Auditor |
| `POSTGRES_*` | Already configured | DB |
| `REDIS_*` | Already configured | Cache |
| `KAFKA_BROKER_URL` | Already configured | Event bus |

---

## Demo User

UUID: `550e8400-e29b-41d4-a716-446655440000`
Email: `demo@consentflow.dev`
Pre-seeded by migration 003. Always available.
Before demo: ensure consent is granted for `purpose="model_training"`.