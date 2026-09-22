"use client";

import { ChevronDown, Download, FileCode2, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, exportNotebook, type ExportOptions } from "@/lib/api";

export function ExportMenu({
  sessionId,
  hasCells,
}: {
  sessionId: string;
  /** Export needs at least one cell to be worth downloading. */
  hasCells: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState<ExportOptions["format"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includePipeline, setIncludePipeline] = useState(true);
  const [includeExploratory, setIncludeExploratory] = useState(false);
  const [includeData, setIncludeData] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const run = async (format: ExportOptions["format"]) => {
    setExporting(format);
    setError(null);
    try {
      await exportNotebook(sessionId, {
        format,
        includePipeline,
        includeExploratory,
        includeData,
      });
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed.");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <Button
        variant="secondary"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={!hasCells}
        title={hasCells ? undefined : "Run an analysis first. There's nothing to export yet."}
      >
        <Download size={13} />
        Export
        <ChevronDown size={12} className="opacity-60" />
      </Button>

      {open && (
        <div
          role="menu"
          className="animate-fade-in absolute right-0 z-30 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-lg border border-line-strong bg-surface p-1.5 shadow-floating"
        >
          <MenuItem
            icon={<FileCode2 size={15} />}
            title="Notebook (.ipynb)"
            description="A zip with the notebook and requirements.txt, ready to run in Jupyter."
            busy={exporting === "zip"}
            disabled={exporting !== null}
            onClick={() => void run("zip")}
          />
          <MenuItem
            icon={<FileText size={15} />}
            title="HTML report"
            description="One self-contained page with every chart and insight, for sharing."
            busy={exporting === "html"}
            disabled={exporting !== null}
            onClick={() => void run("html")}
          />

          <div className="mt-1 flex flex-col gap-2 border-t border-line px-2.5 pb-1.5 pt-2.5">
            <Toggle checked={includePipeline} onChange={setIncludePipeline}>
              Include the fitted pipeline (.joblib), if one was built
            </Toggle>
            <Toggle checked={includeExploratory} onChange={setIncludeExploratory}>
              Include cells created by chat questions
            </Toggle>
            <Toggle checked={includeData} onChange={setIncludeData}>
              Include the dataset file
            </Toggle>
          </div>

          <p className="px-2.5 pb-1.5 text-[11px] leading-snug text-ink-tertiary">
            {exporting
              ? "Re-running every cell in a fresh kernel to make sure the export works…"
              : "Before downloading, every cell is re-run in a fresh kernel to check it still works. This can take a minute."}
          </p>
          {error && <p className="px-2.5 pb-1.5 text-xs text-critical">{error}</p>}
        </div>
      )}
    </div>
  );
}

function MenuItem({
  icon,
  title,
  description,
  busy,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-start gap-3 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-surface-3 disabled:cursor-wait disabled:opacity-60"
    >
      <span className="mt-0.5 text-accent">{busy ? <SignalMeter /> : icon}</span>
      <span>
        <span className="block text-sm font-medium text-ink">{title}</span>
        <span className="block text-xs leading-snug text-ink-tertiary">{description}</span>
      </span>
    </button>
  );
}

function Toggle({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-secondary">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-accent"
      />
      {children}
    </label>
  );
}
