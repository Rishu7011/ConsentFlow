/**
 * platforms/index.ts — Shared PlatformConfig type and platform detection.
 *
 * Step 4 of the ConsentFlow Privacy Shield build.
 */

import { CHATGPT, getInputText as chatgptGetInput, setInputText as chatgptSetInput } from './chatgpt';
import { CLAUDE, getInputText as claudeGetInput, setInputText as claudeSetInput } from './claude';

// ─── Shared type ─────────────────────────────────────────────────────────────

/**
 * Describes the DOM interface for a supported AI chatbot platform.
 * Both CHATGPT and CLAUDE satisfy this type.
 */
export interface PlatformConfig {
  /** CSS selector for the user input element */
  inputSelector: string;
  /** CSS selector for the send / submit button */
  sendButton: string;
  /** CSS selector for the AI response container */
  responseContainer: string;
  /** CSS class present on the container while the AI is still streaming */
  streamingClass: string;
  /** Whether the input is a plain textarea or a contenteditable div */
  inputType: 'textarea' | 'contenteditable';
  /** Read the current text from the input element */
  getInputText: (el: HTMLElement) => string;
  /** Write text into the input element and fire a synthetic input event */
  setInputText: (el: HTMLElement, text: string) => void;
}

// ─── Concrete configs (re-exported for direct use if needed) ─────────────────

export const CHATGPT_CONFIG: PlatformConfig = {
  ...CHATGPT,
  getInputText: chatgptGetInput,
  setInputText: chatgptSetInput,
};

export const CLAUDE_CONFIG: PlatformConfig = {
  ...CLAUDE,
  getInputText: claudeGetInput,
  setInputText: claudeSetInput,
};

// ─── Detection helpers ────────────────────────────────────────────────────────

/**
 * Identify which supported platform the current page belongs to.
 * Returns null if neither is matched.
 */
export function detectPlatform(): 'chatgpt' | 'claude' | null {
  const host = location.hostname;
  if (host.includes('chat.openai.com') || host.includes('chatgpt.com')) return 'chatgpt';
  if (host.includes('claude.ai')) return 'claude';
  return null;
}

/**
 * Return the full PlatformConfig for the current page, or null if the
 * platform is not recognised.
 */
export function getPlatformConfig(): PlatformConfig | null {
  const platform = detectPlatform();
  if (platform === 'chatgpt') return CHATGPT_CONFIG;
  if (platform === 'claude') return CLAUDE_CONFIG;
  return null;
}
