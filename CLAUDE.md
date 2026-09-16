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
- Run dev server: `uvicorn app.main:app --reload`
- Apply migrations: `alembic upgrade head`
- Create a migration after changing models: `alembic revision --autogenerate -m "..."`
- Test: `pytest` (needs a reachable Postgres; point `TEST_DATABASE_URL` at it, defaults to `localhost:5432/datapilot_test`) and MinIO on `localhost:9000` for `tests/test_storage.py`
- Lint: `ruff check .`
- Format: `ruff format .`
- Type check: `mypy app`

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

## Build phases
Tracked in `MASTER_PROMPT.md` §12. Currently: **Phase 1 (upload & profiling)** complete, awaiting review before Phase 2.
