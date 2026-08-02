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
    .catch(err => console.error(err))