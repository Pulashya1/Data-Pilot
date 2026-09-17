import { Badge } from "@/components/ui/badge";
import type { DecisionOut } from "@/types";

export function DecisionsPanel({ decisions }: { decisions: DecisionOut[] }) {
  const answered = decisions.filter((d) => d.selected_option !== null);
  if (answered.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-display text-xs font-medium tracking-tight text-ink-secondary">
        Decisions
      </h3>
      <ul className="flex flex-col gap-2">
        {answered.map((decision) => (
          <li
            key={decision.id}
            className="rounded-md border border-line bg-surface-2 px-3 py-2.5 text-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-ink">{decision.question}</span>
              <Badge tone={decision.auto_decided ? "neutral" : "success"} className="shrink-0">
                {decision.auto_decided ? "Auto-decided" : "You decided"}
              </Badge>
            </div>
            <p className="mt-1.5 font-mono text-[11px] text-accent-strong">
              → {decision.selected_option}
            </p>
            {decision.reasoning && <p className="mt-1 text-ink-tertiary">{decision.reasoning}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
