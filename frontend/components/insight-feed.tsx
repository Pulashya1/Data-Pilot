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

const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2 } as const;

export function InsightFeed({
  insights,
  onJumpToCell,
  emptyText = "Insights appear here as the agent runs each analysis.",
}: {
  insights: InsightEvent[];
  /** Called with an insight's related cell id, to show the cell it came from. */
  onJumpToCell?: (cellId: string) => void;
  emptyText?: string;
}) {
  if (insights.length === 0) {
    return <p className="text-sm text-ink-tertiary">{emptyText}</p>;
  }

  // Most severe first, keeping arrival order within a severity.
  const ordered = insights
    .map((insight, index) => ({ insight, index }))
    .sort(
      (a, b) =>
        SEVERITY_ORDER[a.insight.severity] - SEVERITY_ORDER[b.insight.severity] ||
        a.index - b.index,
    );

  return (
    <ul className="flex flex-col gap-2">
      {ordered.map(({ insight, index }) => {
        const config = SEVERITY_CONFIG[insight.severity];
        const Icon = config.icon;
        return (
          <li
            key={index}
            className={cn(
              "animate-fade-in flex items-start gap-2.5 rounded-md border-l-2 py-2 pl-3 pr-3 text-sm leading-relaxed",
              TONE_CLASSES[config.tone],
            )}
          >
            <Icon
              size={15}
              className={cn("mt-0.5 shrink-0", ICON_TONE_CLASSES[config.tone])}
              aria-label={config.label}
            />
            <span className="flex-1">{insight.text}</span>
            {insight.related_cell_id && onJumpToCell && (
              <button
                type="button"
                onClick={() => onJumpToCell(insight.related_cell_id as string)}
                className="shrink-0 text-xs text-ink-tertiary underline decoration-line-strong underline-offset-2 hover:text-accent"
              >
                Show cell
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
