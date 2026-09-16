import type { ColumnProfile } from "@/types";

export function ColumnStatsTable({ columns }: { columns: ColumnProfile[] }) {
  return (
    <div className="overflow-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-neutral-100 dark:bg-neutral-900">
          <tr>
            <th className="px-3 py-1.5 font-medium">Column</th>
            <th className="px-3 py-1.5 font-medium">Type</th>
            <th className="px-3 py-1.5 font-medium">Missing</th>
            <th className="px-3 py-1.5 font-medium">Unique</th>
            <th className="px-3 py-1.5 font-medium">Summary</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr key={col.name} className="border-t border-neutral-100 dark:border-neutral-800">
              <td className="whitespace-nowrap px-3 py-1.5 font-medium">{col.name}</td>
              <td className="whitespace-nowrap px-3 py-1.5 text-neutral-500">{col.dtype}</td>
              <td className="whitespace-nowrap px-3 py-1.5">
                {col.missing_count.toLocaleString()} ({col.missing_pct.toFixed(1)}%)
              </td>
              <td className="whitespace-nowrap px-3 py-1.5">{col.unique_count.toLocaleString()}</td>
              <td className="px-3 py-1.5 text-neutral-500">
                {col.numeric_stats ? (
                  <span>
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
