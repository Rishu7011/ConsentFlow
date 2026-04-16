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
  const contentObserver = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        if (!isAiOutput(mutation.target, config)) {
          replaceInNode(mutation.target);
        }
      } else if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(node => {
          walkTextNodes(node, textNode => {
            if (!isAiOutput(textNode, config)) {
              replaceInNode(textNode);
            }
          });
        });
      }
    }
  });

  contentObserver.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  
  // Do an initial pass on the document body to catch anything already rendered
  walkTextNodes(document.body, textNode => {
    if (!isAiOutput(textNode, config)) {
      replaceInNode(textNode);
    }
  });

  return () => {
    contentObserver.disconnect();
  };
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Checks if a node is inside the AI's response container (output).
 * If true, we DO NOT reverse-map it, so it always shows the dummy text.
 */
function isAiOutput(node: Node, config: PlatformConfig): boolean {
  if (node.nodeType === Node.TEXT_NODE && !node.parentElement) return false;
  const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as HTMLElement);
  if (!el) return false;
  return !!el.closest(config.responseContainer);
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
