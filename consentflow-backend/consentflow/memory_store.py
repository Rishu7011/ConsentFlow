"""
consentflow/memory_store.py — Personal RAG knowledge base per user.

Plan 1.4  (optimized)

How it works
------------
Before revocation:
  - Every user message is parsed by extract_and_store().
  - Facts are extracted using pattern matching, stored as memory chunks.
  - Gemini uses those chunks as context in its replies.

After revocation:
  - extract_and_store() is NEVER called (caller checks consent first).
  - get_memories() still returns the frozen set → Gemini stays "frozen".
  - Memory count is locked at whatever it was when consent was revoked.

The consent_freeze_log table (migration 006) records the count at freeze time
so the frontend can show "2 facts (frozen forever)".

Optimisations over v1.3
-----------------------
* Single flat rule list with priority order — avoids nested-loop overhead and
  makes it trivial to add / remove / reorder rules without touching logic code.
* Fingerprint-based dedup — normalises whitespace / case / punctuation before
  comparison so near-duplicate phrasings ("User lives in Delhi" vs
  "User lives in delhi") are caught reliably.
* In-process LRU cache for get_memories — avoids repeated DB round-trips for
  the same user_id within a single request burst; cache is invalidated on every
  successful write.
* Batch INSERT with executemany — replaces N sequential awaits with a single
  round-trip, cutting DB latency proportionally.
* Noise filter on catch-all — discards modal/auxiliary openers that produce
  useless facts ("User can …", "User will …", "User would …").
* Typed return values and fully annotated public API.
* Optional limit parameter on get_memories for large memory banks.
"""
from __future__ import annotations

import functools
import logging
import re
import unicodedata
from collections.abc import Callable
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

# ── Clause splitter ────────────────────────────────────────────────────────────

_CLAUSE_SPLIT: re.Pattern[str] = re.compile(r",\s+| and | but | \. |; ")

# ── Noise words that make catch-all facts meaningless ─────────────────────────

_CATCH_ALL_NOISE: frozenset[str] = frozenset({
    "can", "could", "will", "would", "should", "might", "may",
    "need", "want", "wish", "hope", "think", "believe", "guess",
    "wonder", "know", "understand", "see", "feel", "mean",
    "suppose", "imagine", "suggest", "recommend",
})

# ── Rule definition ────────────────────────────────────────────────────────────

class _Rule(NamedTuple):
    """A single extraction rule with its compiled pattern and fact template."""
    group: str                                    # category label (for logging)
    pattern: re.Pattern[str]
    template: str | Callable[[re.Match[str]], str]


def _t(template: str) -> Callable[[re.Match[str]], str]:
    """Build a template callable that substitutes {1}, {2}, … with match groups."""
    def _apply(m: re.Match[str]) -> str:
        result = template
        for i, group in enumerate(m.groups(), start=1):
            result = result.replace(f"{{{i}}}", (group or "").strip())
        return result
    return _apply


def _r(group: str, pattern: str, template: str | Callable[[re.Match[str]], str]) -> _Rule:
    """Convenience constructor — compiles the pattern and wraps string templates."""
    compiled = re.compile(pattern, re.IGNORECASE)
    tmpl = _t(template) if isinstance(template, str) else template
    return _Rule(group=group, pattern=compiled, template=tmpl)


# ── Flat rule list (priority order — first match per group wins) ───────────────
# Groups are tried in declaration order.  Within a group the FIRST matching rule
# wins and the remaining rules in the SAME group are skipped.
# Adding a new rule: insert it in the right group block below.

