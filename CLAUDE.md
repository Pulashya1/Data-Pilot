# DataPilot — project conventions

Agentic EDA & feature engineering assistant. Full spec: `MASTER_PROMPT.md`. Follow it phase by phase; do not skip ahead without review.

## Stack
- Frontend: Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui, Plotly.js, react-markdown.
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL, Redis, arq, S3/MinIO.
- Agent: LangGraph (added in Phase 3+). LLM access only through `backend/app/agent/llm.py` (`LLMClient`, LiteLLM-based). Never call a provider SDK directly elsewhere, never hardcode model names.
- Execution: one Jupyter kernel per session, sandboxed in Docker, no outbound network (added in Phase 2+).

## Commands

### Backend (from `backend/`)
- Install: `pip install -e ".[dev]"`
- Run dev server: `uvicorn app.main:app --reload` (on Windows, use `python -m app` instead —
  same server, but sets the event loop policy before uvicorn creates its loop, which
  `psycopg`/the LangGraph checkpointer needs; see `app/__main__.py`)
- Apply migrations: `alembic upgrade head`
- Create a migration after changing models: `alembic revision --autogenerate -m "..."`
- Test: `pytest` (needs a reachable Postgres; point `TEST_DATABASE_URL` at it, defaults to `localhost:5432/datapilot_test`) and MinIO on `localhost:9000` for `tests/test_storage.py`
- Lint: `ruff check .`
- Format: `ruff format .`
- Type check: `mypy app`
- Build the sandboxed kernel images (needed for Docker-backed tests and for real kernel execution):
  `docker build -t datapilot-kernel:latest kernel_image/` and
  `docker build -t datapilot-kernel-relay:latest relay_image/`
- Docker-backed kernel integration tests (excluded from the default `pytest` run — see below):
  `pytest -m docker`
- Verify a real LLM key + tool calling works (`LLM_MODEL`/`GEMINI_API_KEY` etc. set in `.env`,
  needs Postgres reachable; no-ops if `LLM_MODEL=mock`): `python scripts/verify_llm.py`

### Frontend (from `frontend/`)
- Install: `npm install`
- Run dev server: `npm run dev`
- Test: `npm test`
- Lint: `npm run lint`
- Format: `npm run format`
- Type check: `npm run typecheck`

### Full stack
- `docker compose up --build` — starts Postgres, Redis, MinIO, backend (`:8000`), frontend (`:3000`).
- Health check: `GET http://localhost:8000/health`
- The backend container does not auto-run migrations; run `alembic upgrade head` (from `backend/`, or `docker compose exec backend alembic upgrade head`) after first bringing Postgres up.

## Conventions
- Type hints everywhere (Python); strict TypeScript. Pydantic models at every backend boundary.
- No bare `except`. Small, focused modules. Docstrings on public functions only where non-obvious.
- Every LLM design decision must minimize calls/tokens — see MASTER_PROMPT.md §5.5 and §5.8. Zero paid LLM APIs.
- Standard analyses use tested templates in `backend/app/analysis/templates/`, not LLM-generated code (§5.3).
- CI must never call a real LLM. Agent tests use `LLM_MODEL=mock`.
- Never send the full dataset to the LLM (schema + stats + sample rows only, §5.5).
- Do not add libraries outside `MASTER_PROMPT.md`'s tech stack without asking first.

## Repository layout
See `MASTER_PROMPT.md` §11 for the full target structure. Not all directories are populated yet — they are scaffolded phase by phase per §12.

## Sandboxed kernel execution (Phase 2)
- One Jupyter kernel per session, run as two Docker containers (`app/execution/docker_backend.py`):
  a **kernel** container (built from `backend/kernel_image/`, pinned data-science stack, non-root
  user, read-only rootfs, attached only to an internal Docker network with no outbound access),
  and a **relay** container (`backend/relay_image/`, a fixed `socat` process, never runs user
  code) that bridges the kernel's 5 ZMQ ports back to the host on a public network. This split is
  required because Docker's `internal: true` networks block host-published ports too, not just
  outbound traffic — see the module docstring in `docker_backend.py` for the verified details.
- `app/execution/kernel_manager.py` tracks one kernel per session, idles kernels out
  (`kernel_idle_timeout_minutes`), and rebuilds a crashed kernel by re-seeding the dataset file and
  re-running previously-successful notebook cells before running new code.
