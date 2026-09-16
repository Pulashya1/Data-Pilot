import { cn } from "@/lib/utils";
import type { DataQualityScore } from "@/types";

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function barColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
}

export function DataQualityScoreCard({ score }: { score: DataQualityScore }) {
  return (
    <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex items-baseline gap-2">
        <span className={cn("text-3xl font-semibold", scoreColor(score.overall))}>
          {score.overall.toFixed(0)}
        </span>
        <span className="text-sm text-neutral-500">/ 100 data quality</span>
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {Object.entries(score.breakdown).map(([label, value]) => (
          <div key={label}>
            <div className="mb-0.5 flex justify-between text-xs text-neutral-500">
              <span className="capitalize">{label}</span>
              <span>{value.toFixed(0)}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-neutral-200 dark:bg-neutral-800">
              <div
                className={cn("h-1.5 rounded-full", barColor(value))}
                style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      {score.issues.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 text-xs text-neutral-600 dark:text-neutral-400">
          {score.issues.map((issue) => (
            <li key={issue}>• {issue}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
