"use client";

import { CircleHelp } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { DecisionOut } from "@/types";

const KIND_LABEL: Record<string, string> = {
  target_confirmation: "Confirm target",
  plan_approval: "Approve plan",
  feature_engineering_approval: "Approve feature engineering",
  baseline_approval: "Run baseline model?",
};

function TargetConfirmationCard({
  decision,
  busy,
  onAnswer,
}: {
  decision: DecisionOut;
  busy: boolean;
  onAnswer: (selectedOption: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {decision.options.map((option) => (
        <button
          key={option}
          type="button"
          disabled={busy}
          onClick={() => onAnswer(option)}
          className={cn(
            "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50",
            option === decision.recommended_option
              ? "border-secondary/50 bg-secondary/12 text-secondary-strong hover:bg-secondary/20"
              : "border-line-strong text-ink-secondary hover:border-line-strong hover:text-ink",
          )}
        >
          {option}
          {option === decision.recommended_option && " (recommended)"}
        </button>
      ))}
    </div>
  );
}

function PlanApprovalCard({
  decision,
  busy,
  onAnswer,
}: {
  decision: DecisionOut;
  busy: boolean;
  onAnswer: (selectedOption: string) => void;
}) {
  const recommended = (decision.recommended_option ?? "").split(",").filter(Boolean);
  const initial = [...recommended, ...decision.options.filter((o) => !recommended.includes(o))];
  const [order, setOrder] = useState<string[]>(initial);
  const [checked, setChecked] = useState<Set<string>>(new Set(recommended));

  const toggle = (step: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(step)) next.delete(step);
      else next.add(step);
      return next;
    });
  };

  const move = (step: string, direction: -1 | 1) => {
    setOrder((prev) => {
      const index = prev.indexOf(step);
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      const a = next[index];
      const b = next[target];
      if (a === undefined || b === undefined) return prev;
      next[index] = b;
      next[target] = a;
      return next;
    });
  };

  const selectedSteps = order.filter((step) => checked.has(step));

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-1">
        {order.map((step, index) => (
          <li
            key={step}
            className="flex items-center gap-2 rounded-md border border-line-strong bg-surface-2 px-2 py-1.5 font-mono text-xs"
          >
            <input
              type="checkbox"
              checked={checked.has(step)}
              onChange={() => toggle(step)}
              disabled={busy}
              className="accent-secondary"
            />
            <span className="flex-1 text-ink">{step}</span>
            <button
              type="button"
              disabled={busy || index === 0}
              onClick={() => move(step, -1)}
              className="text-ink-tertiary transition-colors hover:text-ink disabled:opacity-30"
              aria-label={`Move ${step} up`}
            >
              ↑
            </button>
            <button
              type="button"
              disabled={busy || index === order.length - 1}
              onClick={() => move(step, 1)}
              className="text-ink-tertiary transition-colors hover:text-ink disabled:opacity-30"
              aria-label={`Move ${step} down`}
            >
              ↓
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        disabled={busy || selectedSteps.length === 0}
        onClick={() => onAnswer(selectedSteps.join(","))}
        className="self-start rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-secondary-strong disabled:opacity-50"
      >
        {busy ? "Submitting…" : "Approve plan"}
      </button>
    </div>
  );
}

export function DecisionCard({
  decision,
  onAnswer,
}: {
  decision: DecisionOut;
  onAnswer: (decisionId: string, selectedOption: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answer = async (selectedOption: string) => {
    setBusy(true);
    setError(null);
    try {
      await onAnswer(decision.id, selectedOption);
    } catch {
      setError("Could not submit your answer. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2.5 rounded-lg border border-secondary/30 bg-secondary/[0.05] p-4">
      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-secondary-strong">
        <CircleHelp size={13} />
        {KIND_LABEL[decision.kind] ?? decision.kind} — awaiting your input
      </span>
      <p className="text-sm font-medium text-ink">{decision.question}</p>
      {decision.reasoning && (
        <p className="text-xs leading-relaxed text-ink-tertiary">{decision.reasoning}</p>
      )}
      {decision.kind === "plan_approval" ? (
        <PlanApprovalCard decision={decision} busy={busy} onAnswer={(o) => void answer(o)} />
      ) : (
        <TargetConfirmationCard decision={decision} busy={busy} onAnswer={(o) => void answer(o)} />
      )}
      {error && <p className="text-xs text-critical">{error}</p>}
    </div>
  );
}
