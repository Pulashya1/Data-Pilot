"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  answerDecision,
  ApiError,
  getDecisions,
  getNotebook,
  getSession,
  revertToCell,
  selectSheet,
  setAutoDecide,
  startAgent,
  subscribeToAgentStream,
} from "@/lib/api";
import { AgentStatusBar } from "@/components/agent-status";
import { AnalysisActions } from "@/components/analysis-actions";
import { ColumnStatsTable } from "@/components/column-stats-table";
import { DataQualityScoreCard } from "@/components/data-quality-score";
import { DecisionCard } from "@/components/decision-card";
import { DecisionsPanel } from "@/components/decisions-panel";
import { InsightFeed } from "@/components/insight-feed";
import { NotebookPanel } from "@/components/notebook-panel";
import { PreviewTable } from "@/components/preview-table";
import { formatBytes } from "@/lib/utils";
import type {
  AgentEvent,
  AgentStatus,
  DecisionOut,
  InsightEvent,
  LLMStatusEvent,
  NotebookCell,
  SessionDetail,
} from "@/types";

function SheetPicker({
  session,
  onResolved,
}: {
  session: SessionDetail;
  onResolved: (s: SessionDetail) => void;
}) {
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
  const [cells, setCells] = useState<NotebookCell[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [agentStatus, setAgentStatus] = useState<AgentStatus>("not_started");
  const [agentError, setAgentError] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LLMStatusEvent["state"] | null>(null);
  const [callsUsed, setCallsUsed] = useState(0);
  const [callsBudget, setCallsBudget] = useState(0);
  const [insights, setInsights] = useState<InsightEvent[]>([]);
  const [decisions, setDecisions] = useState<DecisionOut[]>([]);
  const [reverting, setReverting] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getSession(id)
      .then((detail) => {
        setSession(detail);
        setAgentStatus(detail.agent_status);
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load session."),
      );
  }, [id]);

  const refreshNotebook = useCallback(() => {
    getNotebook(id)
      .then(setCells)
      .catch(() => undefined);
  }, [id]);

  const refreshDecisions = useCallback(() => {
    getDecisions(id)
      .then(setDecisions)
      .catch(() => undefined);
  }, [id]);

  useEffect(() => {
    if (session?.status !== "ready") return;
    refreshNotebook();
    refreshDecisions();
  }, [session?.status, refreshNotebook, refreshDecisions]);

  useEffect(() => () => unsubscribeRef.current?.(), []);

  const handleAgentEvent = useCallback(
    (event: AgentEvent) => {
      switch (event.type) {
        case "insight":
          setInsights((prev) => [...prev, event]);
          break;
        case "llm_status":
          setLlmStatus(event.state);
          setCallsUsed(event.calls_used);
          setCallsBudget(event.calls_budget);
          break;
        case "decision":
          setDecisions((prev) => {
            const others = prev.filter((d) => d.id !== event.id);
            return [
              ...others,
              {
                id: event.id,
                kind: event.kind as DecisionOut["kind"],
                question: event.question,
                options: event.options,
                recommended_option: event.recommended_option,
                selected_option: event.selected_option,
                reasoning: event.reasoning,
                auto_decided: event.auto_decided,
                allow_free_text: event.kind === "plan_approval",
                created_at: new Date().toISOString(),
              },
            ];
          });
          break;
        case "cell_update":
        case "plan_update":
          refreshNotebook();
          break;
        case "error":
          setAgentError(event.message);
          break;
        case "agent_status":
          setAgentStatus(event.status);
          if (event.error_message) setAgentError(event.error_message);
          if (event.status !== "running") {
            unsubscribeRef.current?.();
            unsubscribeRef.current = null;
            refreshNotebook();
            getSession(id)
              .then(setSession)
              .catch(() => undefined);
          }
          break;
      }
    },
    [id, refreshNotebook],
  );

  const runAgent = useCallback(async () => {
    setInsights([]);
    setAgentError(null);
    setAgentStatus("running");
    try {
      await startAgent(id);
    } catch (err) {
      setAgentError(err instanceof ApiError ? err.message : "Could not start the agent.");
      setAgentStatus("error");
      return;
    }
    unsubscribeRef.current?.();
    unsubscribeRef.current = subscribeToAgentStream(id, handleAgentEvent);
  }, [id, handleAgentEvent]);

  const handleAnswerDecision = useCallback(
    async (decisionId: string, selectedOption: string) => {
      // The resumed graph run only re-publishes a `decision` SSE event for a *newly reached*
      // decision, not for this one settling — replaying an already-answered decision skips
      // straight past the pause (see app.agent.decisions on the backend) — so apply the answer
      // from this response directly instead of waiting for one over the stream.
      const updated = await answerDecision(id, decisionId, selectedOption);
      setDecisions((prev) => [...prev.filter((d) => d.id !== updated.id), updated]);
      setAgentError(null);
      setAgentStatus("running");
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeToAgentStream(id, handleAgentEvent);
    },
    [id, handleAgentEvent],
  );

  const handleRevert = useCallback(
    async (cellId: string) => {
      setReverting(true);
      try {
        const remaining = await revertToCell(id, cellId);
        setCells(remaining);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not revert the notebook.");
      } finally {
        setReverting(false);
      }
    },
    [id],
  );

  const handleAutoDecideToggle = useCallback(
    async (checked: boolean) => {
      try {
        const updated = await setAutoDecide(id, checked);
        setSession(updated);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not update settings.");
      }
    },
    [id],
  );

  const pendingDecision = decisions.find((d) => d.selected_option === null) ?? null;

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
            <p className="text-sm text-red-500">
              {session.error_message ?? "This file could not be parsed."}
            </p>
          )}

          {session.status === "ready" && session.profile && (
            <>
              {session.profile.is_sampled && (
                <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                  This dataset has {session.profile.n_rows.toLocaleString()} rows. Statistics below
                  were computed on a random sample of{" "}
                  {session.profile.sample_size?.toLocaleString()} rows.
                </p>
              )}

              <DataQualityScoreCard score={session.profile.data_quality} />

              <div>
                <h2 className="mb-2 text-lg font-medium">Columns</h2>
                <ColumnStatsTable columns={session.profile.columns} />
              </div>

              <div>
                <h2 className="mb-2 text-lg font-medium">Preview</h2>
                <PreviewTable
                  sessionId={session.id}
                  columns={session.profile.columns.map((c) => c.name)}
                />
              </div>

              <AnalysisActions sessionId={session.id} onRunComplete={refreshNotebook} />

              <div className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-sm font-medium">Agent</h2>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-1.5 text-xs text-neutral-600 dark:text-neutral-400">
                      <input
                        type="checkbox"
                        checked={session.auto_decide}
                        onChange={(e) => void handleAutoDecideToggle(e.target.checked)}
                      />
                      Let the agent decide
                    </label>
                    <button
                      type="button"
                      onClick={() => void runAgent()}
                      disabled={agentStatus === "running" || agentStatus === "waiting_decision"}
                      className="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                    >
                      {agentStatus === "running" ? "Running…" : "Run agent"}
                    </button>
                  </div>
                </div>
                <AgentStatusBar
                  agentStatus={agentStatus}
                  llmStatus={llmStatus}
                  callsUsed={callsUsed}
                  callsBudget={callsBudget}
                />
                {session.target_column !== null && (
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Target: <span className="font-medium">{session.target_column}</span>
                    {session.problem_type && ` · ${session.problem_type.replace(/_/g, " ")}`}
                  </p>
                )}
                {agentError && <p className="text-sm text-red-500">{agentError}</p>}
                {pendingDecision && (
                  <DecisionCard decision={pendingDecision} onAnswer={handleAnswerDecision} />
                )}
                <InsightFeed insights={insights} />
                <DecisionsPanel decisions={decisions} />
              </div>

              <div>
                <h2 className="mb-2 text-lg font-medium">Notebook</h2>
                <NotebookPanel cells={cells} onRevert={handleRevert} reverting={reverting} />
              </div>
            </>
          )}
        </div>
      )}
    </main>
  );
}
