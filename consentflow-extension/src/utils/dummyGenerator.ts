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
    regex: () => /\b[6-9]\d{9}\b/g,
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
  rawMatches.sort((a, b) => a.start - b.start);

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

    mappings.push({
      original: match.original,
      placeholder,
      dummy: mode === 'direct' ? match.dummy : '',
      type: match.type,
    });

    // Append the unchanged text before this match
    result += text.slice(textCursor, match.start);
    // Append either the placeholder token or the dummy value
    result += mode === 'placeholder' ? placeholder : match.dummy;
    textCursor = match.end;
  }

  // Append any remaining text
  result += text.slice(textCursor);

  return { anonymized: result, mappings };
}
