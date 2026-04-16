/**
 * dummyGenerator.ts — Offline PII detection and placeholder/dummy substitution.
 *
 * Step 2 of the ConsentFlow Privacy Shield build.
 *
 * Two modes:
 *   'placeholder' — replaces PII with tokens like [PERSON_1]. Used when calling backend.
 *   'direct'      — replaces PII immediately with realistic dummy values. Used offline.
 */

// ─── Types ──────────────────────────────────────────────────────────────────

export interface PiiMapping {
  /** The original PII value found in the text */
  original: string;
  /** The placeholder token e.g. [PERSON_1] */
  placeholder: string;
  /** The realistic dummy value (filled after backend responds, or in direct mode) */
  dummy: string;
  /** Entity type e.g. PERSON, PHONE_NUMBER */
  type: string;
}

export interface DetectAndReplaceResult {
  /** Text with PII removed (either placeholder tokens or dummy values) */
  anonymized: string;
  /** One entry per PII match */
  mappings: PiiMapping[];
}

// ─── Redaction strategy ───────────────────────────────────────────────────────

/**
 * Types where we intentionally use a non-semantic dummy token.
 *
 * Rationale: realistic-looking dummies (e.g. 9000000000) still reveal the *kind*
 * of data shared (phone number), which can cause the model to describe it.
 */
const NON_SEMANTIC_DUMMY_TYPES = new Set<SupportedType>([
  'PERSON',
  'PHONE_NUMBER',
  'EMAIL_ADDRESS',
  'IN_AADHAAR',
  'IN_PAN',
  'UPI_ID',
]);

function makeRedactedDummy(counter: number): string {
  // Unique per match, but does not encode entity type.
  return `⟦REDACTED_${counter}⟧`;
}

// ─── Supported types (order matters — applied in this exact sequence) ────────

export const SUPPORTED_TYPES = [
  'PERSON',
  'EMAIL_ADDRESS',
  'IN_AADHAAR',
  'IN_PAN',
  'PHONE_NUMBER',
  'UPI_ID',
] as const;

export type SupportedType = (typeof SUPPORTED_TYPES)[number];

// ─── Pattern definitions ─────────────────────────────────────────────────────

interface PatternDef {
  type: SupportedType;
  /** Factory — called each time so the lastIndex resets properly */
  regex: () => RegExp;
  dummy: string;
}

const PATTERNS: PatternDef[] = [
  {
    type: 'PERSON',
    regex: () => /\b[A-Z][a-z]+\s[A-Z][a-z]+\b/g,
    dummy: 'Alex Smith',
  },
  {
    type: 'EMAIL_ADDRESS',
    // Must come before UPI_ID to win on foo@gmail.com
    regex: () => /[\w.+-]+@[\w-]+\.[a-z]{2,}/gi,
    dummy: 'user@example.com',
  },
  {
    type: 'IN_AADHAAR',
    regex: () => /\b\d{4}\s\d{4}\s\d{4}\b/g,
    dummy: 'XXXX XXXX XXXX',
  },
  {
    type: 'IN_PAN',
    regex: () => /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g,
    dummy: 'AAAAA0000A',
  },
  {
    type: 'PHONE_NUMBER',
    // Indian mobile numbers; supports optional +91 and spaced/dashed formats.
    regex: () => /\b(?:\+91[\-\s]?)?[6-9]\d{4}[\s\-]?\d{5}\b/g,
    dummy: '9000000000',
  },
  {
    type: 'UPI_ID',
    regex: () => /\b[\w.\-]+@[\w]+\b/g,
    dummy: 'user@upi',
  },
];

// ─── Main function ────────────────────────────────────────────────────────────

/**
 * Detect PII in `text` and either replace with placeholder tokens or dummy values.
 *
 * @param text          - Raw user input
 * @param mode          - 'placeholder' builds [TYPE_N] tokens; 'direct' inserts dummies inline
 * @param enabledTypes  - Optional allow-list; if omitted all SUPPORTED_TYPES are active
 */