_RULES: list[_Rule] = [
    # ── identity ──────────────────────────────────────────────────────────────
    _r("identity", r"my name is ([\w'-]+)",          "User's name is {1}"),
    _r("identity", r"call me ([\w'-]+)",              "User's name is {1}"),
    _r("identity", r"i am called ([\w'-]+)",          "User's name is {1}"),
    _r("identity", r"i'?m (\d+) years? old",          "User is {1} years old"),
    _r("identity", r"i am (\d+) years? old",          "User is {1} years old"),
    _r("identity", r"i turned (\d+)",                 "User is {1} years old"),
    _r("identity", r"i'?m (\d+)$",                   "User is {1} years old"),
    _r("identity", r"my birthday falls on (.+?)(?:\.|,|$)", "User's birthday is {1}"),
    _r("identity", r"my birthday is in (.+?)(?:\.|,|$)",    "User's birthday is in {1}"),
    _r("identity", r"my birthday is on (.+?)(?:\.|,|$)",    "User's birthday is on {1}"),
    _r("identity", r"my birthday is (.+?)(?:\.|,|$)",       "User's birthday is {1}"),
    _r("identity", r"i was born in (.+?)(?:\.|,|$)",        "User was born in {1}"),
    _r("identity", r"i was born on (.+?)(?:\.|,|$)",        "User was born on {1}"),

    _r("identity", r"my (?:aadhaar|aadhar|addhar)(?: card)? number is (.+?)(?:\.|,|$)", "User's Aadhaar number is {1}"),
    _r("identity", r"my pan(?: card)? number is (.+?)(?:\.|,|$)", "User's PAN number is {1}"),
    _r("identity", r"my (?:(?:phone|mobile)\s+)?number is (.+?)(?:\.|,|$)", "User's mobile number is {1}"),
    _r("identity", r"my email(?: address)? is (.+?)(?:\.|,|$)", "User's email is {1}"),

    # ── location ──────────────────────────────────────────────────────────────
    _r("location", r"i live in (.+?)(?:\.|,|$)",       "User lives in {1}"),
    _r("location", r"i'?m from (.+?)(?:\.|,|$)",       "User is from {1}"),
    _r("location", r"i am from (.+?)(?:\.|,|$)",       "User is from {1}"),
    _r("location", r"i moved to (.+?)(?:\.|,|$)",      "User moved to {1}"),
    _r("location", r"i stay in (.+?)(?:\.|,|$)",       "User stays in {1}"),
    _r("location", r"i'?m based in (.+?)(?:\.|,|$)",   "User is based in {1}"),
    _r("location", r"my city is (.+?)(?:\.|,|$)",      "User's city is {1}"),
    _r("location", r"i'?m in (.+?)(?:\.|,|$)",         "User is in {1}"),

    # ── professional ──────────────────────────────────────────────────────────
    _r("professional", r"i'?ve been coding for (\d+) years?",    "User has {1} years coding experience"),
    _r("professional", r"i work at (.+?)(?:\.|,|$)",              "User works at {1}"),
    _r("professional", r"i work in (.+?)(?:\.|,|$)",              "User works in {1}"),
    _r("professional", r"i work as (.+?)(?:\.|,|$)",              "User works as {1}"),
    _r("professional", r"i'?m working as (.+?)(?:\.|,|$)",        "User works as {1}"),
    _r("professional", r"i study at (.+?)(?:\.|,|$)",             "User studies at {1}"),
    _r("professional", r"i'?m studying (.+?)(?:\.|,|$)",          "User is studying {1}"),
    _r("professional", r"i graduated from (.+?)(?:\.|,|$)",       "User graduated from {1}"),
    _r("professional", r"my company is (.+?)(?:\.|,|$)",          "User's company is {1}"),
    _r("professional", r"i'?m a (.+?) engineer",                  "User is a {1} engineer"),
    _r("professional", r"i am a ([\w\s-]+?)(?:\.|,|$)",           "User is a {1}"),
    _r("professional", r"i'?m a ([\w\s-]+?)(?:\.|,|$)",           "User is a {1}"),

    # ── health ────────────────────────────────────────────────────────────────
    _r("health", r"i am diabetic",                   "User is diabetic"),
    _r("health", r"i'?m diabetic",                   "User is diabetic"),
    _r("health", r"i'?m allergic to (.+)",           "User is allergic to {1}"),
    _r("health", r"i'?m (\d+)\s*kg",                 "User weighs {1} kg"),
    _r("health", r"i weigh (.+)",                    "User weighs {1}"),
    _r("health", r"i'?m (\d+)\s*cm tall",            "User is {1} cm tall"),
    _r("health", r"i go to the gym",                 "User goes to the gym"),
    _r("health", r"i work out (.+)",                 "User works out {1}"),
    _r("health", r"my diet is (.+)",                 "User follows {1} diet"),
    _r("health", r"i'?m vegetarian",                 "User is vegetarian"),
    _r("health", r"i'?m vegan",                      "User is vegan"),
    _r("health", r"i have (.+)",                     "User has {1}"),

    # ── relationship ──────────────────────────────────────────────────────────
    _r("relationship", r"i'?m married",              "User is married"),
    _r("relationship", r"i'?m single",               "User is single"),
    _r("relationship", r"i have a (wife|husband|girlfriend|boyfriend|partner)",
       lambda m: f"User has a {m.group(1).strip()}"),
    _r("relationship", r"my (.+?)'s name is (.+)",
       lambda m: f"User's {m.group(1).strip()} is named {m.group(2).strip()}"),
    _r("relationship", r"i have (\d+) kids?",        "User has {1} kids"),
    _r("relationship", r"i have (\d+) children",     "User has {1} children"),
    _r("relationship", r"i have a (dog|cat) named (.+)",
       lambda m: f"User has a {m.group(1).strip()} named {m.group(2).strip()}"),
    _r("relationship", r"my pet is (.+)",            "User's pet is {1}"),

    # ── financial ─────────────────────────────────────────────────────────────
    _r("financial", r"i make (.+) lpa",              "User's CTC is {1} LPA"),
    _r("financial", r"i make (.+) per month",        "User makes {1} per month"),
    _r("financial", r"i earn (.+)",                  "User earns {1}"),
    _r("financial", r"my salary is (.+)",            "User's salary is {1}"),
    _r("financial", r"i'?m broke",                  "User has financial constraints"),
    _r("financial", r"i bought a (.+)",              "User owns a {1}"),
    _r("financial", r"i own a (.+)",                 "User owns a {1}"),

    # ── preference ────────────────────────────────────────────────────────────
    _r("preference", r"my favou?rite (.+?) is (.+?)(?:\.|,|$)",
       lambda m: f"User's favourite {m.group(1).strip()} is {m.group(2).strip()}"),
    _r("preference", r"i like to do (.+?)(?:\.|,|$)", "User likes to do {1}"),
    _r("preference", r"i like (.+?)(?:\.|,|$)",        "User likes {1}"),
    _r("preference", r"i love (.+?)(?:\.|,|$)",        "User loves {1}"),
    _r("preference", r"i enjoy (.+?)(?:\.|,|$)",       "User enjoys {1}"),
    _r("preference", r"i hate (.+?)(?:\.|,|$)",        "User dislikes {1}"),
    _r("preference", r"i don'?t like (.+?)(?:\.|,|$)", "User dislikes {1}"),
    _r("preference", r"i prefer (.+?)(?:\.|,|$)",      "User prefers {1}"),
    _r("preference", r"i'?m into (.+?)(?:\.|,|$)",     "User is into {1}"),
    _r("preference", r"i do (.+?)(?:\.|,|$)",          "User does {1}"),
    _r("preference", r"i watch (.+?)(?:\.|,|$)",       "User watches {1}"),
    _r("preference", r"i listen to (.+?)(?:\.|,|$)",   "User listens to {1}"),
    _r("preference", r"i play (.+?)(?:\.|,|$)",        "User plays {1}"),
    _r("preference", r"i read (.+?)(?:\.|,|$)",        "User reads {1}"),
]

