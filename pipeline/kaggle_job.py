"""Run a generated Python script as a Kaggle GPU notebook and download its outputs.

Used by the music (ACE-Step) and shots (Wan 2.2) stages. The script is pushed with the Kaggle CLI,
polled until it finishes, and /kaggle/working is downloaded. Wall-clock time is logged as GPU minutes,
which is the quota that actually binds (about 30 GPU hours a week).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from common import OUTPUTS, ROOT, input_hash, load_env, log_call, need

JOBS = OUTPUTS / "kaggle_jobs"


def _kaggle(*args: str) -> subprocess.CompletedProcess:
    load_env()
    env = os.environ | {"KAGGLE_API_TOKEN": need("KAGGLE_API_TOKEN"), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "kaggle", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def _status(user: str, slug: str) -> str:
    """Kernel status in lower case; a network error is reported as 'unknown' instead of crashing."""
    try:
        res = _kaggle("kernels", "status", f"{user}/{slug}")
        out = (res.stdout + res.stderr).strip().lower()
        if "connectionerror" in out or "traceback" in out:
            return "unknown (network error, will retry)"
        return out
    except Exception as exc:  # noqa: BLE001
        return f"unknown ({type(exc).__name__})"


def run_job(slug: str, script: str, stage: str, params: dict, out_dir: Path,
            poll_s: int = 30, timeout_min: int = 180) -> Path:
    """Push `script` as kernel <user>/<slug>, wait for it, download outputs into out_dir."""
    user = need("KAGGLE_USERNAME")
    folder = JOBS / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.py").write_text(script, encoding="utf-8")
    (folder / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{user}/{slug}", "title": slug, "code_file": "run.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
        # no "machine_shape": pinning NvidiaTeslaT4 left both jobs QUEUED for 12+ hours (FAILURES F09);
        # without it Kaggle assigns whatever free GPU is available
    }, indent=2), encoding="utf-8")

    t0 = time.time()
    # Re-attach instead of re-pushing when the same script is already queued/running (a network drop
    # killed the local poller once while the job sat in Kaggle's queue: FAILURES F08).
    sig = input_hash(script)
    sig_file = folder / ".pushed"
    current = _status(user, slug)
    if sig_file.exists() and sig_file.read_text() == sig and ("queued" in current or "running" in current):
        print(f"  re-attaching to {user}/{slug} ({current})")
    else:
        push = _kaggle("kernels", "push", "-p", str(folder))
        print(push.stdout.strip() or push.stderr.strip())
        if push.returncode != 0 or "error" in push.stdout.lower():
            log_call(stage, f"kaggle:{slug}", params, None, time.time() - t0, False, error=(push.stdout + push.stderr)[-400:])
            raise RuntimeError(f"kaggle push failed: {push.stdout} {push.stderr}")
        sig_file.write_text(sig)

    status = ""
    while time.time() - t0 < timeout_min * 60:
        time.sleep(poll_s)
        status = _status(user, slug)
        print(f"  [{(time.time() - t0) / 60:5.1f} min] {status}", flush=True)
        if "complete" in status or "error" in status or "cancel" in status:
            break

    minutes = (time.time() - t0) / 60
    out_dir.mkdir(parents=True, exist_ok=True)
    dl = _kaggle("kernels", "output", f"{user}/{slug}", "-p", str(out_dir), "-o")
    ok = "complete" in status
    log_call(stage, f"kaggle:{slug}", params, params.get("seeds"), minutes * 60, ok,
             output=str(out_dir.relative_to(ROOT)), gpu_minutes=round(minutes, 2),
             gpu="T4", error=None if ok else status[-300:])
    print(f"  kaggle job {slug}: {status} after {minutes:.1f} min → {out_dir.relative_to(ROOT)}")
    if not ok:
        log = next(out_dir.glob("*.log"), None)
        raise RuntimeError(f"kaggle job {slug} did not complete: {status}. Log: {log}")
    if dl.returncode != 0:
        raise RuntimeError(f"download failed: {dl.stderr}")
    return out_dir
