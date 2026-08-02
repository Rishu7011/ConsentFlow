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
    .catch(err => console.error(err))