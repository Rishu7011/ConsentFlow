/**
 * chatgpt.ts — ChatGPT platform DOM selectors and textarea input helpers.
 *
 * Step 4 of the ConsentFlow Privacy Shield build.
 */

import type { PlatformConfig } from './index';

export const CHATGPT: PlatformConfig = {
  inputSelector: '#prompt-textarea',
  sendButton: '[data-testid="send-button"]',
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
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    el.value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  } else {
    el.focus();
    
    // First try the execCommand approach
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    selection?.removeAllRanges();
    selection?.addRange(range);
    
    try {
      document.execCommand('insertText', false, text);
    } catch (e) {
      // Ignore
    }

    // Modern ProseMirror fallback: emit a native paste event!
    // This perfectly mimics a user pasting text, which React and ProseMirror intercept.
    const dataTransfer = new DataTransfer();
    dataTransfer.setData('text/plain', text);
    const pasteEvent = new ClipboardEvent('paste', {
      clipboardData: dataTransfer,
      bubbles: true,
      cancelable: true,
    });
    el.dispatchEvent(pasteEvent);
    
    // Final fallback to trigger any remaining React onChange listeners
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
}
