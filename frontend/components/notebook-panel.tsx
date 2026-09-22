"use client";

import {
  Check,
  ChevronDown,
  CircleAlert,
  CircleDot,
  Copy,
  MessagesSquare,
  RotateCcw,
} from "lucide-react";
import { useState } from "react";
import ReactMarkdown, { type ExtraProps } from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CellOutput, NotebookCell } from "@/types";

const STATUS_TONE: Record<NotebookCell["status"], "neutral" | "success" | "critical"> = {
  pending: "neutral",
  success: "success",
  error: "critical",
};

/** Code longer than this many lines starts collapsed behind a "Show all" toggle. */
const COLLAPSED_LINES = 12;

// Jupyter tracebacks carry terminal color codes; they render as garbage in a <pre>.
// eslint-disable-next-line no-control-regex
const ANSI_PATTERN = /\u001b\[[0-9;]*m/g;

export function stripAnsi(text: string): string {
  return text.replace(ANSI_PATTERN, "");
}

type MarkdownTag = "h1" | "h2" | "h3" | "p" | "ul" | "ol" | "strong" | "code";

/** A react-markdown component for `tag` with fixed styling. Drops the `node` prop that
 * react-markdown passes, so it doesn't end up as a DOM attribute. */
export function markdownElement(tag: MarkdownTag, className: string) {
  const Tag = tag as React.ElementType;
  function MarkdownElement({
    node: _node,
    ...props
  }: React.HTMLAttributes<HTMLElement> & ExtraProps) {
    return <Tag {...props} className={className} />;
  }
  return MarkdownElement;
}

export const MARKDOWN_COMPONENTS = {
  h1: markdownElement("h1", "mb-2 font-display text-lg font-semibold text-ink"),
  h2: markdownElement("h2", "mb-1 mt-3 font-display text-base font-semibold text-ink first:mt-0"),
  h3: markdownElement("h3", "mb-1 mt-2 font-display text-sm font-semibold text-ink"),
  p: markdownElement("p", "mb-1.5 text-sm leading-relaxed text-ink-secondary last:mb-0"),
  ul: markdownElement("ul", "mb-1.5 list-disc pl-5 text-sm leading-relaxed text-ink-secondary"),
  ol: markdownElement("ol", "mb-1.5 list-decimal pl-5 text-sm leading-relaxed text-ink-secondary"),
  strong: markdownElement("strong", "font-semibold text-ink"),
  code: markdownElement(
    "code",
    "rounded bg-surface-3 px-1 py-0.5 font-mono text-[0.85em] text-ink",
  ),
};

function OutputView({ output }: { output: CellOutput }) {
  if (output.output_type === "stream") {
    return (
      <pre
        className={cn(
          "whitespace-pre-wrap font-mono text-xs leading-relaxed",
          output.name === "stderr" ? "text-warning" : "text-ink-secondary",
        )}
      >
        {stripAnsi(output.text)}
      </pre>
    );
  }
  if (output.output_type === "error") {
    return (
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-critical">
        {stripAnsi(output.traceback.join("\n")) || `${output.ename}: ${output.evalue}`}
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
        className="max-w-full rounded border border-line bg-white"
      />
    );
  }
  const text = output.data["text/plain"];
  if (typeof text === "string") {
    return (
      <pre className="overflow-x-auto whitespace-pre font-mono text-xs leading-relaxed text-ink-secondary">
        {text}
      </pre>
    );
  }
  return null;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
      aria-label={copied ? "Copied" : "Copy code"}
      title={copied ? "Copied" : "Copy code"}
      className="rounded p-1 text-ink-tertiary transition-colors hover:bg-surface-3 hover:text-ink"
    >
      {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
    </button>
  );
}

function CodeBlock({ source }: { source: string }) {
  const lineCount = source.split("\n").length;
  const collapsible = lineCount > COLLAPSED_LINES;
  const [expanded, setExpanded] = useState(false);
  const collapsed = collapsible && !expanded;

  return (
    <div className="relative">
      <pre
        className={cn(
          "overflow-x-auto px-3.5 py-2.5 font-mono text-[12.5px] leading-relaxed text-ink",
          collapsed && "max-h-[14.5rem] overflow-y-hidden",
        )}
      >
        <code>{source}</code>
      </pre>
      {collapsible && (
        <div
          className={cn(
            "flex justify-center pb-2",
            collapsed &&
              "absolute inset-x-0 bottom-0 bg-gradient-to-t from-surface via-surface/90 to-transparent pt-10",
          )}
        >
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
            className="flex items-center gap-1 rounded-md border border-line bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-ink-secondary transition-colors hover:text-ink"
          >
            <ChevronDown
              size={11}
              className={cn("transition-transform", expanded && "rotate-180")}
            />
            {expanded ? "Collapse code" : `Show all ${lineCount} lines`}
          </button>
        </div>
      )}
    </div>
  );
}

function RevertControl({
  cellId,
  reverting,
  onRevert,
}: {
  cellId: string;
  reverting: boolean;
  onRevert: (cellId: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <span className="flex items-center gap-2 text-[11px]">
        <span className="text-ink-secondary">Delete every cell after this one?</span>
        <button
          type="button"
          disabled={reverting}
          onClick={() => {
            onRevert(cellId);
            setConfirming(false);
          }}
          className="font-medium text-critical hover:underline disabled:opacity-50"
        >
          Delete them
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          className="text-ink-tertiary hover:text-ink"
        >
          Cancel
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      disabled={reverting}
      onClick={() => setConfirming(true)}
      title="Remove the cells after this one and rebuild the kernel from here"
      className="flex items-center gap-1 text-[11px] font-medium text-ink-tertiary transition-colors hover:text-ink disabled:opacity-50"
    >
      <RotateCcw size={10} />
      Revert to here
    </button>
  );
}

export function cellAnchorId(position: number): string {
  return `cell-${position}`;
}

function CellCard({
  cell,
  onRevert,
  reverting,
  onAskAboutCell,
  showCode,
  highlighted,
}: {
  cell: NotebookCell;
  onRevert?: (cellId: string) => void;
  reverting: boolean;
  onAskAboutCell?: (position: number) => void;
  showCode: boolean;
  highlighted: boolean;
}) {
  const ring = highlighted && "ring-2 ring-accent/60 ring-offset-2 ring-offset-canvas";

  if (cell.cell_type === "markdown") {
    return (
      <div
        id={cellAnchorId(cell.position)}
        className={cn(
          "scroll-mt-24 rounded-lg border border-line bg-surface p-4 transition-shadow",
          ring,
        )}
      >
        <ReactMarkdown components={MARKDOWN_COMPONENTS}>{cell.source}</ReactMarkdown>
      </div>
    );
  }

  const hasOutputs = cell.outputs !== null && cell.outputs.length > 0;

  return (
    <div
      id={cellAnchorId(cell.position)}
      className={cn(
        "scroll-mt-24 overflow-hidden rounded-lg border bg-surface transition-shadow",
        cell.status === "error" ? "border-critical/40" : "border-line",
        ring,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-3 py-1.5">
        <span className="flex min-w-0 items-center gap-1.5 font-mono text-xs text-ink-tertiary">
          <span className="tabular text-ink-tertiary/70">[{cell.position}]</span>
          <span className="truncate">{cell.label ?? "Code"}</span>
          {cell.is_exploratory && (
            <Badge tone="secondary" className="gap-1">
              <MessagesSquare size={9} />
              exploratory
            </Badge>
          )}
        </span>
        <div className="flex flex-wrap items-center gap-3">
          {onAskAboutCell && (
            <button
              type="button"
              onClick={() => onAskAboutCell(cell.position)}
              className="text-[11px] font-medium text-ink-tertiary underline decoration-line-strong underline-offset-2 transition-colors hover:text-accent"
            >
              Ask about this cell
            </button>
          )}
          {onRevert && <RevertControl cellId={cell.id} reverting={reverting} onRevert={onRevert} />}
          {showCode && <CopyButton text={cell.source} />}
          <Badge tone={STATUS_TONE[cell.status]} className="gap-1">
            <CircleDot size={8} />
            {cell.status}
          </Badge>
        </div>
      </div>
      {showCode && <CodeBlock source={cell.source} />}
      {cell.error_message && (
        <p className="border-t border-line bg-critical/[0.06] px-3.5 py-2 font-mono text-xs text-critical">
          {stripAnsi(cell.error_message)}
        </p>
      )}
      {hasOutputs && (
        <div
          className={cn("flex flex-col gap-2 px-3.5 py-2.5", showCode && "border-t border-line")}
        >
          {cell.outputs?.map((output, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <OutputView key={i} output={output} />
          ))}
        </div>
      )}
      {!showCode && !hasOutputs && !cell.error_message && (
        <p className="px-3.5 py-2.5 text-xs text-ink-tertiary">No output.</p>
      )}
    </div>
  );
}

export function NotebookPanel({
  cells,
  onRevert,
  reverting = false,
  onAskAboutCell,
  highlightPosition = null,
  className,
}: {
  cells: NotebookCell[];
  onRevert?: (cellId: string) => void;
  reverting?: boolean;
  onAskAboutCell?: (position: number) => void;
  /** Position of a cell to outline, e.g. after following an @cell link from chat. */
  highlightPosition?: number | null;
  className?: string;
}) {
  const [showCode, setShowCode] = useState(true);

  if (cells.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-ink-tertiary">
        No notebook cells yet. Run the agent, or a single analysis, to start the notebook.
      </p>
    );
  }

  const codeCells = cells.filter((c) => c.cell_type === "code");
  const failed = codeCells.filter((c) => c.status === "error");
  const firstFailed = failed[0];

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-tertiary">
        <span className="tabular">
          {codeCells.length} code {codeCells.length === 1 ? "cell" : "cells"}
        </span>
        {firstFailed && (
          <a
            href={`#${cellAnchorId(firstFailed.position)}`}
            className="tabular flex items-center gap-1 text-critical hover:underline"
          >
            <CircleAlert size={12} />
            {failed.length} failed
          </a>
        )}
        <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-ink-secondary">
          <input
            type="checkbox"
            checked={showCode}
            onChange={(e) => setShowCode(e.target.checked)}
            className="accent-accent"
          />
          Show code
        </label>
      </div>
      {cells.map((cell) => (
        <CellCard
          key={cell.id}
          cell={cell}
          onRevert={onRevert}
          reverting={reverting}
          onAskAboutCell={onAskAboutCell}
          showCode={showCode}
          highlighted={cell.position === highlightPosition}
        />
      ))}
    </div>
  );
}
