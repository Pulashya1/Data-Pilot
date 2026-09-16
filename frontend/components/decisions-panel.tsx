import { cn } from "@/lib/utils";
import type { DecisionOut } from "@/types";

export function DecisionsPanel({ decisions }: { decisions: DecisionOut[] }) {
  const answered = decisions.filter((d) => d.selected_option !== null);
  if (answered.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-medium">Decisions</h2>
      <ul className="flex flex-col gap-2">
        {answered.map((decision) => (
          <li
            key={decision.id}
            className="rounded-md border border-neutral-200 px-3 py-2 text-xs dark:border-neutral-800"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{decision.question}</span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 font-medium uppercase",
                  decision.auto_decided
                    ? "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
                )}
              >
                {decision.auto_decided ? "auto-decided" : "you decided"}
              </span>
            </div>
            <p className="mt-1 text-neutral-700 dark:text-neutral-300">
              → {decision.selected_option}
            </p>
            {decision.reasoning && <p className="mt-1 text-neutral-500">{decision.reasoning}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
