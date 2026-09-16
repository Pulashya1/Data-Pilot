# DataPilot

Agentic EDA & feature engineering assistant. See `MASTER_PROMPT.md` for the full product and technical spec, and `CLAUDE.md` for commands and conventions.

## Status

Phase 6 (feature engineering & baseline) complete — see `MASTER_PROMPT.md` §12 for the build-phase roadmap.

## Quickstart

```bash
cp .env.example .env
# fill in GEMINI_API_KEY etc. once you reach the phases that need it
docker compose up --build
```

- Backend: http://localhost:8000 (health check at `/health`)
- Frontend: http://localhost:3000

## Development without Docker

See `CLAUDE.md` for backend/frontend install, run, test, lint, and type-check commands.
