"""Stage: music, Hugging Face fallback. ACE-Step 1.5 through the official Space (ACE-Step/Ace-Step-v1.5).

Used when the Kaggle job cannot get a GPU (FAILURES F10). Same caption, bpm, key, duration and seeds as
music.py, so candidates are comparable; output goes to outputs/music/hf_<hash>/score_seed<N>.wav.

  python music_hf.py            generate the three candidates (cached per seed)

The Space's endpoint /generation_wrapper takes 49 positional UI values; the names below map them to the
fields documented in ACE-Step's INFERENCE.md (captured with gradio_client view_api()).
"""

from __future__ import annotations

import shutil
import sys
import time

from common import OUTPUTS, ROOT, input_hash, load_env, load_storyboard, log_call
from music import SEEDS

SPACE = "ACE-Step/Ace-Step-v1.5"


def params_for(caption: str, bpm: int, key: str, duration: int, seed: int) -> dict:
    return {
        "selected_model": "acestep-v15-xl-turbo",
        "generation_mode": "custom",
        "param_4": caption,             # captions
        "param_5": "[Instrumental]",    # lyrics
        "param_6": bpm,                 # bpm (metadata field, not in the caption: Appendix B)
        "param_7": key,                 # key_scale
        "param_8": "4",                 # time signature 4/4
        "param_12": False,              # random_seed_checkbox off â†’ use our seed
        "param_13": str(seed),          # seed
        "param_15": duration,           # audio_duration (s)
        "param_16": 1,                  # batch size
        "param_30": "flac",             # audio_format (Space allows mp3/flac only)
        "param_32": False,              # think (LM planner) off: bpm/key are given
        "param_37": False, "param_38": False, "param_39": False,  # no LM rewriting of metas/caption/language
    }


def run() -> None:
    from gradio_client import Client

    load_env()
    board = load_storyboard()
    m = board["music"]
    from assemble import END_CARD_S, timeline
    from narration import run as narration_run
    total = sum(r["dur"] for r in timeline(board, narration_run())) + END_CARD_S
    duration = int(total) + 4
    base = {"caption": m["caption"], "bpm": m.get("bpm", 72), "key": m.get("key", "C minor"), "duration": duration}
    out = OUTPUTS / "music" / f"hf_{input_hash(base)}"
    out.mkdir(parents=True, exist_ok=True)
    client = None
    seeds = [int(s) for s in sys.argv[1:]] or SEEDS
    for seed in seeds:
        dest = out / f"score_seed{seed}.flac"
        if dest.exists():
            log_call("music", f"hf:{SPACE}", base | {"seed": seed}, seed, 0.0, True,
                     output=str(dest.relative_to(ROOT)), cache_hit=True)
            print(f"  seed {seed}: cached")
            continue
        if client is None:
            client = Client(SPACE, verbose=False)
            api = client.view_api(return_format="dict", print_info=False)["named_endpoints"]["/generation_wrapper"]
            defaults = {p["parameter_name"]: p.get("parameter_default") for p in api["parameters"]}
        t = time.time()
        try:
            args = defaults | {"simple_query_input": "", "simple_vocal_language": "unknown"} \
                | params_for(base["caption"], base["bpm"], base["key"], duration, seed)
            res = client.predict(**args, api_name="/generation_wrapper")
        except Exception as exc:  # noqa: BLE001
            log_call("music", f"hf:{SPACE}", base | {"seed": seed}, seed, time.time() - t, False, error=str(exc)[:400])
            print(f"  seed {seed}: FAILED {exc}")
            continue
        audio = find_audio(res)
        if not audio:
            log_call("music", f"hf:{SPACE}", base | {"seed": seed}, seed, time.time() - t, False,
                     error=f"no audio in result: {str(res)[:300]}")
            print(f"  seed {seed}: no audio in result {str(res)[:300]}")
            continue
        shutil.copy(audio, dest)
        log_call("music", f"hf:{SPACE}", base | {"seed": seed}, seed, time.time() - t, True,
                 output=str(dest.relative_to(ROOT)), gpu="hf-zerogpu")
        print(f"  seed {seed}: {time.time() - t:.0f}s â†’ {dest.relative_to(ROOT)}")


def find_audio(res) -> str | None:
    """The Space returns a tuple of UI updates; take the first value that is an audio file path."""
    stack = [res]
    while stack:
        v = stack.pop(0)
        if isinstance(v, str) and v.lower().endswith((".wav", ".mp3", ".flac")):
            return v
        if isinstance(v, dict):
            stack += [v.get("value"), v.get("path"), v.get("name")]
        elif isinstance(v, (list, tuple)):
            stack += list(v)
    return None


if __name__ == "__main__":
    run()

