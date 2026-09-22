import { Badge } from "@/components/ui/badge";
import type { DecisionOut, TemplateInfo } from "@/types";

const KIND_TITLE: Record<string, string> = {
  target_confirmation: "Target",
  plan_approval: "Analysis plan",
  feature_engineering_approval: "Preprocessing",
  baseline_approval: "Baseline model",
};

/** Renders a stored answer in words: plan step titles instead of keys, a readable summary of a
 * JSON preprocessing override, and "Train"/"Skip" instead of yes/no. */
export function formatDecisionAnswer(
  decision: DecisionOut,
  templates: Record<string, TemplateInfo> = {},
): string {
  const answer = decision.selected_option ?? "";
  switch (decision.kind) {
    case "target_confirmation":
      return answer === "(no target)" ? "No target, explore only" : answer;
    case "plan_approval":
      return answer
        .split(",")
        .map((step) => templates[step]?.title ?? step)
        .join(", ");
    case "baseline_approval":
      return answer === "yes" ? "Train a baseline model" : "Skip the baseline";
    case "feature_engineering_approval": {
      if (answer === "recommended") return "Recommended defaults";
      try {
        const overrides = JSON.parse(answer) as Record<string, unknown>;
        const parts = Object.entries(overrides).map(([key, value]) =>
          Array.isArray(value)
            ? `${key.replace(/_/g, " ")}: ${value.join(", ")}`
            : `${key.replace(/_/g, " ")}: ${String(value)}`,
        );
        return `Custom (${parts.join("; ")})`;
      } catch {
        return answer;
      }
    }
  }
}

export function DecisionsPanel({
  decisions,
  templates,
}: {
  decisions: DecisionOut[];
  templates?: Record<string, TemplateInfo>;
}) {
  const answered = decisions.filter((d) => d.selected_option !== null);
  if (answered.length === 0) {
    return (
      <p className="text-sm text-ink-tertiary">
        No decisions yet. The agent asks before choosing a target, a plan, preprocessing, and a
        baseline model.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-2">
      {answered.map((decision) => (
        <li key={decision.id} className="rounded-md border border-line bg-surface-2 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-ink-secondary">
              {KIND_TITLE[decision.kind] ?? decision.question}
            </span>
            <Badge tone={decision.auto_decided ? "neutral" : "success"} className="shrink-0">
              {decision.auto_decided ? "Agent decided" : "You decided"}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-ink">{formatDecisionAnswer(decision, templates)}</p>
          {decision.reasoning && decision.kind !== "feature_engineering_approval" && (
            <p className="mt-1 text-xs leading-relaxed text-ink-tertiary">{decision.reasoning}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
