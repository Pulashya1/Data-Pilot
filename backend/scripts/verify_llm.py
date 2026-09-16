"""Quick standalone check that a configured LLM provider (e.g. a Gemini API key) is reachable
and that tool calling works, before relying on it inside the agent (MASTER_PROMPT.md §12
Phase 3). Run with `python scripts/verify_llm.py` from `backend/` once `.env` has a real
`LLM_MODEL`/`GEMINI_API_KEY` set — `LLM_MODEL=mock` (the default) skips the real call.

Goes through `LLMClient` like everything else must (CLAUDE.md: never call a provider SDK
directly outside `app/agent/llm.py`), which means it needs a reachable Postgres (the same one
`docker compose up` gives you) to create a throwaway session for the call-budget tracking
`LLMClient` does on every real call. The row is deleted again once the script finishes.
"""

import asyncio
import time

from pydantic import BaseModel, Field

from app.agent.llm import LLMUnavailableError, get_llm_client
from app.core.config import get_settings
from app.core.db import async_session_maker
from app.models.session import FileType, SessionStatus, UploadSession


class Ping(BaseModel):
    """Reply with a short, friendly greeting."""

    greeting: str = Field(description="A short greeting, one sentence.")


async def main() -> None:
    settings = get_settings()
    if settings.llm_model == "mock":
        print("LLM_MODEL=mock — nothing to verify. Set a real model + API key in .env first.")
        return

    client = get_llm_client()
    async with async_session_maker() as db:
        session = UploadSession(
            original_filename="verify_llm.csv",
            storage_key="verify_llm",
            file_type=FileType.CSV,
            size_bytes=0,
            status=SessionStatus.READY,
        )
        db.add(session)
        await db.commit()

        try:
            start = time.monotonic()
            result = await client.complete_structured(
                [
                    {"role": "system", "content": "You are a terse assistant."},
                    {"role": "user", "content": "Call the Ping tool."},
                ],
                Ping,
                db=db,
                session_id=session.id,
            )
            latency_ms = (time.monotonic() - start) * 1000
        except LLMUnavailableError as exc:
            print(f"FAILED: {exc}")
            raise SystemExit(1) from None
        finally:
            await db.delete(session)
            await db.commit()

    print(f"OK — model={settings.llm_model} latency_ms={latency_ms:.0f}")
    print(f"Tool call round-tripped: greeting={result.greeting!r}")


if __name__ == "__main__":
    asyncio.run(main())
