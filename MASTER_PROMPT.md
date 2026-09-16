# MASTER PROMPT — Agentic EDA & Feature Engineering Assistant ("DataPilot")

You are a senior full-stack engineer and ML engineer. You will build a production-quality web application step by step with me. Read this entire document before writing any code. Work **phase by phase** (see "Build Phases"). At the end of each phase: run the tests, summarize what you built, list any deviations from this spec, commit, and **stop and wait for my review** before starting the next phase. If a requirement is ambiguous or a major architectural choice arises, ask me instead of guessing.

---

## 1. Product Overview

DataPilot is an agentic data-analysis assistant. A user uploads a dataset, and an LLM agent performs exploratory data analysis (EDA) and feature engineering **collaboratively** with the user:

- The agent detects the problem type (regression, binary/multiclass classification, clustering/no target, time series) and **asks the user to confirm**.
- The agent plans and executes analysis steps by writing and running real Python code in a sandboxed Jupyter kernel.
- The agent proactively shares insights and **pauses at key decisions** (dropping columns, imputation, outliers, encoding, suspected leakage) to ask the user what to do, offering recommended options.
- The user can chat at any time: ask about the data, a chart, a specific step, or a specific notebook cell's code.
- A Jupyter notebook (`.ipynb`) is built live as the analysis proceeds and can be downloaded at any time. It must run top to bottom in a fresh kernel.

### Core design principle
**The notebook is the single source of truth.** Every analysis action is a notebook cell executed in the session's live kernel. The UI chat, charts, Q&A, and exported files all derive from this notebook plus the session's message history. No hidden analysis happens outside the notebook.

### Cost principle
This project must run at **zero LLM cost** using free API tiers. Every design choice should minimize LLM calls and tokens (see Section 5.5 and Section 5.8).

---

## 2. Tech Stack (use these unless you ask me first)

**Frontend:** Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui, Plotly.js (`react-plotly.js`) for interactive charts, `react-markdown` for chat, a read-only code viewer with syntax highlighting (e.g. Shiki or Prism). Streaming via Server-Sent Events or WebSocket.

**Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL, Redis, arq (background jobs), S3-compatible storage (MinIO locally).

**Agent:** LangGraph for orchestration (use `interrupt` for human-in-the-loop and a Postgres checkpointer for persistence).

**LLM:** The primary provider is the Google Gemini API (free tier, a current Gemini Flash model), accessed through **LiteLLM** with tool calling.
- The model name comes from the `LLM_MODEL` environment variable. Optional fallback models come from `LLM_FALLBACKS` (comma-separated, e.g. a Groq model).
- Never hardcode model names. Never call a provider SDK directly outside `backend/app/agent/llm.py`. All LLM access goes through a single `LLMClient` wrapper, so providers can be swapped (Gemini, Groq, OpenRouter, Ollama) via configuration only.
- Implement retry with exponential backoff and jitter on rate-limit (429) and transient errors. After retries are exhausted, fail over to the next fallback model.
- Log token usage, latency, model used, and errors for every call, aggregated per session.

**Code execution:** One Jupyter kernel per session via `jupyter_client`, running inside a Docker container with CPU/memory/time limits and **no outbound network**. Put this behind an `ExecutionBackend` interface so an E2B sandbox backend can be swapped in later.

**Notebook:** `nbformat` for building and exporting notebooks.

**Data & ML libraries available in the kernel image:** pandas, numpy, pyarrow, polars, openpyxl, charset-normalizer, scipy, statsmodels, scikit-learn, imbalanced-learn, category_encoders, matplotlib, seaborn, plotly, shap, ydata-profiling, joblib.

**Tooling:** Docker Compose for local dev, pytest, ruff + mypy (backend), ESLint + Prettier (frontend), GitHub Actions CI.

---

## 3. Architecture

```
[Next.js UI] <--SSE/WS--> [FastAPI API] <--> [LangGraph Agent] --tools--> [Kernel Manager] --> [Sandboxed Jupyter Kernel (Docker)]
                               |                   |
                          [Postgres]          [LLMClient (LiteLLM)] --> Gemini (primary) / Groq (fallback) / Ollama (optional local)
                          [Redis]
                          [S3/MinIO: uploads, exports, artifacts]
```

