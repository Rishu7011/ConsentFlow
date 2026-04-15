"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo } from "@/lib/utils";
import type { PolicyScanResult, PolicyScanListItem } from "@/lib/types";

const SEVERITY_COLORS: Record<string, { bg: string; color: string }> = {
  low:      { bg: "rgba(62,207,178,0.15)",  color: "var(--cf-teal)" },
  medium:   { bg: "rgba(245,166,35,0.15)",  color: "var(--cf-amber)" },
  high:     { bg: "rgba(250,109,138,0.15)", color: "var(--cf-coral)" },
  critical: { bg: "rgba(250,109,138,0.2)",  color: "var(--cf-coral)" },
};

export default function PolicyPage() {
  const qc = useQueryClient();
  const [integration, setIntegration] = useState("");
  const [policyUrl, setPolicyUrl] = useState("");
  const [policyText, setPolicyText] = useState("");
  const [inputTab, setInputTab] = useState("url");
  const [scanResult, setScanResult] = useState<PolicyScanResult | null>(null);

  const { data: scans, isLoading: scansLoading } = useQuery<PolicyScanListItem[]>({
    queryKey: ["policy-scans"],
    queryFn: () => api.get("/policy").then((r) => Array.isArray(r.data) ? r.data : r.data?.scans ?? []),
  });

  const scan = useMutation({
    mutationFn: () =>
      api.post("/policy", {
        integration_name: integration,
        ...(inputTab === "url" ? { policy_url: policyUrl } : { policy_text: policyText }),
      }).then((r) => r.data),
    onSuccess: (data) => {
      setScanResult(data);
      qc.invalidateQueries({ queryKey: ["policy-scans"] });
      toast.success("Scan complete");
    },
    onError: () => toast.error("Scan failed"),
  });

  const riskColor = scanResult ? SEVERITY_COLORS[scanResult.overall_risk_level] : null;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Policy Scanner</h1>
          <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Scan privacy policies for GDPR risks</p>
        </div>
        <span className="text-xs px-3 py-1.5 rounded-full font-medium" style={{ background: "rgba(62,207,178,0.15)", color: "var(--cf-teal)", border: "1px solid rgba(62,207,178,0.3)" }}>
          Powered by Anthropic Claude
        </span>
      </div>

      {/* Scan form */}
      <Card className="p-5 space-y-4" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
        <div>
          <label className="text-xs mb-1.5 block" style={{ color: "var(--cf-muted)" }}>Integration Name</label>
          <input value={integration} onChange={(e) => setIntegration(e.target.value)} placeholder="e.g. OpenAI, Salesforce…" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
        </div>
        <Tabs value={inputTab} onValueChange={setInputTab}>
          <TabsList style={{ background: "var(--cf-surface2)" }}>
            <TabsTrigger value="url">Policy URL</TabsTrigger>
            <TabsTrigger value="text">Paste Text</TabsTrigger>
          </TabsList>
          <TabsContent value="url" className="mt-3">
            <input value={policyUrl} onChange={(e) => setPolicyUrl(e.target.value)} placeholder="https://example.com/privacy" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
          </TabsContent>
          <TabsContent value="text" className="mt-3">
            <textarea value={policyText} onChange={(e) => setPolicyText(e.target.value)} rows={6} placeholder="Paste privacy policy text here…" className="w-full px-4 py-3 rounded-lg text-sm outline-none resize-none" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
          </TabsContent>
        </Tabs>
        <Button onClick={() => scan.mutate()} disabled={scan.isPending || !integration.trim()} style={{ background: "var(--cf-purple)", color: "white" }}>
          {scan.isPending ? "⏳ Scanning…" : "🔍 Scan for GDPR Risks"}
        </Button>
      </Card>

      {/* Risk banner */}
      {scanResult && riskColor && (
        <div className={`rounded-xl px-5 py-4 ${scanResult.overall_risk_level === "critical" ? "pulse-coral" : ""}`} style={{ background: riskColor.bg, border: `1px solid ${riskColor.color}40` }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-bold text-sm" style={{ color: riskColor.color }}>{scanResult.overall_risk_level.toUpperCase()} RISK — {scanResult.integration_name}</p>
              <p className="text-xs mt-1" style={{ color: "var(--cf-muted)" }}>{scanResult.findings_count} finding{scanResult.findings_count !== 1 ? "s" : ""} · {timeAgo(scanResult.scanned_at)}</p>
            </div>
            <Badge style={{ background: riskColor.bg, color: riskColor.color, border: `1px solid ${riskColor.color}40`, fontSize: "13px", padding: "6px 12px" }}>
              {scanResult.overall_risk_level}
            </Badge>
          </div>
        </div>
      )}

      {/* Findings */}
      {scanResult?.findings?.map((f) => {
        const s = SEVERITY_COLORS[f.severity];
        return (
          <Card key={f.id} className="p-4 space-y-2" style={{ background: "var(--cf-surface)", border: `1px solid ${s?.color ?? "var(--cf-border)"}40` }}>
            <div className="flex items-center gap-3">
              <Badge style={{ fontSize: "10px", background: s?.bg, color: s?.color, border: "none" }}>{f.severity}</Badge>
              <span className="text-sm font-semibold" style={{ color: "var(--cf-text)" }}>{f.category}</span>
              <span className="ml-auto text-xs px-2 py-0.5 rounded" style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", fontFamily: "monospace" }}>{f.article_reference}</span>
            </div>
            <pre className="text-xs p-3 rounded-lg overflow-auto" style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
              {f.clause_excerpt}
            </pre>
            <p className="text-xs leading-relaxed" style={{ color: "var(--cf-text)" }}>{f.explanation}</p>
          </Card>
        );
      })}

      {/* Scan history */}
      {!scansLoading && (scans?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--cf-text)" }}>Scan History</h2>
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--cf-border)" }}>
            <Table>
              <TableHeader>
                <TableRow style={{ background: "var(--cf-surface2)", borderColor: "var(--cf-border)" }}>
                  {["Integration", "Risk", "Findings", "Scanned"].map((h) => (
                    <TableHead key={h} className="text-xs" style={{ color: "var(--cf-muted)" }}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {scans!.map((s) => {
                  const sc = SEVERITY_COLORS[s.overall_risk_level];
                  return (
                    <TableRow key={s.scan_id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                      <TableCell className="text-sm" style={{ color: "var(--cf-text)" }}>{s.integration_name}</TableCell>
                      <TableCell><Badge style={{ fontSize: "10px", background: sc?.bg, color: sc?.color, border: "none" }}>{s.overall_risk_level}</Badge></TableCell>
                      <TableCell className="text-sm" style={{ color: "var(--cf-muted)" }}>{s.findings_count}</TableCell>
                      <TableCell className="text-xs" style={{ color: "var(--cf-muted)" }}>{timeAgo(s.scanned_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}
