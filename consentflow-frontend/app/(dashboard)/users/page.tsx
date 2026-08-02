"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo } from "@/lib/utils";
import type { User } from "@/lib/types";

const DEMO_UUID = "550e8400-e29b-41d4-a716-446655440000";

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  active:  { bg: "rgba(62,207,178,0.15)",  color: "var(--cf-teal)" },
  revoked: { bg: "rgba(250,109,138,0.15)", color: "var(--cf-coral)" },
  pending: { bg: "rgba(245,166,35,0.15)",  color: "var(--cf-amber)" },
};

export default function UsersPage() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [open, setOpen] = useState(false);

  const { data: rawUsers, isLoading } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users").then((r) => Array.isArray(r.data) ? r.data : r.data?.users ?? []),
    .catch(err => console.error(err))