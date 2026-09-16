"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getPreview } from "@/lib/api";
import type { PreviewRow } from "@/types";

const ROW_HEIGHT = 32;
const VIEWPORT_HEIGHT = 384;
const OVERSCAN = 8;

/**
 * Renders only the rows scrolled into view (plus a small overscan buffer)
 * instead of the whole table, so a few hundred cached preview rows stay cheap
 * to scroll regardless of column count.
 */
export function PreviewTable({ sessionId, columns }: { sessionId: string; columns: string[] }) {
  const [rows, setRows] = useState<PreviewRow[]>([]);
  const [totalAvailable, setTotalAvailable] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getPreview(sessionId, 0, 500)
      .then((res) => {
        setRows(res.rows);
        setTotalAvailable(res.total_available);
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load preview."),
      );
  }, [sessionId]);

  const { startIndex, visibleRows, topPad, bottomPad } = useMemo(() => {
    const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
    const visibleCount = Math.ceil(VIEWPORT_HEIGHT / ROW_HEIGHT) + OVERSCAN * 2;
    const end = Math.min(rows.length, start + visibleCount);
    return {
      startIndex: start,
      visibleRows: rows.slice(start, end),
      topPad: start * ROW_HEIGHT,
      bottomPad: (rows.length - end) * ROW_HEIGHT,
    };
  }, [rows, scrollTop]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (rows.length === 0)
    return <p className="text-sm text-neutral-500">No preview rows available.</p>;

  return (
    <div>
      <div
        ref={containerRef}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
        style={{ height: VIEWPORT_HEIGHT }}
        className="overflow-auto rounded-lg border border-neutral-200 dark:border-neutral-800"
      >
        <table className="w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 bg-neutral-100 dark:bg-neutral-900">
            <tr>
              {columns.map((col) => (
                <th key={col} className="whitespace-nowrap px-3 py-1.5 font-medium">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topPad > 0 && (
              <tr style={{ height: topPad }}>
                <td colSpan={columns.length} />
              </tr>
            )}
            {visibleRows.map((row, i) => (
              <tr
                key={startIndex + i}
                style={{ height: ROW_HEIGHT }}
                className="border-t border-neutral-100 dark:border-neutral-800"
              >
                {columns.map((col) => (
                  <td key={col} className="whitespace-nowrap px-3 py-1.5">
                    {row[col] === null || row[col] === undefined ? (
                      <span className="text-neutral-400">—</span>
                    ) : (
                      String(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {bottomPad > 0 && (
              <tr style={{ height: bottomPad }}>
                <td colSpan={columns.length} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs text-neutral-500">
        Showing {rows.length.toLocaleString()} of {totalAvailable.toLocaleString()} cached preview
        rows.
      </p>
    </div>
  );
}
