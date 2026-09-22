"use client";

import { ArrowLeft, CircleAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  answerDecision,
  ApiError,
  getDecisions,
  getNotebook,
  getSession,
  getUsage,
  listTemplates,
  revertToCell,
  selectSheet,
  setAutoDecide,
  setExpertiseLevel,
  startAgent,
  subscribeToAgentStream,
} from "@/lib/api";
import { AnalysisActions } from "@/components/analysis-actions";
import { AuthGuard } from "@/components/auth-guard";
import { ChatPanel } from "@/components/chat-panel";
import { ColumnStatsTable } from "@/components/column-stats-table";
import { DataQualityScoreCard } from "@/components/data-quality-score";
import { DecisionCard } from "@/components/decision-card";
import { DecisionsPanel } from "@/components/decisions-panel";
import { ExportMenu } from "@/components/export-menu";
import { FlightPath } from "@/components/flight-path";
import { InsightFeed } from "@/components/insight-feed";
import { cellAnchorId, NotebookPanel } from "@/components/notebook-panel";
import { PreviewTable } from "@/components/preview-table";
import { Badge } from "@/components/ui/badge";
import { SignalMeter } from "@/components/ui/signal-meter";
import { tabId, tabPanelId, Tabs } from "@/components/ui/tabs";
import { deriveFlightPath, describeProgress } from "@/lib/flight-path";
import { formatBytes, formatUsd, PROBLEM_TYPE_LABEL } from "@/lib/utils";
import type {
  AgentEvent,
  AgentStatus,
  DatasetProfile,
  DecisionOut,
  ExpertiseLevel,
  InsightEvent,
  LLMStatusEvent,
  NotebookCell,
  SessionDetail,
  TemplateInfo,
  UsageOut,
} from "@/types";

type WorkspaceTab = "overview" | "agent" | "notebook";

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
    <div className="max-w-lg rounded-lg border border-line bg-surface p-4">
      <h2 className="mb-1 font-display font-medium text-ink">Choose a sheet</h2>
      <p className="mb-3 text-sm text-ink-tertiary">This workbook has more than one sheet.</p>
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
        {busy ? "Loading…" : "Analyze this sheet"}
      </button>
    </div>
  );
}

