"""Local dev entrypoint: `python -m app` (MASTER_PROMPT.md §12).

Runs the same app as `uvicorn app.main:app --reload`, but sets the Windows event loop policy
before uvicorn creates its own loop. psycopg (the LangGraph checkpointer, `app/agent/
checkpoint.py`) can't run in async mode on Windows' default ProactorEventLoop, and by the time
plain `uvicorn app.main:app` gets around to importing this package, uvicorn's already created
its loop — too late to switch policies from inside `app/main.py`. Not needed on Linux/Mac, or
inside Docker (`docker compose up`), which don't have this issue.
"""

import sys

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
