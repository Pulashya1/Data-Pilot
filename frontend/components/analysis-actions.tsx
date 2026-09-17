"use client";

import { CircleDot, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PanelHeader, PanelTitle } from "@/components/ui/panel";
import { ApiError, exportNotebook, getKernelStatus, listTemplates, runTemplate } from "@/lib/api";
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
  const [includePipeline, setIncludePipeline] = useState(false);
  const [includeExploratory, setIncludeExploratory] = useState(false);
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
      await exportNotebook(sessionId, false, includePipeline, includeExploratory);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not export notebook.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="rounded-lg border border-line bg-surface">
      <PanelHeader>
        <div className="flex items-center gap-2">
          <PanelTitle>Run analysis</PanelTitle>
          <Badge tone={kernel === "running" ? "success" : "neutral"} className="gap-1">
            <CircleDot size={9} className={kernel === "running" ? "animate-pulse" : ""} />
            kernel: {kernel}
          </Badge>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
            <input
              type="checkbox"
              checked={includePipeline}
              onChange={(e) => setIncludePipeline(e.target.checked)}
              className="accent-accent"
            />
            Include fitted pipeline
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
            <input
              type="checkbox"
              checked={includeExploratory}
              onChange={(e) => setIncludeExploratory(e.target.checked)}
              className="accent-accent"
            />
            Include Q&amp;A cells
          </label>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleExport()}
            disabled={exporting}
          >
            <Download size={12} />
            {exporting ? "Exporting…" : "Export notebook"}
          </Button>
        </div>
      </PanelHeader>
      <div className="flex flex-wrap gap-2 p-4">
        {templates.map((t) => (
          <Button
            key={t.key}
            variant="secondary"
            size="sm"
            title={t.description}
            onClick={() => void run(t.key)}
            disabled={runningKey !== null}
          >
            {runningKey === t.key ? "Running…" : t.title}
          </Button>
        ))}
      </div>
      {error && <p className="px-4 pb-3 text-xs text-critical">{error}</p>}
    </div>
  );
}
