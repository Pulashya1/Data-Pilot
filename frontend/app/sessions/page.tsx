"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, deleteSession, listSessions } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
import type { SessionSummary } from "@/types";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  needs_sheet_selection: "Needs sheet",
  profiling: "Profiling…",
  ready: "Ready",
  error: "Error",
};

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    listSessions()
      .then(setSessions)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load sessions."));
  };

  useEffect(load, []);

  const handleDelete = async (id: string) => {
    await deleteSession(id);
    load();
  };

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Sessions</h1>
        <Link href="/" className="text-sm text-neutral-500 underline hover:text-neutral-900">
          New upload
        </Link>
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {sessions === null && !error && <p className="text-sm text-neutral-500">Loading…</p>}
      {sessions?.length === 0 && <p className="text-sm text-neutral-500">No sessions yet.</p>}
      <ul className="flex flex-col gap-2">
        {sessions?.map((session) => (
          <li
            key={session.id}
            className="flex items-center justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"
          >
            <Link href={`/sessions/${session.id}`} className="flex-1">
              <p className="font-medium">{session.original_filename}</p>
              <p className="text-xs text-neutral-500">
                {STATUS_LABEL[session.status] ?? session.status} · {formatBytes(session.size_bytes)}
                {session.row_count !== null && ` · ${session.row_count.toLocaleString()} rows`}
                {session.column_count !== null && ` · ${session.column_count} cols`}
              </p>
            </Link>
            <button
              type="button"
              onClick={() => void handleDelete(session.id)}
              className="ml-4 text-xs text-red-500 hover:underline"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
