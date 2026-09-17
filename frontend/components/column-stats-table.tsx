import type { ColumnProfile } from "@/types";

export function ColumnStatsTable({ columns }: { columns: ColumnProfile[] }) {
  return (
    <div className="styled-scrollbar overflow-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-surface-2 font-mono text-xs uppercase tracking-wide text-ink-tertiary">
          <tr>
            <th className="px-3 py-2 font-medium">Column</th>
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Missing</th>
            <th className="px-3 py-2 font-medium">Unique</th>
            <th className="px-3 py-2 font-medium">Summary</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr
              key={col.name}
              className="border-t border-line transition-colors hover:bg-surface-2"
            >
              <td className="whitespace-nowrap px-3 py-2 font-medium text-ink">{col.name}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-ink-tertiary">
                {col.dtype}
              </td>
              <td className="tabular whitespace-nowrap px-3 py-2 text-ink-secondary">
                {col.missing_count.toLocaleString()} ({col.missing_pct.toFixed(1)}%)
              </td>
              <td className="tabular whitespace-nowrap px-3 py-2 text-ink-secondary">
                {col.unique_count.toLocaleString()}
              </td>
              <td className="px-3 py-2 text-ink-tertiary">
                {col.numeric_stats ? (
                  <span className="tabular">
                    mean {col.numeric_stats.mean?.toFixed(2)} · min{" "}
                    {col.numeric_stats.min?.toFixed(2)} · max {col.numeric_stats.max?.toFixed(2)}
                  </span>
                ) : col.top_values && col.top_values.length > 0 ? (
                  <span>
                    top: {col.top_values.map((tv) => `${tv.value} (${tv.count})`).join(", ")}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
