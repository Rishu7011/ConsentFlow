/**
 * dummyGenerator.test.ts — Vitest unit tests for detectAndReplace()
 *
 * Run with: npm test
 */

import { describe, it, expect } from 'vitest';
import { detectAndReplace, SUPPORTED_TYPES } from './dummyGenerator';

// ─── placeholder mode ────────────────────────────────────────────────────────

describe('placeholder mode', () => {
  it('replaces PII with placeholder tokens — no original value remains', () => {
    const text = 'My phone is 9876543210 and email is john@example.com';
    const { anonymized, mappings } = detectAndReplace(text, 'placeholder');

    expect(anonymized).not.toContain('9876543210');
    expect(anonymized).not.toContain('john@example.com');
    // Counter is positional (left-to-right in text):
    // phone at index 12 → _1, email at index ~36 → _2
    expect(anonymized).toContain('[PHONE_NUMBER_1]');
    expect(anonymized).toContain('[EMAIL_ADDRESS_2]');

    // dummy field is empty in placeholder mode
    for (const m of mappings) {
      expect(m.dummy).toBe('');
    }
  });

  it('mapping contains the correct original values', () => {
    const text = 'Aadhaar: 1234 5678 9012';
    const { mappings } = detectAndReplace(text, 'placeholder');

    expect(mappings).toHaveLength(1);
    expect(mappings[0].original).toBe('1234 5678 9012');
    expect(mappings[0].type).toBe('IN_AADHAAR');
    expect(mappings[0].placeholder).toBe('[IN_AADHAAR_1]');
  });

  it('returns unchanged text when no PII found', () => {
    const text = 'Hello, how are you?';
    const { anonymized, mappings } = detectAndReplace(text, 'placeholder');

    expect(anonymized).toBe(text);
    expect(mappings).toHaveLength(0);
  });
});

// ─── direct mode ─────────────────────────────────────────────────────────────

describe('direct mode', () => {
  it('replaces PII with dummy values — no original value remains', () => {
    const text = 'My name is 9876543210';
    const { anonymized } = detectAndReplace(text, 'direct');

    expect(anonymized).not.toContain('9876543210');
    // Non-semantic redaction token (unique per match)
    expect(anonymized).toContain('⟦REDACTED_1⟧');
  });

  it('dummy field is populated in direct mode', () => {
    const text = 'PAN: ABCDE1234F';
    const { mappings } = detectAndReplace(text, 'direct');

    expect(mappings[0].dummy).toBe('⟦REDACTED_1⟧');
    expect(mappings[0].original).toBe('ABCDE1234F');
  });

  it('anonymized text uses dummy values, not placeholder tokens', () => {
    const text = 'Aadhaar 1234 5678 9012 here';
    const { anonymized } = detectAndReplace(text, 'direct');

    expect(anonymized).toContain('⟦REDACTED_1⟧');
    expect(anonymized).not.toContain('[IN_AADHAAR');
  });
});

// ─── global counter across types ─────────────────────────────────────────────

describe('global counter', () => {
  it('counter increments across different types within one call', () => {
    // EMAIL comes first in pattern order, PHONE comes 4th
    const text = 'Email: foo@bar.com and phone: 9123456789';
    const { mappings } = detectAndReplace(text, 'placeholder');

    // email should be _1, phone should be _2
    const email = mappings.find((m) => m.type === 'EMAIL_ADDRESS');
    const phone = mappings.find((m) => m.type === 'PHONE_NUMBER');

    expect(email?.placeholder).toBe('[EMAIL_ADDRESS_1]');
    expect(phone?.placeholder).toBe('[PHONE_NUMBER_2]');
  });

  it('two matches of the same type get sequential counters', () => {
    const text = 'Call 9111111111 or 8222222222';
    const { mappings } = detectAndReplace(text, 'placeholder');

    expect(mappings[0].placeholder).toBe('[PHONE_NUMBER_1]');
    expect(mappings[1].placeholder).toBe('[PHONE_NUMBER_2]');
  });
});

