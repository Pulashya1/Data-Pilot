# Evaluation suite

Benchmark datasets (`datasets.py`, synthetic and seeded — see its module docstring for why they
aren't downloads of the real public datasets) and the eval runner (`run_eval.py`), per
MASTER_PROMPT.md §10/§12 Phase 8.

Uses a real, paid LLM call and needs the full local stack running (Postgres, Redis, MinIO, the
built kernel/relay images) — run manually and deliberately, **never in CI**:

```bash
python eval/run_eval.py                    # every dataset
python eval/run_eval.py --dataset titanic   # just one (repeatable)
```

See `run_eval.py`'s module docstring for the full preconditions and what each dataset checks.
