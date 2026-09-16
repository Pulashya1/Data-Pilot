"use client";

import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import type { CellOutput, NotebookCell } from "@/types";

const STATUS_STYLES: Record<NotebookCell["status"], string> = {
  pending: "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
  success: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  error: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

const MARKDOWN_COMPONENTS = {
  h1: (props: React.ComponentPropsWithoutRef<"h1">) => (
    <h1 className="mb-2 text-lg font-semibold" {...props} />
  ),
  h2: (props: React.ComponentPropsWithoutRef<"h2">) => (
    <h2 className="mb-1 mt-3 text-base font-semibold" {...props} />
  ),
  p: (props: React.ComponentPropsWithoutRef<"p">) => (
    <p className="mb-1 text-sm leading-relaxed" {...props} />
  ),
  ul: (props: React.ComponentPropsWithoutRef<"ul">) => (
    <ul className="mb-1 list-disc pl-5 text-sm leading-relaxed" {...props} />
  ),
  ol: (props: React.ComponentPropsWithoutRef<"ol">) => (
    <ol className="mb-1 list-decimal pl-5 text-sm leading-relaxed" {...props} />
  ),
  strong: (props: React.ComponentPropsWithoutRef<"strong">) => (
    <strong className="font-semibold" {...props} />
  ),
};

function OutputView({ output }: { output: CellOutput }) {
  if (output.output_type === "stream") {
    return (
      <pre className="whitespace-pre-wrap text-xs text-neutral-700 dark:text-neutral-300">
        {output.text}
      </pre>
    );
  }
  if (output.output_type === "error") {
    return (
      <pre className="whitespace-pre-wrap text-xs text-red-600 dark:text-red-400">
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
        className="max-w-full rounded"
      />
    );
  }
  const text = output.data["text/plain"];
  if (typeof text === "string") {
    return (
      <pre className="whitespace-pre-wrap text-xs text-neutral-700 dark:text-neutral-300">
        {text}
      </pre>
    );
  }
  return null;
}

function CellCard({ cell }: { cell: NotebookCell }) {
  if (cell.cell_type === "markdown") {
    return (
      <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
        <ReactMarkdown components={MARKDOWN_COMPONENTS}>{cell.source}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center justify-between border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
        <span className="text-xs font-medium text-neutral-500">{cell.label ?? "Code"}</span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase",
            STATUS_STYLES[cell.status],
          )}
        >
          {cell.status}
        </span>
      </div>
      <pre className="overflow-x-auto px-3 py-2 text-xs text-neutral-800 dark:text-neutral-200">
        <code>{cell.source}</code>
      </pre>
      {cell.error_message && (
        <p className="border-t border-neutral-200 px-3 py-2 text-xs text-red-600 dark:border-neutral-800 dark:text-red-400">
          {cell.error_message}
        </p>
      )}
      {cell.outputs && cell.outputs.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-neutral-200 px-3 py-2 dark:border-neutral-800">
          {cell.outputs.map((output, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <OutputView key={i} output={output} />
          ))}
        </div>
      )}
    </div>
  );
}

export function NotebookPanel({ cells }: { cells: NotebookCell[] }) {
  if (cells.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No notebook cells yet. Run an analysis below to get started.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {cells.map((cell) => (
        <CellCard key={cell.id} cell={cell} />
      ))}
    </div>
  );
}
