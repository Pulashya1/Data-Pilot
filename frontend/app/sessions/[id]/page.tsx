"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, getSession, selectSheet } from "@/lib/api";
import { ColumnStatsTable } from "@/components/column-stats-table";
import { DataQualityScoreCard } from "@/components/data-quality-score";
import { PreviewTable } from "@/components/preview-table";
import { formatBytes } from "@/lib/utils";
import type { SessionDetail } from "@/types";

function SheetPicker({ session, onResolved }: { session: SessionDetail; onResolved: (s: SessionDetail) => void }) {
  const [selected, setSelected] = useState(session.sheet_names?.[0] ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      onResolved(await selectSheet(session.id, selected));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not select sheet.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <h2 className="mb-2 font-medium">Choose a sheet</h2>
      <div className="mb-3 flex flex-col gap-2">
        {session.sheet_names?.map((name) => (
          <label key={name} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="sheet"
              checked={selected === name}
              onChange={() => setSelected(name)}
            />
            {name}
          </label>
        ))}
      </div>
      {error && <p className="mb-2 text-sm text-red-500">{error}</p>}
      <button
        type="button"
        onClick={() => void confirm()}
        disabled={busy}
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {busy ? "Loading…" : "Continue"}
      </button>
    </div>
  );
}

export default function SessionDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSession(id)
      .then(setSession)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load session."));
  }, [id]);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <Link href="/sessions" className="text-sm text-neutral-500 underline hover:text-neutral-900">
        ← All sessions
      </Link>

      {error && <p className="mt-4 text-sm text-red-500">{error}</p>}
      {!session && !error && <p className="mt-4 text-sm text-neutral-500">Loading…</p>}

      {session && (
        <div className="mt-4 flex flex-col gap-6">
          <div>
            <h1 className="text-2xl font-semibold">{session.original_filename}</h1>
            <p className="text-sm text-neutral-500">
              {session.file_type.toUpperCase()} · {formatBytes(session.size_bytes)}
              {session.row_count !== null && ` · ${session.row_count.toLocaleString()} rows`}
              {session.column_count !== null && ` · ${session.column_count} columns`}
            </p>
          </div>

          {session.status === "needs_sheet_selection" && (
            <SheetPicker session={session} onResolved={setSession} />
          )}

          {session.status === "error" && (
            <p className="text-sm text-red-500">{session.error_message ?? "This file could not be parsed."}</p>
          )}

          {session.status === "ready" && session.profile && (
            <>
              {session.profile.is_sampled && (
                <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                  This dataset has {session.profile.n_rows.toLocaleString()} rows. Statistics below were
                  computed on a random sample of {session.profile.sample_size?.toLocaleString()} rows.
                </p>
              )}

              <DataQualityScoreCard score={session.profile.data_quality} />

              <div>
                <h2 className="mb-2 text-lg font-medium">Columns</h2>
                <ColumnStatsTable columns={session.profile.columns} />
              </div>

              <div>
                <h2 className="mb-2 text-lg font-medium">Preview</h2>
                <PreviewTable sessionId={session.id} columns={session.profile.columns.map((c) => c.name)} />
              </div>
            </>
          )}
        </div>
      )}
    </main>
  );
}