function DatasetFacts({ profile }: { profile: DatasetProfile }) {
  const missingCells = profile.columns.reduce((sum, c) => sum + c.missing_count, 0);
  const totalCells = profile.n_rows * profile.n_columns;
  const facts: { label: string; value: string; warn?: boolean }[] = [
    { label: "Rows", value: profile.n_rows.toLocaleString() },
    { label: "Columns", value: profile.n_columns.toLocaleString() },
    {
      label: "Missing cells",
      value: totalCells > 0 ? `${((missingCells / totalCells) * 100).toFixed(1)}%` : "0%",
      warn: totalCells > 0 && missingCells / totalCells > 0.1,
    },
    {
      label: "Duplicate rows",
      value: profile.n_duplicate_rows.toLocaleString(),
      warn: profile.n_duplicate_rows > 0,
    },
    {
      label: "Constant columns",
      value: profile.constant_columns.length.toLocaleString(),
      warn: profile.constant_columns.length > 0,
    },
    { label: "In memory", value: formatBytes(profile.memory_usage_bytes) },
  ];

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3">
      {facts.map((fact) => (
        <div key={fact.label} className="bg-surface px-4 py-3">
          <dt className="text-xs text-ink-tertiary">{fact.label}</dt>
          <dd
            className={`tabular mt-0.5 font-display text-xl font-medium ${fact.warn ? "text-warning" : "text-ink"}`}
          >
            {fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function SectionHeading({
  children,
  aside,
}: {
  children: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <div className="mb-2.5 flex items-baseline justify-between gap-3">
      <h2 className="font-display text-base font-medium tracking-tight text-ink">{children}</h2>
      {aside}
    </div>
  );
}

export default function SessionDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [cells, setCells] = useState<NotebookCell[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);

  const [agentStatus, setAgentStatus] = useState<AgentStatus>("not_started");
  const [agentError, setAgentError] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LLMStatusEvent["state"] | null>(null);
  const [usage, setUsage] = useState<UsageOut | null>(null);
  const [insights, setInsights] = useState<InsightEvent[]>([]);
  const [decisions, setDecisions] = useState<DecisionOut[]>([]);
  const [planSteps, setPlanSteps] = useState<string[]>([]);
  const [planIndex, setPlanIndex] = useState(0);
  const [reverting, setReverting] = useState(false);
  const [chatPrefill, setChatPrefill] = useState<string | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>("overview");
  const [highlightPosition, setHighlightPosition] = useState<number | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

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

  const refreshUsage = useCallback(() => {
    getUsage(id)
      .then(setUsage)
      .catch(() => undefined);
  }, [id]);

  const applySession = useCallback((detail: SessionDetail) => {
    setSession(detail);
    setPlanSteps(detail.plan_steps ?? []);
    setPlanIndex(detail.plan_step_index);
  }, []);

  const handleAgentEvent = useCallback(
    (event: AgentEvent) => {
      switch (event.type) {
        case "insight":
          setInsights((prev) => [...prev, event]);
          break;
        case "llm_status":
          setLlmStatus(event.state);
          setUsage((prev) =>
            prev
              ? { ...prev, calls_used: event.calls_used, calls_budget: event.calls_budget }
              : prev,
          );
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
        case "plan_update":
          setPlanSteps(event.steps);
          setPlanIndex(event.step_index);
          refreshNotebook();
          break;
        case "cell_update":
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
            setLlmStatus(null);
            refreshNotebook();
            refreshUsage();
            getSession(id)
              .then(applySession)
              .catch(() => undefined);
          }
          break;
      }
    },
    [id, refreshNotebook, refreshUsage, applySession],
  );

  const subscribe = useCallback(() => {
    unsubscribeRef.current?.();
    unsubscribeRef.current = subscribeToAgentStream(id, handleAgentEvent);
  }, [id, handleAgentEvent]);

  useEffect(() => {
    getSession(id)
      .then((detail) => {
        applySession(detail);
        setAgentStatus(detail.agent_status);
        if (detail.agent_status !== "not_started") setTab("agent");
        // A reload while the agent is mid-run would otherwise leave the page frozen until the
        // run finished; pick the live stream back up instead.
        if (detail.agent_status === "running") subscribe();
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load session."),
      );
    listTemplates()
      .then(setTemplates)
      .catch(() => undefined);
    // `subscribe` is stable per `id`; only re-run this when the session changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (session?.status !== "ready") return;
    refreshNotebook();
    refreshDecisions();
    refreshUsage();
  }, [session?.status, refreshNotebook, refreshDecisions, refreshUsage]);

  useEffect(() => () => unsubscribeRef.current?.(), []);

  const runAgent = useCallback(async () => {
    setInsights([]);
    setAgentError(null);
    setAgentStatus("running");
    setTab("agent");
    try {
      await startAgent(id);
    } catch (err) {
      setAgentError(err instanceof ApiError ? err.message : "Could not start the agent.");
      setAgentStatus("error");
      return;
    }
    subscribe();
  }, [id, subscribe]);

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
      subscribe();
    },
    [id, subscribe],
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

  const updateSettings = useCallback(
    async (change: () => Promise<SessionDetail>) => {
      try {
        applySession(await change());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not update settings.");
      }
    },
    [applySession],
  );

  const showCell = useCallback((position: number) => {
    setTab("notebook");
    setHighlightPosition(position);
  }, []);

  const showCellById = useCallback(
    (cellId: string) => {
      const cell = cells.find((c) => c.id === cellId);
      if (cell) showCell(cell.position);
    },
    [cells, showCell],
  );

  // Scroll a linked cell into view once the notebook tab has rendered it, then let the
  // highlight fade so it doesn't linger.
  useEffect(() => {
    if (highlightPosition === null || tab !== "notebook") return;
    document.getElementById(cellAnchorId(highlightPosition))?.scrollIntoView({ block: "start" });
    const timer = window.setTimeout(() => setHighlightPosition(null), 2500);
    return () => window.clearTimeout(timer);
  }, [highlightPosition, tab]);

  const handleAskAboutCell = useCallback((position: number) => {
    setChatPrefill(`@cell-${position}`);
  }, []);

  const handlePrefillConsumed = useCallback(() => {
    setChatPrefill(null);
  }, []);

  const templatesByKey = useMemo(
    () => Object.fromEntries(templates.map((t) => [t.key, t])),
    [templates],
  );

  const flightInput = {
    agentStatus,
    decisions,
    planSteps,
    planIndex,
    targetColumn: session?.target_column ?? null,
    templateTitles: Object.fromEntries(templates.map((t) => [t.key, t.title])),
  };
  const stages = deriveFlightPath(flightInput);
  const sentence = describeProgress(flightInput, stages);

  const pendingDecision = decisions.find((d) => d.selected_option === null) ?? null;
  const failedCells = cells.filter((c) => c.status === "error").length;
  const codeCells = cells.filter((c) => c.cell_type === "code").length;
  const answeredDecisions = decisions.filter((d) => d.selected_option !== null).length;

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
          <p className="mt-4 flex items-center gap-1.5 text-sm text-critical" role="alert">
            <CircleAlert size={14} />
            {error}
          </p>
        )}
        {!session && !error && (
          <div className="flex justify-center py-16">
            <SignalMeter label="Loading session" />
          </div>
        )}

        {session && (
          <div className="mt-4 flex flex-col gap-6">
            <header className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="truncate font-display text-2xl font-semibold tracking-tight text-ink">
                  {session.original_filename}
                </h1>
                <p className="tabular mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-ink-tertiary">
                  <span>
                    {session.file_type.toUpperCase()}, {formatBytes(session.size_bytes)}
                  </span>
                  {session.row_count !== null && (
                    <span>{session.row_count.toLocaleString()} rows</span>
                  )}
                  {session.column_count !== null && <span>{session.column_count} columns</span>}
                  {session.target_column && (
                    <Badge tone="accent" className="text-[11px]">
                      Target: <span className="font-mono">{session.target_column}</span>
                    </Badge>
                  )}
                  {session.problem_type && (
                    <Badge tone="secondary" className="text-[11px]">
                      {PROBLEM_TYPE_LABEL[session.problem_type] ?? session.problem_type}
                    </Badge>
                  )}
                </p>
              </div>
              {session.status === "ready" && (
                <ExportMenu sessionId={session.id} hasCells={cells.length > 0} />
              )}
            </header>

            {session.status === "needs_sheet_selection" && (
              <SheetPicker session={session} onResolved={applySession} />
            )}

            {session.status === "error" && (
              <p className="flex items-center gap-1.5 text-sm text-critical">
                <CircleAlert size={14} />
                {session.error_message ?? "This file could not be parsed."}
              </p>
            )}

            {session.status === "ready" && session.profile && (
              <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-8">
                <div className="flex min-w-0 flex-col gap-6">
                  <FlightPath
                    stages={stages}
                    sentence={sentence}
                    agentStatus={agentStatus}
                    onRun={() => void runAgent()}
                    footer={
                      <>
                        {usage && (
                          <span className="tabular" title={usage.models_used.join(", ")}>
                            LLM calls <span className="text-ink-secondary">{usage.calls_used}</span>{" "}
                            of {usage.calls_budget}
                          </span>
                        )}
                        {usage && usage.cost_budget_usd > 0 && (
                          <span className="tabular">
                            Spend{" "}
                            <span className="text-ink-secondary">
                              {formatUsd(usage.cost_used_usd)}
                            </span>{" "}
                            of {formatUsd(usage.cost_budget_usd)}
                          </span>
                        )}
                        {llmStatus === "waiting_for_capacity" && (
                          <Badge tone="warning">Waiting for LLM capacity</Badge>
                        )}
                        <span className="flex flex-wrap items-center gap-x-5 gap-y-2 sm:ml-auto">
                          <label className="flex items-center gap-1.5 text-ink-secondary">
                            Explain like I&apos;m
                            <select
                              value={session.expertise_level}
                              onChange={(e) =>
                                void updateSettings(() =>
                                  setExpertiseLevel(id, e.target.value as ExpertiseLevel),
                                )
                              }
                              className="rounded-md border border-line-strong bg-surface-2 px-1.5 py-0.5 text-xs text-ink"
                            >
                              <option value="beginner">a beginner</option>
                              <option value="intermediate">intermediate</option>
                              <option value="expert">an expert</option>
                            </select>
                          </label>
                          <label
                            className="flex cursor-pointer items-center gap-1.5 text-ink-secondary"
                            title="Accept the recommended answer at every decision instead of pausing"
                          >
                            <input
                              type="checkbox"
                              checked={session.auto_decide}
                              onChange={(e) =>
                                void updateSettings(() => setAutoDecide(id, e.target.checked))
                              }
                              className="accent-accent"
                            />
                            Let the agent decide
                          </label>
                        </span>
                      </>
                    }
                  />

                  {agentError && (
                    <p
                      className="flex items-start gap-1.5 rounded-md border border-critical/30 bg-critical/[0.06] px-3 py-2.5 text-sm text-critical"
                      role="alert"
                    >
                      <CircleAlert size={14} className="mt-0.5 shrink-0" />
                      {agentError}
                    </p>
                  )}

                  {pendingDecision && (
                    <DecisionCard
                      key={pendingDecision.id}
                      decision={pendingDecision}
                      onAnswer={handleAnswerDecision}
                      templates={templatesByKey}
                      columns={session.profile.columns
                        .map((c) => c.name)
                        .filter((name) => name !== session.target_column)}
                    />
                  )}

                  <div>
                    <Tabs<WorkspaceTab>
                      active={tab}
                      onChange={setTab}
                      items={[
                        { key: "overview", label: "Data overview" },
                        {
                          key: "agent",
                          label: "Insights & decisions",
                          count: insights.length + answeredDecisions || undefined,
                        },
                        {
                          key: "notebook",
                          label: "Notebook",
                          count: codeCells || undefined,
                          alert: failedCells > 0,
                        },
                      ]}
                    />

                    <div
                      role="tabpanel"
                      id={tabPanelId(tab)}
                      aria-labelledby={tabId(tab)}
                      className="pt-5"
                    >
                      {tab === "overview" && (
                        <div className="flex flex-col gap-6">
                          {session.profile.is_sampled && (
                            <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm text-ink">
                              This dataset has {session.profile.n_rows.toLocaleString()} rows.
                              Statistics below were computed on a random sample of{" "}
                              {session.profile.sample_size?.toLocaleString()} rows.
                            </p>
                          )}
                          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                            <DatasetFacts profile={session.profile} />
                            <DataQualityScoreCard score={session.profile.data_quality} />
                          </div>
                          <section>
                            <SectionHeading>Columns</SectionHeading>
                            <ColumnStatsTable
                              columns={session.profile.columns}
                              rowCount={
                                session.profile.is_sampled
                                  ? (session.profile.sample_size ?? undefined)
                                  : session.profile.n_rows
                              }
                            />
                          </section>
                          <section>
                            <SectionHeading>Preview</SectionHeading>
                            <PreviewTable
                              sessionId={session.id}
                              columns={session.profile.columns.map((c) => c.name)}
                            />
                          </section>
                        </div>
                      )}

                      {tab === "agent" && (
                        <div className="flex flex-col gap-8">
                          <section>
                            <SectionHeading>Insights from this run</SectionHeading>
                            <InsightFeed
                              insights={insights}
                              onJumpToCell={showCellById}
                              emptyText={
                                agentStatus === "not_started"
                                  ? "Run the agent to collect insights. Each analysis adds a few findings here."
                                  : "Live insights show here while the agent runs. Findings from earlier runs are saved in the notebook."
                              }
                            />
                          </section>
                          <section>
                            <SectionHeading>Decision log</SectionHeading>
                            <DecisionsPanel decisions={decisions} templates={templatesByKey} />
                          </section>
                          <AnalysisActions
                            sessionId={session.id}
                            templates={templates}
                            disabled={agentStatus === "running"}
                            onRunComplete={() => {
                              refreshNotebook();
                              setTab("notebook");
                            }}
                          />
                        </div>
                      )}

                      {tab === "notebook" && (
                        <NotebookPanel
                          cells={cells}
                          onRevert={agentStatus === "running" ? undefined : handleRevert}
                          reverting={reverting}
                          onAskAboutCell={handleAskAboutCell}
                          highlightPosition={highlightPosition}
                        />
                      )}
                    </div>
                  </div>
                </div>

                {/* Chat stays docked and sticky beside the scrolling workspace. */}
                <aside className="lg:sticky lg:top-[4.5rem] lg:h-[calc(100vh-6rem)]">
                  <ChatPanel
                    sessionId={session.id}
                    prefill={chatPrefill}
                    onPrefillConsumed={handlePrefillConsumed}
                    onCellLinkClick={showCell}
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
