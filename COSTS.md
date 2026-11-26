# Costs

All numbers below are **measured** from `runs.jsonl` by `python pipeline/costs.py` (re-run it to
refresh). Latency is wall-clock time per call as seen by the pipeline, including network. Kaggle GPU
minutes are the wall-clock time of the job (queue + setup + model download + generation), which is
what the weekly quota is charged for.

<!-- AUTO:START -->
| Stage | Model calls | ok / failed | Cache hits | Total latency | Mean latency | GPU min (T4) | Cash spent | List-price equivalent |
|---|---|---|---|---|---|---|---|---|
| assemble | 66 | 65 / 1 | 0 | 1392 s | 21.1 s | 0.0 | $0.000 | $0.000 |
| experiment:addis_vs_gemini | 2 | 2 / 0 | 0 | 17 s | 8.5 s | 0.0 | $0.000 | $0.000 |
| experiment:pronunciation_saq | 4 | 4 / 0 | 0 | 51 s | 12.8 s | 0.0 | $0.000 | $0.000 |
| experiment:tts_style | 3 | 3 / 0 | 0 | 16 s | 5.3 s | 0.0 | $0.000 | $0.000 |
| keyframes | 31 | 31 / 0 | 229 | 410 s | 13.2 s | 0.0 | $0.000 | $0.108 |
| music | 6 | 1 / 5 | 9 | 39939 s | 6656.5 s | 0.0 | $0.000 | $0.000 |
| narration | 22 | 20 / 2 | 327 | 470 s | 21.4 s | 0.0 | $0.037 | $0.037 |
| references | 7 | 7 / 0 | 77 | 106 s | 15.1 s | 0.0 | $0.000 | $0.025 |
| run_all | 2 | 2 / 0 | 0 | 363 s | 181.6 s | 0.0 | $0.000 | $0.000 |
| shots | 2 | 0 / 2 | 0 | 11020 s | 5510.1 s | 0.0 | $0.000 | $0.000 |
| smoke | 3 | 2 / 1 | 0 | 4 s | 1.5 s | 0.0 | $0.000 | $0.000 |

Kaggle jobs waited **849 minutes** in the GPU queue without ever starting (FAILURES F08–F11); that wait is not GPU time and is excluded above.

**Totals:** 148 model calls, 642 cache hits, 0.0 T4 GPU minutes, $0.037 of Addis AI signup credit, $0 cash. Generated from 790 lines of runs.jsonl.
<!-- AUTO:END -->

## Free tiers as I actually found them (25–26 Nov 2026)

| Provider | What the brief said | What I found |
|---|---|---|
| Gemini 3.8 Flash TTS | free tier | free, but **10 requests per day per model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) — FAILURES F01 |
| Addis AI TTS | (not in the brief) | $3.17 signup credit, no card; $0.032 per minute of audio; `client_request_id` required |
| Cloudflare Workers AI, FLUX.2 klein 4B | daily free allowance | worked for every call so far; ~10–18 s per 1024² image incl. network |
| Kaggle | ~30 GPU h/week, phone verification | T4 via CLI `kernels push`; jobs wait in a queue before starting |

## List-price assumptions (for the "equivalent" column)

These are assumptions, not quotes; check each provider's pricing page before relying on them.

- Kaggle T4 time priced at a cloud on-demand T4 rate of **$0.35 / GPU-hour**.
- FLUX.2 klein 4B at **$0.0035 per 1024² image** on Workers AI paid usage.
- Addis AI at its published **$0.032 / minute** (this is real spend from the signup credit).
- Gemini TTS fallback: free tier, $0.

## Where the time goes

- Narration is cheap and fast (≈10 s per line) and fully cached after the first run.
- Images are the fastest generative stage per item, which is why iterating on keyframes (E03–E05) was
  affordable; only changed shots were regenerated.
- The Kaggle stages are dominated by **setup and model download**, not generation. Batching all clips
  into one job (shots.py) pays that cost once.
