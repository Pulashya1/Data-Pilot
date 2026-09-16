import { cn } from "@/lib/utils";
import type { AgentStatus, LLMStatusEvent } from "@/types";

const STATUS_LABEL: Record<AgentStatus, string> = {
  not_started: "Not started",
  running: "Running",
  waiting_decision: "Waiting for you",
  done: "Done",
  error: "Error",
};

const STATUS_COLOR: Record<AgentStatus, string> = {
  not_started: "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  waiting_decision: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  error: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
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
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 p-3 text-xs dark:border-neutral-800">
      <span
        className={cn("rounded-full px-2 py-0.5 font-medium uppercase", STATUS_COLOR[agentStatus])}
      >
        agent: {STATUS_LABEL[agentStatus]}
      </span>
      {llmStatus === "waiting_for_capacity" && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          Waiting for LLM capacity…
        </span>
      )}
      {llmStatus === "calling" && (
        <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          Calling LLM…
        </span>
      )}
      <span className="text-neutral-500">
        LLM calls: {callsUsed} / {callsBudget}
      </span>
    </div>
  );
}
