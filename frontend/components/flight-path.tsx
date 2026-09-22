"use client";

import { Check, Hand, Minus, Play, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { SignalMeter } from "@/components/ui/signal-meter";
import type { Stage, StageState } from "@/lib/flight-path";
import { cn } from "@/lib/utils";
import type { AgentStatus } from "@/types";

const NODE_CLASSES: Record<StageState, string> = {
  done: "border-accent bg-accent text-accent-fg",
  active: "border-accent bg-accent/15 text-accent",
  waiting: "border-warning bg-warning/15 text-warning",
  upcoming: "border-line-strong bg-surface text-ink-tertiary",
  skipped: "border-dashed border-line-strong bg-surface text-ink-tertiary",
  error: "border-critical bg-critical/15 text-critical",
};

const LABEL_CLASSES: Record<StageState, string> = {
  done: "text-ink",
  active: "text-accent-strong",
  waiting: "text-warning",
  upcoming: "text-ink-tertiary",
  skipped: "text-ink-tertiary line-through decoration-line-strong",
  error: "text-critical",
};

const STATE_TEXT: Record<StageState, string> = {
  done: "done",
  active: "in progress",
  waiting: "needs your input",
  upcoming: "not started",
  skipped: "skipped",
  error: "failed",
};

function NodeIcon({ state }: { state: StageState }) {
  switch (state) {
    case "done":
      return <Check size={12} strokeWidth={3} />;
    case "active":
      return <span className="h-2 w-2 rounded-full bg-accent motion-safe:animate-pulse" />;
    case "waiting":
      return <Hand size={11} />;
    case "skipped":
      return <Minus size={11} />;
    case "error":
      return <X size={12} strokeWidth={3} />;
    case "upcoming":
      return null;
  }
}

/** The agent's route through its graph, from profiling to summary: the workspace's one
 * always-visible answer to "what is the agent doing, and does it need me?". */
export function FlightPath({
  stages,
  sentence,
  agentStatus,
  onRun,
  footer,
}: {
  stages: Stage[];
  sentence: string;
  agentStatus: AgentStatus;
  onRun: () => void;
  footer?: React.ReactNode;
}) {
  const busy = agentStatus === "running" || agentStatus === "waiting_decision";
  const trackRef = useRef<HTMLDivElement>(null);
  const currentKey = stages.find((s) => s.state === "waiting" || s.state === "active")?.key;

  // On narrow screens the track scrolls sideways; keep the stage that matters in view.
  useEffect(() => {
    const track = trackRef.current;
    if (!track || track.scrollWidth <= track.clientWidth) return;
    const node = track.querySelector<HTMLElement>(`[data-stage="${currentKey ?? "profile"}"]`);
    if (node) track.scrollLeft = node.offsetLeft - (track.clientWidth - node.offsetWidth) / 2;
  }, [currentKey]);

  return (
    <section aria-label="Agent progress" className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pb-2 pt-4 sm:px-5">
        <p className="flex min-w-0 items-center gap-2.5 text-base text-ink" aria-live="polite">
          {agentStatus === "running" && <SignalMeter />}
          {sentence}
        </p>
        <Button variant="primary" onClick={onRun} disabled={busy}>
          <Play size={12} />
          {agentStatus === "running" ? "Running…" : "Run agent"}
        </Button>
      </div>

      <div
        ref={trackRef}
        className="styled-scrollbar relative overflow-x-auto px-2 pb-4 pt-3 sm:px-3"
      >
        <ol className="grid min-w-[560px] grid-cols-7">
          {stages.map((stage, index) => {
            const previous = stages[index - 1];
            const leftLit = previous !== undefined && previous.state === "done";
            const rightLit = stage.state === "done";
            return (
              <li
                key={stage.key}
                data-stage={stage.key}
                className="flex flex-col items-center gap-2 text-center"
              >
                <div className="flex w-full items-center" aria-hidden="true">
                  <span
                    className={cn(
                      "h-0.5 flex-1",
                      index === 0 ? "invisible" : leftLit ? "bg-accent" : "bg-line-strong",
                    )}
                  />
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                      NODE_CLASSES[stage.state],
                    )}
                  >
                    <NodeIcon state={stage.state} />
                  </span>
                  <span
                    className={cn(
                      "h-0.5 flex-1",
                      index === stages.length - 1
                        ? "invisible"
                        : rightLit
                          ? "bg-accent"
                          : "bg-line-strong",
                    )}
                  />
                </div>
                <div className="flex min-w-0 max-w-full flex-col px-1">
                  <span className={cn("text-xs font-medium", LABEL_CLASSES[stage.state])}>
                    {stage.label}
                    <span className="sr-only">: {STATE_TEXT[stage.state]}</span>
                  </span>
                  <span
                    className={cn(
                      "tabular truncate text-[11px] text-ink-tertiary",
                      stage.key === "target" && stage.detail !== "No target" && "font-mono",
                    )}
                    title={stage.detail ?? undefined}
                  >
                    {stage.state === "waiting" ? "Needs you" : (stage.detail ?? " ")}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      {footer && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line px-4 py-2.5 text-xs text-ink-tertiary sm:px-5">
          {footer}
        </div>
      )}
    </section>
  );
}
