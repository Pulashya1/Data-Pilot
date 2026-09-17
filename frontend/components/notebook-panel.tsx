"use client";

import { CircleDot, MessagesSquare, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CellOutput, NotebookCell } from "@/types";

const STATUS_TONE: Record<NotebookCell["status"], "neutral" | "success" | "critical"> = {
  pending: "neutral",
  success: "success",
  error: "critical",
};

const MARKDOWN_COMPONENTS = {
  h1: (props: React.ComponentPropsWithoutRef<"h1">) => (
    <h1 className="mb-2 font-display text-lg font-semibold text-ink" {...props} />
  ),
  h2: (props: React.ComponentPropsWithoutRef<"h2">) => (
    <h2 className="mb-1 mt-3 font-display text-base font-semibold text-ink" {...props} />
  ),
  p: (props: React.ComponentPropsWithoutRef<"p">) => (
    <p className="mb-1 text-sm leading-relaxed text-ink-secondary" {...props} />
  ),
  ul: (props: React.ComponentPropsWithoutRef<"ul">) => (
    <ul className="mb-1 list-disc pl-5 text-sm leading-relaxed text-ink-secondary" {...props} />
  ),
  ol: (props: React.ComponentPropsWithoutRef<"ol">) => (
    <ol className="mb-1 list-decimal pl-5 text-sm leading-relaxed text-ink-secondary" {...props} />
  ),
  strong: (props: React.ComponentPropsWithoutRef<"strong">) => (
    <strong className="font-semibold text-ink" {...props} />
  ),
};

function OutputView({ output }: { output: CellOutput }) {
  if (output.output_type === "stream") {
    return (
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink-secondary">
        {output.text}
      </pre>
    );
  }
  if (output.output_type === "error") {
    return (
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-critical">
        {output.traceback.join("\n") || `${output.ename}: ${output.evalue}`}
      </pre>
    );
  }

  const png = output.data["image/png"];
  if (typeof png === "string") {
    return (
      // next/image doesn't add value for an inline base64 data URI.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`data:image/png;base64,${png}`}
        alt="Chart output from this cell"
        className="max-w-full rounded border border-line"
      />
    );
  }
  const text = output.data["text/plain"];
  if (typeof text === "string") {
    return (
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink-secondary">
        {text}
      </pre>
    );
  }
  return null;
}

function CellCard({
  cell,
  onRevert,
  reverting,
  onAskAboutCell,
}: {
  cell: NotebookCell;
  onRevert?: (cellId: string) => void;
  reverting: boolean;
  onAskAboutCell?: (position: number) => void;
}) {
  if (cell.cell_type === "markdown") {
    return (
      <div className="rounded-lg border border-line bg-surface p-4">
        <ReactMarkdown components={MARKDOWN_COMPONENTS}>{cell.source}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-line bg-surface-2 px-3 py-1.5">
        <span className="flex items-center gap-1.5 font-mono text-xs text-ink-tertiary">
          <span className="tabular text-ink-tertiary/70">[{cell.position}]</span>
          {cell.label ?? "Code"}
          {cell.is_exploratory && (
            <Badge tone="secondary" className="gap-1">
              <MessagesSquare size={9} />
              exploratory
            </Badge>
          )}
        </span>
        <div className="flex items-center gap-3">
          {onAskAboutCell && (
            <button
              type="button"
              onClick={() => onAskAboutCell(cell.position)}
              className="text-[11px] font-medium text-ink-tertiary underline decoration-line-strong underline-offset-2 transition-colors hover:text-accent"
            >
              Ask about this cell
            </button>
          )}
          {onRevert && (
            <button
              type="button"
              disabled={reverting}
              onClick={() => onRevert(cell.id)}
              className="flex items-center gap-1 text-[11px] font-medium text-ink-tertiary transition-colors hover:text-ink disabled:opacity-50"
            >
              <RotateCcw size={10} />
              Revert
            </button>
          )}
          <Badge tone={STATUS_TONE[cell.status]} className="gap-1">
            <CircleDot size={8} />
            {cell.status}
          </Badge>
        </div>
      </div>
      <pre className="overflow-x-auto px-3.5 py-2.5 font-mono text-[12.5px] leading-relaxed text-ink">
        <code>{cell.source}</code>
      </pre>
      {cell.error_message && (
        <p className="border-t border-line bg-critical/[0.06] px-3.5 py-2 font-mono text-xs text-critical">
          {cell.error_message}
        </p>
      )}
      {cell.outputs && cell.outputs.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-line px-3.5 py-2.5">
          {cell.outputs.map((output, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <OutputView key={i} output={output} />
          ))}
        </div>
      )}
    </div>
  );
}

export function NotebookPanel({
  cells,
  onRevert,
  reverting = false,
  onAskAboutCell,
  className,
}: {
  cells: NotebookCell[];
  onRevert?: (cellId: string) => void;
  reverting?: boolean;
  onAskAboutCell?: (position: number) => void;
  className?: string;
}) {
  if (cells.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-ink-tertiary">
        No notebook cells yet. Run an analysis above to get started.
      </p>
    );
  }
  return (
    <div className={cn("styled-scrollbar flex flex-col gap-3", className)}>
      {cells.map((cell) => (
        <CellCard
          key={cell.id}
          cell={cell}
          onRevert={onRevert}
          reverting={reverting}
          onAskAboutCell={onAskAboutCell}
        />
      ))}
    </div>
  );
}
