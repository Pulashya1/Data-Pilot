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

  // Agent state (Phase 3, MASTER_PROMPT.md §12)
  problem_type: ProblemType | null;
  target_column: string | null;
  agent_status: AgentStatus;
  agent_error_message: string | null;
  plan_steps: string[] | null;
  llm_calls_used: number;
  auto_decide: boolean;
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

// Notebook & analysis templates (Phase 2, MASTER_PROMPT.md §6, §12)

export type CellType = "markdown" | "code";
export type CellStatus = "pending" | "success" | "error";

export interface StreamOutput {
  output_type: "stream";
  name: "stdout" | "stderr";
  text: string;
}

export interface DataOutput {
  output_type: "execute_result" | "display_data";
  data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  execution_count?: number | null;
}

export interface ErrorOutput {
  output_type: "error";
  ename: string;
  evalue: string;
  traceback: string[];
}

export type CellOutput = StreamOutput | DataOutput | ErrorOutput;

export interface NotebookCell {
  id: string;
  session_id: string;
  position: number;
  cell_type: CellType;
  source: string;
  label: string | null;
  outputs: CellOutput[] | null;
  execution_count: number | null;
  status: CellStatus;
  error_message: string | null;
  created_at: string;
}

export interface TemplateInfo {
  key: string;
  title: string;
  description: string;
}

export interface KernelStatusOut {
  status: "stopped" | "running";
}

// Agent run (Phase 3, MASTER_PROMPT.md §5, §7, §8, §12)

export type ProblemType =
  | "regression"
  | "binary_classification"
  | "multiclass_classification"
  | "clustering"
  | "time_series";

export type AgentStatus = "not_started" | "running" | "waiting_decision" | "done" | "error";

export type InsightSeverity = "info" | "warning" | "critical";

export interface CellUpdateEvent {
  type: "cell_update";
  cell_id: string;
  status: CellStatus;
  label: string | null;
}

export interface InsightEvent {
  type: "insight";
  text: string;
  severity: InsightSeverity;
  related_cell_id: string | null;
}

export interface PlanUpdateEvent {
  type: "plan_update";
  steps: string[];
  step_index: number;
}

export interface DecisionEvent {
  type: "decision";
  id: string;
  kind: string;
  question: string;
  options: string[];
  recommended_option: string | null;
  selected_option: string | null;
  reasoning: string | null;
  auto_decided: boolean;
}

export interface LLMStatusEvent {
  type: "llm_status";
  state: "idle" | "calling" | "waiting_for_capacity" | "error";
  model: string;
  calls_used: number;
  calls_budget: number;
}

export interface AgentStatusEvent {
  type: "agent_status";
  status: "running" | "waiting_decision" | "done" | "error";
  error_message: string | null;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  cell_id: string | null;
}

export type AgentEvent =
  | CellUpdateEvent
  | InsightEvent
  | PlanUpdateEvent
  | DecisionEvent
  | LLMStatusEvent
  | AgentStatusEvent
  | ErrorEvent;

export interface UsageOut {
  calls_used: number;
  calls_budget: number;
  tokens_used: number;
  models_used: string[];
}

// Human-in-the-loop decisions (Phase 4, MASTER_PROMPT.md §5.4, §8, §12)

export type DecisionKind = "target_confirmation" | "plan_approval";

export interface DecisionOut {
  id: string;
  kind: DecisionKind;
  question: string;
  options: string[];
  recommended_option: string | null;
  selected_option: string | null;
  reasoning: string | null;
  auto_decided: boolean;
  allow_free_text: boolean;
  created_at: string;
}