- Each **session** has: an uploaded dataset, one live kernel, one notebook (a list of cells with outputs), a chat history, an agent state/checkpoint, a list of decisions, and an LLM usage record.
- Kernels are shut down after an idle timeout (configurable, default 30 minutes). On resume, the kernel is rebuilt by re-executing the notebook's accepted cells.

---

## 4. Supported Inputs

- CSV, TSV, Excel (.xlsx/.xls, with a sheet picker), JSON (records and lines), Parquet.
- Auto-detect encoding and delimiter. Upload size limit is configurable (default 200 MB).
- For large files (for example, more than 1M rows), the agent uses a random sample for visual EDA and says so explicitly. It uses polars or chunked reads where helpful.
- Validate files: reject unsupported types, show clear parse errors, and never execute anything contained in the upload.

---

## 5. Agent Design

### 5.1 LangGraph workflow (nodes)
1. **ingest**: Load the file in the kernel. Produce a `DatasetProfile` (shape, dtypes, missing %, unique counts, memory usage, sample rows, basic statistics). This step is deterministic Python with no LLM call.
2. **understand**: Infer semantic column types (numeric, categorical, ordinal, boolean, datetime, text, ID-like, constant) using deterministic heuristics first. Then make one LLM call to propose candidate target column(s) and the problem type with reasoning. **INTERRUPT** to confirm the target and problem type (the user may also choose "no target / explore only").
3. **plan**: Produce an ordered EDA + feature engineering plan tailored to the problem type (see 5.3). Show the plan to the user. **INTERRUPT** so the user can approve, reorder, skip, or add steps.
4. **execute_step** (loop over the plan): generate code, run it, capture outputs, and interpret the results into 2–4 concise insights.
   - If a step involves a data-changing decision, **INTERRUPT** with options and a recommended default.
   - On error: read the traceback, fix the code, and retry (maximum 3 attempts). Keep only the successful version in the notebook, and log failed attempts in an internal debug log.
5. **feature_engineering**: Build a scikit-learn `Pipeline`/`ColumnTransformer` from the accepted decisions. Fit only on the training split (stratified split for classification, time-ordered split for time series).
6. **baseline** (optional, ask first): Train a quick baseline model and report appropriate metrics, feature importance, and a SHAP summary.
7. **summarize**: Write a final summary markdown cell with key findings, decisions made, risks, and recommended next steps.

The user can interrupt at any time via chat. A chat message during execution is handled by a **qa** node, and then the workflow resumes.

### 5.2 Agent tools (function calling)
Implement these as typed tools with Pydantic schemas:
- `run_code(code, purpose, cell_markdown)`: execute in the kernel, append to the notebook, and return a truncated stdout/stderr, a result summary, and generated figure references.
- `get_dataframe_info(name)`: return a compact schema and stats of a kernel variable (no raw bulk data).
- `ask_user(question, options[], recommended_option, allow_free_text)`: triggers a LangGraph interrupt and renders a decision card in the UI.
- `add_markdown_cell(text)`
- `emit_insight(text, severity: info|warning|critical, related_cell_id)`
- `update_plan(steps)`
- `get_notebook_cells(range | cell_ids)`: used for Q&A about the code.
- `revert_to_cell(cell_id)`: truncate the notebook after this cell and rebuild kernel state.
- `export(format: ipynb|html|clean_csv|pipeline_joblib)`

**Tool schema compatibility:** Keep JSON schemas simple and flat so they work across providers (Gemini, Groq, Ollama). Use basic types, enums, and required fields. Avoid deeply nested `anyOf`/`oneOf`, `$ref`, and unusual JSON Schema features. Validate all tool arguments with Pydantic. If the model returns malformed tool arguments, send the validation error back to the model and retry once.

### 5.3 Problem-type-specific analysis

