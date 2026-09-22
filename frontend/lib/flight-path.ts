import type { AgentStatus, DecisionKind, DecisionOut } from "@/types";

/**
 * Derives the agent's progress through its graph (backend/app/agent/graph.py:
 * ingest -> understand -> plan -> execute_step* -> feature_engineering -> baseline -> summarize)
 * from what the frontend already knows: the session's agent status, its decisions, and plan
 * progress. Pure, so the workspace header and tests share one definition of "where are we".
 */

export type StageKey =
  | "profile"
  | "target"
  | "plan"
  | "explore"
  | "features"
  | "baseline"
  | "summary";

export type StageState = "done" | "active" | "waiting" | "upcoming" | "skipped" | "error";

export interface Stage {
  key: StageKey;
  label: string;
  state: StageState;
  detail: string | null;
}

export interface FlightPathInput {
  agentStatus: AgentStatus;
  decisions: DecisionOut[];
  planSteps: string[];
  /** Number of plan steps completed so far. */
  planIndex: number;
  targetColumn: string | null;
  templateTitles: Record<string, string>;
}

const DECISION_STAGE: Record<DecisionKind, StageKey> = {
  target_confirmation: "target",
  plan_approval: "plan",
  feature_engineering_approval: "features",
  baseline_approval: "baseline",
};

function findDecision(decisions: DecisionOut[], kind: DecisionKind): DecisionOut | undefined {
  return decisions.find((d) => d.kind === kind);
}

export function deriveFlightPath(input: FlightPathInput): Stage[] {
  const { agentStatus, decisions, planSteps, planIndex } = input;
  const target = findDecision(decisions, "target_confirmation");
  const plan = findDecision(decisions, "plan_approval");
  const features = findDecision(decisions, "feature_engineering_approval");
  const baseline = findDecision(decisions, "baseline_approval");
  const finished = agentStatus === "done";

  const answered = (d: DecisionOut | undefined) => d !== undefined && d.selected_option !== null;
  const exploreDone =
    answered(plan) && (features !== undefined || finished || planIndex >= planSteps.length);

  const done: Record<StageKey, boolean> = {
    profile: true,
    target: answered(target),
    plan: answered(plan),
    explore: exploreDone,
    features: answered(features) && (baseline !== undefined || finished),
    baseline: answered(baseline) && (finished || baseline?.selected_option === "no"),
    summary: finished,
  };

  const details: Record<StageKey, string | null> = {
    profile: null,
    target:
      target?.selected_option === "(no target)"
        ? "No target"
        : (target?.selected_option ?? input.targetColumn),
    plan: answered(plan) ? `${planSteps.length} analyses` : null,
    explore:
      planSteps.length > 0
        ? `${Math.min(planIndex, planSteps.length)} of ${planSteps.length}`
        : null,
    features: answered(features)
      ? features?.selected_option === "recommended"
        ? "Recommended"
        : "Custom"
      : null,
    baseline: baseline?.selected_option === "no" ? "Skipped" : null,
    summary: null,
  };

  const order: [StageKey, string][] = [
    ["profile", "Profile"],
    ["target", "Target"],
    ["plan", "Plan"],
    ["explore", "Explore"],
    ["features", "Features"],
    ["baseline", "Baseline"],
    ["summary", "Summary"],
  ];

  const pending = decisions.find((d) => d.selected_option === null);
  const waitingStage = pending ? DECISION_STAGE[pending.kind] : null;
  let currentAssigned = false;

  return order.map(([key, label]) => {
    let state: StageState;
    if (key === "baseline" && baseline?.selected_option === "no") {
      state = "skipped";
    } else if (done[key]) {
      state = "done";
    } else if (finished) {
      // The graph skips the baseline entirely for clustering/time-series/no-target sessions.
      state = "skipped";
    } else if (!currentAssigned && key === waitingStage) {
      state = "waiting";
      currentAssigned = true;
    } else if (!currentAssigned && agentStatus === "running") {
      state = "active";
      currentAssigned = true;
    } else if (!currentAssigned && agentStatus === "error") {
      state = "error";
      currentAssigned = true;
    } else {
      state = "upcoming";
    }
    return { key, label, state, detail: details[key] };
  });
}

const WAITING_SENTENCE: Record<DecisionKind, string> = {
  target_confirmation: "Waiting for you to confirm the target column.",
  plan_approval: "Waiting for you to approve the analysis plan.",
  feature_engineering_approval: "Waiting for you to choose preprocessing settings.",
  baseline_approval: "Waiting for you to decide on a baseline model.",
};

/** One plain sentence describing what the agent is doing right now. */
export function describeProgress(input: FlightPathInput, stages: Stage[]): string {
  const pending = input.decisions.find((d) => d.selected_option === null);
  if (pending) return WAITING_SENTENCE[pending.kind];

  switch (input.agentStatus) {
    case "not_started":
      return "The agent hasn't run yet. Start it to profile a target, plan, and explore.";
    case "done":
      return "Analysis complete. Review the notebook, ask questions, or export.";
    case "error":
      return "The agent stopped with an error. You can run it again.";
    case "waiting_decision":
      return "Waiting for your input.";
    case "running":
      break;
  }

  const active = stages.find((s) => s.state === "active");
  if (active?.key === "explore") {
    const step = input.planSteps[input.planIndex];
    const title = step ? (input.templateTitles[step] ?? step) : null;
    const count = `${Math.min(input.planIndex + 1, input.planSteps.length)} of ${input.planSteps.length}`;
    return title ? `Running ${title.toLowerCase()} (${count}).` : "Running analyses.";
  }
  const running: Partial<Record<StageKey, string>> = {
    target: "Reading the dataset to propose a target.",
    plan: "Drafting an analysis plan.",
    features: "Building the preprocessing pipeline.",
    baseline: "Training a baseline model.",
    summary: "Writing the summary.",
  };
  return (active && running[active.key]) ?? "Working…";
}
