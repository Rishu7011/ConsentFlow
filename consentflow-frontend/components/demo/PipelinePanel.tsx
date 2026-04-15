"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";

interface GateStates {
  training: string;
  presidio: string;
  dataset: string;
  inference: string;
  drift: string;
  kafka: string;
  mlflow: string;
  redis: string;
}

interface Props {
  frozen: boolean;
  gateStates: GateStates;
  frozenAt: number | null;
}

const GATES = [
  { id: "training",  icon: "🤖", name: "Training Gate",  activeLabel: "Learning",    frozenLabel: "FROZEN",       activeColor: "#3ecfb2", frozenColor: "#fa6d8a" },
  { id: "presidio",  icon: "🛡", name: "Presidio PII",   activeLabel: "Scanning",    frozenLabel: "Blocking",     activeColor: "#7c6dfa", frozenColor: "#fa6d8a" },
  { id: "dataset",   icon: "🗄", name: "Dataset Gate",   activeLabel: "Active",      frozenLabel: "PII Scrubbed", activeColor: "#3ecfb2", frozenColor: "#fa6d8a" },
  { id: "inference", icon: "⚡", name: "Inference Gate", activeLabel: "Allowed",     frozenLabel: "Blocked 403",  activeColor: "#3ecfb2", frozenColor: "#fa6d8a" },
  { id: "drift",     icon: "📊", name: "Drift Monitor",  activeLabel: "Monitoring",  frozenLabel: "Flagged",      activeColor: "#3ecfb2", frozenColor: "#f5a623" },
];

export function PipelinePanel({ frozen, gateStates, frozenAt }: Props) {
  return (
    <div
      className="flex flex-col h-full rounded-xl border overflow-hidden"
      style={{ background: "var(--cf-surface)", borderColor: "var(--cf-border)" }}
    >
      {/* Header */}
      <div className="px-4 pt-4 pb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚡</span>
          <span className="font-semibold text-sm" style={{ color: "var(--cf-text)" }}>
            Pipeline Gates
          </span>
        </div>
        <div className="h-px mt-3" style={{ background: "var(--cf-border)" }} />
      </div>

      {/* Gate rows */}
      <div className="flex-1 px-3 pb-3 space-y-2 overflow-y-auto">
        {GATES.map((gate) => {
          const isFrozen = frozen;
          const isBorderPulse = gate.id === "training" && frozen;
          return (
            <div
              key={gate.id}
              className={`flex items-center justify-between p-3 rounded-lg border transition-all duration-300 ${isBorderPulse ? "pulse-border-coral" : ""}`}
              style={{ borderColor: isFrozen ? `${gate.frozenColor}40` : "var(--cf-border)" }}
            >
              <div className="flex items-center gap-2">
                <span className="text-base">{gate.icon}</span>
                <div>
                  <p className="text-xs font-medium" style={{ color: "var(--cf-text)" }}>
                    {gate.name}
                  </p>
                  {gate.id === "training" && frozen && frozenAt != null && (
                    <p className="text-xs font-mono" style={{ color: "var(--cf-muted)" }}>
                      frozen at {frozenAt} facts
                    </p>
                  )}
                </div>
              </div>
              <AnimatePresence mode="wait">
                {isFrozen ? (
                  <motion.div key="frozen" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
                    <Badge style={{ background: `${gate.frozenColor}15`, color: gate.frozenColor, border: `1px solid ${gate.frozenColor}40`, fontSize: "10px" }}>
                      🔴 {gate.frozenLabel}
                    </Badge>
                  </motion.div>
                ) : (
                  <motion.div key="active" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
                    <Badge style={{ background: `${gate.activeColor}15`, color: gate.activeColor, border: `1px solid ${gate.activeColor}40`, fontSize: "10px" }}>
                      🟢 {gate.activeLabel}
                    </Badge>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}

        {/* Kafka */}
        <div className="flex items-center justify-between p-3 rounded-lg border" style={{ borderColor: "var(--cf-border)" }}>
          <div className="flex items-center gap-2">
            <span className="text-base">📨</span>
            <div>
              <p className="text-xs font-medium" style={{ color: "var(--cf-text)" }}>Kafka</p>
              <AnimatePresence>
                {frozen && (
                  <motion.p initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="text-xs font-mono" style={{ color: "var(--cf-coral)" }}>
                    consent.revoked published
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          </div>
          <Badge style={{ fontSize: "10px", background: frozen ? "rgba(250,109,138,0.15)" : "rgba(62,207,178,0.15)", color: frozen ? "var(--cf-coral)" : "var(--cf-teal)", border: `1px solid ${frozen ? "rgba(250,109,138,0.4)" : "rgba(62,207,178,0.4)"}` }}>
            {frozen ? "🔴 Event fired" : "🟢 Connected"}
          </Badge>
        </div>

        {/* MLflow */}
        <div className="flex items-center justify-between p-3 rounded-lg border" style={{ borderColor: "var(--cf-border)" }}>
          <div className="flex items-center gap-2">
            <span className="text-base">🧪</span>
            <p className="text-xs font-medium" style={{ color: "var(--cf-text)" }}>MLflow</p>
          </div>
          <Badge style={{ fontSize: "10px", background: frozen ? "rgba(250,109,138,0.15)" : "rgba(62,207,178,0.15)", color: frozen ? "var(--cf-coral)" : "var(--cf-teal)", border: `1px solid ${frozen ? "rgba(250,109,138,0.4)" : "rgba(62,207,178,0.4)"}` }}>
            {frozen ? "🔴 Quarantined" : "🟢 Active"}
          </Badge>
        </div>

        {/* Redis */}
        <div className="flex items-center justify-between p-3 rounded-lg border" style={{ borderColor: "var(--cf-border)" }}>
          <div className="flex items-center gap-2">
            <span className="text-base">⚡</span>
            <div>
              <p className="text-xs font-medium" style={{ color: "var(--cf-text)" }}>Redis Cache</p>
              <AnimatePresence>
                {gateStates.redis === "invalidating" && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs font-mono" style={{ color: "var(--cf-amber)" }}>
                    invalidating…
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          </div>
          <Badge style={{ fontSize: "10px", background: gateStates.redis === "cleared" ? "rgba(250,109,138,0.15)" : "rgba(62,207,178,0.15)", color: gateStates.redis === "cleared" ? "var(--cf-coral)" : "var(--cf-teal)", border: `1px solid ${gateStates.redis === "cleared" ? "rgba(250,109,138,0.4)" : "rgba(62,207,178,0.4)"}` }}>
            {gateStates.redis === "cleared" ? "🔴 Cleared" : "🟢 Cached"}
          </Badge>
        </div>
      </div>
    </div>
  );
}