export function detectAndReplace(
  text: string,
  mode: 'placeholder' | 'direct',
  enabledTypes?: string[],
): DetectAndReplaceResult {
  const activeTypes = new Set<string>(enabledTypes ?? SUPPORTED_TYPES);

  // Global counter across all types within this single call
  let counter = 0;

  // We collect all raw matches first, then sort by position so we can do a
  // single left-to-right replacement pass (avoids index drift from repeated
  // String.replace calls).
  interface RawMatch {
    start: number;
    end: number;
    original: string;
    type: SupportedType;
    dummy: string;
  }

  const rawMatches: RawMatch[] = [];

  // Phrase-level redaction: remove semantic cues like "my phone number is" so the model
  // cannot describe the category of PII even if the value is masked.
  if (activeTypes.has('PERSON')) {
    const namePhrases = [
      /\bmy\s+name\s+is\s+[A-Z][a-z]{1,30}\b/gi,
      /\b(?:i\s+am|i'?m|this\s+is)\s+[A-Z][a-z]{1,30}\b/g,
    ];
    for (const re of namePhrases) {
      let m: RegExpExecArray | null;
      while ((m = re.exec(text)) !== null) {
        rawMatches.push({
          start: m.index,
          end: m.index + m[0].length,
          original: m[0],
          type: 'PERSON',
          dummy: 'Alex Smith',
        });
      }
    }
  }

  if (activeTypes.has('PHONE_NUMBER')) {
    const phonePhrase =
      /\b(?:my\s+)?(?:phone|mobile)\s*(?:number\s*)?(?:is|:)\s*(?:\+91[\-\s]?)?[6-9]\d{4}[\s\-]?\d{5}\b/gi;
    let m: RegExpExecArray | null;
    while ((m = phonePhrase.exec(text)) !== null) {
      rawMatches.push({
        start: m.index,
        end: m.index + m[0].length,
        original: m[0],
        type: 'PHONE_NUMBER',
        dummy: '9000000000',
      });
    }
  }

  // Heuristic PERSON detection for single names in common self-identification phrases.
  // This intentionally extracts ONLY the name token, not the whole phrase.
  if (activeTypes.has('PERSON')) {
    const singleName = /\b(?:my\s+name\s+is|i\s+am|i'?m|this\s+is)\s+([A-Z][a-z]{1,30})\b/g;
    let m: RegExpExecArray | null;
    while ((m = singleName.exec(text)) !== null) {
      const name = m[1];
      const start = (m.index ?? 0) + m[0].lastIndexOf(name);
      rawMatches.push({
        start,
        end: start + name.length,
        original: name,
        type: 'PERSON',
        dummy: 'Alex Smith',
      });
    }
  }

  for (const pattern of PATTERNS) {
    if (!activeTypes.has(pattern.type)) continue;

    const regex = pattern.regex();
    let m: RegExpExecArray | null;

    while ((m = regex.exec(text)) !== null) {
      rawMatches.push({
        start: m.index,
        end: m.index + m[0].length,
        original: m[0],
        type: pattern.type,
        dummy: pattern.dummy,
      });
    }
  }

  // Sort by start position
  rawMatches.sort((a, b) => (a.start - b.start) || (b.end - a.end));

  // Remove overlapping matches (keep the first / leftmost)
  const nonOverlapping: RawMatch[] = [];
  let cursor = 0;
  for (const match of rawMatches) {
    if (match.start >= cursor) {
      nonOverlapping.push(match);
      cursor = match.end;
    }
  }

  // Build result
  const mappings: PiiMapping[] = [];
  let result = '';
  let textCursor = 0;

  for (const match of nonOverlapping) {
    counter++;
    const placeholder = `[${match.type}_${counter}]`;
    const dummyValue =
      mode === 'direct'
        ? (NON_SEMANTIC_DUMMY_TYPES.has(match.type) ? makeRedactedDummy(counter) : match.dummy)
        : '';

    mappings.push({
      original: match.original,
      placeholder,
      dummy: dummyValue,
      type: match.type,
    });

    // Append the unchanged text before this match
    result += text.slice(textCursor, match.start);
    // Append either the placeholder token or the dummy value
    result += mode === 'placeholder' ? placeholder : dummyValue;
    textCursor = match.end;
  }

  // Append any remaining text
  result += text.slice(textCursor);

  return { anonymized: result, mappings };
}
