"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/axios";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { timeAgo, PII_COLORS } from "@/lib/utils";
import type { ChatMessage, MemoryState } from "@/lib/types";

export default function ChatHistoryPage() {
  const [filterUser, setFilterUser] = useState("");

  const { data: rawMessages, isLoading } = useQuery<ChatMessage[]>({
    queryKey: ["chat-history", filterUser],
    queryFn: () =>
      api.get(`/chat/history${filterUser ? `?user_id=${filterUser}` : ""}`).then((r) =>
        Array.isArray(r.data) ? r.data : r.data?.entries ?? r.data?.messages ?? []
      ),
    refetchInterval: 10000,
  });

  const { data: memState } = useQuery<MemoryState>({
    queryKey: ["chat-state", filterUser],
    queryFn: () => api.get(`/chat/state/${filterUser || "550e8400-e29b-41d4-a716-446655440000"}`).then((r) => r.data),
    enabled: true,
    refetchInterval: 5000,
  });

  const messages = rawMessages ?? [];

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Chat History</h1>
        <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Full conversation log with PII and training metadata</p>
      </div>

      <div className="flex gap-3 items-center">
        <input
          value={filterUser}
          onChange={(e) => setFilterUser(e.target.value)}
          placeholder="Filter by user_id…"
          className="px-4 py-2 rounded-lg text-sm outline-none w-80"
          style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6">
        {/* Table */}
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--cf-border)" }}>
          {isLoading ? (
            <div className="p-4 space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow style={{ background: "var(--cf-surface2)", borderColor: "var(--cf-border)" }}>
                  {["Time", "Message", "Trained", "PII", "Memories", "Status"].map((h) => (
                    <TableHead key={h} className="text-xs" style={{ color: "var(--cf-muted)" }}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {messages.map((m) => (
                  <TableRow key={m.id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                    <TableCell className="text-xs whitespace-nowrap" style={{ color: "var(--cf-muted)" }}>{timeAgo(m.event_time)}</TableCell>
                    <TableCell className="text-xs max-w-[200px] truncate" style={{ color: "var(--cf-text)" }} title={m.message}>{m.message || m.reply}</TableCell>
                    <TableCell>
                      <Badge style={{ fontSize: "10px", background: m.trained ? "rgba(62,207,178,0.15)" : "rgba(250,109,138,0.15)", color: m.trained ? "var(--cf-teal)" : "var(--cf-coral)", border: "none" }}>
                        {m.trained ? "🟢" : "🔴"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {m.pii_detected.slice(0, 2).map((p) => (
                          <span key={p} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: `${PII_COLORS[p] ?? "#7c6dfa"}20`, color: PII_COLORS[p] ?? "#7c6dfa" }}>{p}</span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs" style={{ color: "var(--cf-muted)" }}>{m.memory_used?.length ?? 0}</TableCell>
                    <TableCell>
                      <Badge style={{ fontSize: "10px", background: m.consent_status === "granted" ? "rgba(62,207,178,0.15)" : "rgba(250,109,138,0.15)", color: m.consent_status === "granted" ? "var(--cf-teal)" : "var(--cf-coral)", border: "none" }}>
                        {m.consent_status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        {/* Memory state panel */}
        <Card className="p-4 h-fit" style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold" style={{ color: "var(--cf-text)" }}>🧠 Memory State</p>
            <Badge style={{ fontSize: "10px", background: memState?.frozen ? "rgba(250,109,138,0.15)" : "rgba(62,207,178,0.15)", color: memState?.frozen ? "var(--cf-coral)" : "var(--cf-teal)", border: "none" }}>
              {memState?.frozen ? "🔴 FROZEN" : "🟢 LEARNING"}
            </Badge>
          </div>
          {memState?.frozen_at_count != null && (
            <p className="text-xs mb-2" style={{ color: "var(--cf-muted)" }}>Frozen at {memState.frozen_at_count} facts</p>
          )}
          <ScrollArea className="h-64">
            <div className="space-y-1.5">
              {(memState?.memories ?? []).map((mem, i) => (
                <div key={i} className="text-xs px-3 py-2 rounded-lg" style={{ background: "var(--cf-surface2)", color: "var(--cf-text)", border: "1px solid var(--cf-border)" }}>
                  {mem}
                </div>
              ))}
              {(memState?.memories ?? []).length === 0 && (
                <p className="text-xs text-center py-4" style={{ color: "var(--cf-muted)" }}>No memories yet</p>
              )}
            </div>
          </ScrollArea>
        </Card>
      </div>
    </div>
  );
}
