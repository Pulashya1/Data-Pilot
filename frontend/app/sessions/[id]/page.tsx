"use client";

import { ArrowLeft, CircleAlert, Play } from "lucide-react";
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
  setExpertiseLevel,
  startAgent,
  subscribeToAgentStream,
} from "@/lib/api";
import { AgentStatusBar } from "@/components/agent-status";
import { AnalysisActions } from "@/components/analysis-actions";
import { AuthGuard } from "@/components/auth-guard";
import { ChatPanel } from "@/components/chat-panel";
import { ColumnStatsTable } from "@/components/column-stats-table";
import { DataQualityScoreCard } from "@/components/data-quality-score";
import { DecisionCard } from "@/components/decision-card";
import { DecisionsPanel } from "@/components/decisions-panel";
import { InsightFeed } from "@/components/insight-feed";
import { NotebookPanel } from "@/components/notebook-panel";
import { PreviewTable } from "@/components/preview-table";
import { PanelHeader, PanelTitle } from "@/components/ui/panel";
import { SignalMeter } from "@/components/ui/signal-meter";
import { formatBytes } from "@/lib/utils";
import type {
  AgentEvent,
  AgentStatus,
  DecisionOut,
  ExpertiseLevel,
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
    <div className="rounded-lg border border-line bg-surface p-4">
      <h2 className="mb-2 font-display font-medium text-ink">Choose a sheet</h2>
      <div className="mb-3 flex flex-col gap-2">
        {session.sheet_names?.map((name) => (
          <label key={name} className="flex items-center gap-2 text-sm text-ink-secondary">
            <input
              type="radio"
              name="sheet"
              checked={selected === name}
              onChange={() => setSelected(name)}
              className="accent-accent"
            />
            {name}
          </label>
        ))}
      </div>
      {error && <p className="mb-2 text-sm text-critical">{error}</p>}
      <button
        type="button"
        onClick={() => void confirm()}
        disabled={busy}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-50"
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
  const [chatPrefill, setChatPrefill] = useState<string | null>(null);
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

  const handleExpertiseLevelChange = useCallback(
    async (level: ExpertiseLevel) => {
      try {
        const updated = await setExpertiseLevel(id, level);
        setSession(updated);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not update settings.");
      }
    },
    [id],
  );

  const handleAskAboutCell = useCallback((position: number) => {
    setChatPrefill(`@cell-${position}`);
  }, []);

  const handlePrefillConsumed = useCallback(() => {
    setChatPrefill(null);
  }, []);

  const pendingDecision = decisions.find((d) => d.selected_option === null) ?? null;

  return (
    <AuthGuard>
      <main className="mx-auto max-w-[1440px] px-4 py-6 lg:px-8 lg:py-8">
        <Link
          href="/sessions"
          className="flex w-fit items-center gap-1 text-sm text-ink-tertiary transition-colors hover:text-accent"
        >
          <ArrowLeft size={13} />
          All sessions
        </Link>

        {error && (
          <p className="mt-4 flex items-center gap-1.5 text-sm text-critical">
            <CircleAlert size={14} />
            {error}
          </p>
        )}
        {!session && !error && (
          <div className="flex justify-center py-16">
            <SignalMeter />
          </div>
        )}

        {session && (
          <div className="mt-4 flex flex-col gap-6">
            <div>
              <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">
                {session.original_filename}
              </h1>
              <p className="tabular mt-1 text-sm text-ink-tertiary">
                {session.file_type.toUpperCase()} · {formatBytes(session.size_bytes)}
                {session.row_count !== null && ` · ${session.row_count.toLocaleString()} rows`}
                {session.column_count !== null && ` · ${session.column_count} columns`}
              </p>
            </div>

            {session.status === "needs_sheet_selection" && (
              <SheetPicker session={session} onResolved={setSession} />
            )}

            {session.status === "error" && (
              <p className="flex items-center gap-1.5 text-sm text-critical">
                <CircleAlert size={14} />
                {session.error_message ?? "This file could not be parsed."}
              </p>
            )}

            {session.status === "ready" && session.profile && (
              <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-8">
                {/* Analysis + notebook — the main scrollable column. */}
                <div className="flex min-w-0 flex-col gap-6">
                  {session.profile.is_sampled && (
                    <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm text-ink">
                      This dataset has {session.profile.n_rows.toLocaleString()} rows. Statistics
                      below were computed on a random sample of{" "}
                      {session.profile.sample_size?.toLocaleString()} rows.
                    </p>
                  )}

                  <DataQualityScoreCard score={session.profile.data_quality} />

                  <section>
                    <h2 className="mb-2 font-display text-base font-medium tracking-tight text-ink">
                      Columns
                    </h2>
                    <ColumnStatsTable columns={session.profile.columns} />
                  </section>

                  <section>
                    <h2 className="mb-2 font-display text-base font-medium tracking-tight text-ink">
                      Preview
                    </h2>
                    <PreviewTable
                      sessionId={session.id}
                      columns={session.profile.columns.map((c) => c.name)}
                    />
                  </section>

                  <AnalysisActions sessionId={session.id} onRunComplete={refreshNotebook} />

                  <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface">
                    <PanelHeader>
                      <PanelTitle>Agent</PanelTitle>
                      <div className="flex items-center gap-3">
                        <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
                          Explain like I&apos;m
                          <select
                            value={session.expertise_level}
                            onChange={(e) =>
                              void handleExpertiseLevelChange(e.target.value as ExpertiseLevel)
                            }
                            className="rounded-md border border-line-strong bg-surface-2 px-1.5 py-0.5 text-xs text-ink"
                          >
                            <option value="beginner">a beginner</option>
                            <option value="intermediate">intermediate</option>
                            <option value="expert">an expert</option>
                          </select>
                        </label>
                        <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
                          <input
                            type="checkbox"
                            checked={session.auto_decide}
                            onChange={(e) => void handleAutoDecideToggle(e.target.checked)}
                            className="accent-accent"
                          />
                          Let the agent decide
                        </label>
                        <button
                          type="button"
                          onClick={() => void runAgent()}
                          disabled={agentStatus === "running" || agentStatus === "waiting_decision"}
                          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-50"
                        >
                          <Play size={11} />
                          {agentStatus === "running" ? "Running…" : "Run agent"}
                        </button>
                      </div>
                    </PanelHeader>
                    <div className="flex flex-col gap-3 px-4 pb-4">
                      <AgentStatusBar
                        agentStatus={agentStatus}
                        llmStatus={llmStatus}
                        callsUsed={callsUsed}
                        callsBudget={callsBudget}
                      />
                      {session.target_column !== null && (
                        <p className="text-sm text-ink-secondary">
                          Target:{" "}
                          <span className="font-mono font-medium text-ink">
                            {session.target_column}
                          </span>
                          {session.problem_type && (
                            <span className="text-ink-tertiary">
                              {" "}
                              · {session.problem_type.replace(/_/g, " ")}
                            </span>
                          )}
                        </p>
                      )}
                      {agentError && (
                        <p className="flex items-center gap-1.5 text-sm text-critical">
                          <CircleAlert size={14} />
                          {agentError}
                        </p>
                      )}
                      {pendingDecision && (
                        <DecisionCard decision={pendingDecision} onAnswer={handleAnswerDecision} />
                      )}
                      <InsightFeed insights={insights} />
                      <DecisionsPanel decisions={decisions} />
                    </div>
                  </div>

                  <section>
                    <h2 className="mb-2 font-display text-base font-medium tracking-tight text-ink">
                      Notebook
                    </h2>
                    <NotebookPanel
                      cells={cells}
                      onRevert={handleRevert}
                      reverting={reverting}
                      onAskAboutCell={handleAskAboutCell}
                    />
                  </section>
                </div>

                {/* Chat — docked and sticky, so it stays in view alongside the scrolling
                    analysis/notebook column instead of living inline in the stack. */}
                <aside className="lg:sticky lg:top-[4.5rem] lg:h-[calc(100vh-6rem)]">
                  <ChatPanel
                    sessionId={session.id}
                    prefill={chatPrefill}
                    onPrefillConsumed={handlePrefillConsumed}
                    className="h-[32rem] lg:h-full"
                  />
                </aside>
              </div>
            )}
          </div>
        )}
      </main>
    </AuthGuard>
  );
}
