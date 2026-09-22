"use client";

import { ChevronDown, CircleDot, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { PanelHeader, PanelTitle } from "@/components/ui/panel";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, getKernelStatus, runTemplate } from "@/lib/api";
import type { KernelStatusOut, TemplateInfo } from "@/types";

const COLLAPSED_COUNT = 6;

/** Runs one analysis template on demand, outside the agent's plan. Each run appends a cell to
 * the notebook. */
export function AnalysisActions({
  sessionId,
  templates,
  disabled = false,
  onRunComplete,
}: {
  sessionId: string;
  templates: TemplateInfo[];
  /** True while the agent is running, so manual runs don't race it in the same kernel. */
  disabled?: boolean;
  onRunComplete: (templateKey: string) => void;
}) {
  const [kernel, setKernel] = useState<KernelStatusOut | null>(null);
  const [runningKey, setRunningKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getKernelStatus(sessionId)
      .then(setKernel)
      .catch(() => undefined);
  }, [sessionId]);

  const run = async (key: string) => {
    setRunningKey(key);
    setError(null);
    try {
      await runTemplate(sessionId, key);
      onRunComplete(key);
      setKernel(await getKernelStatus(sessionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run analysis.");
    } finally {
      setRunningKey(null);
    }
  };

  const kernelRunning = kernel?.status === "running";
  // The full catalog is long; show the generic EDA core until asked for the rest.
  const shown = expanded ? templates : templates.slice(0, COLLAPSED_COUNT);

  return (
    <div className="rounded-lg border border-line bg-surface">
      <PanelHeader>
        <PanelTitle>Run a single analysis</PanelTitle>
        <Badge tone={kernelRunning ? "success" : "neutral"} className="gap-1">
          <CircleDot size={9} />
          Kernel {kernelRunning ? "running" : "stopped"}
          {kernel && kernel.compute_seconds_used > 0 && (
            <span className="tabular font-normal opacity-80">
              , {Math.round(kernel.compute_seconds_used)}s used
            </span>
          )}
        </Badge>
      </PanelHeader>
      <p className="px-4 pt-3 text-xs text-ink-tertiary">
        {disabled
          ? "Available once the agent pauses or finishes."
          : "Each run adds a cell to the notebook. The first run starts the kernel, which takes a few seconds."}
      </p>
      <ul className="grid gap-2 px-4 pb-3 pt-3 sm:grid-cols-2">
        {shown.map((t) => (
          <li key={t.key}>
            <button
              type="button"
              onClick={() => void run(t.key)}
              disabled={disabled || runningKey !== null}
              className="group flex h-full w-full items-start gap-2.5 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-left transition-colors hover:border-line-strong hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="mt-0.5 shrink-0 text-ink-tertiary group-hover:text-accent">
                {runningKey === t.key ? <SignalMeter /> : <Play size={12} />}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink">{t.title}</span>
                <span className="mt-0.5 block text-xs leading-snug text-ink-tertiary">
                  {t.description}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {templates.length > COLLAPSED_COUNT && (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
          className="mx-4 mb-4 flex items-center gap-1 text-xs font-medium text-ink-secondary hover:text-accent"
        >
          <ChevronDown size={12} className={expanded ? "rotate-180" : ""} />
          {expanded ? "Show fewer" : `Show all ${templates.length} analyses`}
        </button>
      )}
      {error && <p className="px-4 pb-3 text-xs text-critical">{error}</p>}
    </div>
  );
}
