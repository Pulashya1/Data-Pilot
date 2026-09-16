// Shared frontend types mirroring backend/app/schemas/*.py. A generated
// OpenAPI client can replace these by hand once the agent phases stabilize.

export type FileType = "csv" | "tsv" | "excel" | "json" | "json_lines" | "parquet";

export type SessionStatus = "uploaded" | "needs_sheet_selection" | "profiling" | "ready" | "error";

export interface TopValue {
  value: string | number | boolean | null;
  count: number;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  missing_count: number;
  missing_pct: number;
  unique_count: number;
  numeric_stats: Record<string, number> | null;
  top_values: TopValue[] | null;
}

export interface DataQualityScore {
  overall: number;
  breakdown: Record<string, number>;
  issues: string[];
}

export interface DatasetProfile {
  n_rows: number;
  n_columns: number;
  memory_usage_bytes: number;
  is_sampled: boolean;
  sample_size: number | null;
  columns: ColumnProfile[];
  n_duplicate_rows: number;
  duplicate_pct: number;
  constant_columns: string[];
  data_quality: DataQualityScore;
}

export interface SessionSummary {
  id: string;
  original_filename: string;
  file_type: FileType;
  status: SessionStatus;
  size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  created_at: string;
}

export interface SessionDetail extends SessionSummary {
  sheet_names: string[] | null;
  selected_sheet: string | null;
  error_message: string | null;
  profile: DatasetProfile | null;
}

export interface PreviewRow {
  [column: string]: string | number | boolean | null;
}

export interface PreviewResponse {
  total_available: number;
  offset: number;
  limit: number;
  rows: PreviewRow[];
}
