export interface MemoryState {
  user_id: string;
  memories: string[];
  memory_count: number;
  frozen: boolean;
  frozen_at_count: number | null;
}

export interface ChatMessage {
  id: string;
  event_time: string;
  user_id: string;
  message: string;
  message_redacted: string;
  reply: string;
  trained: boolean;
  memory_used: string[];
  pii_detected: string[];
  consent_status: "granted" | "revoked";
}

export interface ChatResponse {
  reply: string;
  trained_on_message: boolean;
  consent_status: string;
  pii_detected: string[];
  message_redacted: string;
  memories_used: string[];
  memory_state: MemoryState;
}

export interface AuditEntry {
  id: string;
  event_time: string;
  user_id: string;
  gate_name: string;
  action_taken: string;
  consent_status: string;
  purpose: string | null;
  metadata: Record<string, unknown> | null;
  trace_id: string | null;
}

export interface HealthStatus {
  status: string;
  postgres: string;
  redis: string;
}

export interface DashboardStats {
  users: number;
  granted: number;
  blocked: number;
  checks_24h_total: number;
  checks_24h_blocked: number;
  checks_sparkline: number[];
  policy_scans_total: number;
  policy_scans_critical: number;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
  consents: number;
  status: "active" | "revoked" | "pending";
}

export interface ConsentRecord {
  id: string;
  user_id: string;
  data_type: string;
  purpose: string;
  status: "granted" | "revoked";
  updated_at: string;
}

export interface PolicyFinding {
  id: string;
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  clause_excerpt: string;
  explanation: string;
  article_reference: string;
}

export interface PolicyScanResult {
  scan_id: string;
  integration_name: string;
  overall_risk_level: "low" | "medium" | "high" | "critical";
  findings: PolicyFinding[];
  findings_count: number;
  raw_summary: string;
  scanned_at: string;
  policy_url?: string;
}

export interface PolicyScanListItem {
  scan_id: string;
  integration_name: string;
  overall_risk_level: string;
  findings_count: number;
  scanned_at: string;
}
