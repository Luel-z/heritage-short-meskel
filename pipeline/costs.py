"""Summarise runs.jsonl into the measured table in COSTS.md (between the AUTO markers).

  python costs.py

Latency, call counts, cache hits and GPU minutes are measured. List-price equivalents use the rates in
LIST_PRICES — assumptions stated in COSTS.md, to be checked against each provider's current page.
"""

from __future__ import annotations

import json
from collections import defaultdict

from common import ROOT, RUNS_LOG

COSTS = ROOT / "COSTS.md"
START, END = "<!-- AUTO:START -->", "<!-- AUTO:END -->"
T4_USD_PER_HOUR = 0.35            # assumed cloud on-demand T4 rate
FLUX_USD_PER_IMAGE = 0.0035       # assumed Workers AI paid rate for a 1024² FLUX.2 klein 4B image


def main() -> None:
    rows = [json.loads(l) for l in RUNS_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    agg: dict[str, dict] = defaultdict(lambda: {"calls": 0, "ok": 0, "failed": 0, "cache": 0, "lat": 0.0,
                                                "gpu_min": 0.0, "usd": 0.0, "audio_s": 0.0})
    for r in rows:
        a = agg[r["stage"]]
        if r.get("cache_hit"):
            a["cache"] += 1
            continue
        a["calls"] += 1
        a["ok" if r.get("ok") else "failed"] += 1
        a["lat"] += r.get("latency_s") or 0.0
        if r.get("ok"):  # a job that never left Kaggle's queue used no GPU (its wait is logged, not billed)
            a["gpu_min"] += r.get("gpu_minutes") or 0.0
        else:
            a["queued_min"] = a.get("queued_min", 0.0) + (r.get("gpu_minutes") or 0.0)
        a["usd"] += r.get("cost_usd") or 0.0
        a["audio_s"] += r.get("audio_s") or 0.0

    lines = ["| Stage | Model calls | ok / failed | Cache hits | Total latency | Mean latency | GPU min (T4) | Cash spent | List-price equivalent |",
             "|---|---|---|---|---|---|---|---|---|"]
    for stage in sorted(agg):
        a = agg[stage]
        mean = a["lat"] / a["calls"] if a["calls"] else 0
        if stage in ("keyframes", "references"):
            listp = a["ok"] * FLUX_USD_PER_IMAGE
        elif a["gpu_min"]:
            listp = a["gpu_min"] / 60 * T4_USD_PER_HOUR
        else:
            listp = a["usd"]
        lines.append(f"| {stage} | {a['calls']} | {a['ok']} / {a['failed']} | {a['cache']} | {a['lat']:.0f} s | "
                     f"{mean:.1f} s | {a['gpu_min']:.1f} | ${a['usd']:.3f} | ${listp:.3f} |")
    gpu = sum(a["gpu_min"] for a in agg.values())
    queued = sum(a.get("queued_min", 0.0) for a in agg.values())
    lines.append(f"\nKaggle jobs waited **{queued:.0f} minutes** in the GPU queue without ever starting "
                 f"(FAILURES F08–F11); that wait is not GPU time and is excluded above.")
    usd = sum(a["usd"] for a in agg.values())
    lines.append(f"\n**Totals:** {sum(a['calls'] for a in agg.values())} model calls, "
                 f"{sum(a['cache'] for a in agg.values())} cache hits, {gpu:.1f} T4 GPU minutes, "
                 f"${usd:.3f} of Addis AI signup credit, $0 cash. Generated from {len(rows)} lines of runs.jsonl.")
    table = "\n".join(lines)

    text = COSTS.read_text(encoding="utf-8")
    pre, rest = text.split(START, 1)
    _, post = rest.split(END, 1)
    COSTS.write_text(f"{pre}{START}\n{table}\n{END}{post}", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
