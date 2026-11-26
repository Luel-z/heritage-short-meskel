
import json, os, subprocess, sys, time, glob, shutil
P = json.loads('{"caption": "instrumental, gentle Ethiopian folk lullaby, solo krar and soft masenqo, light hand drum, warm and nostalgic, sparse texture, no lead vocals, intimate room recording", "bpm": 72, "key": "C minor", "duration": 83, "seeds": [301, 302, 303]}')
W = "/kaggle/working"
def sh(c):
    print("$", c, flush=True)
    subprocess.run(c, shell=True, check=True)

print(sys.version, flush=True)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
t_setup = time.time()
sh(f"git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git {W}/ace")
os.chdir(f"{W}/ace")
sh("pip install -q -e . 2>&1 | tail -n 5")
sys.path.insert(0, f"{W}/ace")
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

dit = AceStepHandler()
try:
    dit.initialize_service(project_root=f"{W}/ace", config_path="acestep-v15-turbo", device="cuda",
                           offload_to_cpu=True)
except TypeError:
    dit.initialize_service(project_root=f"{W}/ace", config_path="acestep-v15-turbo", device="cuda")
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
