"use client";

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
      <div className="w-full max-w-lg rounded-lg border border-neutral-300 p-6 dark:border-neutral-700">
        <h2 className="mb-2 text-lg font-medium">Choose a sheet</h2>
        <p className="mb-4 text-sm text-neutral-500">
          &quot;{pendingSheetSession.original_filename}&quot; has multiple sheets. Pick the one to
          analyze.
        </p>
        <div className="mb-4 flex flex-col gap-2">
          {pendingSheetSession.sheet_names?.map((name) => (
            <label key={name} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="sheet"
                value={name}
                checked={selectedSheet === name}
                onChange={() => setSelectedSheet(name)}
              />
              {name}
            </label>
          ))}
        </div>
        {error && <p className="mb-3 text-sm text-red-500">{error}</p>}
        <button
          type="button"
          onClick={confirmSheet}
          disabled={isUploading}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
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
          "flex w-full cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-12 text-center transition-colors",
          isDragging
            ? "border-neutral-900 bg-neutral-50 dark:border-neutral-100 dark:bg-neutral-900"
            : "border-neutral-300 dark:border-neutral-700",
        )}
      >
        <p className="font-medium">
          {isUploading ? "Uploading…" : "Drag & drop a dataset, or click to browse"}
        </p>
        <p className="text-sm text-neutral-500">CSV, TSV, Excel, JSON, or Parquet — up to 200 MB</p>
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
      {error && <p className="text-sm text-red-500">{error}</p>}
      <p className="text-xs text-neutral-500">
        Data you upload may be sent to a third-party LLM provider for analysis. Prefer public or
        non-sensitive datasets.
      </p>
    </div>
  );
}
