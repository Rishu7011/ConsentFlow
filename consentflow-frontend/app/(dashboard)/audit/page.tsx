"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/axios";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { timeAgo, GATE_COLORS } from "@/lib/utils";
import type { AuditEntry } from "@/lib/types";

const GATE_OPTIONS = ["all", "training_gate", "dataset_gate", "inference_gate", "monitoring_gate"];
const LIMIT_OPTIONS = [10, 25, 50, 100];

export default function AuditPage() {
  const [userId, setUserId] = useState("");
  const [gate, setGate] = useState("all");
  const [limit, setLimit] = useState(25);

  const params = new URLSearchParams({ limit: String(limit) });
  if (userId) params.set("user_id", userId);
  if (gate !== "all") params.set("gate_name", gate);

  const { data: raw, isLoading } = useQuery<AuditEntry[]>({
    queryKey: ["audit", userId, gate, limit],
    queryFn: () => api.get(`/audit?${params}`).then((r) => Array.isArray(r.data) ? r.data : r.data?.entries ?? []),
    refetchInterval: 10000,
  });
  const entries = raw ?? [];

  const selectStyle = {
    background: "var(--cf-surface2)",
    border: "1px solid var(--cf-border)",
    color: "var(--cf-text)",
    borderRadius: "8px",
    padding: "6px 12px",
    fontSize: "13px",
    outline: "none",
  } as React.CSSProperties;

  return (
    <TooltipProvider>
      <div className="space-y-6 max-w-7xl">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Audit Trail</h1>
          <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Full compliance log of all gate decisions</p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Filter by user_id…"
            className="px-4 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)", width: "260px" }}
          />
          <select value={gate} onChange={(e) => setGate(e.target.value)} style={selectStyle}>
            {GATE_OPTIONS.map((g) => <option key={g} value={g}>{g === "all" ? "All gates" : g}</option>)}
          </select>
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} style={selectStyle}>
            {LIMIT_OPTIONS.map((l) => <option key={l} value={l}>{l} rows</option>)}
          </select>
        </div>

        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--cf-border)" }}>
          {isLoading ? (
            <div className="p-4 space-y-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow style={{ background: "var(--cf-surface2)", borderColor: "var(--cf-border)" }}>
                  {["Time", "Gate", "Action", "Consent", "PII", "Trace ID"].map((h) => (
                    <TableHead key={h} className="text-xs" style={{ color: "var(--cf-muted)" }}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((e) => {
                  const actionColor =
                    e.action_taken.includes("blocked") || e.action_taken.includes("frozen")
                      ? "var(--cf-coral)"
                      : e.action_taken.includes("flagged") || e.action_taken.includes("warning")
                      ? "var(--cf-amber)"
                      : "var(--cf-teal)";
                  const hasPii = !!(e.metadata as Record<string, unknown>)?.pii_redacted;
                  return (
                    <TableRow key={e.id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                      <TableCell className="text-xs whitespace-nowrap" style={{ color: "var(--cf-muted)" }}>{timeAgo(e.event_time)}</TableCell>
                      <TableCell>
                        <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ background: `${GATE_COLORS[e.gate_name] ?? "#7c6dfa"}20`, color: GATE_COLORS[e.gate_name] ?? "#7c6dfa" }}>
                          {e.gate_name}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs font-mono" style={{ color: actionColor }}>{e.action_taken}</TableCell>
                      <TableCell>
                        <Badge style={{ fontSize: "10px", background: e.consent_status === "granted" ? "rgba(62,207,178,0.15)" : "rgba(250,109,138,0.15)", color: e.consent_status === "granted" ? "var(--cf-teal)" : "var(--cf-coral)", border: "none" }}>
                          {e.consent_status}
                        </Badge>
                      </TableCell>
                      <TableCell>{hasPii && <span style={{ color: "var(--cf-purple)" }}>🛡 PII</span>}</TableCell>
                      <TableCell>
                        {e.trace_id && (
                          <Tooltip>
                            <TooltipTrigger>
                              <span className="text-xs font-mono" style={{ color: "var(--cf-muted)" }}>{e.trace_id.slice(0, 12)}…</span>
                            </TooltipTrigger>
                            <TooltipContent style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}>
                              {e.trace_id}
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
