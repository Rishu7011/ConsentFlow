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
import type { ConsentRecord } from "@/lib/types";

export default function ConsentPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ user_id: "", data_type: "pii", purpose: "model_training", status: "granted" });
  const [open, setOpen] = useState(false);

  // Fetch a default user to pre-fill the form
  useQuery({
    queryKey: ["users-for-consent"],
    queryFn: () => api.get("/users").then(r => {
    .catch(err => console.error(err))