// ─── EMAIL_ADDRESS matched before UPI_ID ─────────────────────────────────────

describe('pattern ordering', () => {
  it('foo@gmail.com is classified as EMAIL_ADDRESS, not UPI_ID', () => {
    const text = 'Contact me at foo@gmail.com';
    const { mappings } = detectAndReplace(text, 'placeholder');

    expect(mappings).toHaveLength(1);
    expect(mappings[0].type).toBe('EMAIL_ADDRESS');
  });

  it('UPI ID like user@okaxis is classified as UPI_ID when it has no TLD', () => {
    const text = 'Pay to user@okaxis please';
    const { mappings } = detectAndReplace(text, 'placeholder');

    expect(mappings).toHaveLength(1);
    expect(mappings[0].type).toBe('UPI_ID');
  });
});

// ─── enabledTypes filter ──────────────────────────────────────────────────────

describe('enabledTypes filter', () => {
  it('skips types not in enabledTypes list', () => {
    const text = 'Phone: 9876543210 and Aadhaar: 1234 5678 9012';
    const { mappings } = detectAndReplace(text, 'placeholder', ['PHONE_NUMBER']);

    // Only phone should be detected
    expect(mappings).toHaveLength(1);
    expect(mappings[0].type).toBe('PHONE_NUMBER');
  });

  it('returns no mappings when enabledTypes is empty', () => {
    const text = 'Phone: 9876543210 and email: foo@bar.com';
    const { mappings, anonymized } = detectAndReplace(text, 'placeholder', []);

    expect(mappings).toHaveLength(0);
    expect(anonymized).toBe(text);
  });

  it('handles all SUPPORTED_TYPES when enabledTypes matches full list', () => {
    const text = 'Phone 9876543210 email foo@bar.com pan ABCDE1234F';
    const { mappings } = detectAndReplace(text, 'placeholder', [...SUPPORTED_TYPES]);

    expect(mappings.length).toBeGreaterThanOrEqual(3);
  });
});

// ─── Edge cases ───────────────────────────────────────────────────────────────

describe('edge cases', () => {
  it('handles overlapping patterns by keeping the leftmost match', () => {
    // An Aadhaar number starts at index 0, a phone might be a substring
    const text = '9876 5432 1098';  // looks like Aadhaar (12 digits with spaces)
    const { mappings } = detectAndReplace(text, 'placeholder');

    // Should be classified as IN_AADHAAR, not overlapping PHONE
    expect(mappings.length).toBeGreaterThanOrEqual(1);
    expect(mappings[0].type).toBe('IN_AADHAAR');
  });

  it('preserves text around PII correctly', () => {
    const text = 'Hello 9876543210 world';
    const { anonymized } = detectAndReplace(text, 'direct');

    expect(anonymized.startsWith('Hello ')).toBe(true);
    expect(anonymized.endsWith(' world')).toBe(true);
  });

  it('handles multiple PII in a realistic message', () => {
    const text =
      'Hi, I am Rohan. My Aadhaar is 1234 5678 9012, phone 9876543210, email rohan@example.com, PAN ABCDE1234F';
    const { anonymized, mappings } = detectAndReplace(text, 'placeholder');

    expect(mappings.length).toBeGreaterThanOrEqual(4);
    expect(anonymized).not.toContain('1234 5678 9012');
    expect(anonymized).not.toContain('9876543210');
    expect(anonymized).not.toContain('rohan@example.com');
    expect(anonymized).not.toContain('ABCDE1234F');
  });

  it('detects single-name PERSON in "my name is ..." phrases', () => {
    const text = 'Hello! My name is Rishabh and my phone number is 9988776655.';
    const { anonymized, mappings } = detectAndReplace(text, 'placeholder');

    expect(anonymized).not.toContain('Rishabh');
    expect(anonymized).not.toContain('9988776655');

    const person = mappings.find(m => m.type === 'PERSON');
    const phone = mappings.find(m => m.type === 'PHONE_NUMBER');
    expect(person).toBeTruthy();
    expect(phone).toBeTruthy();
  });
});
