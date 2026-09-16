import { cn } from "@/lib/utils";
import type { InsightEvent, InsightSeverity } from "@/types";

const SEVERITY_STYLE: Record<InsightSeverity, string> = {
  info: "border-neutral-200 bg-neutral-50 text-neutral-700 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300",
  warning:
    "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
  critical:
    "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200",
};

export function InsightFeed({ insights }: { insights: InsightEvent[] }) {
  if (insights.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-medium">Insights</h2>
      <ul className="flex flex-col gap-2">
        {insights.map((insight, index) => (
          <li
            key={index}
            className={cn("rounded-md border px-3 py-2 text-sm", SEVERITY_STYLE[insight.severity])}
          >
            {insight.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
