import { Check, CircleDot, Hourglass, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SignalMeter } from "@/components/ui/signal-meter";
import type { AgentStatus, LLMStatusEvent } from "@/types";

const STATUS_CONFIG: Record<
  AgentStatus,
  {
    label: string;
    tone: "neutral" | "accent" | "warning" | "success" | "critical";
    icon: typeof Check;
  }
> = {
  not_started: { label: "Not started", tone: "neutral", icon: CircleDot },
  running: { label: "Running", tone: "accent", icon: CircleDot },
  waiting_decision: { label: "Waiting for you", tone: "warning", icon: Hourglass },
  done: { label: "Done", tone: "success", icon: Check },
  error: { label: "Error", tone: "critical", icon: TriangleAlert },
};

export function AgentStatusBar({
  agentStatus,
  llmStatus,
  callsUsed,
  callsBudget,
}: {
  agentStatus: AgentStatus;
  llmStatus: LLMStatusEvent["state"] | null;
  callsUsed: number;
  callsBudget: number;
}) {
  const status = STATUS_CONFIG[agentStatus];
  const StatusIcon = status.icon;

  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-md border border-line bg-surface-2 px-3 py-2 text-xs">
      <Badge tone={status.tone} className="gap-1">
        <StatusIcon size={11} className={agentStatus === "running" ? "animate-pulse" : ""} />
        {status.label}
      </Badge>
      {agentStatus === "running" && llmStatus === "calling" && <SignalMeter label="Calling LLM" />}
      {llmStatus === "waiting_for_capacity" && (
        <Badge tone="warning">Waiting for LLM capacity…</Badge>
      )}
      <span className="tabular ml-auto text-ink-tertiary">
        LLM calls <span className="text-ink-secondary">{callsUsed}</span> / {callsBudget}
      </span>
    </div>
  );
}
