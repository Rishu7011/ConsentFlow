"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { PII_ICONS, PII_COLORS } from "@/lib/utils";
import type { MemoryState } from "@/lib/types";

interface Props {
  memoryState: MemoryState | null;
  frozen: boolean;
}

export function MemoryPanel({ memoryState, frozen }: Props) {
  const memories = memoryState?.memories ?? [];

  return (
    <div
      className="memory-panel flex flex-col h-full rounded-xl border transition-colors duration-500 relative overflow-hidden"
      style={{
        background: "var(--cf-surface)",
        borderColor: frozen ? "rgba(250,109,138,0.6)" : "var(--cf-border)",
      }}
    >
      {/* FROZEN stamp — React-controlled so it appears correctly on page refresh.
          Uses AnimatePresence for a spring fade-in matching the original GSAP feel. */}
      <AnimatePresence>
        {frozen && (
          <motion.div
            className="memory-stamp absolute inset-0 flex items-center justify-center pointer-events-none z-10"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 0.9, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.5, ease: [0.175, 0.885, 0.32, 1.275] }}
          >
            <span
              className="text-4xl font-black px-5 py-2 rounded-lg tracking-widest"
              style={{
                color: "var(--cf-coral)",
                border: "3px solid var(--cf-coral)",
                transform: "rotate(-15deg)",
                opacity: 0.9,
              }}
            >
              FROZEN
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-lg">🧠</span>
          <span className="font-semibold text-sm" style={{ color: "var(--cf-text)" }}>
            Memory Bank
          </span>
        </div>
        <AnimatePresence mode="wait">
          {frozen ? (
            <motion.div key="frozen" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}>
              <Badge style={{ background: "rgba(250,109,138,0.15)", color: "var(--cf-coral)", border: "1px solid rgba(250,109,138,0.4)" }}>
                🔴 FROZEN
              </Badge>
            </motion.div>
          ) : (
            <motion.div key="learning" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}>
              <Badge style={{ background: "rgba(62,207,178,0.15)", color: "var(--cf-teal)", border: "1px solid rgba(62,207,178,0.4)" }}>
                🟢 LEARNING
              </Badge>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="px-4 pb-2 flex-shrink-0">
        <div className="h-px w-full" style={{ background: "var(--cf-border)" }} />
        <p className="text-xs mt-2" style={{ color: "var(--cf-muted)" }}>
          {memories.length} fact{memories.length !== 1 ? "s" : ""} known
          {frozen && memoryState?.frozen_at_count != null
            ? ` · frozen at ${memoryState.frozen_at_count}`
            : ""}
        </p>
      </div>

      {/* Memory chips — opacity driven by frozen prop for correct refresh behaviour */}
      <div className="flex-1 px-4 pb-3 overflow-y-auto">
        <div
          className="memory-chips space-y-2"
          style={{ opacity: frozen ? 0.45 : 1, transition: "opacity 0.4s ease" }}
        >
          {memories.length === 0 ? (
            <p className="text-xs py-4 text-center" style={{ color: "var(--cf-muted)" }}>
              No memories yet. Start chatting!
            </p>
          ) : (
            memories.map((mem, i) => {
              const piiKey = Object.keys(PII_ICONS).find((k) =>
                mem.toLowerCase().includes(k.toLowerCase())
              );
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.05 }}
                  className="flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
                  style={{
                    background: "var(--cf-surface2)",
                    border: "1px solid var(--cf-border)",
                    color: "var(--cf-text)",
                  }}
                >
                  {piiKey && (
                    <span
                      className="flex-shrink-0 px-1.5 py-0.5 rounded text-xs font-mono"
                      style={{
                        background: `${PII_COLORS[piiKey]}20`,
                        color: PII_COLORS[piiKey],
                      }}
                    >
                      {PII_ICONS[piiKey]}
                    </span>
                  )}
                  <span className="leading-relaxed">{mem}</span>
                </motion.div>
              );
            })
          )}
        </div>
      </div>

      {/* PII shield row */}
      <div
        className="pii-shield-row px-4 py-3 border-t flex items-center gap-2 flex-shrink-0 transition-colors duration-300"
        style={{
          borderColor: "var(--cf-border)",
          color: frozen ? "var(--cf-coral)" : "var(--cf-muted)",
        }}
      >
        <span className="text-xs">🛡</span>
        <span className="text-xs">
          Presidio: {frozen ? "blocking all new PII" : "scanning all msgs"}
        </span>
      </div>
    </div>
  );
}