- The notebook (`app/notebook/`, `notebook_cells` table) is the source of truth for a session's
  analysis; `.ipynb` export (`app/notebook/export.py`) re-runs every cell in a fresh throwaway
  kernel first and fails the export if it doesn't run top to bottom.
- Analysis templates (`app/analysis/templates/`) are parameterized code strings, not
  LLM-generated (MASTER_PROMPT.md §5.3): each renders a cell, and the backend parses a
  `##DATAPILOT_SUMMARY##<json>` marker line out of the kernel's own stdout to build the insight
  bullets, rather than recomputing statistics outside the kernel.
- Most backend tests use `tests/fakes.py::FakeExecutionBackend` (`exec()`s cell code in-process,
  no Docker). Real-Docker tests are marked `@pytest.mark.docker` and are excluded from the default
  `pytest` run (build the images first, then `pytest -m docker`); CI builds them in a separate
  `kernel` job.

## LLM agent (Phase 3)
- `app/agent/llm.py::LLMClient` is the only thing that calls `litellm` or knows a model name
  (see the stack rule above). `LLM_MODEL=mock` short-circuits everything before any network/
  Redis/budget cost, via a deterministic heuristic (`app/agent/heuristics.py`) shared with the
  real-LLM graceful-degradation fallback in `understand_node`.
- Only two places ever make a real LLM call: `understand_node` (one-shot target/problem-type
  proposal) and the `execute_step` error-repair loop (max 3 attempts). Planning, running
  templates, and the final summary are all deterministic — no LLM call, per §5.5/§5.8 cost
  minimization.
- The graph (`app/agent/graph.py`, nodes in `app/agent/nodes.py`) runs `ingest -> understand ->
  plan -> execute_step (loop) -> summarize` end to end automatically, with no pausing — §5.1's
  `interrupt()`-based pauses land in Phase 4 per the §12 phase split. `understand`/`plan` still
  record their choice as a `Decision` row (`app/models/decision.py`) so Phase 4 can build real
  pausing/editing against data that already exists.
- Per-run state that can't go through LangGraph's checkpointed state (DB session, kernel
  manager, LLM client, event bus) is looked up by `session_id` from `app/agent/deps.py` instead;
  `app/agent/state.py`'s `AgentState` stays small and JSON-serializable.
- Progress streams over SSE (`GET /sessions/{id}/stream`) from an in-process
  `app/agent/events.py::SessionEventBus`, as typed events (`app/schemas/events.py`).
