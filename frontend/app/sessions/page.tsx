"use client";

import { ArrowLeft, FileText, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { Badge } from "@/components/ui/badge";
import { ApiError, deleteSession, listSessions } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
import type { SessionStatus, SessionSummary } from "@/types";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  needs_sheet_selection: "Needs sheet",
  profiling: "Profiling…",
  ready: "Ready",
  error: "Error",
};

const STATUS_TONE: Record<SessionStatus, "neutral" | "success" | "critical" | "warning"> = {
  uploaded: "neutral",
  needs_sheet_selection: "warning",
  profiling: "neutral",
  ready: "success",
  error: "critical",
};

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    listSessions()
      .then(setSessions)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load sessions."),
      );
  };

  useEffect(load, []);

  const handleDelete = async (id: string) => {
    await deleteSession(id);
    load();
  };

  return (
    <AuthGuard>
      <main className="mx-auto max-w-3xl px-4 py-10 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-display text-xl font-semibold tracking-tight text-ink">Sessions</h1>
          <Link
            href="/"
            className="flex items-center gap-1 text-sm text-ink-tertiary transition-colors hover:text-accent"
          >
            <ArrowLeft size={13} />
            New upload
          </Link>
        </div>
        {error && <p className="text-sm text-critical">{error}</p>}
        {sessions === null && !error && <p className="text-sm text-ink-tertiary">Loading…</p>}
        {sessions?.length === 0 && (
          <div className="rounded-lg border border-dashed border-line px-6 py-12 text-center">
            <p className="text-sm text-ink-tertiary">
              No sessions yet — upload a dataset to start one.
            </p>
          </div>
        )}
        <ul className="flex flex-col gap-2">
          {sessions?.map((session) => (
            <li
              key={session.id}
              className="group flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-3 transition-colors hover:border-line-strong hover:bg-surface-2"
            >
              <Link
                href={`/sessions/${session.id}`}
                className="flex min-w-0 flex-1 items-center gap-3"
              >
                <FileText size={16} className="shrink-0 text-ink-tertiary" />
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{session.original_filename}</p>
                  <p className="tabular mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-tertiary">
                    <Badge tone={STATUS_TONE[session.status]}>
                      {STATUS_LABEL[session.status] ?? session.status}
                    </Badge>
                    <span>{formatBytes(session.size_bytes)}</span>
                    {session.row_count !== null && (
                      <span>· {session.row_count.toLocaleString()} rows</span>
                    )}
                    {session.column_count !== null && <span>· {session.column_count} cols</span>}
                  </p>
                </div>
              </Link>
              <button
                type="button"
                onClick={() => void handleDelete(session.id)}
                aria-label="Delete session"
                className="shrink-0 rounded-md p-1.5 text-ink-tertiary opacity-0 transition-colors hover:bg-critical/10 hover:text-critical group-hover:opacity-100"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      </main>
    </AuthGuard>
  );
}
