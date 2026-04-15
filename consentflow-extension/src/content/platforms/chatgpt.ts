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
 * Read the current text from a textarea element.
 */
export function getInputText(el: HTMLElement): string {
  return (el as HTMLTextAreaElement).value;
}

/**
 * Set text on a textarea element and fire a native 'input' event so that
 * React's synthetic event system picks up the change.
 */
export function setInputText(el: HTMLElement, text: string): void {
  (el as HTMLTextAreaElement).value = text;
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