- **`.env` loading gotcha**: `Settings.model_config`'s `env_file=".env"` resolves relative to
  the process's *current working directory*, not the repo root or `backend/`. `docker compose
  up` picks up the root `.env` automatically (the `backend` service sets `env_file: - .env` in
  `docker-compose.yml`); running the backend locally from `backend/` will **not** find a
  root-level `.env` — copy/symlink it to `backend/.env`, run from the repo root, or export the
  vars yourself.
- Verify a real key actually works before relying on it: `python scripts/verify_llm.py` (needs
  Postgres reachable; no-ops under `LLM_MODEL=mock`).
- LangGraph checkpoints to Postgres (`app/agent/checkpoint.py`, `AsyncPostgresSaver`), started
  and stopped once in `app/main.py`'s lifespan. This is also why Windows needs `python -m app`
  instead of a bare `uvicorn app.main:app` — see the "Run dev server" command above.
- Tests: `tests/test_llm_client.py` (mock mode, retry/fallback/cache/budget, using
  `tests/fakes.py::FakeRedis`), `tests/agent/test_graph.py` (a full graph run through the API
  with `FakeExecutionBackend`), `tests/test_agent_api.py` (start/stream/usage endpoints).

## Human-in-the-loop (Phase 4)
- `app/agent/decisions.py` is the shared `ask_user`-style primitive: a node creates a `Decision`
  row, then calls `resolve_decision`, which pauses the graph via LangGraph's `interrupt()`
  unless `UploadSession.auto_decide` is on (default off — sessions pause by default; the
  "Let the agent decide" toggle is `POST /sessions/{id}/settings`). `understand_node` and
  `plan_node` (`app/agent/nodes.py`) both use it for the target-confirmation and plan-approval
  decision points; Phase 5/6's data-changing decisions (drop columns, imputation, encoding,
  etc.) should reuse the same primitive rather than re-implementing pausing.
- **Replay safety, read this before touching a node that can pause**: LangGraph reruns a
  paused node's entire function body from the top on resume, not just the code after
  `interrupt()`. Any one-time side effect (an LLM call, creating the `Decision` row, writing a
  markdown cell) must be guarded by "does a `Decision` of this kind already exist for this
  session?" — see the module docstring in `app/agent/decisions.py` for the full mechanics and
  why `resolve_decision` itself is safe to call unconditionally on every replay.
- `AgentStatus.WAITING_DECISION` is a real, persisted status (not just an SSE event) — the
  `GET /sessions/{id}/stream` SSE connection closes on it the same way it does on `done`/`error`;
  the frontend reopens a new stream after answering (`answerDecision` in `frontend/lib/api.ts`).
- API: `GET/POST /sessions/{id}/decisions[/{decision_id}]` (Decisions panel + answer an
  interrupt), `POST /sessions/{id}/plan` (structured plan editing — same underlying
  answer-and-resume path, just a `{steps: [...]}` body instead of a csv string),
  `POST /sessions/{id}/cells/{cell_id}/revert` (truncates the notebook after that cell and
  shuts the kernel down so the next run rebuilds it from the remaining cells).
- Overriding the confirmed target column does **not** trigger a second LLM call: problem type
  is derived deterministically from the chosen column's stats either way
  (`heuristics.classify_single_column`), which is also why the Decisions panel always credits
  target-confirmation's *reasoning* to the LLM's original proposal even when the user picked a
  different column.
- Tests: `tests/agent/test_graph.py` covers pause/answer/resume, target override, plan editing,
  and rejection cases; `tests/test_notebook_api.py` covers revert. Phase 3's original
  full-auto-run tests now call `POST /sessions/{id}/settings {"auto_decide": true}` first, since
  auto-decide is no longer the default.

## Problem-type modules (Phase 5)
- `app/analysis/templates/`: classification (`class_balance`, `classification_feature_analysis`
  — mutual info, chi-square, ANOVA F-test), regression (`regression_target_analysis` — skew/
  transform suggestion, top-feature scatter plots, mutual info, a Breusch-Pagan heteroscedasticity
  check), clustering (`clustering_analysis` — scaling report, PCA explained variance + 2D
  projection, Hopkins statistic, elbow/silhouette suggested k), time series
  (`time_series_analysis` — date-column detection, frequency/gaps, seasonal decomposition,
  ACF/PACF, lag/split suggestions), and `leakage_checks` (near-duplicate/high-correlation/
  ID-like/suspicious-name checks against the target — always runs for classification and
  regression, not clustering/time-series, per MASTER_PROMPT.md §5.3).
- `app/agent/planning.py::build_plan` now returns the generic EDA core followed by each problem
  type's extra templates (`_PROBLEM_TYPE_EXTRA`), read from the same `TEMPLATES` registry.
- `app/notebook/seed.py::render_and_run_template_step` injects `target_column`/`problem_type`
  into every template's rendered params *after* calling `Template.default_params(profile)` —
  deliberately not part of that function's signature, so all Phase 2/3 templates (which only
  take `profile`) are untouched. A problem-type template with no target (e.g. run manually via
  `POST /templates/{key}/run` before a target is confirmed) degrades to a no-target summary
  rather than erroring.
- `app/agent/insight_severity.py` has explicit buckets for `class_balance` (imbalance ratio) and
  `leakage_checks` (critical on near-duplicate/ID-correlation, warning on high-correlation/
  suspicious names); every other new template key falls through to the existing `"info"` default.
- **Dependency fix**: `statsmodels` was bumped `0.14.4` -> `0.15.0` in `backend/pyproject.toml`'s
  `dev` extra — 0.14.4 calls pandas' `deprecate_kwarg` with its pre-3.0 two-argument signature,
  which breaks (`TypeError`) against pandas 3.0.5's `deprecate_kwarg(klass, old_arg_name,
  new_arg_name, ...)` the moment anything imports `statsmodels.api`, `.tsa.stattools`, or
  `.stats.diagnostic` — as the new regression/time-series templates' `exec()`-based tests do.
  0.15.0 is the first release built against pandas 3.x. The sandboxed kernel image pins its own
  older, compatible `statsmodels==0.14.4` (`kernel_image/requirements.txt`) and is unaffected.

## Feature engineering & baseline (Phase 6)
- Two more `app/analysis/templates/` entries, both self-contained like every other template
  (MASTER_PROMPT.md §5.3) — neither assumes the other ran first, since §5.1 step 3 lets the
  user freely reorder/skip/add EDA-plan steps:
  - `feature_engineering` — builds a scikit-learn `ColumnTransformer`/`Pipeline` (impute, scale,
    one-hot encode low-cardinality categoricals; drops constant/ID-like columns, recomputed at
    render time the same way `constant_and_id_columns.py` does — except float-dtype columns are
    excluded from the ID-like check, since a continuous numeric feature is often ~100% unique
    too and unlike a real ID shouldn't be dropped). Splits are strategy-appropriate: stratified
    for classification, time-ordered for time series, random otherwise, skipped for
    clustering/no-target (the pipeline still fits on the full `X`).
  - `baseline_model` — trains a quick `RandomForestClassifier`/`RandomForestRegressor` (its own
    light inline preprocessing, deliberately not sharing kernel state with
    `feature_engineering` for the reason above) and reports metrics, feature importance, and a
    SHAP summary plot via `shap.TreeExplainer` (exact and fast — no sampling-based
    `KernelExplainer`). No-ops for clustering/time-series/no-target sessions.
- **Pipeline artifact, no container-filesystem access needed**: `feature_engineering`
  base64-encodes its fitted `Pipeline` (joblib, in-memory) behind a second stdout marker,
  `##DATAPILOT_PIPELINE##` (`app/analysis/templates/base.py`'s `extract_pipeline_artifact`,
  alongside the existing `##DATAPILOT_SUMMARY##`/`extract_summary`). `render_and_run_template_step`
  (`app/notebook/seed.py`) uploads it to storage generically for any template that emits it and
  sets `UploadSession.pipeline_storage_key`; `POST /sessions/{id}/notebook/export?include_pipeline=true`
  fetches it and adds `pipeline.joblib` to the export zip — this is how MASTER_PROMPT.md §5.2's
  `export(format=pipeline_joblib)` and §6's "the exported pipeline code" are implemented, as a
  zip flag on the one existing export endpoint rather than a separate route/format value.
