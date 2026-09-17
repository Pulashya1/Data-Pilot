import { SEVERITY_CONFIG } from "@/lib/severity";
import { cn } from "@/lib/utils";
import type { InsightEvent } from "@/types";

const TONE_CLASSES = {
  info: "border-l-info bg-info/[0.06] text-ink",
  warning: "border-l-warning bg-warning/[0.07] text-ink",
  critical: "border-l-critical bg-critical/[0.07] text-ink",
} as const;

const ICON_TONE_CLASSES = {
  info: "text-info",
  warning: "text-warning",
  critical: "text-critical",
} as const;

export function InsightFeed({ insights }: { insights: InsightEvent[] }) {
  if (insights.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-display text-xs font-medium tracking-tight text-ink-secondary">
        Insights
      </h3>
      <ul className="flex flex-col gap-2">
        {insights.map((insight, index) => {
          const config = SEVERITY_CONFIG[insight.severity];
          const Icon = config.icon;
          return (
            <li
              key={index}
              className={cn(
                "flex items-start gap-2.5 rounded-md border-l-2 py-2 pl-3 pr-3 text-sm leading-relaxed",
                TONE_CLASSES[config.tone],
              )}
            >
              <Icon
                size={15}
                className={cn("mt-0.5 shrink-0", ICON_TONE_CLASSES[config.tone])}
                aria-hidden="true"
              />
              <span>{insight.text}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
