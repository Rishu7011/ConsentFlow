"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const DEMO_UUID = "550e8400-e29b-41d4-a716-446655440000";

const DEFAULT_PAYLOAD = JSON.stringify({
  userId: DEMO_UUID,
  purpose: "model_training",
  consentStatus: "revoked",
  timestamp: new Date().toISOString(),
}, null, 2);

export default function WebhookPage() {
  const [payload, setPayload] = useState(DEFAULT_PAYLOAD);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const fire = useMutation({
    mutationFn: async () => {
      const body = JSON.parse(payload);
      const res = await api.post("/webhook", body);
      return res.data;
    },
    onSuccess: (data) => { setResult(data); toast.success("Webhook fired"); },
    onError: () => toast.error("Webhook failed — check JSON"),
  });

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Webhook Simulator</h1>
        <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Simulate a consent revocation event via webhook</p>
      </div>

      <Card className="p-5 space-y-4" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
        <div>
          <label className="text-xs mb-1.5 block" style={{ color: "var(--cf-muted)" }}>Payload (JSON)</label>
          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            rows={10}
            className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono resize-none"
            style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}
          />
        </div>
        <div className="flex gap-3">
          <Button onClick={() => fire.mutate()} disabled={fire.isPending} style={{ background: "var(--cf-coral)", color: "white" }}>
            {fire.isPending ? "⏳ Firing…" : "🚨 Simulate Revocation"}
          </Button>
          <Button variant="outline" onClick={() => { setPayload(DEFAULT_PAYLOAD); setResult(null); }} style={{ borderColor: "var(--cf-border)", color: "var(--cf-muted)" }}>
            Reset
          </Button>
        </div>
      </Card>

      {result && (
        <Card className="p-5" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
          <p className="text-xs font-semibold mb-2" style={{ color: "var(--cf-muted)" }}>RESPONSE</p>
          {result.kafka_published != null && (
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm">📨 Kafka:</span>
              <span className="text-sm font-semibold" style={{ color: result.kafka_published ? "var(--cf-teal)" : "var(--cf-coral)" }}>
                {result.kafka_published ? "✅ Published" : "❌ Failed"}
              </span>
            </div>
          )}
          <pre className="text-xs overflow-auto rounded-lg p-3" style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", fontFamily: "monospace" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
