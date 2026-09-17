"""Manual evaluation suite (MASTER_PROMPT.md §10, §12 Phase 8).

Runs the full agent (LangGraph graph, real sandboxed kernel, real LLM) end to end against each
benchmark dataset in `eval/datasets.py`, asserting problem-type detection is correct and the
exported notebook runs top to bottom in a fresh kernel, and records LLM calls/tokens/cost per
dataset.

**Costs real money and needs real infra running — never run this in CI** (MASTER_PROMPT.md
§10/§13):
    - the full `docker compose up` stack (Postgres, Redis, MinIO) reachable
    - `datapilot-kernel`/`datapilot-kernel-relay` images built (see CLAUDE.md)
    - a real `LLM_MODEL` + API key set in `.env` — `LLM_MODEL=mock` would make every run
      trivially "pass" without testing anything, so this script refuses to run under it, the
      same guard `scripts/verify_llm.py` uses.

Usage (from `backend/`):
    python eval/run_eval.py                    # every dataset
    python eval/run_eval.py --dataset titanic   # just one (repeatable)
    python eval/run_eval.py --yes               # skip the "this costs money" prompt
"""

import argparse
import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Run as a plain script (`python eval/run_eval.py`), not an installed package — `app` and
# `eval` both need `backend/` (this file's parent's parent) on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from eval.datasets import DATASET_SPECS, DatasetSpec  # noqa: E402

_POLL_INTERVAL_SECONDS = 3.0
_POLL_TIMEOUT_SECONDS = 600.0
_EVAL_EMAIL = "eval@datapilot.local"


@dataclass
class EvalResult:
    dataset: str
    ok: bool
    detail: str
    problem_type: str | None = None
    calls_used: int = 0
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    duration_seconds: float = 0.0


def _login(client: TestClient) -> None:
    response = client.post("/auth/request-link", json={"email": _EVAL_EMAIL})
    response.raise_for_status()
    login_url = response.json()["dev_login_url"]
    if login_url is None:
        raise RuntimeError(
            "SMTP is configured, so no dev-mode login link was returned — unset SMTP_HOST for "
            "eval runs, or adapt this script to read the link from the real mailbox."
        )
    token = login_url.rsplit("token=", 1)[1]
    client.get(f"/auth/verify?token={token}").raise_for_status()


def _run_one(client: TestClient, spec: DatasetSpec) -> EvalResult:
    started = time.monotonic()
    csv_bytes = spec.build().to_csv(index=False).encode()
    upload = client.post(
        "/sessions", files={"file": (f"{spec.name}.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    if upload.status_code != 201:
        return EvalResult(spec.name, False, f"upload failed: {upload.text}")
    session_id = upload.json()["id"]

    client.post(f"/sessions/{session_id}/settings", json={"auto_decide": True})
    start_response = client.post(f"/sessions/{session_id}/agent/start")
    if start_response.status_code != 202:
        return EvalResult(spec.name, False, f"agent start failed: {start_response.text}")

    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
    session: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        session = client.get(f"/sessions/{session_id}").json()
        if session["agent_status"] in ("done", "error"):
            break
        time.sleep(_POLL_INTERVAL_SECONDS)
    else:
        return EvalResult(spec.name, False, "timed out waiting for the agent to finish")

    assert session is not None
    usage = client.get(f"/sessions/{session_id}/usage").json()
    duration = time.monotonic() - started
    detected = session.get("problem_type")
    common = {
        "problem_type": detected,
        "calls_used": usage["calls_used"],
        "tokens_used": usage["tokens_used"],
        "cost_used_usd": usage["cost_used_usd"],
        "duration_seconds": duration,
    }

    if session["agent_status"] != "done":
        error_message = session.get("agent_error_message")
        return EvalResult(spec.name, False, f"agent ended in error: {error_message}", **common)

    if spec.expected_problem_type is not None and detected != spec.expected_problem_type:
        return EvalResult(
            spec.name,
            False,
            f"expected problem_type={spec.expected_problem_type!r}, got {detected!r}",
            **common,
        )

    export = client.post(f"/sessions/{session_id}/notebook/export")
    if export.status_code != 200:
        detail = f"notebook export/fresh-kernel validation failed: {export.text}"
        return EvalResult(spec.name, False, detail, **common)

    if spec.expects_leakage_flagged:
        cells = client.get(f"/sessions/{session_id}/notebook").json()
        flagged = any(
            "leak" in (c.get("source") or "").lower() for c in cells if c["cell_type"] == "markdown"
        )
        if not flagged:
            return EvalResult(
                spec.name, False, "expected a leakage warning, none found in the notebook", **common
            )

    return EvalResult(spec.name, True, "ok", **common)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", action="append", help="Run only this dataset (repeatable). Default: all."
    )
    parser.add_argument("--yes", action="store_true", help="Skip the cost confirmation prompt.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.llm_model == "mock":
        print("LLM_MODEL=mock — every run would trivially pass. Set a real model + API key first.")
        return 1

    specs = [s for s in DATASET_SPECS if not args.dataset or s.name in args.dataset]
    if not specs:
        print(f"No dataset(s) matching {args.dataset}. Known: {[s.name for s in DATASET_SPECS]}")
        return 1

    if not args.yes:
        answer = input(
            f"This runs {len(specs)} real agent session(s) against {settings.llm_model}, which "
            "costs real money. Continue? [y/N] "
        )
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    with TestClient(app) as client:
        _login(client)
        results = [_run_one(client, spec) for spec in specs]

    print()
    header = (
        f"{'dataset':<24}{'ok':<6}{'problem_type':<24}{'calls':<7}{'tokens':<9}"
        f"{'cost_usd':<10}{'seconds':<8}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.dataset:<24}{'yes' if r.ok else 'NO':<6}{(r.problem_type or '-'):<24}"
            f"{r.calls_used:<7}{r.tokens_used:<9}{r.cost_used_usd:<10.4f}{r.duration_seconds:<8.1f}"
        )
        if not r.ok:
            print(f"    -> {r.detail}")

    total_cost = sum(r.cost_used_usd for r in results)
    print(f"\nTotal cost: ${total_cost:.4f}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
