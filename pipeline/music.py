"""Stage: music. Generate score candidates with ACE-Step 1.5 on a Kaggle T4, then choose one.

  python music.py              generate candidates (cached by caption/bpm/key/duration/seeds)
  python music.py choose <n>   record candidate n as music.chosen in storyboard.json

The caption, bpm and key come from storyboard.json (tempo and key go in the metadata fields, not
the caption: Appendix B). Duration = film length rounded up. Three seeds = three candidates, like a
composer's sketchbook; the choice and the reason go in EXPERIMENTS.md.
"""

from __future__ import annotations

import json
import shutil
import sys

from common import OUTPUTS, ROOT, STORYBOARD, input_hash, load_storyboard, log_call
from kaggle_job import run_job

OUT = OUTPUTS / "music"
SEEDS = [301, 302, 303]

KAGGLE_SCRIPT = r'''
import json, os, subprocess, sys, time, glob, shutil
P = json.loads(__PARAMS__)
W = "/kaggle/working"
def sh(c):
    print("$", c, flush=True)
    subprocess.run(c, shell=True, check=True)

print(sys.version, flush=True)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
t_setup = time.time()
if not os.path.isdir(f"{W}/ace"):
    sh(f"git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git {W}/ace")
os.chdir(f"{W}/ace")
# Show install errors instead of hiding them behind `| tail` (FAILURES F11): a failed `pip install -e .`
# left loguru and other dependencies missing. Install the package, then its imports explicitly.
# Colab now runs Python 3.13 but ace-step declares '<3.13,>=3.11', so pip refused to install it and
# none of its dependencies arrived. --ignore-requires-python installs it anyway.
r = subprocess.run("pip install --ignore-requires-python -e . 2>&1", shell=True, capture_output=True, text=True)
print(r.stdout[-3000:], flush=True)
sh("pip install -q loguru vector_quantize_pytorch")
sys.path.insert(0, f"{W}/ace")
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

# Download the weights explicitly (FAILURES F11: without them initialize_service() *returns* a failure
# status instead of raising, and every generation then fails with "Model not fully initialized").
from huggingface_hub import snapshot_download
ckpt = f"{W}/ace/checkpoints"
snapshot_download("ACE-Step/Ace-Step1.5", local_dir=ckpt)
os.environ["ACESTEP_CHECKPOINTS_DIR"] = ckpt
sh(f"ls {ckpt}")

dit = AceStepHandler()
try:
    status = dit.initialize_service(project_root=f"{W}/ace", config_path="acestep-v15-turbo", device="cuda",
                                    offload_to_cpu=True)
except TypeError:
    status = dit.initialize_service(project_root=f"{W}/ace", config_path="acestep-v15-turbo", device="cuda")
print("initialize_service returned:", status, flush=True)
if "not" in str(status).lower() and "init" in str(status).lower() or "error" in str(status).lower() or "fail" in str(status).lower():
    raise SystemExit(f"ACE-Step did not initialise: {status}")
llm = LLMHandler()
setup_s = time.time() - t_setup

results = []
for seed in P["seeds"]:
    params = GenerationParams(task_type="text2music", caption=P["caption"], lyrics="[Instrumental]",
                              instrumental=True, bpm=P["bpm"], keyscale=P["key"],
                              duration=P["duration"], inference_steps=8, shift=3.0, thinking=False)
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav")
    t = time.time()
    res = generate_music(dit, llm, params, config, save_dir=f"{W}/raw_{seed}")
    took = time.time() - t
    ok = bool(getattr(res, "success", False))
    path = None
    if ok and res.audios:
        path = f"{W}/score_seed{seed}.wav"
        shutil.copy(res.audios[0]["path"], path)
    results.append({"seed": seed, "ok": ok, "latency_s": round(took, 1), "file": os.path.basename(path) if path else None,
                    "error": None if ok else str(getattr(res, "error", ""))[:500]})
    print(results[-1], flush=True)

json.dump({"setup_s": round(setup_s, 1), "results": results}, open(f"{W}/music_results.json", "w"), indent=2)
shutil.rmtree(f"{W}/ace", ignore_errors=True)  # keep the output small
for d in glob.glob(f"{W}/raw_*"):
    shutil.rmtree(d, ignore_errors=True)
'''


