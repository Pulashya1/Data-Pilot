"use client";

import { Calendar, Hash, Search, ToggleLeft, Type } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { ColumnProfile } from "@/types";

type ColumnKind = "numeric" | "text" | "boolean" | "date";

const KIND: Record<ColumnKind, { label: string; icon: typeof Hash }> = {
  numeric: { label: "Number", icon: Hash },
  text: { label: "Text", icon: Type },
  boolean: { label: "Yes/no", icon: ToggleLeft },
  date: { label: "Date", icon: Calendar },
};

function columnKind(col: ColumnProfile): ColumnKind {
  const dtype = col.dtype.toLowerCase();
  if (dtype.startsWith("bool")) return "boolean";
  if (dtype.includes("datetime") || dtype.includes("date")) return "date";
  if (col.numeric_stats) return "numeric";
  return "text";
}

type SortKey = "original" | "missing" | "unique";

function formatNumber(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs >= 1e6 || abs < 0.01)) return value.toExponential(1);
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** A one-line box plot: whiskers span min to max, the box spans the interquartile range, and a
 * tick marks the median. Hover shows the exact five numbers. */
function RangeGlyph({ stats }: { stats: Record<string, number> }) {
  const { min, max } = stats;
  const q1 = stats["25%"];
  const median = stats["50%"];
  const q3 = stats["75%"];
  if (min === undefined || max === undefined || q1 === undefined || q3 === undefined) return null;
  const span = max - min;
  const pos = (v: number) => (span === 0 ? 50 : ((v - min) / span) * 100);
  const title = `min ${formatNumber(min)}, 25% ${formatNumber(q1)}, median ${formatNumber(median)}, 75% ${formatNumber(q3)}, max ${formatNumber(max)}`;

  return (
    <span className="relative block h-3 w-24 shrink-0" title={title} role="img" aria-label={title}>
      <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line-strong" />
      <span
        className="absolute top-0.5 h-2 rounded-sm bg-accent/35"
        style={{ left: `${pos(q1)}%`, width: `${Math.max(pos(q3) - pos(q1), 2)}%` }}
      />
      {median !== undefined && (
        <span
          className="absolute top-0 h-3 w-0.5 -translate-x-1/2 rounded-full bg-accent"
          style={{ left: `${pos(median)}%` }}
        />
      )}
    </span>
  );
}

function MissingCell({ col }: { col: ColumnProfile }) {
  const pct = col.missing_pct;
  const tone = pct >= 50 ? "bg-critical" : pct >= 20 ? "bg-warning" : "bg-ink-tertiary";
  if (col.missing_count === 0) {
    return <span className="text-ink-tertiary">None</span>;
  }
  return (
    <span className="flex items-center gap-2">
      <span className="block h-1.5 w-12 overflow-hidden rounded-full bg-surface-3">
        <span
          className={cn("block h-full rounded-full", tone)}
          style={{ width: `${Math.max(pct, 3)}%` }}
        />
      </span>
      <span className={cn(pct >= 20 ? "text-ink" : "text-ink-secondary")}>{pct.toFixed(1)}%</span>
    </span>
  );
}

export function ColumnStatsTable({
  columns,
  rowCount,
}: {
  columns: ColumnProfile[];
  /** Total rows profiled, used to flag columns where every value is unique. */
  rowCount?: number;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("original");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q ? columns.filter((c) => c.name.toLowerCase().includes(q)) : columns;
    if (sort === "missing") return [...filtered].sort((a, b) => b.missing_pct - a.missing_pct);
    if (sort === "unique") return [...filtered].sort((a, b) => b.unique_count - a.unique_count);
    return filtered;
  }, [columns, query, sort]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-[12rem] flex-1 sm:max-w-xs">
          <span className="sr-only">Filter columns</span>
          <Search
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-tertiary"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Filter ${columns.length} columns`}
            className="w-full rounded-md border border-line-strong bg-surface-2 py-1.5 pl-8 pr-2 text-sm text-ink placeholder:text-ink-tertiary focus:border-accent"
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
          Sort by
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-md border border-line-strong bg-surface-2 px-1.5 py-1 text-xs text-ink"
          >
            <option value="original">File order</option>
            <option value="missing">Most missing</option>
            <option value="unique">Most distinct values</option>
          </select>
        </label>
      </div>

      <div className="styled-scrollbar overflow-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-surface-2 text-xs text-ink-tertiary">
            <tr>
              <th className="px-3 py-2 font-medium">Column</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Missing</th>
              <th className="px-3 py-2 font-medium">Distinct</th>
              <th className="px-3 py-2 font-medium">Values</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((col) => {
              const kind = KIND[columnKind(col)];
              const KindIcon = kind.icon;
              const allUnique =
                rowCount !== undefined && rowCount > 1 && col.unique_count >= rowCount;
              return (
                <tr
                  key={col.name}
                  className="border-t border-line transition-colors hover:bg-surface-2"
                >
                  <td className="whitespace-nowrap px-3 py-2 font-medium text-ink">{col.name}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-ink-secondary">
                    <span className="flex items-center gap-1.5" title={col.dtype}>
                      <KindIcon size={12} className="text-ink-tertiary" />
                      {kind.label}
                    </span>
                  </td>
                  <td className="tabular whitespace-nowrap px-3 py-2 text-xs">
                    <MissingCell col={col} />
                  </td>
                  <td className="tabular whitespace-nowrap px-3 py-2 text-xs text-ink-secondary">
                    {col.unique_count.toLocaleString()}
                    {col.unique_count <= 1 && <span className="ml-1.5 text-warning">constant</span>}
                    {allUnique && <span className="ml-1.5 text-ink-tertiary">all unique</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-ink-tertiary">
                    {col.numeric_stats ? (
                      <span className="tabular flex items-center gap-3 whitespace-nowrap">
                        <RangeGlyph stats={col.numeric_stats} />
                        <span>
                          {formatNumber(col.numeric_stats.min)} to{" "}
                          {formatNumber(col.numeric_stats.max)}
                          <span className="ml-2 text-ink-tertiary/80">
                            mean {formatNumber(col.numeric_stats.mean)}
                          </span>
                        </span>
                      </span>
                    ) : col.top_values && col.top_values.length > 0 ? (
                      <span className="flex flex-wrap gap-1">
                        {col.top_values.slice(0, 3).map((tv) => (
                          <span
                            key={String(tv.value)}
                            className="max-w-[10rem] truncate rounded bg-surface-3 px-1.5 py-0.5 text-ink-secondary"
                            title={`${String(tv.value)}: ${tv.count.toLocaleString()} rows`}
                          >
                            {String(tv.value)}{" "}
                            <span className="tabular text-ink-tertiary">{tv.count}</span>
                          </span>
                        ))}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-xs text-ink-tertiary">
                  No columns match &ldquo;{query}&rdquo;.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