# Group boundaries for "first match per group wins" logic.
# Built once at import time from the flat rule list.
_GROUP_ORDER: list[str] = list(dict.fromkeys(r.group for r in _RULES))  # stable, deduped


# ── Document-level PII facts (Presidio entities with no regex equivalent) ─────

_DOCUMENT_ENTITY_FACTS: dict[str, str] = {
    "IN_AADHAAR":    "User shared Aadhaar number (redacted)",
    "IN_PAN":        "User shared PAN number (redacted)",
    "IN_PHONE":      "User shared Indian mobile number (redacted)",
    "CREDIT_CARD":   "User shared credit card number (redacted)",
    "EMAIL_ADDRESS": "User shared email address (redacted)",
    "PHONE_NUMBER":  "User shared phone number (redacted)",
    "IP_ADDRESS":    "User shared IP address (redacted)",
    "PASSPORT":      "User shared passport number (redacted)",
    "US_SSN":        "User shared SSN (redacted)",
}

# Entity types fully covered by regex rules — skip document-level facts for these
# when regex already produced at least one fact.
_REGEX_COVERED_ENTITIES: frozenset[str] = frozenset({
    "PERSON", "LOCATION", "DATE_TIME", "AGE",
    "MEDICAL_CONDITION", "FINANCIAL_INFO", "RELATIONSHIP_STATUS",
    "IN_AADHAAR", "IN_PAN", "IN_PHONE", "EMAIL_ADDRESS", "PHONE_NUMBER",
})


