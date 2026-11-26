# Architecture

## The contract

`storyboard.json` is the only thing stages share. It is validated against
`schema/storyboard.schema.json` at the start of every stage (`common.load_storyboard()`), so a typo
fails loudly before any model is called. It holds everything that determines the film: shots and their
reasons, image prompts, motion prompts, seeds, narration lines, subtitles, the style block, character
descriptions, reference-sheet prompts, the voice chain, the music caption/bpm/key/cues and the chosen score.
Prompts and seeds live in the storyboard, not in code, so any shot can be explained and reproduced.

```
                         storyboard.json  ── validated by schema/storyboard.schema.json
                                │
   ┌──────────────┬─────────────┼──────────────┬───────────────────┐
   ▼              ▼             ▼              ▼                   ▼
narration.py  keyframes.py   shots.py       music.py            assemble.py
Addis AI TTS  FLUX.2 klein   Wan 2.2 5B     ACE-Step 1.5        FFmpeg (no AI)
(Gemini       (Cloudflare)   (Kaggle T4)    (Kaggle T4)         Ken Burns / clips,
 fallback)    refs → frames                                     duck, subtitles,
   │              │             │              │                 loudnorm, end card
   ▼              ▼             ▼              ▼                   ▼
outputs/      outputs/       outputs/       outputs/music/     outputs/segments/
narration/    references/    shots/                            outputs/film/
              keyframes/                                        meskel_{vertical,horizontal}.mp4
```

## Stages

| Stage | Script | Reads | Writes | Model / tool |
|---|---|---|---|---|
| Narration | `pipeline/narration.py` | `voice`, `shots[].narration`, `narration_take` | `outputs/narration/<shot>_<hash>.wav` | Addis AI `am-yohanes-calm`; Gemini TTS fallback |
| Reference sheet | `pipeline/keyframes.py refs` | `references`, `style_block` | `outputs/references/<id>_<hash>.png` | FLUX.2 klein 4B |
| Keyframes | `pipeline/keyframes.py` | `shots[].image_prompt`, `characters`, `refs`, `seed`, `style_block` | `outputs/keyframes/<shot>_<hash>.png` | FLUX.2 klein 4B, reference images as conditioning |
| Moving shots | `pipeline/shots.py` | shots with `motion: "wan"`, `motion_prompt`, keyframe | `outputs/shots/<shot>_<keyframe>_<hash>.mp4` | Wan 2.2 TI2V-5B on Kaggle |
| Score (default) | `pipeline/compose.py` | `music.bpm`, `scale`, `seed`, `cues`, shot timeline | `outputs/music/composed_<hash>.wav` | deterministic synthesis (numpy), no GPU |
| Music (GPU, optional) | `pipeline/music.py` | `music.caption`, `bpm`, `key`, film length | `outputs/music/<hash>/score_seed*.wav` | ACE-Step 1.5 turbo on Kaggle / Colab |
| Assembly | `pipeline/assemble.py` | everything above + `subtitle_en`, `kenburns`, `music.chosen` | `outputs/segments/*`, `outputs/film/*` | FFmpeg, Pillow |

`pipeline/run_all.py` (or `make film`) runs them in order.

## Caching: a re-run only regenerates what changed

Every output file name contains a short SHA-256 of **everything that determines it**
(`common.input_hash`). Before calling a model, a stage checks whether that file exists.

| Output | Hash inputs |
|---|---|
| narration line | main voice config, line text, `narration_take` (if > 1) |
| reference image | model, prompt + style block, seed, size |
| keyframe | model, full prompt (shot + characters + style), seed, size, **hashes of its reference images** |
| Wan clip | keyframe file name, motion prompt, seed, resolution, frames, steps, negative prompt |
| score | caption, bpm, key, duration, seeds |
| film segment | source (clip or keyframe) name, duration, camera move, aspect |

Consequences, by design:

- Change one narration line → one TTS call; that shot's segment is re-timed, nothing else is generated.
- Change one image prompt → one FLUX call, one segment re-rendered per aspect.
- Regenerate a reference image → every keyframe that uses it is regenerated (its hash includes the
  reference's hash), and nothing else.
- A mispronounced line can be re-taken without changing its text by bumping `narration_take`.

Cache hits are logged to `runs.jsonl` with `"cache_hit": true`, so the logs show exactly what a run did.

## Logging

`common.log_call` appends one JSON line per model call (and per cache hit) to `runs.jsonl`:
stage, model, parameters, seed, latency, cost, ok/error, output path, plus stage-specific fields
(`audio_s`, `gpu_minutes`, `fallback`). COSTS.md is computed from it.

## Failure handling

- **Retries:** `common.with_retries` retries transient errors with exponential back-off.
- **Quota-aware fallback:** a daily-quota error is *not* retried (waiting cannot help, FAILURES F01/F02);
  the narration stage moves on to the next voice in `voice.fallbacks`, and logs which one it used.
- **Graceful degradation for video:** if a Wan clip is missing or failed, `assemble.py` renders that
  shot as a Ken Burns pan/zoom over the keyframe. The film always builds; GPU time only improves it.
- **Temp music:** until a score is chosen, a soft synthesized drone stands in, so the edit and the
  ducking can be tested early.
- **Idempotent paid calls:** Addis AI requests carry a fresh `client_request_id` (FAILURES F03).
- **Schema validation** before every stage, so a malformed storyboard fails before spending quota.
- **Secrets** live in `.env` (git-ignored); `.env.example` lists the names.

## Why the picture is square

Keyframes are generated at 1024×1024 with the subject centred. The assembler crops the same frame to
9:16 or 16:9 and adds slow movement, so one image serves both exports (Appendix B). Where a centre crop
fails (s06: two portraits side by side), the shot uses a pan across the frame instead of a zoom.

## Sound

Each narration line is placed at its shot start + 0.6 s (`adelay`), mixed to one voice track, and used
as the sidechain that ducks the music (`sidechaincompress threshold=0.02 ratio=6 attack=300
release=1500`). The mix is normalised with `loudnorm I=-14 TP=-1`. Shot length = 0.6 s + line + 0.9 s,
so the picture is cut to the voice.
