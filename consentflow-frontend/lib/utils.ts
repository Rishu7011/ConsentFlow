import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { formatDistanceToNow } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function timeAgo(dateStr: string): string {
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  } catch {
    return "just now";
  }
}

export const PII_COLORS: Record<string, string> = {
  PERSON:              "#7c6dfa",   // purple
  LOCATION:            "#3ecfb2",   // teal
  AGE:                 "#f5a623",   // amber
  MEDICAL_CONDITION:   "#fa6d8a",   // coral
  FINANCIAL_INFO:      "#f5a623",   // amber
  RELATIONSHIP_STATUS: "#a78bfa",   // light purple
  EMAIL_ADDRESS:       "#38bdf8",   // sky
  PHONE_NUMBER:        "#38bdf8",   // sky
  IN_AADHAAR:          "#fb923c",   // orange
  IN_PAN:              "#fb923c",   // orange
  IN_PHONE:            "#38bdf8",   // sky
  NRP:                 "#c084fc",   // purple
  DATE_TIME:           "#94a3b8",   // slate
};

export const PII_ICONS: Record<string, string> = {
  PERSON:              "👤",
  LOCATION:            "📍",
  AGE:                 "🎂",
  MEDICAL_CONDITION:   "🏥",
  FINANCIAL_INFO:      "💰",
  RELATIONSHIP_STATUS: "💑",
  EMAIL_ADDRESS:       "📧",
  PHONE_NUMBER:        "📞",
  IN_AADHAAR:          "🆔",
  IN_PAN:              "🆔",
  IN_PHONE:            "📞",
  NRP:                 "🌐",
  DATE_TIME:           "📅",
};

export const GATE_COLORS: Record<string, string> = {
  training_gate:   "#7c6dfa",
  dataset_gate:    "#3ecfb2",
  inference_gate:  "#fa6d8a",
  monitoring_gate: "#f5a623",
};

export const SEVERITY_COLORS: Record<string, string> = {
  low:      "#3ecfb2",
  medium:   "#f5a623",
  high:     "#fa6d8a",
  critical: "#fa6d8a",
};