# ── Dedup fingerprint ──────────────────────────────────────────────────────────

def _fingerprint(fact: str) -> str:
    """
    Return a normalised fingerprint for dedup comparison.

    Strips accents, lowercases, collapses whitespace, and removes trailing
    punctuation so that minor surface variations map to the same key.

    Examples
    --------
    "User's name is Rishabh"  → "user's name is rishabh"
    "User lives in Delhi."    → "user lives in delhi"
    "User lives in delhi"     → "user lives in delhi"   ← same key
    """
    # NFKD decompose, drop combining chars (accents)
    nfkd = unicodedata.normalize("NFKD", fact)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    lower = ascii_str.lower()
    stripped = lower.strip().rstrip(".,;:!?")
    collapsed = re.sub(r"\s+", " ", stripped)
    return collapsed


# ── Core extraction logic ──────────────────────────────────────────────────────

def _extract_facts_from_clause(clause: str) -> list[str]:
    """
    Run one clause through the flat rule list.

    Returns at most one fact per group (first matching rule within each group
    wins).  Groups are tried in declaration order.
    """
    clause = clause.strip()
    if not clause:
        return []

    facts: list[str] = []
    matched_groups: set[str] = set()

    for rule in _RULES:
        if rule.group in matched_groups:
            continue
        m = rule.pattern.search(clause)
        if m:
            try:
                fact = rule.template(m).strip().rstrip(".,;")
            except Exception:  # noqa: BLE001 — defensive; bad match groups
                continue
            if fact:
                facts.append(fact)
            matched_groups.add(rule.group)

        # Stop early once every group has been matched.
        if len(matched_groups) == len(_GROUP_ORDER):
            break

    return facts


def _extract_facts(message: str) -> list[str]:
    """
    Split *message* into clauses, extract facts from each, and return a flat
    deduplicated list (order preserved, fingerprint-based dedup).
    """
    clauses = _CLAUSE_SPLIT.split(message)
    seen_fps: set[str] = set()
    facts: list[str] = []

    for clause in clauses:
        for fact in _extract_facts_from_clause(clause):
            fp = _fingerprint(fact)
            if fp not in seen_fps:
                seen_fps.add(fp)
                facts.append(fact)

    return facts


def _is_noisy_catchall(clause: str) -> bool:
    """
    Return True if the clause starts with a noise modal / auxiliary that
    would produce a useless catch-all fact ("User can run Python", etc.).
    """
    after_i = clause[2:].strip().lower()
    first_word = after_i.split()[0] if after_i.split() else ""
    return first_word in _CATCH_ALL_NOISE


