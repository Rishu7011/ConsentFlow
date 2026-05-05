import { describe, it, expect, beforeEach } from 'vitest';
import { attachHistoryMasker } from './historyMasker';
import { vault } from '../vault/vault';

beforeEach(() => {
  vault.clear();
  document.body.innerHTML = '';
});

describe('attachHistoryMasker', () => {
  it('masks PII inside existing user message bubbles', async () => {
    const userBubble = document.createElement('div');
    userBubble.setAttribute('data-message-author-role', 'user');
    userBubble.textContent = 'My name is Rishabh and my phone number is 9988776655';
    document.body.appendChild(userBubble);

    const cleanup = attachHistoryMasker();
    await new Promise(r => setTimeout(r, 0));

    expect(userBubble.textContent).toContain('⟦REDACTED_');
    expect(userBubble.textContent).not.toContain('Rishabh');
    expect(userBubble.textContent).not.toContain('9988776655');

    cleanup();
  });

  it('masks PII inside newly added user message bubbles', async () => {
    const cleanup = attachHistoryMasker();

    const userBubble = document.createElement('div');
    userBubble.setAttribute('data-message-author-role', 'user');
    userBubble.textContent = 'Phone: 9988776655';
    document.body.appendChild(userBubble);

    await new Promise(r => setTimeout(r, 0));

    expect(userBubble.textContent).toContain('⟦REDACTED_');
    expect(userBubble.textContent).not.toContain('9988776655');

    cleanup();
  });

  it('respects limit: only masks the last 1 user message', async () => {
    const oldBubble = document.createElement('div');
    oldBubble.setAttribute('data-message-author-role', 'user');
    oldBubble.textContent = 'My phone number is 9988776655';
    document.body.appendChild(oldBubble);

    const newBubble = document.createElement('div');
    newBubble.setAttribute('data-message-author-role', 'user');
    newBubble.textContent = 'My name is Rishabh';
    document.body.appendChild(newBubble);

    const cleanup = attachHistoryMasker({ limit: 1 });
    await new Promise(r => setTimeout(r, 0));

    // Only the last bubble should be masked.
    expect(oldBubble.textContent).toContain('9988776655');
    expect(newBubble.textContent).toContain('⟦REDACTED_');
    expect(newBubble.textContent).not.toContain('Rishabh');

    cleanup();
  });
});

