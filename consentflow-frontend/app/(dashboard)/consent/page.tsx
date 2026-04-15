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
      const users = Array.isArray(r.data) ? r.data : r.data?.users ?? [];
      if (users.length > 0 && !form.user_id) {
        setForm(p => ({ ...p, user_id: users[0].id }));
      }
      return users;
    }),
  });

  const { data: rawRecords, isLoading } = useQuery<ConsentRecord[]>({
    queryKey: ["consent-records"],
    queryFn: () => api.get("/consent").then((r) => Array.isArray(r.data) ? r.data : r.data?.consents ?? []),
    refetchInterval: 10000,
  });
  const records = rawRecords ?? [];

  const grantConsent = useMutation({
    mutationFn: (f: typeof form) => api.post("/consent", f),
    onSuccess: () => { toast.success("Consent record created"); qc.invalidateQueries({ queryKey: ["consent-records"] }); setOpen(false); },
    onError: () => toast.error("Failed"),
  });

  const revokeConsent = useMutation({
    mutationFn: ({ user_id, purpose }: { user_id: string, purpose: string }) => api.post("/consent/revoke", { user_id, purpose }),
    onSuccess: () => { toast.success("Consent revoked"); qc.invalidateQueries({ queryKey: ["consent-records"] }); },
    onError: () => toast.error("Revoke failed"),
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--cf-text)" }}>Consent Records</h1>
          <p className="text-sm mt-1" style={{ color: "var(--cf-muted)" }}>Grant and revoke data processing consent</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button style={{ background: "var(--cf-teal)", color: "var(--cf-bg)" }}>+ Grant Consent</Button>
          </DialogTrigger>
          <DialogContent style={{ background: "var(--cf-surface)", border: "1px solid var(--cf-border)" }}>
            <DialogHeader><DialogTitle style={{ color: "var(--cf-text)" }}>Grant Consent</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              {[
                { key: "user_id", label: "User ID" },
                { key: "data_type", label: "Data Type" },
                { key: "purpose", label: "Purpose" },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="text-xs mb-1 block" style={{ color: "var(--cf-muted)" }}>{label}</label>
                  <input value={form[key as keyof typeof form]} onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))} className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)", color: "var(--cf-text)" }} />
                </div>
              ))}
              <Button onClick={() => grantConsent.mutate(form)} disabled={grantConsent.isPending} className="w-full" style={{ background: "var(--cf-teal)", color: "var(--cf-bg)" }}>
                {grantConsent.isPending ? "Saving…" : "Grant"}
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
                {["User ID", "Data Type", "Purpose", "Status", "Updated", "Actions"].map((h) => (
                  <TableHead key={h} className="text-xs" style={{ color: "var(--cf-muted)" }}>{h}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((r) => (
                <TableRow key={r.id} style={{ borderColor: "var(--cf-border)", background: "var(--cf-surface)" }}>
                  <TableCell className="text-xs font-mono" style={{ color: "var(--cf-muted)" }}>{r.user_id.slice(0, 8)}…</TableCell>
                  <TableCell className="text-xs" style={{ color: "var(--cf-text)" }}>{r.data_type}</TableCell>
                  <TableCell className="text-xs" style={{ color: "var(--cf-text)" }}>{r.purpose}</TableCell>
                  <TableCell>
                    <Badge style={{ fontSize: "10px", background: r.status === "granted" ? "rgba(62,207,178,0.15)" : "rgba(250,109,138,0.15)", color: r.status === "granted" ? "var(--cf-teal)" : "var(--cf-coral)", border: "none" }}>
                      {r.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs" style={{ color: "var(--cf-muted)" }}>{timeAgo(r.updated_at)}</TableCell>
                  <TableCell>
                    {r.status === "granted" && (
                      <button onClick={() => revokeConsent.mutate({ user_id: r.user_id, purpose: r.purpose })} className="text-xs px-3 py-1.5 rounded-lg" style={{ background: "rgba(250,109,138,0.15)", color: "var(--cf-coral)", border: "1px solid rgba(250,109,138,0.3)" }}>
                        Revoke
                      </button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