def generate() -> list:
    board = load_storyboard()
    m = board["music"]
    from assemble import END_CARD_S, timeline
    from narration import run as narration_run
    total = sum(r["dur"] for r in timeline(board, narration_run())) + END_CARD_S
    p = {"caption": m["caption"], "bpm": m.get("bpm", 72), "key": m.get("key", "C minor"),
         "duration": int(total) + 4, "seeds": SEEDS}
    h = input_hash(p)
    out = OUT / h
    if (out / "music_results.json").exists():
        log_call("music", "ace-step-1.5-turbo", p, SEEDS, 0.0, True, output=str(out.relative_to(ROOT)), cache_hit=True)
        print(f"  candidates cached in {out.relative_to(ROOT)}")
    else:
        script = KAGGLE_SCRIPT.replace("__PARAMS__", repr(json.dumps(p)))
        run_job("meskel-acestep-score", script, "music", p, out)
    res = json.loads((out / "music_results.json").read_text())
    for i, r in enumerate(res["results"], 1):
        print(f"  candidate {i}: seed {r['seed']} ok={r['ok']} {r['latency_s']}s → {r['file']}")
        log_call("music", "ace-step-1.5-turbo", {"seed": r["seed"], "duration": p["duration"]}, r["seed"],
                 r["latency_s"], r["ok"], output=str((out / r["file"]).relative_to(ROOT)) if r["file"] else None,
                 error=r["error"], gpu="T4")
    return res["results"]


def colab() -> None:
    """Write notebooks/meskel_acestep_colab.ipynb: the same job, for Google Colab (FAILURES F10).

    Upload it to colab.research.google.com, set Runtime → T4 GPU, Run all. The last cell downloads
    music_out.zip; unzip it into outputs/music/colab/ and run `python music.py choose <n>`.
    """
    board = load_storyboard()
    m = board["music"]
    from assemble import END_CARD_S, timeline
    from narration import run as narration_run
    total = sum(r["dur"] for r in timeline(board, narration_run())) + END_CARD_S
    p = {"caption": m["caption"], "bpm": m.get("bpm", 72), "key": m.get("key", "C minor"),
         "duration": int(total) + 4, "seeds": SEEDS}
    script = KAGGLE_SCRIPT.replace("__PARAMS__", repr(json.dumps(p))).replace('W = "/kaggle/working"', 'W = "/content/out"')
    script = 'import os; os.makedirs("/content/out", exist_ok=True)\n' + script
    finish = ('import shutil\nshutil.make_archive("/content/music_out", "zip", "/content/out")\n'
              'from google.colab import files\nfiles.download("/content/music_out.zip")\n')
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "cells": [
              {"cell_type": "markdown", "metadata": {}, "source": ["# Meskel score — ACE-Step 1.5\n",
                                                                  "Generated by `pipeline/music.py colab` from storyboard.json. Runtime → Change runtime type → **T4 GPU**, then Runtime → **Run all**."]},
              {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": script.splitlines(keepends=True)},
              {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": finish.splitlines(keepends=True)},
          ]}
    path = ROOT / "notebooks" / "meskel_acestep_colab.ipynb"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print("wrote", path)


def choose(n: int) -> None:
    board = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    files = sorted(OUT.glob("*/score_seed*.wav"), key=lambda p: p.stat().st_mtime)
    pick = [f for f in files if f.name == f"score_seed{SEEDS[n - 1]}.wav"][-1]
    board["music"]["chosen"] = str(pick.relative_to(ROOT)).replace("\\", "/")
    STORYBOARD.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chosen:", board["music"]["chosen"])


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "choose":
        choose(int(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "colab":
        colab()
    else:
        generate()
