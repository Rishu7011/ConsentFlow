"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

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
    .catch(err => console.error(err))