**All problem types:** missing value analysis (matrix/heatmap, missingness patterns), duplicates, constant or near-constant columns, ID-like columns, univariate distributions, skewness/kurtosis, outliers (IQR and z-score), correlations (Pearson/Spearman for numeric, Cramér's V for categorical), multicollinearity (VIF), high-cardinality categoricals, datetime feature extraction opportunities, and a data quality score (0–100 with a breakdown).

**Classification:** class balance (with an imbalance warning and resampling/class-weight suggestions), feature distributions by class, mutual information, chi-square tests for categoricals, ANOVA F-test for numeric features, target leakage checks.

**Regression:** target distribution and transformation suggestions (log/Box-Cox/Yeo-Johnson), scatter plots of top features against the target, residual-friendly checks, heteroscedasticity hints, mutual information regression, leakage checks.

**No target / clustering:** scaling analysis, PCA explained variance, a 2D projection plot, cluster tendency (Hopkins statistic), suggested k (elbow/silhouette).

**Time series:** ordering and frequency detection, gaps, trend/seasonality decomposition, autocorrelation (ACF/PACF), lag and rolling feature suggestions, and a time-aware split only.

**Leakage heuristics (always run):** features with an absurdly high single-feature predictive score, near-duplicates of the target, post-event columns (name hints like `*_after`, `outcome`, `status_final`), and IDs correlated with the target.

**Template-first code generation (to save LLM calls):** Standard analyses (missing values, distributions, correlations, class balance, VIF, outliers, etc.) are implemented as tested, parameterized Python code templates in `backend/app/analysis/templates/`. For these, the agent selects a template and fills in the parameters (column names, thresholds). It does not generate code from scratch. The LLM writes free-form code only for custom requests, Q&A computations, or repairs. This makes the project reliable with smaller free models and greatly reduces token usage.

### 5.4 Human-in-the-loop rules
- Ask only at **decision points**: target/problem type, plan approval, dropping columns, imputation strategy, outlier treatment, encoding strategy, scaling, resampling, suspected leakage, running the baseline.
- Every question includes 2–4 concrete options, a recommended option with a one-sentence reason, and a free-text option.
- A "Let the agent decide" session toggle auto-accepts recommendations but still records them as decisions.
- All decisions are stored and listed in a "Decisions" panel and in the final notebook summary.

### 5.5 LLM context management (privacy and cost)
- **Never send the full dataset to the LLM.** Send the schema, aggregated statistics, at most 20 sample rows (configurable, can be set to 0), and truncated cell outputs (a maximum number of characters per output).
- Figures are described to the LLM via the underlying numbers or summaries, not images.
- Keep a rolling session summary to keep long sessions within the context window and reduce tokens per call.
- Only send the notebook cells relevant to the current question or step, not the entire notebook, unless the user asks about the whole notebook.

### 5.6 Q&A behavior
- The user can ask about the dataset, any insight, any chart, any decision, or any notebook cell. Clicking "Ask about this" on a cell pre-fills a reference like `@cell-12`.
- Answers must be grounded in the actual notebook cells and outputs. If an answer requires new computation, the agent runs a new cell (marked as "exploratory" so the user can keep or discard it in the final notebook).
- If asked something the data cannot answer, the agent says so.
- Adapt explanations to a user expertise setting (beginner / intermediate / expert).

### 5.7 System prompt for the analysis agent
Create `backend/app/agent/prompts/system.md`. It must instruct the agent to:
- act as a careful senior data scientist who explains *why*, not just *what*;
- write clean, idiomatic, commented pandas/sklearn code with no unnecessary cells;
- never modify the original dataframe in place without a named copy (`df_raw` is preserved; the working copy is `df`);
- set random seeds;
- prefer statistical evidence over vague claims;
- flag uncertainty;
- keep insights short and specific (with numbers);
- ask before any irreversible data change;
- never fabricate outputs it did not execute;
- always use the provided tools instead of describing code in plain text.

Keep the system prompt concise (it is sent on every call and costs tokens on the free tier).

### 5.8 Free-tier resilience
- **Rate limiting:** A per-provider token bucket (requests/min and tokens/min, configurable via env) sits in `LLMClient`. Calls wait for capacity instead of failing.
- **Graceful degradation:** If all models are rate-limited, the UI shows a clear "Waiting for LLM capacity…" status with a countdown. The session state is preserved and resumes automatically.
- **Caching:** Cache LLM responses for identical prompts (keyed by a hash of model + messages + tools) in Redis with a TTL, which is useful during development and repeated runs.
- **Call budget:** Configurable maximum number of LLM calls per session (`LLM_MAX_CALLS_PER_SESSION`). Show usage in a small indicator in the UI.
- **Dev mode:** `LLM_MODEL=mock` uses a deterministic fake LLM for tests and UI development, consuming no quota.
- **Privacy note:** Free tiers may use prompts to improve provider models. Show a one-line notice on the upload page, and recommend public or non-sensitive datasets.

---

## 6. Notebook Generation Rules

- Start the notebook with: a title, dataset name, generation timestamp, problem type, and table of contents (markdown); an imports cell; a config/seed cell; and a data loading cell that uses a relative path (`data/<filename>`).
- Each step is a markdown header cell (step name + purpose) followed by its code cell(s) and a short markdown "Insights" cell.
- Use matplotlib/seaborn for figures in the notebook (static, reliable). For each chart, the backend additionally produces a Plotly JSON spec for the interactive UI.
- Include decisions as markdown callouts ("Decision: imputed `age` with the median, because ...").
- End with a summary, the exported pipeline code, and next steps.
- **Validation:** Before export, run the notebook top to bottom in a fresh kernel (a separate sandbox). If it fails, the agent repairs it. The export is a zip containing the `.ipynb`, `requirements.txt` with pinned versions, and a `data/` README (the dataset itself is included only if the user opts in).
- Exploratory Q&A cells are excluded by default. The user can toggle them in.
- The exported notebook must contain no API keys, LLM calls, or references to DataPilot internals. It is a plain, standalone data science notebook.

---

## 7. Frontend UX

Three-pane layout on desktop, collapsing to tabs on mobile:
1. **Left: Chat.** Streaming agent messages, insight cards (colored by severity), and decision cards with option buttons.
2. **Center: Analysis.** Plan progress (step checklist with status), interactive Plotly charts, dataset preview table (virtualized), and data quality score.
3. **Right: Notebook.** Live cell list with code and outputs, an "Ask about this cell" button, a "Revert to here" button, and an export menu.

Other pages and features: landing/upload page (drag-and-drop, file validation, sheet picker, privacy notice), session list, settings (expertise level, auto-decide toggle, sample rows sent to the LLM), an LLM status indicator (model in use, calls used, waiting-for-capacity state), light/dark mode, and accessible components (keyboard navigation, ARIA labels).

---

## 8. Backend API (initial)

- `POST /sessions` (multipart upload) → session id
- `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
- `GET /sessions/{id}/stream` (SSE: agent tokens, insights, decisions, cell updates, plan updates, LLM status, errors)
- `POST /sessions/{id}/messages` (user chat)
- `POST /sessions/{id}/decisions/{decision_id}` (answer an interrupt)
- `POST /sessions/{id}/plan` (edit plan)
- `POST /sessions/{id}/cells/{cell_id}/revert`
- `GET /sessions/{id}/notebook`
- `GET /sessions/{id}/usage` (LLM calls, tokens, models used)
- `POST /sessions/{id}/export?format=ipynb|html|clean_csv|pipeline`
- `GET /health` (includes LLM provider reachability)

Define typed event schemas shared with the frontend (generate TypeScript types from the OpenAPI spec).

---

## 9. Security & Reliability

- Kernel containers: no network, a read-only root filesystem except the working directory, a non-root user, memory/CPU limits, per-cell timeout (default 120 s), and per-session total compute limits.
- Validate and size-limit uploads, and sanitize filenames.
- Rate-limit API calls per user, in addition to the LLM rate limiting in 5.8.
- Simple auth (email magic link or OAuth). Users can access only their own sessions.
- Store secrets in environment variables and provide a `.env.example`. API keys are never sent to the frontend or into the kernel.
- Structured logging, plus LLM call logging (model, tokens, latency, tool calls, retries, fallbacks).
- Graceful handling of kernel crashes (auto-restart and state rebuild from the notebook).

### `.env.example` must include
```
LLM_MODEL=gemini/<current-gemini-flash-model>
LLM_FALLBACKS=groq/<groq-model>
GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_API_BASE=http://localhost:11434
LLM_MAX_CALLS_PER_SESSION=150
LLM_RPM_LIMIT=10
LLM_TPM_LIMIT=200000
LLM_CACHE_TTL_SECONDS=86400
LLM_SAMPLE_ROWS=20
DATABASE_URL=
REDIS_URL=
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
```
Rate limit defaults are placeholders. Add a comment telling me to set them from my provider's current free-tier limits.

---

## 10. Testing & Evaluation

- Unit tests for the file loaders, profile builder, analysis templates, notebook builder, tool schemas, leakage heuristics, and `LLMClient` (retry, backoff, fallback, rate limiter, cache, using mocked responses).
- Integration tests for the kernel manager (execute, timeout, crash recovery).
- Agent tests use `LLM_MODEL=mock` for deterministic flows. **CI must never call a real LLM.**
- **Evaluation suite (run manually, uses real free-tier LLM):** Run the full agent on benchmark datasets and assert that problem type detection is correct, the exported notebook runs end to end, and known issues are flagged. Record LLM calls and tokens per dataset:
  - Titanic (classification, missing values, leakage-prone columns)
  - California Housing (regression)
  - Credit card fraud sample (heavy imbalance)
  - Iris without the label column (clustering)
  - Airline passengers (time series)
  - A deliberately messy CSV (mixed types, bad encoding, duplicates, a column that leaks the target)
- Frontend: component tests and one Playwright end-to-end test using the mock LLM (upload → confirm target → approve plan → answer a decision → download notebook).

---

## 11. Repository Structure

```
datapilot/
  CLAUDE.md                 # project conventions and commands (create and keep updated)
  docker-compose.yml
  .env.example
  backend/
    app/
      api/                  # FastAPI routers
      agent/                # LangGraph graph, nodes, tools, prompts/
        llm.py              # LLMClient: LiteLLM wrapper, retries, fallbacks, rate limiter, cache, mock
      analysis/
        templates/          # tested parameterized analysis code templates
      execution/            # ExecutionBackend interface, docker jupyter backend
      notebook/             # nbformat builder, validator, exporters
      data/                 # loaders, profiling, leakage heuristics
      models/               # SQLAlchemy models
      schemas/              # Pydantic schemas and events
      core/                 # config, logging, auth, storage
    kernel_image/           # Dockerfile with pinned data-science libraries
    tests/
    eval/                   # benchmark datasets and eval runner
  frontend/
    app/  components/  lib/  types/
    tests/
```

---

## 12. Build Phases (stop for review after each)

- **Phase 0: Scaffold.** Repo structure, Docker Compose (Postgres, Redis, MinIO, backend, frontend), CI, linting, `CLAUDE.md`, `.env.example`, health endpoint, basic frontend shell.
- **Phase 1: Upload & profiling.** File loaders for all formats, session creation, `DatasetProfile`, preview table, and data quality score in the UI. No LLM yet.
- **Phase 2: Sandboxed execution + notebook.** Kernel image, kernel manager, `run_code`, notebook builder, live notebook panel, `.ipynb` export, fresh-kernel validation. Build the first analysis templates and run them without the LLM.
- **Phase 3: LLM client + agent core.** `LLMClient` (LiteLLM, Gemini primary, fallback, retries, rate limiter, cache, mock mode), a small script to verify my Gemini key and tool calling works, then the LangGraph graph with ingest → understand → plan → execute loop, SSE streaming, insight cards, error self-correction, and the LLM status indicator.
- **Phase 4: Human-in-the-loop.** Interrupts, decision cards, plan editing, Decisions panel, auto-decide toggle, revert-to-cell.
- **Phase 5: Problem-type modules.** Classification, regression, clustering, and time series analysis templates; leakage heuristics; Plotly specs.
- **Phase 6: Feature engineering & baseline.** Pipeline builder, train/test split logic, baseline model, SHAP, pipeline export.
- **Phase 7: Q&A.** Cell references, grounded answers, exploratory cells, expertise levels.
- **Phase 8: Hardening.** Auth, API rate limits, resource limits, crash recovery, HTML report export, evaluation suite, Playwright end-to-end test, README with screenshots, an architecture diagram, and setup instructions for getting a free Gemini API key.

---

## 13. Engineering Standards

- Type hints everywhere. Pydantic models at every boundary. No bare `except`.
- Small, focused modules. Docstrings on public functions.
- Pin dependency versions. Keep the kernel image reproducible.
- Write tests alongside features. Do not mark a phase complete with failing tests.
- Keep `CLAUDE.md` updated with commands (run, test, lint, migrate) and key conventions.
- Do not add libraries outside this spec without asking.
- Do not use any paid LLM API. If a feature seems to require one, ask me first.
- When unsure about a requirement, ask. When you make an assumption, state it in your phase summary.

Begin with **Phase 0** only.
