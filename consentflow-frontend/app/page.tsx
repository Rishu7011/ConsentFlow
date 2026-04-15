"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import gsap from "gsap";
import { toast } from "sonner";
import { MemoryPanel } from "@/components/demo/MemoryPanel";
import { PipelinePanel } from "@/components/demo/PipelinePanel";
import { ChatPanel } from "@/components/demo/ChatPanel";
import { GATE_COLORS, timeAgo } from "@/lib/utils";
import api from "@/lib/axios";
import type { ChatMessage, MemoryState, AuditEntry, ChatResponse } from "@/lib/types";



const DEFAULT_GATES = {
  training: "active", presidio: "active", dataset: "active",
  inference: "active", drift: "active", kafka: "connected",
  mlflow: "active", redis: "cached",
};

// FE-2 fix: gate states for the frozen/revoked scenario, used to re-hydrate
// the pipeline panel correctly after a page refresh while consent is revoked.
const FROZEN_GATES = {
  training: "frozen", presidio: "blocking", dataset: "scrubbed",
  inference: "blocked", drift: "flagged", kafka: "fired",
  mlflow: "quarantined", redis: "cleared",
};

export default function DemoPage() {
  const [demoUuid, setDemoUuid] = useState<string | null>(null);
  const [frozen, setFrozen] = useState(false);
  const [memoryState, setMemoryState] = useState<MemoryState | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [gateStates, setGateStates] = useState(DEFAULT_GATES);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [typing, setTyping] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Keep containerRef for future GSAP scope use; suppress lint warning
  void containerRef;

  // Fetch demo user on mount
  useEffect(() => {
    api.get("/users").then((res) => {
      const users = Array.isArray(res.data) ? res.data : res.data?.users ?? [];
      if (users.length > 0) {
        setDemoUuid(users[0].id);
        // FE-5: Persist active user so the axios X-User-ID interceptor works
        if (typeof window !== "undefined") {
          sessionStorage.setItem("active_user_id", users[0].id);
        }
      }
    }).catch(() => toast.error("Failed to fetch demo user"));
  }, []);

  // Fetch chat history
  useEffect(() => {
    if (!demoUuid) return;
    api.get(`/chat/history?user_id=${demoUuid}`).then((res) => {
      const history = Array.isArray(res.data) ? res.data : res.data?.entries ?? [];
      const expanded: ChatMessage[] = [];
      history.reverse().forEach((row: any) => {
        expanded.push({
          id: row.id + "-user",
          event_time: row.event_time,
          user_id: row.user_id,
          message: row.message,
          message_redacted: row.message_redacted,
          reply: "",
          trained: row.trained,
          memory_used: row.memory_used ?? [],
          pii_detected: row.pii_detected ?? [],
          consent_status: row.consent_status,
        });
        expanded.push({
          id: row.id + "-ai",
          event_time: row.event_time,
          user_id: "ai",
          message: "",
          message_redacted: "",
          reply: row.reply,
          trained: row.trained,
          memory_used: row.memory_used ?? [],
          pii_detected: [],
          consent_status: row.consent_status,
        });
      });
      setMessages(expanded);
    }).catch(() => toast.error("Failed to load chat history"));
  }, [demoUuid]);

  // Poll memory state every 2s
  useEffect(() => {
    if (!demoUuid) return;
    const poll = async () => {
      try {
        const res = await api.get(`/chat/state/${demoUuid}`);
        setMemoryState(res.data);
        // FE-1 fix: only use consent_status — freeze log existing after restore
        // no longer incorrectly keeps the UI in a frozen state.
        const isFrozen = res.data.consent_status === "revoked";
        setFrozen(isFrozen);
        // FE-2 fix: sync gate states on every poll so a page-refresh while
        // revoked shows the correct frozen pipeline state.
        setGateStates(isFrozen ? FROZEN_GATES : DEFAULT_GATES);
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [demoUuid]);

  // Poll audit log every 3s
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await api.get("/audit?limit=6");
        const entries = Array.isArray(res.data) ? res.data : res.data?.entries ?? [];
        setAuditEntries(entries);
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  const freezeMemoryPanel = useCallback(() => {
    // Animate border + PII shield for the revoke click effect.
    // Stamp and chip opacity are now React-controlled (see MemoryPanel.tsx).
    gsap.to(".memory-panel", { borderColor: "rgba(250,109,138,0.6)", duration: 0.3 });
    gsap.to(".pii-shield-row", { color: "#fa6d8a", duration: 0.3 });
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending || !demoUuid) return;
    const msg = input.trim();
    setInput("");
    setSending(true);
    setTyping(true);

    const optimistic: ChatMessage = {
      id: crypto.randomUUID(),
      event_time: new Date().toISOString(),
      user_id: demoUuid,
      message: msg,
      message_redacted: msg,
      reply: "",
      trained: false,
      memory_used: [],
      pii_detected: [],
      consent_status: frozen ? "revoked" : "granted",
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const res = await api.post<ChatResponse>("/chat/message", {
        user_id: demoUuid, message: msg,
      });
      const data = res.data;
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        { ...optimistic, pii_detected: data.pii_detected, message_redacted: data.message_redacted, trained: data.trained_on_message, consent_status: data.consent_status as "granted" | "revoked" },
        { id: crypto.randomUUID(), event_time: new Date().toISOString(), user_id: "ai", message: "", message_redacted: "", reply: data.reply, trained: data.trained_on_message, memory_used: data.memories_used, pii_detected: [], consent_status: data.consent_status as "granted" | "revoked" },
      ]);
      setMemoryState(data.memory_state);
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      toast.error("Failed to send message");
    } finally {
      setTyping(false);
      setSending(false);
    }
  }, [input, sending, frozen, demoUuid]);

  const handleRevoke = useCallback(async () => {
    if (!demoUuid) return;
    setRevoking(true);
    try {
      await api.post("/webhook", {
        userId: demoUuid,
        purpose: "model_training",
        consentStatus: "revoked",
        timestamp: new Date().toISOString(),
      });
      setFrozen(true);

      const tl = gsap.timeline();
      tl.call(() => setGateStates((g) => ({ ...g, training: "frozen" })))
        .call(() => freezeMemoryPanel(), [], 0.1)
        .call(() => setGateStates((g) => ({ ...g, presidio: "blocking" })), [], 0.2)
        .call(() => setGateStates((g) => ({ ...g, dataset: "scrubbed" })), [], 0.4)
        .call(() => setGateStates((g) => ({ ...g, redis: "invalidating" })), [], 0.5)
        .call(() => setGateStates((g) => ({ ...g, redis: "cleared" })), [], 0.7)
        .call(() => setGateStates((g) => ({ ...g, kafka: "fired" })), [], 0.6)
        .call(() => setGateStates((g) => ({ ...g, inference: "blocked" })), [], 0.8)
        .call(() => setGateStates((g) => ({ ...g, mlflow: "quarantined" })), [], 1.0)
        .call(() => setGateStates((g) => ({ ...g, drift: "flagged" })), [], 1.2)
        .call(() => {
          toast.success("Revocation propagated", {
            description: "✓ Kafka event fired  ✓ Redis cleared  ✓ 5 gates frozen",
            duration: 4000,
          });
        }, [], 1.4);
    } catch {
      toast.error("Revocation failed");
    } finally {
      setRevoking(false);
    }
  }, [freezeMemoryPanel, demoUuid]);

  const handleRestore = useCallback(async () => {
    if (!demoUuid) return;
    try {
      // Just grant consent so the backend allows memory updates again.
      // The backend will automatically clear the freeze log.
      await api.post("/consent", {
        user_id: demoUuid, data_type: "pii",
        purpose: "model_training", status: "granted",
      });
      setFrozen(false);
      setGateStates(DEFAULT_GATES);
      gsap.to(".memory-panel", { borderColor: "rgba(255,255,255,0.07)", duration: 0.3 });
      toast.success("Consent restored", { description: "Memory un-frozen. You can continue chatting!" });
    } catch {
      toast.error("Restore failed");
    }
  }, [demoUuid]);

  const handleReset = useCallback(async () => {
    if (!demoUuid) return;
    try {
      await api.delete(`/chat/state/${demoUuid}`);
      setMessages([]);
      setMemoryState(null);
      setFrozen(false);
      setGateStates(DEFAULT_GATES);
      toast.success("Demo Reset", { description: "Memory & chat wiped clean!" });
    } catch {
      toast.error("Failed to reset demo");
    }
  }, [demoUuid]);

  if (!demoUuid) {
    return <div className="flex h-screen items-center justify-center text-white" style={{ background: "var(--cf-bg)" }}><div className="animate-spin text-4xl">⚙️</div><span className="ml-4">Loading demo user...</span></div>;
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "var(--cf-bg)" }}>
      {/* Top Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b flex-shrink-0" style={{ background: "var(--cf-surface)", borderColor: "var(--cf-border)" }}>
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black" style={{ background: "linear-gradient(135deg,#7c6dfa,#3ecfb2)" }}>CF</div>
          <span className="font-bold text-sm" style={{ background: "linear-gradient(135deg,#7c6dfa,#3ecfb2)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
            ConsentFlow
          </span>
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", border: "1px solid var(--cf-border)" }}>
            GDPR AI Demo
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: frozen ? "var(--cf-coral)" : "var(--cf-teal)" }} />
            <span className="text-xs" style={{ color: frozen ? "var(--cf-coral)" : "var(--cf-teal)" }}>
              {frozen ? "Consent Revoked" : "Consent Active"}
            </span>
          </div>
          <button 
            onClick={handleReset}
            className="text-[10px] uppercase font-bold tracking-wider px-3 py-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors border border-white/10"
          >
            Reset Demo
          </button>
        </div>
      </div>

      {/* Three-column main */}
      <div className="flex-1 grid grid-cols-[1fr_2fr_1fr] gap-3 p-3 overflow-hidden min-h-0">
        <MemoryPanel memoryState={memoryState} frozen={frozen} />
        <ChatPanel messages={messages} input={input} setInput={setInput} sending={sending} typing={typing} frozen={frozen} onSend={handleSend} />
        <PipelinePanel frozen={frozen} gateStates={gateStates} frozenAt={memoryState?.frozen_at_count ?? null} />
      </div>

      {/* Revoke / Restore button */}
      <div className="flex flex-col items-center gap-2 py-3 flex-shrink-0" style={{ borderTop: "1px solid var(--cf-border)" }}>
        <AnimatePresence mode="wait">
          {!frozen ? (
            <motion.button
              key="revoke"
              id="revoke-btn"
              onClick={handleRevoke}
              disabled={revoking}
              className="pulse-coral font-bold text-base px-12 py-3.5 rounded-2xl transition-all disabled:opacity-50 flex items-center gap-3"
              style={{ background: "var(--cf-coral)", color: "white", minWidth: "400px", justifyContent: "center" }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {revoking ? <><span className="animate-spin">⚙️</span> Revoking…</> : <>🚨 REVOKE DEMO&apos;S CONSENT</>}
            </motion.button>
          ) : (
            <motion.button
              key="restore"
              id="restore-btn"
              onClick={handleRestore}
              className="glow-teal font-bold text-base px-12 py-3.5 rounded-2xl transition-all flex items-center gap-3"
              style={{ background: "var(--cf-teal)", color: "var(--cf-bg)", minWidth: "400px", justifyContent: "center" }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              ✅ RESTORE CONSENT
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Audit ticker */}
      <div className="h-10 border-t flex items-center overflow-hidden relative flex-shrink-0" style={{ background: "var(--cf-surface)", borderColor: "var(--cf-border)" }}>
        <div className="absolute left-0 w-12 h-full z-10" style={{ background: "linear-gradient(to right, var(--cf-surface), transparent)" }} />
        <div className="absolute right-0 w-12 h-full z-10" style={{ background: "linear-gradient(to left, var(--cf-surface), transparent)" }} />
        <div className="flex items-center gap-6 px-4 overflow-x-hidden w-full">
          {auditEntries.length === 0 ? (
            <span className="text-xs" style={{ color: "var(--cf-muted)" }}>⏳ Waiting for audit events…</span>
          ) : (
            <AnimatePresence initial={false}>
              {auditEntries.map((entry) => (
                <motion.div
                  key={entry.id}
                  initial={{ opacity: 0, x: 80 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -80 }}
                  className="flex items-center gap-2 flex-shrink-0 text-xs"
                >
                  <span className="px-2 py-0.5 rounded font-mono text-xs" style={{ background: `${GATE_COLORS[entry.gate_name] ?? "#7c6dfa"}20`, color: GATE_COLORS[entry.gate_name] ?? "#7c6dfa" }}>
                    {entry.gate_name}
                  </span>
                  <span style={{ color: "var(--cf-muted)" }}>{entry.action_taken}</span>
                  {!!(entry.metadata as Record<string, unknown>)?.pii_redacted && <span style={{ color: "var(--cf-purple)" }}>🛡 PII</span>}
                  <span style={{ color: "var(--cf-muted)", opacity: 0.5 }}>·</span>
                  <span style={{ color: "var(--cf-muted)", opacity: 0.5 }}>{timeAgo(entry.event_time)}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
