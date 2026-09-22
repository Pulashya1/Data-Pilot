"use client";

import { ArrowDown, ArrowUp, Hand, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DecisionOut, TemplateInfo } from "@/types";

const KIND_LABEL: Record<string, string> = {
  target_confirmation: "Confirm the target",
  plan_approval: "Approve the analysis plan",
  feature_engineering_approval: "Choose preprocessing",
  baseline_approval: "Baseline model",
};

const NO_TARGET = "(no target)";
/** Above this many columns, the target picker gets a filter box instead of showing every chip. */
const TARGET_CHIP_LIMIT = 12;

type AnswerFn = (selectedOption: string) => void;

function TargetConfirmationCard({
  decision,
  busy,
  onAnswer,
}: {
  decision: DecisionOut;
  busy: boolean;
  onAnswer: AnswerFn;
}) {
  const [query, setQuery] = useState("");
  const recommended = decision.recommended_option;
  const others = decision.options.filter((o) => o !== recommended && o !== NO_TARGET);
  const needsFilter = others.length > TARGET_CHIP_LIMIT;
  const visible = needsFilter
    ? others
        .filter((o) => o.toLowerCase().includes(query.trim().toLowerCase()))
        .slice(0, TARGET_CHIP_LIMIT)
    : others;

  const chip = (option: string, primary = false) => (
    <button
      key={option}
      type="button"
      disabled={busy}
      onClick={() => onAnswer(option)}
      className={cn(
        "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50",
        option === NO_TARGET ? "font-sans" : "font-mono",
        primary
          ? "border-accent bg-accent text-accent-fg hover:bg-accent-strong"
          : "border-line-strong bg-surface text-ink-secondary hover:border-ink-tertiary hover:text-ink",
      )}
    >
      {option === NO_TARGET ? "No target — just explore" : option}
      {primary && <span className="ml-1.5 font-sans font-normal opacity-80">(recommended)</span>}
    </button>
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {recommended && chip(recommended, true)}
        {recommended !== NO_TARGET && decision.options.includes(NO_TARGET) && chip(NO_TARGET)}
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-xs text-ink-tertiary">Or pick a different column:</p>
        {needsFilter && (
          <label className="relative block max-w-xs">
            <Search
              size={12}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-tertiary"
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Filter ${others.length} columns`}
              className="w-full rounded-md border border-line-strong bg-surface-2 py-1.5 pl-7 pr-2 text-xs text-ink placeholder:text-ink-tertiary focus:border-accent"
            />
          </label>
        )}
        <div className="flex flex-wrap gap-1.5">{visible.map((o) => chip(o))}</div>
      </div>
    </div>
  );
}

function PlanApprovalCard({
  decision,
  busy,
  onAnswer,
  templates,
}: {
  decision: DecisionOut;
  busy: boolean;
  onAnswer: AnswerFn;
  templates: Record<string, TemplateInfo>;
}) {
  const recommended = (decision.recommended_option ?? "").split(",").filter(Boolean);
  const initialOrder = [
    ...recommended,
    ...decision.options.filter((o) => !recommended.includes(o)),
  ];
  const [order, setOrder] = useState<string[]>(initialOrder);
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

  const reset = () => {
    setOrder(initialOrder);
    setChecked(new Set(recommended));
  };

  const selectedSteps = order.filter((step) => checked.has(step));

  return (
    <div className="flex flex-col gap-3">
      <ol className="flex flex-col gap-1">
        {order.map((step, index) => {
          const info = templates[step];
          const isChecked = checked.has(step);
          const runOrder = isChecked ? selectedSteps.indexOf(step) + 1 : null;
          return (
            <li
              key={step}
              className={cn(
                "flex items-center gap-3 rounded-md border px-3 py-2 transition-colors",
                isChecked ? "border-line-strong bg-surface" : "border-line bg-transparent",
              )}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => toggle(step)}
                disabled={busy}
                aria-label={`Include ${info?.title ?? step}`}
                className="accent-accent"
              />
              <span className="tabular w-4 shrink-0 text-right text-xs text-ink-tertiary">
                {runOrder ?? ""}
              </span>
              <span className="min-w-0 flex-1">
                <span
                  className={cn(
                    "block text-sm",
                    isChecked ? "text-ink" : "text-ink-tertiary line-through",
                  )}
                >
                  {info?.title ?? step}
                </span>
                {info?.description && (
                  <span className="block truncate text-xs text-ink-tertiary">
                    {info.description}
                  </span>
                )}
              </span>
              <span className="flex shrink-0 gap-0.5">
                <button
                  type="button"
                  disabled={busy || index === 0}
                  onClick={() => move(step, -1)}
                  className="rounded p-1 text-ink-tertiary transition-colors hover:bg-surface-3 hover:text-ink disabled:opacity-30"
                  aria-label={`Move ${step} up`}
                >
                  <ArrowUp size={12} />
                </button>
                <button
                  type="button"
                  disabled={busy || index === order.length - 1}
                  onClick={() => move(step, 1)}
                  className="rounded p-1 text-ink-tertiary transition-colors hover:bg-surface-3 hover:text-ink disabled:opacity-30"
                  aria-label={`Move ${step} down`}
                >
                  <ArrowDown size={12} />
                </button>
              </span>
            </li>
          );
        })}
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          disabled={busy || selectedSteps.length === 0}
          onClick={() => onAnswer(selectedSteps.join(","))}
        >
          {busy ? "Submitting…" : "Approve plan"}
        </Button>
        <span className="tabular text-xs text-ink-tertiary">
          {selectedSteps.length} of {order.length} analyses selected
        </span>
        <button
          type="button"
          onClick={reset}
          disabled={busy}
          className="ml-auto flex items-center gap-1 text-xs text-ink-tertiary transition-colors hover:text-ink"
        >
          <RotateCcw size={11} />
          Reset to recommended
        </button>
      </div>
    </div>
  );
}

interface FeatureSettings {
  numeric_impute: string;
  categorical_impute: string;
  scaling: string;
  high_cardinality_threshold: number;
  test_size: number;
  drop_columns: string[];
}

// Mirrors the `feature_engineering` template's defaults (backend/app/analysis/templates/
// feature_engineering.py); only fields that differ from these are sent as overrides.
const FEATURE_DEFAULTS: FeatureSettings = {
  numeric_impute: "median",
  categorical_impute: "most_frequent",
  scaling: "standard",
  high_cardinality_threshold: 15,
  test_size: 0.2,
  drop_columns: [],
};

const NUMERIC_IMPUTE_LABEL: Record<string, string> = {
  median: "Median",
  mean: "Mean",
  most_frequent: "Most frequent value",
  constant: "Zero",
};

const CATEGORICAL_IMPUTE_LABEL: Record<string, string> = {
  most_frequent: "Most frequent value",
  constant: 'Its own "missing" category',
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-ink-secondary">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-ink-tertiary">{hint}</span>}
    </label>
  );
}

const SELECT_CLASS =
  "rounded-md border border-line-strong bg-surface-2 px-2 py-1.5 text-sm text-ink focus:border-accent";

function FeatureEngineeringCard({
  busy,
  onAnswer,
  columns,
}: {
  busy: boolean;
  onAnswer: AnswerFn;
  columns: string[];
}) {
  const [customizing, setCustomizing] = useState(false);
  const [settings, setSettings] = useState<FeatureSettings>(FEATURE_DEFAULTS);

  const overrides = useMemo(() => {
    const changed: Partial<FeatureSettings> = {};
    (Object.keys(FEATURE_DEFAULTS) as (keyof FeatureSettings)[]).forEach((key) => {
      if (JSON.stringify(settings[key]) !== JSON.stringify(FEATURE_DEFAULTS[key])) {
        Object.assign(changed, { [key]: settings[key] });
      }
    });
    return changed;
  }, [settings]);

  const set = <K extends keyof FeatureSettings>(key: K, value: FeatureSettings[K]) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  const toggleDrop = (column: string) =>
    set(
      "drop_columns",
      settings.drop_columns.includes(column)
        ? settings.drop_columns.filter((c) => c !== column)
        : [...settings.drop_columns, column],
    );

  const hasOverrides = Object.keys(overrides).length > 0;

  return (
    <div className="flex flex-col gap-3">
      <ul className="grid gap-x-6 gap-y-1 text-xs text-ink-secondary sm:grid-cols-2">
        <li>Missing numbers: {NUMERIC_IMPUTE_LABEL[settings.numeric_impute]?.toLowerCase()}</li>
        <li>
          Missing categories: {CATEGORICAL_IMPUTE_LABEL[settings.categorical_impute]?.toLowerCase()}
        </li>
        <li>Scaling: {settings.scaling === "standard" ? "standardize" : "none"}</li>
        <li>One-hot encode up to {settings.high_cardinality_threshold} categories</li>
        <li>Hold out {Math.round(settings.test_size * 100)}% for testing</li>
        <li>
          Extra columns dropped:{" "}
          {settings.drop_columns.length > 0 ? settings.drop_columns.join(", ") : "none"}
        </li>
      </ul>

      {customizing && (
        <div className="grid gap-4 rounded-md border border-line bg-surface p-4 sm:grid-cols-2">
          <Field label="Fill missing numbers with">
            <select
              value={settings.numeric_impute}
              onChange={(e) => set("numeric_impute", e.target.value)}
              className={SELECT_CLASS}
            >
              {Object.entries(NUMERIC_IMPUTE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fill missing categories with">
            <select
              value={settings.categorical_impute}
              onChange={(e) => set("categorical_impute", e.target.value)}
              className={SELECT_CLASS}
            >
              {Object.entries(CATEGORICAL_IMPUTE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Scale numeric features">
            <select
              value={settings.scaling}
              onChange={(e) => set("scaling", e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="standard">Standardize (mean 0, std 1)</option>
              <option value="none">Leave as is</option>
            </select>
          </Field>
          <Field
            label="Max categories to one-hot encode"
            hint="Categorical columns with more distinct values are left out."
          >
            <input
              type="number"
              min={2}
              max={200}
              value={settings.high_cardinality_threshold}
              onChange={(e) =>
                set("high_cardinality_threshold", Math.max(2, Number(e.target.value) || 2))
              }
              className={SELECT_CLASS}
            />
          </Field>
          <Field label={`Test split: ${Math.round(settings.test_size * 100)}%`}>
            <input
              type="range"
              min={0.1}
              max={0.4}
              step={0.05}
              value={settings.test_size}
              onChange={(e) => set("test_size", Number(e.target.value))}
              className="accent-accent"
            />
          </Field>
          {columns.length > 0 && (
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <span className="text-xs font-medium text-ink-secondary">
                Also drop these columns
              </span>
              <div className="flex flex-wrap gap-1.5">
                {columns.map((column) => {
                  const dropped = settings.drop_columns.includes(column);
                  return (
                    <button
                      key={column}
                      type="button"
                      aria-pressed={dropped}
                      onClick={() => toggleDrop(column)}
                      className={cn(
                        "rounded-md border px-2 py-1 font-mono text-[11px] transition-colors",
                        dropped
                          ? "border-critical/50 bg-critical/10 text-critical line-through"
                          : "border-line-strong text-ink-secondary hover:text-ink",
                      )}
                    >
                      {column}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {customizing && hasOverrides ? (
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => onAnswer(JSON.stringify(overrides))}
          >
            {busy ? "Submitting…" : "Build with these settings"}
          </Button>
        ) : (
          <Button variant="primary" disabled={busy} onClick={() => onAnswer("recommended")}>
            {busy ? "Submitting…" : "Use recommended settings"}
          </Button>
        )}
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => {
            if (customizing) setSettings(FEATURE_DEFAULTS);
            setCustomizing((prev) => !prev);
          }}
        >
          <SlidersHorizontal size={12} />
          {customizing ? "Back to recommended" : "Customize"}
        </Button>
      </div>
    </div>
  );
}

function BaselineCard({ busy, onAnswer }: { busy: boolean; onAnswer: AnswerFn }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="primary" disabled={busy} onClick={() => onAnswer("yes")}>
        Train baseline model
      </Button>
      <Button variant="outline" disabled={busy} onClick={() => onAnswer("no")}>
        Skip
      </Button>
    </div>
  );
}

export function DecisionCard({
  decision,
  onAnswer,
  templates = {},
  columns = [],
}: {
  decision: DecisionOut;
  onAnswer: (decisionId: string, selectedOption: string) => Promise<void>;
  /** Template metadata keyed by template key, used to show readable plan step names. */
  templates?: Record<string, TemplateInfo>;
  /** Dataset column names, offered as extra columns to drop during preprocessing. */
  columns?: string[];
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answer = async (selectedOption: string) => {
    setBusy(true);
    setError(null);
    try {
      await onAnswer(decision.id, selectedOption);
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Could not submit your answer. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const onAnswerOption = (o: string) => void answer(o);

  return (
    <section
      aria-label="Decision needed"
      className="animate-fade-in flex flex-col gap-3 rounded-lg border border-warning/40 bg-warning/[0.05] p-4 sm:p-5"
    >
      <div className="flex items-center gap-2 text-xs font-medium text-warning">
        <Hand size={13} />
        {KIND_LABEL[decision.kind] ?? decision.kind}
        <span className="font-normal text-ink-tertiary">The agent is paused until you answer.</span>
      </div>
      <h2 className="font-display text-lg font-medium tracking-tight text-ink">
        {decision.question}
      </h2>
      {decision.reasoning && decision.kind !== "feature_engineering_approval" && (
        <p className="max-w-3xl text-sm leading-relaxed text-ink-secondary">{decision.reasoning}</p>
      )}
      {decision.kind === "plan_approval" ? (
        <PlanApprovalCard
          decision={decision}
          busy={busy}
          onAnswer={onAnswerOption}
          templates={templates}
        />
      ) : decision.kind === "feature_engineering_approval" ? (
        <FeatureEngineeringCard busy={busy} onAnswer={onAnswerOption} columns={columns} />
      ) : decision.kind === "baseline_approval" ? (
        <BaselineCard busy={busy} onAnswer={onAnswerOption} />
      ) : (
        <TargetConfirmationCard decision={decision} busy={busy} onAnswer={onAnswerOption} />
      )}
      {error && <p className="text-xs text-critical">{error}</p>}
    </section>
  );
}
