import { PanelHeader, PanelTitle } from "@/components/ui/panel";
import { cn } from "@/lib/utils";
import type { DataQualityScore } from "@/types";

function scoreTone(score: number): "success" | "warning" | "critical" {
  if (score >= 80) return "success";
  if (score >= 60) return "warning";
  return "critical";
}

const TEXT_TONE = { success: "text-success", warning: "text-warning", critical: "text-critical" };
const BAR_TONE = { success: "bg-success", warning: "bg-warning", critical: "bg-critical" };

export function DataQualityScoreCard({ score }: { score: DataQualityScore }) {
  const tone = scoreTone(score.overall);

  return (
    <div className="rounded-lg border border-line bg-surface">
      <PanelHeader>
        <PanelTitle>Data quality</PanelTitle>
        <span className="tabular flex items-baseline gap-1">
          <span className={cn("font-display text-2xl font-semibold", TEXT_TONE[tone])}>
            {score.overall.toFixed(0)}
          </span>
          <span className="text-xs text-ink-tertiary">/ 100</span>
        </span>
      </PanelHeader>
      <div className="flex flex-col gap-3 p-4">
        {Object.entries(score.breakdown).map(([label, value]) => {
          const rowTone = scoreTone(value);
          return (
            <div key={label}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="capitalize text-ink-secondary">{label}</span>
                <span className={cn("tabular font-medium", TEXT_TONE[rowTone])}>
                  {value.toFixed(0)}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className={cn("h-full rounded-full transition-all", BAR_TONE[rowTone])}
                  style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
                />
              </div>
            </div>
          );
        })}
        {score.issues.length > 0 && (
          <ul className="mt-1 flex flex-col gap-1.5 border-t border-line pt-3 text-xs text-ink-tertiary">
            {score.issues.map((issue) => (
              <li key={issue} className="flex gap-2">
                <span className="text-ink-tertiary">–</span>
                {issue}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
