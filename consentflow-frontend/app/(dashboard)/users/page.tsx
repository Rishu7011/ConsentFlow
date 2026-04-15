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
    refetchInterval: 15000,
  });
  const users = rawUsers ?? [];

  const createUser = useMutation({
    mutationFn: (e: string) => api.post("/users", { email: e }),
    onSuccess: () => { toast.success("User registered"); qc.invalidateQueries({ queryKey: ["users"] }); setOpen(false); setEmail(""); },
    onError: () => toast.error("Failed to register user"),
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Users</h1>
          <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Manage registered users and consent records</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button style={{ background: "var(--cf-purple)", color: "white" }}>+ Register User</Button>
          </DialogTrigger>
          <DialogContent style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
            <DialogHeader>
              <DialogTitle style={{ color: "var(--cf-text)" }}>Register New User</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
              <Button onClick={() => createUser.mutate(email)} disabled={!email.trim() || createUser.isPending} className="w-full" style={{ background: "var(--cf-purple)", color: "white" }}>
                {createUser.isPending ? "Registering…" : "Register"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--cf-border)" }}>
        {isLoading ? (
          <div className="p-4 space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow style={{ background: "var(--cf-surface2)", borderColor: "var(--cf-border)" }}>
                {["Email", "Status", "Consents", "Created", "Actions"].map((h) => (
                  <TableHead key={h} className="text-xs" style={{ color: "var(--cf-muted)" }}>{h}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => {
                const s = STATUS_STYLE[u.status] ?? STATUS_STYLE.pending;
                return (
                  <TableRow key={u.id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                    <TableCell className="text-sm" style={{ color: "var(--cf-text)" }}>
                      {u.email}
                      {u.id === DEMO_UUID && <span className="ml-2 text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: "rgba(124,109,250,0.15)", color: "var(--cf-purple)" }}>DEMO</span>}
                    </TableCell>
                    <TableCell><Badge style={{ fontSize: "10px", background: s.bg, color: s.color, border: "none" }}>{u.status}</Badge></TableCell>
                    <TableCell className="text-sm" style={{ color: "var(--cf-muted)" }}>{u.consents}</TableCell>
                    <TableCell className="text-xs" style={{ color: "var(--cf-muted)" }}>{timeAgo(u.created_at)}</TableCell>
                    <TableCell>
                      <button
                        onClick={() => { sessionStorage.setItem("active_user_id", u.id); toast.success("Active user set"); }}
                        className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                        style={{ background: "var(--cf-surface2)", color: "var(--cf-muted)", border: "1px solid var(--cf-border)" }}
                      >
                        Set as Demo User
                      </button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
