"""Stage: composed score (no AI, no GPU). Deterministic synthesis that follows the storyboard.

Why this exists: no free GPU could run ACE-Step on the deadline day (FAILURES F09-F11), so the score
is composed in code instead — original, reproducible from storyboard.json, cached and logged like
every other stage.

Musical plan (from music.cues in storyboard.json and the shot timeline):
  - Scale: Tizita (C D Eb G Ab), the Ethiopian mode most associated with nostalgia and memory.
  - Tempo: music.bpm (72). Instrument colours:
      krar   — plucked lyre: additive harmonics, higher partials decay faster
      masenqo — bowed one-string fiddle: slow attack, vibrato, soft (fuller sections only)
      kebero — soft hand drum: pitch-dropping sine thump (warmest section only)
  - Sections follow the cues: solo krar (s01-s04) → fuller with masenqo drone (s05-s07) →
    warmest with drum (s08-s09) → back to solo krar, resolving on C (s10 + end card).
  - The melody is a seeded random walk on the scale (music.seed), so it is the same every run.
  - A short synthetic room reverb, then peak-normalised; assemble.py ducks it under the voice.

  python compose.py        writes outputs/music/composed_<hash>.wav (cached)
"""

from __future__ import annotations

import time
import wave
from pathlib import Path

import numpy as np

from common import OUTPUTS, ROOT, input_hash, load_storyboard, log_call

SR = 48000
VERSION = "compose-v1"
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def hz(pc: int, octave: int) -> float:
    return 440.0 * 2 ** ((pc + 12 * (octave + 1) - 69) / 12)


def krar(f: float, dur: float, vel: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for h in range(1, 9):
        fh = f * h * (1 + 0.0008 * h * h)          # slight stiffness → lyre-like brightness
        if fh > SR / 2:
            break
        out += (0.9 / h) * np.exp(-t * (1.6 + 1.1 * h)) * np.sin(2 * np.pi * fh * t)
    attack = np.minimum(1, t / 0.004)
    return vel * out * attack


def masenqo(f: float, dur: float, vel: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.8)
    phase = 2 * np.pi * np.cumsum(f * vib) / SR
    out = sum((0.6 / h) * np.sin(h * phase) for h in range(1, 6))
    env = np.minimum(1, t / 0.9) * np.minimum(1, (dur - t) / 0.9).clip(0)
    return vel * out * env


def kebero(dur: float, vel: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    f = 55 + 70 * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    click = np.random.default_rng(7).standard_normal(t.size) * np.exp(-t * 120) * 0.15
    return vel * (body + click)


def place(buf: np.ndarray, sig: np.ndarray, at: float, pan: float) -> None:
    i = int(at * SR)
    j = min(buf.shape[1], i + sig.size)
    if i >= buf.shape[1]:
        return
    seg = sig[: j - i]
    buf[0, i:j] += seg * np.sqrt(1 - pan)
    buf[1, i:j] += seg * np.sqrt(pan)


def reverb(x: np.ndarray, seconds: float = 1.1, mix: float = 0.22) -> np.ndarray:
    rng = np.random.default_rng(11)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * (6.9 / seconds))
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(x.shape[1] + n)))
    wet = np.stack([np.fft.irfft(np.fft.rfft(ch, size) * np.fft.rfft(ir, size), size)[: x.shape[1]] for ch in x])
    return (1 - mix) * x + mix * wet


def sections(rows: list[dict], cues: list[dict], total: float) -> list[tuple[float, float, int]]:
    """(start, end, level) where level 0 = solo krar, 1 = fuller, 2 = warmest, 3 = closing solo."""
    start = {r["id"]: r["start"] for r in rows}
    marks = sorted((start[c["at_shot"]], i) for i, c in enumerate(cues) if c["at_shot"] in start)
    out = []
    for k, (t0, level) in enumerate(marks):
        t1 = marks[k + 1][0] if k + 1 < len(marks) else total
        out.append((t0, t1, level))
    return out


def compose(board: dict, rows: list[dict], total: float) -> np.ndarray:
    m = board["music"]
    beat = 60.0 / m.get("bpm", 72)
    scale = [NOTE[n] for n in m.get("scale", ["C", "D", "Eb", "G", "Ab"])]
    rng = np.random.default_rng(m.get("seed", 301))
    buf = np.zeros((2, int((total + 3) * SR)))
    pitches = [(pc, o) for o in (4, 5) for pc in scale] + [(scale[0], 6)]
    idx = 2
    for t0, t1, level in sections(rows, m["cues"], total):
        t = t0
        step = {0: 2, 1: 1, 2: 1, 3: 2}[level]            # beats per krar note
        bar = 0
        while t < t1 - 0.2:
            # krar melody: seeded walk, mostly steps, occasional leap, rests in sparse sections
            if not (level in (0, 3) and rng.random() < 0.18):
                idx = int(np.clip(idx + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 0, len(pitches) - 1))
                pc, octv = pitches[idx]
                vel = 0.28 + 0.08 * rng.random()
                place(buf, krar(hz(pc, octv), 2.6, vel), t, 0.45 + 0.1 * rng.random())
                if level in (1, 2) and bar % 2 == 0:       # a lower answering note
                    place(buf, krar(hz(scale[0] if bar % 4 == 0 else scale[3], 3), 3.0, 0.2), t, 0.5)
            if level in (1, 2) and bar % 4 == 0:           # masenqo drone on the root / fifth
                pc = scale[0] if (bar // 4) % 2 == 0 else scale[3]
                place(buf, masenqo(hz(pc, 3), beat * 4 * step, 0.10 if level == 1 else 0.14), t, 0.6)
            if level == 2:                                  # soft kebero on beats 1 and 3
                place(buf, kebero(0.6, 0.22 if bar % 2 == 0 else 0.13), t, 0.5)
            t += beat * step
            bar += 1
    # resolve: final low C and high C under the end card
    end = total - 3.0
    place(buf, krar(hz(scale[0], 4), 3.5, 0.32), end, 0.5)
    place(buf, krar(hz(scale[0], 3), 3.5, 0.22), end, 0.5)
    place(buf, masenqo(hz(scale[0], 3), 3.2, 0.08), end, 0.5)
    out = reverb(buf)
    fade = np.minimum(1, np.arange(out.shape[1]) / (1.5 * SR))
    out *= fade
    return out / (np.max(np.abs(out)) + 1e-9) * 0.89     # peak about -1 dBFS


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def run() -> Path:
    from assemble import END_CARD_S, timeline
    from narration import run as narration_run

    board = load_storyboard()
    rows = timeline(board, narration_run())
    total = sum(r["dur"] for r in rows) + END_CARD_S
    m = board["music"]
    h = input_hash(VERSION, m.get("bpm"), m.get("scale"), m.get("seed"), m["cues"],
                   [(r["id"], round(r["start"], 3)) for r in rows], round(total, 3))
    path = OUTPUTS / "music" / f"composed_{h}.wav"
    rel = str(path.relative_to(ROOT))
    if path.exists():
        log_call("music", VERSION, {"engine": "composed"}, m.get("seed"), 0.0, True, output=rel, cache_hit=True)
        print(f"  composed score cached: {rel}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    write_wav(path, compose(board, rows, total))
    log_call("music", VERSION, {"engine": "composed", "bpm": m.get("bpm"), "scale": m.get("scale"),
                                "duration_s": round(total + 3, 1)}, m.get("seed"), time.time() - t, True, output=rel)
    print(f"  composed score: {rel} ({total + 3:.1f}s) in {time.time() - t:.1f}s")
    return path


if __name__ == "__main__":
    run()
