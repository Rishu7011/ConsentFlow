/**
 * chatgpt.ts — ChatGPT platform DOM selectors and textarea input helpers.
 *
 * Step 4 of the ConsentFlow Privacy Shield build.
 */

import type { PlatformConfig } from './index';

export const CHATGPT: PlatformConfig = {
  // ChatGPT has shipped multiple DOM variants (textarea vs contenteditable).
  // Keep selectors broad and stable across releases.
  inputSelector:
    '#prompt-textarea, textarea#prompt-textarea, [contenteditable="true"]#prompt-textarea',
  sendButton:
    '[data-testid="send-button"], button[aria-label="Send prompt"], button[aria-label="Send message"], button[aria-label="Send Message"]',
  responseContainer: '[data-message-author-role="assistant"]',
  streamingClass: 'result-streaming',
  inputType: 'textarea',
};

/**
 * Read the current text from a textarea or contenteditable element.
 */
export function getInputText(el: HTMLElement): string {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    return el.value;
  }
  return el.innerText || el.textContent || '';
}

/**
 * Set text on a textarea or contenteditable element and fire a native 'input' event.
 */
export function setInputText(el: HTMLElement, text: string): void {
  try {
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      el.value = text;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      el.focus();
      
      const selection = window.getSelection();
      const range = document.createRange();
      
      // Select the inner paragraph if it exists (common in ProseMirror)
      const innerP = el.querySelector('p');
      range.selectNodeContents(innerP || el);
      
      if (selection) {
        selection.removeAllRanges();
        selection.addRange(range);
      }
      
      try {
        // Force delete first, then insert (most reliable for rich text)
        document.execCommand('delete', false, null);
        document.execCommand('insertText', false, text);
      } catch (e) {}

      // Fallback: Dispatch a heavy paste event if execCommand failed
      try {
        const dataTransfer = new DataTransfer();
        dataTransfer.setData('text/plain', text);
        const pasteEvent = new ClipboardEvent('paste', {
          clipboardData: dataTransfer,
          bubbles: true,
          cancelable: true,
        });
        el.dispatchEvent(pasteEvent);
      } catch (e) {}
      
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  } catch (err) {
    console.error('[ConsentFlow] setInputText wrapper error:', err);
  }
}
