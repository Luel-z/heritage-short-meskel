"""Shared helpers for every stage: env loading, storyboard loading + validation,
the runs.jsonl call log, retries, and input-hash caching."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
RUNS_LOG = ROOT / "runs.jsonl"
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"


def load_env() -> None:
    """Read KEY=VALUE lines from .env into os.environ (no dependency needed)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def need(name: str) -> str:
    load_env()
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return val


def load_storyboard() -> dict[str, Any]:
    """Load storyboard.json and validate it against the JSON Schema. Every stage calls this."""
    import jsonschema

    board = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(board, schema)
    return board


def input_hash(*parts: Any) -> str:
    """A short stable hash of everything that determines an output. Same inputs → same hash → cache hit."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def log_call(stage: str, model: str, params: dict[str, Any], seed: Any, latency_s: float,
             ok: bool, output: str | None = None, cost_usd: float = 0.0,
             cache_hit: bool = False, error: str | None = None, **extra: Any) -> None:
    """Append one line per model call (or cache hit) to runs.jsonl."""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stage": stage,
        "model": model,
        "params": params,
        "seed": seed,
        "latency_s": round(latency_s, 3),
        "cost_usd": cost_usd,
        "cache_hit": cache_hit,
        "ok": ok,
        "output": output,
        "error": error,
        **extra,
    }
    with RUNS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def with_retries(fn: Callable[[], Any], attempts: int = 3, base_delay: float = 4.0,
                 no_retry: tuple[type[Exception], ...] = ()) -> Any:
    """Call fn; on failure wait base_delay, 2x, 4x … and try again. Re-raises the last error.
    Exceptions listed in no_retry (e.g. a daily quota) are raised at once: waiting cannot help."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except no_retry:
            raise
        except Exception as exc:  # noqa: BLE001 — providers raise many kinds
            last = exc
            if i < attempts - 1:
                wait = base_delay * (2 ** i)
                print(f"  retry {i + 1}/{attempts - 1} after {type(exc).__name__}: {exc} (waiting {wait:.0f}s)")
                time.sleep(wait)
    assert last is not None
    raise last
