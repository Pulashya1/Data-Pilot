"use client";

import { FileText, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { Badge } from "@/components/ui/badge";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, deleteSession, listSessions } from "@/lib/api";
import { formatBytes, formatRelativeTime, PROBLEM_TYPE_LABEL } from "@/lib/utils";
import type { SessionSummary } from "@/types";

type Tone = "neutral" | "accent" | "success" | "critical" | "warning";

/** One status per session: file problems first, then where the agent got to. */
function sessionStatus(session: SessionSummary): { label: string; tone: Tone } {
  switch (session.status) {
    case "needs_sheet_selection":
      return { label: "Choose a sheet", tone: "warning" };
    case "error":
      return { label: "Couldn't read file", tone: "critical" };
    case "uploaded":
    case "profiling":
      return { label: "Profiling", tone: "neutral" };
    case "ready":
      break;
  }
  switch (session.agent_status) {
    case "running":
      return { label: "Agent running", tone: "accent" };
    case "waiting_decision":
      return { label: "Needs your input", tone: "warning" };
    case "done":
      return { label: "Analyzed", tone: "success" };
    case "error":
      return { label: "Agent stopped", tone: "critical" };
    case "not_started":
      return { label: "Profiled", tone: "neutral" };
  }
}

function SessionRow({
  session,
  onDelete,
}: {
  session: SessionSummary;
  onDelete: (id: string) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const status = sessionStatus(session);

  return (
    <li className="group flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 transition-colors hover:border-line-strong">
      <Link
        href={`/sessions/${session.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 focus-visible:outline-offset-4"
      >
        <FileText size={16} className="shrink-0 text-ink-tertiary" />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate font-medium text-ink group-hover:text-accent-strong">
              {session.original_filename}
            </p>
            <Badge tone={status.tone} className="shrink-0">
              {status.label}
            </Badge>
          </div>
          <p className="tabular mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-tertiary">
            <time
              dateTime={session.created_at}
              title={new Date(session.created_at).toLocaleString()}
            >
              {formatRelativeTime(session.created_at)}
            </time>
            {session.row_count !== null && session.column_count !== null && (
              <span>
                {session.row_count.toLocaleString()} rows, {session.column_count} columns
              </span>
            )}
            <span>{formatBytes(session.size_bytes)}</span>
            {session.problem_type && (
              <span className="text-ink-secondary">
                {PROBLEM_TYPE_LABEL[session.problem_type] ?? session.problem_type}
                {session.target_column && (
                  <>
                    {" "}
                    on <span className="font-mono">{session.target_column}</span>
                  </>
                )}
              </span>
            )}
          </p>
        </div>
      </Link>

      {confirming ? (
        <span className="flex shrink-0 items-center gap-2 text-xs">
          <span className="hidden text-ink-secondary sm:inline">Delete this session?</span>
          <button
            type="button"
            disabled={deleting}
            onClick={() => {
              setDeleting(true);
              void onDelete(session.id).finally(() => setDeleting(false));
            }}
            className="rounded-md bg-critical/10 px-2 py-1 font-medium text-critical hover:bg-critical/20 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="px-1 text-ink-tertiary hover:text-ink"
          >
            Cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          aria-label={`Delete ${session.original_filename}`}
          title="Delete session"
          className="shrink-0 rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-critical/10 hover:text-critical focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
        >
          <Trash2 size={14} />
        </button>
      )}
    </li>
  );
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load sessions."),
      );
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteSession(id);
      setSessions((prev) => prev?.filter((s) => s.id !== id) ?? prev);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the session.");
    }
  };

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!sessions || !q) return sessions;
    return sessions.filter((s) => s.original_filename.toLowerCase().includes(q));
  }, [sessions, query]);

  const needsInput = sessions?.filter((s) => s.agent_status === "waiting_decision").length ?? 0;

  return (
    <AuthGuard>
      <main className="mx-auto max-w-3xl px-4 py-10 lg:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">
              Sessions
            </h1>
            {sessions && sessions.length > 0 && (
              <p className="tabular mt-1 text-sm text-ink-tertiary">
                {sessions.length} {sessions.length === 1 ? "dataset" : "datasets"}
                {needsInput > 0 && (
                  <span className="text-warning">, {needsInput} waiting for your input</span>
                )}
              </p>
            )}
          </div>
          <Link
            href="/"
            className="flex h-8 items-center gap-1.5 rounded-md bg-accent px-3.5 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong"
          >
            <Plus size={14} />
            New analysis
          </Link>
        </div>

        {error && (
          <p className="mb-4 text-sm text-critical" role="alert">
            {error}
          </p>
        )}
        {sessions === null && !error && (
          <div className="flex justify-center py-12">
            <SignalMeter label="Loading sessions" />
          </div>
        )}

        {sessions?.length === 0 && (
          <div className="grid-texture flex flex-col items-center gap-3 rounded-lg border border-dashed border-line-strong px-6 py-14 text-center">
            <p className="font-display text-lg font-medium text-ink">No sessions yet</p>
            <p className="max-w-sm text-sm text-ink-tertiary">
              Upload a dataset, or start from a sample, and the agent will profile it and walk you
              through an analysis.
            </p>
            <Link
              href="/"
              className="mt-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:bg-accent-strong"
            >
              Start an analysis
            </Link>
          </div>
        )}

        {sessions && sessions.length > 4 && (
          <label className="relative mb-3 block">
            <span className="sr-only">Search sessions</span>
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary"
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by file name"
              className="w-full rounded-md border border-line-strong bg-surface-2 py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-tertiary focus:border-accent"
            />
          </label>
        )}

        <ul className="flex flex-col gap-2">
          {visible?.map((session) => (
            <SessionRow key={session.id} session={session} onDelete={handleDelete} />
          ))}
        </ul>
        {visible && sessions && visible.length === 0 && sessions.length > 0 && (
          <p className="py-8 text-center text-sm text-ink-tertiary">
            No sessions match &ldquo;{query}&rdquo;.
          </p>
        )}
      </main>
    </AuthGuard>
  );
}
