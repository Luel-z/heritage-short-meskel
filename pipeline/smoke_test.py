"""Call each provider once and log latency to runs.jsonl. Also lists available model ids."""

from __future__ import annotations

import time

import requests

from common import log_call, need


def gemini() -> None:
    key = need("GEMINI_API_KEY")
    t = time.time()
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
    ok = r.ok
    names = [m["name"] for m in r.json().get("models", [])] if ok else []
    log_call("smoke", "gemini:list_models", {}, None, time.time() - t, ok,
             error=None if ok else r.text[:300])
    print("GEMINI", r.status_code)
    for n in names:
        if any(s in n for s in ("flash", "tts")):
            print("  ", n)


def cloudflare() -> None:
    acct, tok = need("CLOUDFLARE_ACCOUNT_ID"), need("CLOUDFLARE_API_TOKEN")
    t = time.time()
    r = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/models/search",
                     headers={"Authorization": f"Bearer {tok}"},
                     params={"task": "Text-to-Image"}, timeout=30)
    ok = r.ok
    log_call("smoke", "cloudflare:list_models", {}, None, time.time() - t, ok,
             error=None if ok else r.text[:300])
    print("CLOUDFLARE", r.status_code)
    for m in r.json().get("result", []) if ok else []:
        print("  ", m.get("name"))
    if not ok:
        print(r.text[:300])


def kaggle() -> None:
    tok = need("KAGGLE_API_TOKEN")
    t = time.time()
    r = requests.get("https://www.kaggle.com/api/v1/kernels/list",
                     headers={"Authorization": f"Bearer {tok}"}, params={"mine": "true", "pageSize": 1},
                     timeout=30)
    log_call("smoke", "kaggle:kernels_list", {}, None, time.time() - t, r.ok,
             error=None if r.ok else r.text[:300])
    print("KAGGLE", r.status_code, "" if r.ok else r.text[:200])


if __name__ == "__main__":
    for fn in (gemini, cloudflare, kaggle):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(fn.__name__, "FAILED:", exc)
