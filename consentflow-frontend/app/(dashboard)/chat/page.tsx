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
      .catch(err => console.error(err))