# ── In-process LRU memory cache ───────────────────────────────────────────────
# Keyed by user_id. Holds the last fetched list[str] from DB.
# Invalidated automatically whenever extract_and_store writes new rows.
# maxsize=256 keeps ≈ 256 concurrent users warm without significant RAM cost.

@functools.lru_cache(maxsize=256)
def _cached_memories(user_id: str) -> list[str]:  # pragma: no cover
    """Placeholder — actual value is injected via _set_cache / _get_cache."""
    return []  # never called directly; exists to satisfy lru_cache typing


# We use a plain dict instead of lru_cache so we can mutate values imperatively.
_memory_cache: dict[str, list[str]] = {}


def _cache_get(user_id: str) -> list[str] | None:
    return _memory_cache.get(user_id)


def _cache_set(user_id: str, memories: list[str]) -> None:
    _memory_cache[user_id] = memories


def _cache_invalidate(user_id: str) -> None:
    _memory_cache.pop(user_id, None)


# ── MemoryStore class ──────────────────────────────────────────────────────────

class MemoryStore:
    """
    Personal RAG knowledge base per user.

    Before revocation: messages are scanned by Presidio, facts extracted, stored.
    After revocation:  retrieval still works (frozen memories returned),
                       but no new memories are written.
    Gemini always gets memories from here.  Freeze = Gemini is frozen.

    Performance notes
    -----------------
    * get_memories() is backed by an in-process dict cache.  The cache is
      invalidated on every successful write so callers always see fresh data.
    * extract_and_store() does a single batch INSERT instead of N sequential
      INSERT calls, reducing DB round-trips proportionally.
    * Dedup uses fingerprinted fact strings (normalised lowercase) instead of
      raw 30-char prefixes, catching more near-duplicates.
    """

    # ------------------------------------------------------------------
    # extract_and_store
    # ------------------------------------------------------------------
    async def extract_and_store(
        self,
        pool: Any,
        user_id: str,
        message: str,
        pii_entities: list[str],
    ) -> list[str]:
        """
        Extract factual statements from *message* and persist each as a memory
        chunk in user_memory.

        Parameters
        ----------
        pool:         asyncpg connection pool
        user_id:      user UUID string
        message:      original (non-redacted) message text
        pii_entities: list of Presidio entity types already detected in message

        Returns
        -------
        List of memory_text strings actually stored this call.
        Empty list if nothing worth storing (question, greeting, duplicate).
        """
        stripped = message.strip()

        # ── Pre-flight: skip pure questions unless they contain PII ──────────
        if stripped.endswith("?") and not pii_entities:
            return []

        # ── Pre-flight: skip short greetings with no PII ─────────────────────
        if len(stripped) < 10 and not pii_entities:
            return []

        # ── Fetch existing memories (cache-first) for dedup ──────────────────
        existing = _cache_get(user_id)
        if existing is None:
            existing = await self.get_memories(pool, user_id)

        existing_fps: set[str] = {_fingerprint(m) for m in existing}

        # ── Step A: Regex fact extraction ─────────────────────────────────────
        all_facts: list[str] = _extract_facts(message)
        regex_produced_facts = bool(all_facts)

        # ── Step B: Document-level PII facts (non-regex entities only) ────────
        for entity_type, fact_text in _DOCUMENT_ENTITY_FACTS.items():
            if entity_type not in pii_entities:
                continue
            # Skip when a richer regex fact already covers this entity category
            if regex_produced_facts and entity_type in _REGEX_COVERED_ENTITIES:
                continue
            all_facts.append(fact_text)

        # ── Step C: Catch-all fallback ─────────────────────────────────────────
        if not all_facts:
            for clause in _CLAUSE_SPLIT.split(message):
                clause = clause.strip()
                lower = clause.lower()
                if lower.startswith("i ") and len(lower) > 10 and not _is_noisy_catchall(lower):
                    fact = "User " + clause[2:].strip().rstrip(".,;")
                    if len(fact) > 8:
                        all_facts.append(fact)

        # ── Dedup ─────────────────────────────────────────────────────────────
        new_facts: list[str] = []
        for fact in all_facts:
            fact = fact.strip()
            if not fact:
                continue
            fp = _fingerprint(fact)
            if fp in existing_fps:
                continue
            existing_fps.add(fp)
            new_facts.append(fact)

        if not new_facts:
            return []

        # ── Batch INSERT ──────────────────────────────────────────────────────
        rows = [
            (user_id, fact, message, pii_entities)
            for fact in new_facts
        ]
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO user_memory (user_id, memory_text, source_msg, pii_detected)
                VALUES ($1, $2, $3, $4)
                """,
                rows,
            )

        # Invalidate cache so the next get_memories call reflects the new rows
        _cache_invalidate(user_id)

        logger.debug(
            "Stored %d memories for user %s: %s",
            len(new_facts), user_id, new_facts,
        )
        return new_facts

    # ------------------------------------------------------------------
    # get_memories
    # ------------------------------------------------------------------
    async def get_memories(
        self,
        pool: Any,
        user_id: str,
        *,
        limit: int | None = None,
    ) -> list[str]:
        """
        Retrieve all memory chunks for user_id ordered oldest-first.

        Results are cached in-process to avoid repeated DB round-trips within
        the same request burst.  The cache is invalidated by extract_and_store()
        on every successful write.

        Parameters
        ----------
        pool:    asyncpg connection pool
        user_id: user UUID string
        limit:   optional cap on returned memories (newest-first slice when set)
        """
        cached = _cache_get(user_id)
        if cached is not None:
            return cached if limit is None else cached[-limit:]

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT memory_text
                FROM   user_memory
                WHERE  user_id = $1
                ORDER  BY created_at ASC
                """,
                user_id,
            )

        memories = [row["memory_text"] for row in rows]
        _cache_set(user_id, memories)
        return memories if limit is None else memories[-limit:]

    # ------------------------------------------------------------------
    # get_memory_count
    # ------------------------------------------------------------------
    async def get_memory_count(self, pool: Any, user_id: str) -> int:
        """
        Return the total number of stored memory chunks for this user.

        Uses the in-process cache when warm to avoid a COUNT(*) query.
        """
        cached = _cache_get(user_id)
        if cached is not None:
            return len(cached)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM user_memory WHERE user_id = $1",
                user_id,
            )
        return int(row["cnt"]) if row else 0

    # ------------------------------------------------------------------
    # clear_memories
    # ------------------------------------------------------------------
    async def clear_memories(self, pool: Any, user_id: str) -> None:
        """
        Delete all memory, chat history, and freeze log for this user.
        Used by the demo reset endpoint (DELETE /chat/state/{user_id}).
        """
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM user_memory        WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM chat_log           WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM consent_freeze_log WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM consent_records    WHERE user_id = $1", user_id)

        # Clear in-process cache for this user
        _cache_invalidate(user_id)
        logger.info("Cleared all memory, chat, and consent records for user %s", user_id)

    # ------------------------------------------------------------------
    # get_state
    # ------------------------------------------------------------------
    async def get_state(
        self,
        pool: Any,
        user_id: str,
        frozen: bool,
        frozen_at_count: int | None,
    ) -> dict[str, Any]:
        """
        Return a full state dict for the frontend polling endpoint.

        Shape matches the MemoryState TypeScript interface:
        {
          "user_id":          str,
          "memories":         list[str],
          "memory_count":     int,
          "frozen":           bool,
          "frozen_at_count":  int | None,
        }
        """
        memories = await self.get_memories(pool, user_id)
        return {
            "user_id":         user_id,
            "memories":        memories,
            "memory_count":    len(memories),
            "frozen":          frozen,
            "frozen_at_count": frozen_at_count,
        }


# ── Singleton ──────────────────────────────────────────────────────────────────

memory_store = MemoryStore()