"""Stage: narration. One WAV per shot, cached by a hash of (main voice config, line).

Change one narration line in storyboard.json and only that shot's audio is regenerated.

Providers (see EXPERIMENTS E01/E02 for why):
  addis  — Addis AI native Amharic TTS, main narrator (am-yohanes-calm)
  gemini — Gemini TTS, fallback. Free tier = 10 requests/day/model (FAILURES F01): a per-day 429
           skips to the next fallback at once; a per-minute 429 is retried with back-off.
The provider/model actually used is recorded in runs.jsonl.
"""

from __future__ import annotations

import base64
import time
import uuid
import wave
from pathlib import Path
from typing import Any

import requests

from common import OUTPUTS, ROOT, input_hash, load_storyboard, log_call, need, with_retries

OUT = OUTPUTS / "narration"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ADDIS_API = "https://api.addisassistant.com/api/v1/voice/generations"
ADDIS_USD_PER_MIN = 0.032
GEMINI_RATE = 24000  # Gemini TTS returns 16-bit mono PCM at 24 kHz
THROTTLE_S = 3.0


class QuotaExhausted(RuntimeError):
    """This provider cannot serve more requests today; move on to the next fallback."""


# ---------- providers: each returns WAV bytes ----------

def gemini_tts(cfg: dict[str, Any], text: str) -> bytes:
    prompt = f"{cfg['style']}\n\n{text}" if cfg.get("style") else text
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice_name"]}}}}}
    r = requests.post(GEMINI_API.format(model=cfg["model"]), json=body, timeout=120,
                      headers={"x-goog-api-key": need("GEMINI_API_KEY")})
    if r.status_code == 429 and "PerDay" in r.text:
        raise QuotaExhausted(f"{cfg['model']}: daily free-tier limit reached")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    return pcm_to_wav(pcm, GEMINI_RATE)


def addis_tts(cfg: dict[str, Any], text: str) -> bytes:
    r = requests.post(ADDIS_API, timeout=120, headers={"x-api-key": need("ADDIS_API_KEY")},
                      json={"text": text, "voice_id": cfg["voice_name"], "language": "am",
                            "output_format": "wav_44100",
                            "client_request_id": str(uuid.uuid4())})  # required (FAILURES F03)
    if r.status_code in (402, 429):
        raise QuotaExhausted(f"addis: HTTP {r.status_code} {r.text[:200]}")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    url = r.json()["data"]["audio_url"]
    audio = requests.get(url, timeout=120)
    audio.raise_for_status()
    return audio.content


PROVIDERS = {"gemini": gemini_tts, "addis": addis_tts}


# ---------- helpers ----------

def pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def synth_with_fallback(chain: list[dict[str, Any]], text: str) -> tuple[bytes, dict[str, Any]]:
    last: Exception | None = None
    for cfg in chain:
        fn = PROVIDERS[cfg["provider"]]
        try:
            return with_retries(lambda c=cfg: fn(c, text), attempts=3, base_delay=20.0,
                                no_retry=(QuotaExhausted,)), cfg
        except Exception as exc:  # noqa: BLE001 — any failure moves on to the next provider
            print(f"    {cfg['provider']}:{cfg['voice_name']} failed ({exc}) → next fallback")
            last = exc
    raise RuntimeError(f"all narration providers failed; last error: {last}")


# ---------- stage ----------

def run() -> dict[str, Path | None]:
    board = load_storyboard()
    v = board["voice"]
    main = {k: v[k] for k in ("provider", "model", "voice_name") } | {"style": v.get("style", "")}
    chain = [main, *v.get("fallbacks", [])]
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path | None] = {}
    for shot in board["shots"]:
        sid, text = shot["id"], shot["narration"].strip()
        if not text:
            results[sid] = None
            continue
        take = shot.get("narration_take", 1)
        h = input_hash(main, text) if take == 1 else input_hash(main, text, take)
        path = OUT / f"{sid}_{h}.wav"
        rel = str(path.relative_to(ROOT))
        params = {"provider": main["provider"], "voice": main["voice_name"], "shot": sid}
        if path.exists():
            log_call("narration", main["model"], params, None, 0.0, True, output=rel, cache_hit=True)
            print(f"  {sid}: cached")
            results[sid] = path
            continue
        time.sleep(THROTTLE_S)
        t = time.time()
        try:
            wav, used = synth_with_fallback(chain, text)
        except Exception as exc:  # noqa: BLE001
            log_call("narration", main["model"], params, None, time.time() - t, False, error=str(exc)[:300])
            raise
        path.write_bytes(wav)
        dur = wav_seconds(path)
        cost = round(dur / 60 * ADDIS_USD_PER_MIN, 5) if used["provider"] == "addis" else 0.0
        log_call("narration", f"{used['provider']}:{used['model']}",
                 params | {"voice": used["voice_name"], "chars": len(text)}, None, time.time() - t, True,
                 output=rel, audio_s=round(dur, 2), cost_usd=cost, fallback=used is not main)
        print(f"  {sid}: {dur:.1f}s via {used['provider']}:{used['voice_name']} in {time.time() - t:.1f}s")
        results[sid] = path
    return results


if __name__ == "__main__":
    run()