- **New graph steps**: `feature_engineering` -> `baseline` run between the EDA `execute_step`
  loop and `summarize` (`app/agent/graph.py`). Each has its own decision kind
  (`feature_engineering_approval`, `baseline_approval`, `app/models/decision.py`), created and
  resolved the same guarded way as every other decision (`app.agent.decisions`'s replay-safety
  rules). `feature_engineering` always runs (a pipeline is useful even for clustering/no-target);
  `baseline` is skipped without even asking when there's no confirmed classification/regression
  target. Both templates are still excluded from the *editable EDA plan*'s options
  (`app/agent/planning.py`'s `EDA_PLAN_TEMPLATE_KEYS`), since they're separate graph steps with
  their own dedicated decisions, not `plan_approval` steps — otherwise they'd be addable twice.
- `feature_engineering_approval`'s answer is either the literal `"recommended"` or a JSON object
  overriding any of `numeric_impute`/`categorical_impute`/`scaling`/`high_cardinality_threshold`/
  `test_size`/`drop_columns` (validated in `app.agent.decisions.validate_answer`, merged into the
  template's params via `render_and_run_template_step`'s new `extra_params` kwarg — the same
  minimally-invasive injection pattern Phase 5 used for `target_column`/`problem_type`).
- **Dependency fixes** (`backend/pyproject.toml`'s `dev` extra, same "two separate environments"
  reasoning as Phase 5's statsmodels fix — the sandboxed kernel image keeps its own older,
  compatible pins in `kernel_image/requirements.txt`, unaffected either way):
  - `joblib==1.4.2` added explicitly (already a transitive scikit-learn dependency, but both new
    templates `import joblib` directly).
  - `shap` bumped `0.46.0` (the kernel image's pin, fine against its older `numpy==1.26.4`) ->
    `0.52.0`: 0.46.0 crashes on bare `import shap` here because `numpy==2.5.3` changed
    `np.dtype(np.floating)` handling, which shap's `plots/colors/_colorconv.py` hits at *module
    import time* computing an unrelated color constant. 0.52.0 is numpy-2-compatible.

## Build phases
Tracked in `MASTER_PROMPT.md` §12. Currently: **Phase 3 (LLM client + agent core)** through
**Phase 6 (feature engineering & baseline)** complete and passing tests, awaiting review before
Phase 7.
