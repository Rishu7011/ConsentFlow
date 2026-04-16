/**
 * reverseMapper.test.ts — Unit tests for reverseMapper.ts
 *
 * Uses vitest + jsdom (configured in vitest.config.ts / vitest.setup.ts).
 *
 * We test the exported `replaceInNode` helper directly, and the full
 * `attachReverseMapper` flow using synthetic DOM nodes + vault population.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { vault } from '../vault/vault';
import { replaceInNode, attachReverseMapper } from './reverseMapper';
import type { PlatformConfig } from './platforms/index';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Build a minimal PlatformConfig stub with a given responseContainer selector
 * and streaming class.
 */
function makeConfig(
  selector = '.response-container',
  streamingClass = 'streaming',
): PlatformConfig {
  return {
    inputSelector: '#input',
    sendButton: '#send',
    responseContainer: selector,
    streamingClass,
    inputType: 'textarea',
    getInputText: (el) => (el as HTMLTextAreaElement).value,
    setInputText: (el, text) => { (el as HTMLTextAreaElement).value = text; },
  };
}

// ─── Setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vault.clear();
  document.body.innerHTML = '';
});

// ─── replaceInNode ────────────────────────────────────────────────────────────

describe('replaceInNode', () => {
  it('replaces a dummy token in a text node', () => {
    vault.store('Alex Smith', 'Rishu Nigam');
    const textNode = document.createTextNode('Hello, Alex Smith!');
    replaceInNode(textNode);
    expect(textNode.textContent).toBe('Hello, Rishu Nigam!');
  });

  it('does not reassign textContent when nothing changes', () => {
    // No dummies in vault → applyTo returns the same string.
    const textNode = document.createTextNode('No PII here');
    const spy = vi.spyOn(textNode, 'textContent', 'set');
    replaceInNode(textNode);
    expect(spy).not.toHaveBeenCalled();
  });

  it('ignores non-text nodes', () => {
    const div = document.createElement('div');
    div.textContent = 'Alex Smith';
    vault.store('Alex Smith', 'Rishu Nigam');
    // Should not throw and should not touch the element's text via nodeType check.
    expect(() => replaceInNode(div)).not.toThrow();
    // div.textContent still has the dummy (no replacement was done on the element itself)
    expect(div.textContent).toBe('Alex Smith');
  });

  it('uses longest-first ordering: "Alex Smith" replaced before "Alex"', () => {
    // Store the shorter token first — vault must still do longest-first.
    vault.store('Alex', 'R');
    vault.store('Alex Smith', 'Rishu Nigam');

    const textNode = document.createTextNode('Alex Smith and Alex');
    replaceInNode(textNode);
    // "Alex Smith" → "Rishu Nigam", then remaining "Alex" → "R"
    expect(textNode.textContent).toBe('Rishu Nigam and R');
  });
});

// ─── attachReverseMapper ──────────────────────────────────────────────────────

describe('attachReverseMapper', () => {
  it('does NOT replace dummy token inside the response container (assistant output stays masked)', async () => {
    vault.store('Alex Smith', 'Rishu Nigam');

    // Create the container and attach before calling attachReverseMapper
    const container = document.createElement('div');
    container.className = 'response-container streaming';
    document.body.appendChild(container);

    const config = makeConfig('.response-container', 'streaming');
    const cleanup = attachReverseMapper(config, 'session-1');

    // Simulate streamed text arriving.
    const textNode = document.createTextNode('Hello Alex Smith');
    container.appendChild(textNode);

    // Allow mutation observer microtasks to flush.
    await new Promise(r => setTimeout(r, 0));

    // Assistant output must remain masked (dummy stays visible).
    expect(textNode.textContent).toBe('Hello Alex Smith');

    cleanup();
  });

  it('does NOT replace dummy token inside a user message bubble (transcript stays masked)', async () => {
    vault.store('⟦REDACTED_1⟧', '9988776655');

    const userBubble = document.createElement('div');
    userBubble.setAttribute('data-message-author-role', 'user');
    document.body.appendChild(userBubble);

    const config = makeConfig('.response-container', 'streaming');
    const cleanup = attachReverseMapper(config, 'session-3');

    const textNode = document.createTextNode('My number is ⟦REDACTED_1⟧');
    userBubble.appendChild(textNode);

    await new Promise(r => setTimeout(r, 0));

    // Must remain masked inside transcript.
    expect(textNode.textContent).toBe('My number is ⟦REDACTED_1⟧');

    cleanup();
  });

  it('does NOT replace dummy token inside the input element (prevents re-leak on send)', async () => {
    vault.store('⟦REDACTED_1⟧', '9988776655');

    const input = document.createElement('div');
    input.id = 'input';
    input.setAttribute('contenteditable', 'true');
    document.body.appendChild(input);

    const config = makeConfig('.response-container', 'streaming');
    const cleanup = attachReverseMapper(config, 'session-4');

    const textNode = document.createTextNode('My number is ⟦REDACTED_1⟧');
    input.appendChild(textNode);

    await new Promise(r => setTimeout(r, 0));

    expect(textNode.textContent).toBe('My number is ⟦REDACTED_1⟧');

    cleanup();
  });

  it('does NOT unmask after streaming class is removed (assistant output stays masked)', async () => {
    vault.store('Jordan Lee', 'Test User');

    const container = document.createElement('div');
    container.className = 'response-container streaming';
    document.body.appendChild(container);

    const config = makeConfig('.response-container', 'streaming');
    const cleanup = attachReverseMapper(config, 'session-2');

    // Add text while still streaming (observer picks it up).
    const textNode = document.createTextNode('Jordan Lee said hello');
    container.appendChild(textNode);

    await new Promise(r => setTimeout(r, 0));

    // Simulate streaming end: remove the streaming class.
    container.classList.remove('streaming');

    await new Promise(r => setTimeout(r, 0));

    expect(textNode.textContent).toBe('Jordan Lee said hello');

    cleanup();
  });
});
