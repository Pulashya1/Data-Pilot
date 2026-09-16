"use client";

import { useEffect, useState } from "react";
import { ApiError, exportNotebook, getKernelStatus, listTemplates, runTemplate } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { KernelStatusOut, TemplateInfo } from "@/types";

export function AnalysisActions({
  sessionId,
  onRunComplete,
}: {
  sessionId: string;
  onRunComplete: () => void;
}) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [kernel, setKernel] = useState<KernelStatusOut["status"]>("stopped");
  const [runningKey, setRunningKey] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load templates."),
      );
    getKernelStatus(sessionId)
      .then((res) => setKernel(res.status))
      .catch(() => undefined);
  }, [sessionId]);

  const run = async (key: string) => {
    setRunningKey(key);
    setError(null);
    try {
      await runTemplate(sessionId, key);
      onRunComplete();
      setKernel("running");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run analysis.");
    } finally {
      setRunningKey(null);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      await exportNotebook(sessionId, false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not export notebook.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium">Run analysis</h2>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase",
              kernel === "running"
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                : "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
            )}
          >
            kernel: {kernel}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={exporting}
          className="rounded-md border border-neutral-300 px-3 py-1 text-xs font-medium disabled:opacity-50 dark:border-neutral-700"
        >
          {exporting ? "Exporting…" : "Export notebook"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {templates.map((t) => (
          <button
            key={t.key}
            type="button"
            title={t.description}
            onClick={() => void run(t.key)}
            disabled={runningKey !== null}
            className="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {runningKey === t.key ? "Running…" : t.title}
          </button>
        ))}
      </div>
      {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
    </div>
  );
}
