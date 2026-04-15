"use client";
import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";
import { BotIcon } from "lucide-react";

interface Props {
  messages: ChatMessage[];
  input: string;
  setInput: (v: string) => void;
  sending: boolean;
  typing: boolean;
  frozen: boolean;
  onSend: () => void;
}

export function ChatPanel({ messages, input, setInput, sending, typing, frozen, onSend }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  return (
    <div
      className="flex flex-col h-full rounded-xl border overflow-hidden"
      style={{ background: "var(--cf-surface)", borderColor: "var(--cf-border)" }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0" style={{ borderColor: "var(--cf-border)" }}>
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: "var(--cf-purple)" }}><BotIcon/></div>
        <div>
          <p className="font-semibold text-sm" style={{ color: "var(--cf-text)" }}>ConsentFlow AI</p>
          <p className="text-xs flex items-center gap-1" style={{ color: "var(--cf-teal)" }}>
            <span className="w-1.5 h-1.5 rounded-full inline-block animate-pulse" style={{ background: "var(--cf-teal)" }} />
            {frozen ? "Memory frozen" : "Online · learning"}
          </p>
        </div>
        {frozen && (
          <div className="ml-auto px-2 py-1 rounded text-xs font-mono" style={{ background: "rgba(250,109,138,0.15)", color: "var(--cf-coral)", border: "1px solid rgba(250,109,138,0.3)" }}>
            🔴 CONSENT REVOKED
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 px-4 py-4 overflow-y-auto">
        <div className="space-y-1">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="text-4xl mb-3">🧠</div>
              <p className="text-sm font-medium" style={{ color: "var(--cf-text)" }}>Start a conversation</p>
              <p className="text-xs mt-1" style={{ color: "var(--cf-muted)" }}>Every message builds Demo&apos;s memory profile</p>
            </div>
          )}

          {messages.map((msg) => {
            const isUser = msg.user_id !== "ai";
            if (isUser) {
              return (
                <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end mb-4">
                  <div className="max-w-[75%]">
                    <div className="rounded-2xl rounded-tr-sm px-4 py-3 text-sm" style={{ background: "rgba(124,109,250,0.2)", border: "1px solid rgba(124,109,250,0.4)", color: "var(--cf-text)" }}>
                      {msg.consent_status === "revoked" && msg.message_redacted !== msg.message ? (
                        // FE-6: Escape raw HTML before injecting so user-supplied
                        // markup cannot execute. Only <REDACTED> tokens are then
                        // highlighted as styled spans.
                        <span dangerouslySetInnerHTML={{ __html:
                          msg.message_redacted
                            .replace(/&/g, "&amp;")
                            .replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;")
                            .replace(/&lt;REDACTED&gt;/g,
                              `<mark style="background:rgba(250,109,138,0.3);color:var(--cf-coral);padding:0 4px;border-radius:3px;font-family:monospace;font-size:11px">&lt;REDACTED&gt;</mark>`
                            )
                        }} />
                      ) : msg.message}
                    </div>
                    {msg.pii_detected.length > 0 && (
                      <div className="flex gap-1 mt-1 justify-end flex-wrap">
                        {msg.trained ? (
                          <span className="text-xs" style={{ color: "var(--cf-teal)" }}>🔵 PII detected · stored</span>
                        ) : (
                          <span className="text-xs" style={{ color: "var(--cf-coral)" }}>🔴 PII blocked · {msg.pii_detected.slice(0, 2).join(", ")}</span>
                        )}
                        <span className="text-xs" style={{ color: "var(--cf-muted)" }}>{timeAgo(msg.event_time)}</span>
                      </div>
                    )}
                  </div>
                </motion.div>
              );
            }
            return (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 mb-4">
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}>CF</div>
                <div className="max-w-[75%]">
                  <div className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}>
                    {msg.reply}
                  </div>
                  <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2 mt-1 flex-wrap">
                    <AnimatePresence mode="wait">
                      {msg.trained ? (
                        <motion.span key="trained" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs flex items-center gap-1" style={{ color: "var(--cf-teal)" }}>🟢 Memory updated</motion.span>
                      ) : (
                        <motion.span key="blocked" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs flex items-center gap-1" style={{ color: "var(--cf-coral)" }}>🔴 Memory blocked</motion.span>
                      )}
                    </AnimatePresence>
                    <span className="text-xs" style={{ color: "var(--cf-muted)" }}>· {msg.memory_used.length} facts used{!msg.trained ? " (frozen)" : ""}</span>
                    <span className="text-xs" style={{ color: "var(--cf-muted)" }}>· {timeAgo(msg.event_time)}</span>
                  </motion.div>
                </div>
              </motion.div>
            );
          })}

          {/* Typing indicator */}
          {typing && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 mb-4">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}>CF</div>
              <div className="rounded-2xl rounded-tl-sm px-4 py-3" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)" }}>
                <div className="flex gap-1 items-center h-4">
                  {[0, 1, 2].map((i) => (
                    <motion.div key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--cf-muted)" }} animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }} />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t p-3 flex gap-2 flex-shrink-0" style={{ borderColor: "var(--cf-border)" }}>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !sending && onSend()}
          placeholder={frozen ? "Demo is chatting (memory frozen)…" : "Message as Demo…"}
          disabled={sending}
          className="flex-1 rounded-xl px-4 py-2.5 text-sm outline-none transition-colors"
          style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}
        />
        <Button
          id="chat-send-btn"
          onClick={onSend}
          disabled={sending || !input.trim()}
          className="rounded-xl px-4 text-sm font-semibold"
          style={{ background: "var(--cf-purple)", color: "white" }}
        >
          {sending ? "…" : "Send →"}
        </Button>
      </div>
    </div>
  );
}
