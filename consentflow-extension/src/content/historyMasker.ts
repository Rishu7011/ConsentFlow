/**
 * historyMasker.ts — Mask PII inside existing + newly added user messages.
 *
 * Goal: ensure the full chat transcript (USER bubbles) never contains raw PII,
 * so the model can't "reuse" something it saw earlier even if a prior intercept failed.
 *
 * HARD RULE: we never send real PII to the backend from here.
 */

import { detectAndReplace } from '../utils/dummyGenerator';
import { vault } from '../vault/vault';

export interface HistoryMaskerOptions {
  /** Selector that matches a single user message container. */
  userMessageSelector?: string;
  /**
   * How many most-recent user messages to mask.
   * - 1: only the latest user message
   * - N: last N user messages
   * - 'all': mask all user messages (default)
   */
  limit?: number | 'all';
}

const DEFAULT_USER_SELECTOR = '[data-message-author-role="user"]';

function maskTextInUserBubble(el: HTMLElement): number {
  const raw = el.innerText || el.textContent || '';
  if (!raw.trim()) return 0;

  // Detect originals using placeholders (no dummies generated here).
  const { anonymized, mappings } = detectAndReplace(raw, 'placeholder');
  if (mappings.length === 0) return 0;

  // Replace each placeholder with a stable dummy derived from the original.
  let masked = anonymized;
  for (const m of mappings) {
    const dummy = vault.getOrCreateDummy(m.original);
    masked = masked.split(m.placeholder).join(dummy);
  }

  // Write masked text back. This is a UI-only rewrite; it prevents later reuse.
  // We intentionally keep it simple: set textContent to avoid rich text quirks.
  if (masked !== raw) {
    el.textContent = masked;
  }

  return mappings.length;
}

/**
 * Attach a MutationObserver that keeps user messages masked.
 * Returns a cleanup function.
 */
export function attachHistoryMasker(options: HistoryMaskerOptions = {}): () => void {
  const selector = options.userMessageSelector ?? DEFAULT_USER_SELECTOR;
  const limit = options.limit ?? 'all';

  const maskRelevant = (root: ParentNode) => {
    const all = Array.from(root.querySelectorAll<HTMLElement>(selector));
    const targets =
      limit === 'all'
        ? all
        : all.slice(Math.max(0, all.length - Math.max(1, limit)));
    for (const el of targets) {
      maskTextInUserBubble(el);
    }
  };

  // Initial pass.
  maskRelevant(document);

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type !== 'childList') continue;
      for (const node of m.addedNodes) {
        if (!(node instanceof HTMLElement)) continue;

        // Direct match
        if (node.matches?.(selector)) {
          maskTextInUserBubble(node);
          continue;
        }

        // Descendants
        // For limited mode, re-evaluate from document to keep "last N" correct.
        if (limit === 'all') {
          node.querySelectorAll?.(selector).forEach((el) => {
            if (el instanceof HTMLElement) maskTextInUserBubble(el);
          });
        } else {
          maskRelevant(document);
        }
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}

