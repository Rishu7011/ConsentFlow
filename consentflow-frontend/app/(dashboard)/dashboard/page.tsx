"use client";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/axios";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo, GATE_COLORS } from "@/lib/utils";
import type { AuditEntry, HealthStatus, DashboardStats } from "@/lib/types";

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: number | string; color: string }) {
  return (
    <Card className="p-5 relative overflow-hidden" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)", borderTop: `3px solid ${color}` }}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium mb-1" style={{ color: "var(--cf-muted)" }}>{label}</p>
          <p className="text-3xl font-bold" style={{ color: "var(--cf-text)" }}>{value}</p>
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get("/dashboard-stats").then((r) => r.data),
    refetchInterval: 15000,
  });
  const { data: health } = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: () => api.get("/health").then((r) => r.data),
    refetchInterval: 10000,
  });
  const { data: auditRaw } = useQuery<AuditEntry[]>({
    queryKey: ["audit-recent"],
    queryFn: () => api.get("/audit?limit=8").then((r) => Array.isArray(r.data) ? r.data : r.data?.entries ?? []),
    refetchInterval: 15000,
  });
  const auditEntries = auditRaw ?? [];

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>ConsentFlow system overview</p>
      </div>

      {/* Health */}
      <div className="flex items-center gap-4 px-4 py-3 rounded-xl" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
        <span className="text-xs font-semibold" style={{ color: "var(--cf-muted)" }}>SYSTEM HEALTH</span>
        {[
          { label: "API", ok: health?.status === "ok" },
          { label: "Postgres", ok: health?.postgres === "ok" },
          { label: "Redis", ok: health?.redis === "ok" },
        ].map((s) => (
          <div key={s.label} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: s.ok ? "var(--cf-teal)" : "var(--cf-coral)" }} />
            <span className="text-xs" style={{ color: "var(--cf-text)" }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Metric cards */}
      {statsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard icon="👤" label="Total Users" value={stats?.users ?? 0} color="var(--cf-purple)" />
          <StatCard icon="✅" label="Active Consents" value={stats?.granted ?? 0} color="var(--cf-teal)" />
          <StatCard icon="🚫" label="Blocked / 24h" value={stats?.checks_24h_blocked ?? 0} color="var(--cf-coral)" />
          <StatCard icon="🧠" label="Memories Stored" value={stats?.checks_24h_total ?? 0} color="var(--cf-purple)" />
          <StatCard icon="🛡" label="PII Detections" value={stats?.policy_scans_total ?? 0} color="var(--cf-amber)" />
          <StatCard icon="⚠️" label="Critical Scans" value={stats?.policy_scans_critical ?? 0} color="var(--cf-coral)" />
        </div>
      )}

      {/* Recent audit */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--cf-text)" }}>Recent Audit Trail</h2>
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--cf-border)" }}>
          <Table>
            <TableHeader>
              <TableRow style={{ background: "var(--cf-surface2)", borderColor: "var(--cf-border)" }}>
                <TableHead className="text-xs" style={{ color: "var(--cf-muted)" }}>Time</TableHead>
                <TableHead className="text-xs" style={{ color: "var(--cf-muted)" }}>Gate</TableHead>
                <TableHead className="text-xs" style={{ color: "var(--cf-muted)" }}>Action</TableHead>
                <TableHead className="text-xs" style={{ color: "var(--cf-muted)" }}>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {auditEntries.map((e) => {
                const actionColor = e.action_taken.includes("blocked") || e.action_taken.includes("frozen")
                  ? "var(--cf-coral)"
                  : e.action_taken.includes("flagged") ? "var(--cf-amber)"
                  : "var(--cf-teal)";
                return (
                  <TableRow key={e.id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                    <TableCell className="text-xs" style={{ color: "var(--cf-muted)" }}>{timeAgo(e.event_time)}</TableCell>
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
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
