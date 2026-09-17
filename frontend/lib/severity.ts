import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import type { InsightSeverity } from "@/types";

/** Shared info/warning/critical treatment — icon + tone name, resolved to left-border + wash
 * classes by whatever renders it (currently just InsightFeed). Centralized so the meaning of
 * each severity looks the same everywhere it appears. */
export const SEVERITY_CONFIG: Record<
  InsightSeverity,
  { icon: typeof Info; label: string; tone: "info" | "warning" | "critical" }
> = {
  info: { icon: Info, label: "Info", tone: "info" },
  warning: { icon: AlertTriangle, label: "Warning", tone: "warning" },
  critical: { icon: ShieldAlert, label: "Critical", tone: "critical" },
};
