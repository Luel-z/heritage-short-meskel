"""Experiment: Addis AI native Amharic TTS vs Gemini TTS on the same line (s04).

Hypothesis: a provider trained specifically on Amharic pronounces it more naturally than
Gemini's multilingual TTS. Judged by ear by native speakers; latency and duration logged.
"""

from __future__ import annotations

import json
import sys
import time
import uuid

import requests

from common import OUTPUTS, ROOT, log_call, need

API = "https://api.addisassistant.com/api/v1/voice/generations"
LINE = "እኛ ልጆች ደግሞ እየተጫወትን እንጠብቅ ነበር።"


def generate(voice: str, text: str) -> tuple[bytes, dict]:
    r = requests.post(API, timeout=120, headers={"x-api-key": need("ADDIS_API_KEY")},
                      json={"text": text, "voice_id": voice, "language": "am", "output_format": "wav_44100",
                            # required for paid generation; makes retries idempotent (no double billing)
                            "client_request_id": str(uuid.uuid4())})
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    meta = r.json()
    url = meta.get("audio_url") or meta.get("data", {}).get("audio_url")
    if not url:
        raise RuntimeError("no audio_url in response: " + json.dumps(meta)[:300])
    audio = requests.get(url, timeout=120)
    audio.raise_for_status()
    return audio.content, meta


if __name__ == "__main__":
    out = OUTPUTS / "experiments" / "addis_vs_gemini"
    out.mkdir(parents=True, exist_ok=True)
    for voice in sys.argv[1:] or ["am-hamen", "am-yohanes-calm"]:
        t = time.time()
        wav, meta = generate(voice, LINE)
        path = out / f"addis_{voice}.wav"
        path.write_bytes(wav)
        log_call("experiment:addis_vs_gemini", f"addis:{voice}", {"line": "s04"}, None, time.time() - t,
                 True, output=str(path.relative_to(ROOT)))
        print(voice, f"{time.time() - t:.1f}s", json.dumps(meta)[:300])
