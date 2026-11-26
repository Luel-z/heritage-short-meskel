"""Stage: moving shots. Wan 2.2 TI2V-5B image-to-video on a Kaggle T4, for shots with motion == "wan".

Each clip is cached by a hash of (keyframe, motion prompt, seed, resolution, frames, steps): change one
shot's keyframe or motion prompt and only that clip is regenerated. All missing clips are batched into
one Kaggle job (Appendix B: batch jobs, draft low). Shots without a clip fall back to the Ken Burns
pan/zoom in assemble.py, so a failed or skipped clip never breaks the film.

The keyframes are embedded in the generated script as base64 JPEGs, so no Kaggle dataset is needed.
The image prompt is NOT repeated in the motion prompt: the keyframe already holds the subject, so the
prompt describes only motion and camera (Appendix B).
"""

from __future__ import annotations

import base64
import io
import json

from common import OUTPUTS, ROOT, input_hash, load_storyboard, log_call
from kaggle_job import run_job

OUT = OUTPUTS / "shots"
RES = 704          # square draft resolution (multiple of 32); T4 memory/time bound
FRAMES = 81        # 4k+1; about 3.4 s at 24 fps, held / trimmed in the edit
STEPS = 30
NEGATIVE = "blurry, distorted face, extra fingers, morphing, flicker, text, watermark, fast motion"

KAGGLE_SCRIPT = r'''
import base64, io, json, os, subprocess, sys, time
JOBS = json.loads(__JOBS__)
W = "/kaggle/working"
def sh(c):
    print("$", c, flush=True); subprocess.run(c, shell=True, check=True)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
sh("pip install -q -U diffusers transformers accelerate ftfy imageio imageio-ffmpeg 2>&1 | tail -n 3")
import torch
from PIL import Image
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
from diffusers.utils import export_to_video
MID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
t = time.time()
vae = AutoencoderKLWan.from_pretrained(MID, subfolder="vae", torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(MID, vae=vae, torch_dtype=torch.float16)  # T4 has no native bf16
pipe.enable_model_cpu_offload()
try:
    pipe.vae.enable_tiling()
except Exception as e:
    print("no vae tiling:", e)
load_s = time.time() - t
results = []
for j in JOBS:
    img = Image.open(io.BytesIO(base64.b64decode(j["image_b64"]))).convert("RGB").resize((j["res"], j["res"]))
    t = time.time()
    try:
        frames = pipe(image=img, prompt=j["prompt"], negative_prompt=j["negative"], height=j["res"], width=j["res"],
                      num_frames=j["frames"], num_inference_steps=j["steps"], guidance_scale=5.0,
                      generator=torch.Generator("cpu").manual_seed(j["seed"])).frames[0]
        export_to_video(frames, f"{W}/{j['out']}", fps=24)
        results.append({"out": j["out"], "ok": True, "latency_s": round(time.time() - t, 1)})
    except Exception as e:
        results.append({"out": j["out"], "ok": False, "latency_s": round(time.time() - t, 1), "error": repr(e)[:500]})
        torch.cuda.empty_cache()
    print(results[-1], flush=True)
json.dump({"load_s": round(load_s, 1), "results": results}, open(f"{W}/shots_results.json", "w"), indent=2)
'''


def jpeg_b64(path, size: int) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB").resize((size, size))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def run() -> None:
    from keyframes import run as keyframes_run

    board = load_storyboard()
    frames = keyframes_run()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for shot in board["shots"]:
        if shot["motion"] != "wan":
            continue
        kf = frames[shot["id"]]
        h = input_hash(kf.name, shot["motion_prompt"], shot["seed"], RES, FRAMES, STEPS, NEGATIVE)
        name = f"{shot['id']}_{kf.stem}_{h}.mp4"
        if (OUT / name).exists():
            log_call("shots", "wan2.2-ti2v-5b", {"shot": shot["id"]}, shot["seed"], 0.0, True,
                     output=str((OUT / name).relative_to(ROOT)), cache_hit=True)
            print(f"  {shot['id']}: cached")
            continue
        jobs.append({"shot": shot["id"], "out": name, "prompt": shot["motion_prompt"], "negative": NEGATIVE,
                     "seed": shot["seed"], "res": RES, "frames": FRAMES, "steps": STEPS,
                     "image_b64": jpeg_b64(kf, RES)})
    if not jobs:
        print("  all wan clips cached")
        return
    print(f"  submitting {len(jobs)} clip(s) to Kaggle: {[j['shot'] for j in jobs]}")
    job_dir = OUT / "_job"
    script = KAGGLE_SCRIPT.replace("__JOBS__", repr(json.dumps(jobs)))
    params = {"shots": [j["shot"] for j in jobs], "res": RES, "frames": FRAMES, "steps": STEPS,
              "seeds": [j["seed"] for j in jobs]}
    run_job("meskel-wan22-shots", script, "shots", params, job_dir)
    res = json.loads((job_dir / "shots_results.json").read_text())
    for r in res["results"]:
        src = job_dir / r["out"]
        if r["ok"] and src.exists():
            src.replace(OUT / r["out"])
        log_call("shots", "wan2.2-ti2v-5b", {"clip": r["out"], "res": RES, "frames": FRAMES, "steps": STEPS},
                 None, r["latency_s"], r["ok"], output=str((OUT / r["out"]).relative_to(ROOT)) if r["ok"] else None,
                 error=r.get("error"), gpu="T4", model_load_s=res["load_s"])
        print(f"  {r['out']}: ok={r['ok']} {r['latency_s']}s")


if __name__ == "__main__":
    run()
