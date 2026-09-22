"use client";

import { FileUp, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { ApiError, selectSheet, uploadSession } from "@/lib/api";
import { SignalMeter } from "@/components/ui/signal-meter";
import { cn } from "@/lib/utils";
import type { SessionDetail } from "@/types";

const ACCEPTED_EXTENSIONS = [
  ".csv",
  ".tsv",
  ".xlsx",
  ".xls",
  ".json",
  ".jsonl",
  ".ndjson",
  ".parquet",
];

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function UploadDropzone() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingSheetSession, setPendingSheetSession] = useState<SessionDetail | null>(null);
  const [selectedSheet, setSelectedSheet] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      if (!hasAcceptedExtension(file.name)) {
        setError(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`);
        return;
      }
      setIsUploading(true);
      setFileName(file.name);
      setProgress(0);
      try {
        const session = await uploadSession(file, setProgress);
        if (session.status === "needs_sheet_selection") {
          setPendingSheetSession(session);
          setSelectedSheet(session.sheet_names?.[0] ?? null);
        } else if (session.status === "error") {
          setError(session.error_message ?? "Could not parse this file.");
        } else {
          router.push(`/sessions/${session.id}`);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Upload failed. Try again.");
      } finally {
        setIsUploading(false);
        setProgress(null);
      }
    },
    [router],
  );

  const confirmSheet = useCallback(async () => {
    if (!pendingSheetSession || !selectedSheet) return;
    setIsUploading(true);
    setError(null);
    try {
      const session = await selectSheet(pendingSheetSession.id, selectedSheet);
      if (session.status === "error") {
        setError(session.error_message ?? "Could not parse this sheet.");
      } else {
        router.push(`/sessions/${session.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not select sheet.");
    } finally {
      setIsUploading(false);
    }
  }, [pendingSheetSession, selectedSheet, router]);

  if (pendingSheetSession) {
    return (
      <div className="w-full rounded-lg border border-line bg-surface p-6 shadow-floating">
        <h2 className="mb-2 font-display text-lg font-medium text-ink">Choose a sheet</h2>
        <p className="mb-4 text-sm text-ink-tertiary">
          &quot;{pendingSheetSession.original_filename}&quot; has multiple sheets. Pick the one to
          analyze.
        </p>
        <div className="mb-4 flex flex-col gap-2">
          {pendingSheetSession.sheet_names?.map((name) => (
            <label
              key={name}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors",
                selectedSheet === name
                  ? "border-accent/50 bg-accent/10 text-ink"
                  : "border-line text-ink-secondary hover:border-line-strong",
              )}
            >
              <input
                type="radio"
                name="sheet"
                value={name}
                checked={selectedSheet === name}
                onChange={() => setSelectedSheet(name)}
                className="accent-accent"
              />
              {name}
            </label>
          ))}
        </div>
        {error && <p className="mb-3 text-sm text-critical">{error}</p>}
        <button
          type="button"
          onClick={confirmSheet}
          disabled={isUploading}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-50"
        >
          {isUploading ? "Loading…" : "Analyze this sheet"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const file = e.dataTransfer.files[0];
          if (file && !isUploading) void handleFile(file);
        }}
        onClick={() => {
          if (!isUploading) inputRef.current?.click();
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !isUploading) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        aria-label="Upload a dataset file"
        className={cn(
          "flex min-h-[15rem] w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors duration-150",
          isDragging
            ? "border-accent bg-accent/[0.06]"
            : "border-line-strong bg-surface hover:border-ink-tertiary",
        )}
      >
        {isUploading ? (
          <div className="flex w-full max-w-xs flex-col items-center gap-3" aria-live="polite">
            <SignalMeter />
            <p className="max-w-full truncate font-medium text-ink">{fileName}</p>
            <div className="h-1 w-full overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-200"
                style={{ width: `${Math.round((progress ?? 0) * 100)}%` }}
              />
            </div>
            <p className="tabular text-sm text-ink-tertiary">
              {progress !== null && progress < 1
                ? `Uploading ${Math.round(progress * 100)}%`
                : "Reading and profiling the file…"}
            </p>
          </div>
        ) : (
          <>
            {isDragging ? (
              <FileUp size={26} className="text-accent" />
            ) : (
              <UploadCloud size={26} className="text-ink-tertiary" />
            )}
            <p className="font-medium text-ink">
              {isDragging ? "Drop to upload" : "Drag a file here, or click to browse"}
            </p>
            <p className="text-sm text-ink-tertiary">
              CSV, TSV, Excel, JSON, or Parquet, up to 200 MB
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <p className="text-sm text-critical" role="alert">
          {error}
        </p>
      )}
      <p className="text-xs text-ink-tertiary">
        The agent sends column names, summary statistics, and a few sample rows to a third-party LLM
        provider. Prefer public or non-sensitive datasets.
      </p>
    </div>
  );
}
