# Meskel at Grandfather's House — a heritage short, made by a pipeline

A 76-second short film, narrated in **Amharic** with English subtitles, about Meskel at my
grandfather's house: grass spread on the wooden floor, kitfo, the coffee ceremony, and the whole
family in one room. It is generated from one file, [`storyboard.json`](storyboard.json), by a
five-stage pipeline.

- **Audience and intent:** [DESIGN.md](DESIGN.md)
- **How it works:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **What I tried:** [EXPERIMENTS.md](EXPERIMENTS.md) · **What broke:** [FAILURES.md](FAILURES.md)
- **What it costs:** [COSTS.md](COSTS.md) · **Consent and licences:** [ETHICS.md](ETHICS.md)
- **Every model call:** [`runs.jsonl`](runs.jsonl)

## Run it

Requirements: Python 3.11+, FFmpeg on `PATH`, and free accounts on Google AI Studio, Cloudflare,
Addis AI and Kaggle (phone-verified, for GPU).

```bash
git clone https://github.com/Luel-z/heritage-short-meskel.git
cd heritage-short-meskel
pip install -r requirements.txt
cp .env.example .env        # then paste your own keys into .env
make film                   # or: python pipeline/run_all.py
```

Outputs: `outputs/film/meskel_vertical.mp4` (9:16) and `outputs/film/meskel_horizontal.mp4` (16:9).

Other targets:

| Command | What it does |
|---|---|
| `make smoke` | call each provider once, log latency, list model ids |
| `make validate` | validate `storyboard.json` against the schema |
| `make radio` | narration + temp music on black (the first user-test prototype) |
| `make film-gpu` | also run the Kaggle stages (Wan 2.2 clips, ACE-Step score candidates) |
| `python pipeline/music.py colab` | write a Colab notebook for the ACE-Step job (see FAILURES F10–F11) |

## Change one shot

Edit one `image_prompt` or one `narration` line in `storyboard.json` and run `make film` again.
Only that keyframe or that line is regenerated; everything else is a cache hit (see `runs.jsonl`,
`"cache_hit": true`). To re-take a mispronounced line without changing its text, bump its
`narration_take`.

## Stages

| # | Stage | Model | Runs on |
|---|---|---|---|
| 1 | Narration (Amharic) | Addis AI `am-yohanes-calm` (fallback: Gemini 3.8 Flash TTS) | API |
| 2 | Reference sheet + keyframes | FLUX.2 klein 4B | Cloudflare Workers AI |
| 3 | Moving shots | Ken Burns pan/zoom over each keyframe (Wan 2.2 TI2V-5B stage built, `--gpu`) | local (Kaggle T4 with `--gpu`) |
| 4 | Score | **composed in code** (`compose.py`, Tizita scale, krar / masenqo / kebero synthesis); ACE-Step 1.5 stage built, `--gpu` | local, no GPU |
| 5 | Assembly | FFmpeg: ducking, subtitles, −14 LUFS, end card, 9:16 + 16:9 | local |

**Why no Wan clips or ACE-Step score in the final film:** on the deadline day no free GPU would run
them — Kaggle jobs queued for hours, Colab moved to Python 3.13 (ACE-Step supports ≤ 3.12) and then
hit its GPU limit, the official ACE-Step Space failed to initialise, and the ACE-Step web app charges
for downloads. The full chain is in [FAILURES.md](FAILURES.md) F08–F11. Both GPU stages are in the
code and run with `make film-gpu`; the default `make film` needs no GPU at all.

## Cost

Zero cash beyond free tiers: Addis AI used part of its signup credit, the rest ran on free daily
allowances and the Kaggle weekly GPU quota. Measured numbers per stage are in [COSTS.md](COSTS.md).

## Repository layout

```
storyboard.json      the contract between stages
schema/              JSON Schema, validated before every stage
pipeline/            one script per stage + run_all.py, common.py, kaggle_job.py, experiment scripts
runs.jsonl           one line per model call
outputs/             generated audio, images, clips, segments, film
DESIGN.md  ARCHITECTURE.md  EXPERIMENTS.md  FAILURES.md  COSTS.md  ETHICS.md
```
