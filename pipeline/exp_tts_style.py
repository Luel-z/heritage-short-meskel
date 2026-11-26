"""Experiment: does the style instruction get read aloud? Same line, three prompt formats, compare duration.

Hypothesis: the long multi-sentence style prefix is being spoken, inflating durations;
the short 'Say …:' format from the Gemini TTS docs is treated as direction only.
"""

from __future__ import annotations

import time

import base64

import requests

from common import OUTPUTS, log_call, need
from narration import API, wav_seconds, write_wav

LINE = "እኛ ልጆች ደግሞ እየተጫወትን እንጠብቅ ነበር።"
MODEL, VOICE = "gemini-3.8-flash-tts", "Sulafat"
VARIANTS = {
    "A_long_style": "Speak in Amharic, warmly and slowly, like an adult gently remembering a happy childhood. "
                    "Soft, unhurried, with small pauses between sentences.\n\n" + LINE,
    "B_say_format": "Say warmly and slowly, like gently remembering childhood: " + LINE,
    "C_no_style": LINE,
}

if __name__ == "__main__":
    out = OUTPUTS / "experiments" / "tts_style"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in VARIANTS.items():
        t = time.time()
        body = {"contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"responseModalities": ["AUDIO"],
                                     "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
        r = requests.post(API.format(model=MODEL), json=body, timeout=120,
                          headers={"x-goog-api-key": need("GEMINI_API_KEY")})
        r.raise_for_status()
        pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        path = out / f"{name}.wav"
        write_wav(path, pcm)
        dur = wav_seconds(path)
        log_call("experiment:tts_style", MODEL, {"variant": name, "voice": VOICE}, None, time.time() - t,
                 True, output=str(path), audio_s=round(dur, 2))
        print(f"{name}: {dur:.1f}s")
        time.sleep(15)
