"""Stage: keyframes. Reference sheet first, then one keyframe per shot conditioned on it.

  python keyframes.py           references + all keyframes (cached)
  python keyframes.py refs      references only (approve them before spending on keyframes)

Model: FLUX.2 klein 4B on Cloudflare Workers AI (Apache 2.0, daily free allowance).
Every prompt = shot prompt + character descriptions + the fixed style block (Appendix B: re-describing
things differently each time is what causes drift). Each keyframe is cached by a hash of
(model, full prompt, seed, size, reference image hashes): change one shot's prompt and only that
keyframe is regenerated; regenerate a reference and every keyframe that uses it is regenerated.
"""

from __future__ import annotations

import base64
import hashlib
import sys
import time
from pathlib import Path

import requests

from common import OUTPUTS, ROOT, input_hash, load_storyboard, log_call, need, with_retries

OUT = OUTPUTS / "keyframes"
REF_OUT = OUTPUTS / "references"
SIZE = 1024  # square: crops cleanly to both 9:16 and 16:9 with the subject centred


class QuotaExhausted(RuntimeError):
    pass


def flux(model: str, prompt: str, seed: int, refs: list[Path]) -> bytes:
    acct, tok = need("CLOUDFLARE_ACCOUNT_ID"), need("CLOUDFLARE_API_TOKEN")
    fields: dict = {"prompt": (None, prompt), "width": (None, str(SIZE)), "height": (None, str(SIZE)),
                    "seed": (None, str(seed))}
    for i, ref in enumerate(refs):
        fields[f"input_image_{i}"] = (ref.name, ref.read_bytes(), "image/png")
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                      headers={"Authorization": f"Bearer {tok}"}, files=fields, timeout=180)
    if r.status_code == 429 or "neurons" in r.text.lower() and not r.ok:
        raise QuotaExhausted(f"Cloudflare daily allowance reached: {r.text[:200]}")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return base64.b64decode(r.json()["result"]["image"])


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def generate(stage: str, model: str, prompt: str, seed: int, refs: list[Path], path: Path, label: str) -> Path:
    rel = str(path.relative_to(ROOT))
    params = {"item": label, "size": SIZE, "refs": [r.stem for r in refs]}
    if path.exists():
        log_call(stage, model, params, seed, 0.0, True, output=rel, cache_hit=True)
        print(f"  {label}: cached")
        return path
    t = time.time()
    try:
        png = with_retries(lambda: flux(model, prompt, seed, refs), attempts=3, base_delay=5.0,
                           no_retry=(QuotaExhausted,))
    except Exception as exc:  # noqa: BLE001
        log_call(stage, model, params, seed, time.time() - t, False, error=str(exc)[:300])
        raise
    path.write_bytes(png)
    log_call(stage, model, params | {"prompt_chars": len(prompt)}, seed, time.time() - t, True, output=rel)
    print(f"  {label}: generated in {time.time() - t:.1f}s")
    return path


def references(board: dict) -> dict[str, Path]:
    model, style = board["image_model"], board["style_block"]
    REF_OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for ref in board.get("references", []):
        prompt = f"{ref['prompt']}. Style: {style}"
        h = input_hash(model, prompt, ref["seed"], SIZE)
        out[ref["id"]] = generate("references", model, prompt, ref["seed"], [],
                                  REF_OUT / f"{ref['id']}_{h}.png", ref["id"])
    return out


def shot_prompt(board: dict, shot: dict) -> str:
    chars = {c["id"]: c["description"] for c in board["characters"]}
    who = "; ".join(chars[c] for c in shot.get("characters", []) if c in chars)
    parts = [shot["image_prompt"]]
    if who:
        parts.append(f"Characters: {who}")
    if shot.get("refs"):
        parts.append("Keep the people and the room consistent with the reference images")
    parts.append(f"Style: {board['style_block']}")
    return ". ".join(parts)


def run(only_refs: bool = False) -> dict[str, Path]:
    board = load_storyboard()
    refs = references(board)
    if only_refs:
        return refs
    model = board["image_model"]
    OUT.mkdir(parents=True, exist_ok=True)
    frames: dict[str, Path] = {}
    # locked (approved) keyframes first, so other shots can use them as golden references
    for shot in board["shots"]:
        if shot.get("keyframe_lock"):
            frames[shot["id"]] = ROOT / shot["keyframe_lock"]
            log_call("keyframes", model, {"item": shot["id"], "locked": True}, shot["seed"], 0.0, True,
                     output=shot["keyframe_lock"], cache_hit=True)
            print(f"  {shot['id']}: locked (approved keyframe)")
    for shot in board["shots"]:
        if shot["id"] in frames:
            continue
        ref_paths = []
        for r in shot.get("refs", []):
            if r.startswith("shot:"):
                ref_paths.append(frames[r[5:]])  # golden reference: an approved shot
            elif r in refs:
                ref_paths.append(refs[r])
        prompt = shot_prompt(board, shot)
        h = input_hash(model, prompt, shot["seed"], SIZE, [file_hash(p) for p in ref_paths])
        frames[shot["id"]] = generate("keyframes", model, prompt, shot["seed"], ref_paths,
                                      OUT / f"{shot['id']}_{h}.png", shot["id"])
    return frames


if __name__ == "__main__":
    run(only_refs=len(sys.argv) > 1 and sys.argv[1] == "refs")
