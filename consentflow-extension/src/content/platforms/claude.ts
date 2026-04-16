/**
 * claude.ts — Claude.ai platform DOM selectors and contenteditable input helpers.
 *
 * Step 4 of the ConsentFlow Privacy Shield build.
 */

import type { PlatformConfig } from './index';

export const CLAUDE: PlatformConfig = {
  inputSelector: '[contenteditable="true"].ProseMirror',
  sendButton: '[aria-label="Send message"]',
  responseContainer: '[data-is-streaming]',
  streamingClass: 'streaming',
  inputType: 'contenteditable',
};

/**
 * Read the current text from a contenteditable element.
 */
export function getInputText(el: HTMLElement): string {
  return el.innerText;
}

/**
 * Set text on a contenteditable element and fire a synthetic 'input' event
 * so the page's framework (ProseMirror) can react to the change.
 */
export function setInputText(el: HTMLElement, text: string): void {
  el.focus();
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
  const dataTransfer = new DataTransfer();
  dataTransfer.setData('text/plain', text);
  const pasteEvent = new ClipboardEvent('paste', {
    clipboardData: dataTransfer,
    bubbles: true,
    cancelable: true,
  });
  el.dispatchEvent(pasteEvent);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
