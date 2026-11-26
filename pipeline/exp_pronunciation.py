"""Experiment: Addis AI (am-yohanes-calm) pronounces ሳቅ (laughter) as "ሳክ" — the ejective ቅ comes out as plain k.

Hypothesis: a different spelling or a following vowel/syllable makes the model produce the ejective.
Same voice, same sentence, only the spelling of the word changes. Judged by ear by a native speaker.
"""

from __future__ import annotations

import time

from common import OUTPUTS, ROOT, log_call
from narration import addis_tts

CFG = {"provider": "addis", "model": "addis-voices-2", "voice_name": "am-yohanes-calm"}
VARIANTS = {
    "A_original_ሳቅ": "ያ ቤት፣ ያ መስቀል፣ ያ ሳቅ… ዛሬም ከእኔ ጋር ነው።",
    "B_alt_letter_ሣቅ": "ያ ቤት፣ ያ መስቀል፣ ያ ሣቅ… ዛሬም ከእኔ ጋር ነው።",
    "C_definite_ሳቁ": "ያ ቤት፣ ያ መስቀል፣ ያ ሳቁ… ዛሬም ከእኔ ጋር ነው።",
    "D_plural_ሳቃችን": "ያ ቤት፣ ያ መስቀል፣ ያ ሳቃችን… ዛሬም ከእኔ ጋር ነው።",
}

if __name__ == "__main__":
    out = OUTPUTS / "experiments" / "pronunciation_saq"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in VARIANTS.items():
        t = time.time()
        wav = addis_tts(CFG, text)
        path = out / f"{name}.wav"
        path.write_bytes(wav)
        log_call("experiment:pronunciation_saq", "addis:addis-voices-2", {"variant": name, "voice": CFG["voice_name"]},
                 None, time.time() - t, True, output=str(path.relative_to(ROOT)))
        print(f"{name}: {time.time() - t:.1f}s")
