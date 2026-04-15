/**
 * reverseMapper.ts — Watch the AI's streaming response and swap dummy values
 * back to real PII values as tokens arrive in the DOM.
 *
 * Step 6 of the ConsentFlow Privacy Shield build.
 *
 * Approach:
 *   1. A top-level MutationObserver watches document.body until the response
 *      container (config.responseContainer) appears.
 *   2. A second observer then watches the container for character and child
 *      changes and calls replaceInNode on every affected text node.
 *   3. A third observer watches the container's attributes so we can detect
 *      when the streaming class is removed and trigger a final full pass.
 */

import { vault } from '../vault/vault';
import type { PlatformConfig } from './platforms/index';

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Start watching for the AI response container and reverse-map dummy tokens
 * back to real values as they appear.
 *
 * @param config    - Platform selectors (responseContainer, streamingClass …)
 * @param _sessionId - Session ID (reserved for future per-session vault lookup)
 * @returns Cleanup function — call to disconnect all MutationObservers.
 */
export function attachReverseMapper(
  config: PlatformConfig,
  _sessionId: string,
): () => void {
  const observers: MutationObserver[] = [];

  // ── Step 1: wait for the response container to appear ────────────────────

  const bodyObserver = new MutationObserver(() => {
    const container = document.querySelector<HTMLElement>(config.responseContainer);
    if (!container) return;

    // Found the container — stop watching document.body.
    bodyObserver.disconnect();

    // ── Step 2: observe the container for content mutations ────────────────
    attachContainerObserver(container, config, observers);
  });

  // Also check immediately in case the container is already there.
  const existing = document.querySelector<HTMLElement>(config.responseContainer);
  if (existing) {
    attachContainerObserver(existing, config, observers);
  } else {
    bodyObserver.observe(document.body, { childList: true, subtree: true });
    observers.push(bodyObserver);
  }

  return () => {
    observers.forEach(o => o.disconnect());
    observers.length = 0;
  };
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Attach mutation observers to a discovered response container.
 * Pushed into the shared `observers` array so the cleanup function can
 * disconnect them all.
 */
function attachContainerObserver(
  container: HTMLElement,
  config: PlatformConfig,
  observers: MutationObserver[],
): void {
  // ── Step 3: content observer (characterData + childList) ──────────────────
  const contentObserver = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        replaceInNode(mutation.target);
      } else if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(node => walkTextNodes(node, replaceInNode));
      }
    }
  });

  contentObserver.observe(container, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  observers.push(contentObserver);

  // ── Step 5: attribute observer — fire a final pass when streaming ends ────
  const attrObserver = new MutationObserver(() => {
    if (!container.classList.contains(config.streamingClass)) {
      // Streaming has ended — do one complete final pass.
      walkTextNodes(container, replaceInNode);
      attrObserver.disconnect();
    }
  });

  attrObserver.observe(container, { attributes: true, attributeFilter: ['class'] });
  observers.push(attrObserver);
}

// ─── Node helpers ─────────────────────────────────────────────────────────────

/**
 * Replace dummy tokens in a single text node.
 * Skips non-text nodes and avoids reassignment when nothing changed
 * (prevents re-triggering the MutationObserver).
 */
export function replaceInNode(node: Node): void {
  if (node.nodeType !== Node.TEXT_NODE) return;

  const current = node.textContent ?? '';
  const replaced = vault.applyTo(current);

  if (replaced !== current) {
    node.textContent = replaced;
  }
}

/**
 * Walk all text-node descendants of `root` and call `visitor` on each.
 */
function walkTextNodes(root: Node, visitor: (node: Node) => void): void {
  if (root.nodeType === Node.TEXT_NODE) {
    visitor(root);
    return;
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode()) !== null) {
    visitor(node);
  }
}
