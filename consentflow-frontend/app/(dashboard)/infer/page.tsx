"use client";
import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const DEMO_UUID = "550e8400-e29b-41d4-a716-446655440000";
const PURPOSES = ["model_training", "analytics", "personalization", "marketing"];

export default function InferPage() {
  const [userId, setUserId] = useState(DEMO_UUID);
  const [purpose, setPurpose] = useState("model_training");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [ms, setMs] = useState<number | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("active_user_id") : null;
    if (stored) setUserId(stored);
  }, []);

  const fire = useMutation({
    mutationFn: async () => {
      const t0 = performance.now();
      try {
        const res = await api.post("/infer", { user_id: userId, purpose });
        setMs(Math.round(performance.now() - t0));
        return res.data;
      } catch (error: any) {
        setMs(Math.round(performance.now() - t0));
        if (error.response && error.response.data) {
          // ConsentMiddleware returns 403 with JSON when blocked
          return error.response.data;
        }
        throw error;
      }
    },
    onSuccess: (data) => setResult(data),
    onError: () => toast.error("Request failed"),
  });

  const allowed = result && (result.allowed === true || result.decision === "allow" || result.status === "allowed");

  const selectStyle = {
    background: "var(--cf-surface2)", border: "1px solid var(--cf-border)",
    color: "var(--cf-text)", borderRadius: "8px", padding: "10px 14px",
    fontSize: "13px", outline: "none", width: "100%",
  } as React.CSSProperties;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Inference Gate</h1>
        <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Test consent-aware inference access control</p>
      </div>

      <Card className="p-5 space-y-4" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
        <div>
          <label className="text-xs mb-1.5 block" style={{ color: "var(--cf-muted)" }}>User ID</label>
          <input value={userId} onChange={(e) => setUserId(e.target.value)} className="w-full px-4 py-2.5 rounded-lg text-sm outline-none font-mono" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
        </div>
        <div>
          <label className="text-xs mb-1.5 block" style={{ color: "var(--cf-muted)" }}>Purpose</label>
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} style={selectStyle}>
            {PURPOSES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <Button onClick={() => fire.mutate()} disabled={fire.isPending} className="w-full py-3 font-semibold" style={{ background: "var(--cf-purple)", color: "white" }}>
          {fire.isPending ? "⏳ Firing…" : "⚡ Fire Request"}
        </Button>
      </Card>

      {result && (
        <Card className={`p-5 ${allowed ? "glow-teal" : "glow-coral"}`} style={{ background: "var(--cf-surface)", border: `2px solid ${allowed ? "var(--cf-teal)" : "var(--cf-coral)"}` }}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-lg font-bold" style={{ color: allowed ? "var(--cf-teal)" : "var(--cf-coral)" }}>
              {allowed ? "✅ ALLOWED" : "🚫 BLOCKED"}
            </p>
            {ms != null && <span className="text-xs font-mono" style={{ color: "var(--cf-muted)" }}>{ms}ms</span>}
          </div>
          {!!(!allowed && (result.blocked_by || result.gate)) && (
            <p className="text-xs mb-3" style={{ color: "var(--cf-coral)" }}>
              Blocked by: <span className="font-mono">{String(result.blocked_by ?? result.gate)}</span>
            </p>
          )}
          <pre className="text-xs overflow-auto rounded-lg p-3" style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", fontFamily: "monospace" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
