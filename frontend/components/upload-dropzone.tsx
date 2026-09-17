"use client";

import { FileUp, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { ApiError, selectSheet, uploadSession } from "@/lib/api";
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
      try {
        const session = await uploadSession(file);
        if (session.status === "needs_sheet_selection") {
          setPendingSheetSession(session);
          setSelectedSheet(session.sheet_names?.[0] ?? null);
        } else if (session.status === "error") {
          setError(session.error_message ?? "Could not parse this file.");
        } else {
          router.push(`/sessions/${session.id}`);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
      } finally {
        setIsUploading(false);
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
      <div className="w-full max-w-lg rounded-lg border border-line bg-surface p-6 shadow-floating">
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
          {isUploading ? "Loading…" : "Continue"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-lg flex-col items-center gap-3">
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
          if (file) void handleFile(file);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        aria-label="Upload a dataset file"
        className={cn(
          "flex w-full cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed p-12 text-center transition-all duration-150",
          isDragging
            ? "scale-[1.01] border-accent bg-accent/[0.06]"
            : "border-line-strong bg-surface hover:border-ink-tertiary",
        )}
      >
        {isDragging ? (
          <FileUp size={26} className="text-accent" />
        ) : (
          <UploadCloud size={26} className="text-ink-tertiary" />
        )}
        <p className="font-medium text-ink">
          {isUploading ? "Uploading…" : "Drag & drop a dataset, or click to browse"}
        </p>
        <p className="text-sm text-ink-tertiary">
          CSV, TSV, Excel, JSON, or Parquet — up to 200 MB
        </p>
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
      {error && <p className="text-sm text-critical">{error}</p>}
      <p className="text-xs text-ink-tertiary">
        Data you upload may be sent to a third-party LLM provider for analysis. Prefer public or
        non-sensitive datasets.
      </p>
    </div>
  );
}
