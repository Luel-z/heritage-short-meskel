# Experiments

Each entry: hypothesis → change → result → decision. Every call is in `runs.jsonl` (filter by `stage`).

---

## E01 — Does the TTS style instruction get read aloud? (Gemini 3.8 Flash TTS)

- **Hypothesis:** The long, multi-sentence style prefix in the prompt is being spoken, which is why the
  first run produced 16.8 s and 18.5 s audio for short lines (s03, s04).
- **Change:** Same line (s04, `እኛ ልጆች ደግሞ እየተጫወትን እንጠብቅ ነበር።`), same voice (Sulafat), three prompt formats:
  A = long style paragraph + line, B = short `Say warmly and slowly …: <line>`, C = line only.
  Script: `pipeline/exp_tts_style.py`. Logged as `stage = experiment:tts_style`.
- **Result:** A 4.3 s, B 9.0 s, C 2.7 s. The same prompt A gave 18.5 s in the first run, so output
  length varies a lot between runs. Listening: **B includes English in the audio** (the instruction is
  spoken). **C has no extra speech but "doesn't sound like storytelling — it sounds like someone reading a
  line very fast."**
- **Decision:** Duration alone cannot validate TTS output; it has to be checked by ear. The `Say …:`
  instruction format is not safe for Amharic lines on this model.

## E02 — Native Amharic TTS (Addis AI) vs Gemini TTS

- **Hypothesis:** A provider built for Amharic will pronounce it more naturally and sound more like a
  storyteller than Gemini's multilingual TTS.
- **Change:** Same s04 line through Addis AI voices `am-hamen` (female, warm) and `am-yohanes-calm`
  (male, reflective narration), compared with the Gemini files from E01. Script: `pipeline/exp_addis.py`.
- **Result:** Latency 7.8 s and 9.2 s (Gemini ~6 s). By ear: **Addis AI sounds native.**
  **Yohanes "sounds exactly like a storytelling person."** Gemini C sounded rushed; B spoke the English
  instruction.
- **Decision:** Addis AI `am-yohanes-calm` becomes the main narrator. Gemini TTS stays as the fallback
  (`voice.fallbacks` in `storyboard.json`), so the pipeline still runs if Addis is unavailable.
  Trade-off: Addis costs ~$0.032/min (covered by the free signup credit) and its terms allow training on
  inputs — acceptable because the narration contains no private details (see ETHICS.md).

## E03 — Spelling out ethnicity and clothing in the reference-sheet prompts (same seed)

- **Hypothesis:** The first reference sheet showed a light-skinned grandfather in what looked like a
  bathrobe, and cousins of whom two looked European, in shorts. The model falls back to its defaults
  when the prompt says only "Ethiopian". Naming skin tone, "Habesha", "East African features" and
  describing the gabi as a handwoven shawl with a border should fix it.
- **Change:** Only the prompt text; **seeds kept fixed** (2001, 2002) so the comparison is fair.
  Files: `outputs/references/grandfather_107cf71aec26.png` → `grandfather_3049a77e158f.png`,
  `cousins_a4f05bed2740.png` → `cousins_9600feacf210.png`.
- **Result:** Grandfather now reads as an elderly Ethiopian man; the gabi has a coloured tibeb border.
  Cousins all have darker skin and long jeans. Still **four children instead of five** — exact counts
  did not improve.
- **Decision:** Keep both. Accept four cousins (counting is a known weak spot; Appendix B's "limit
  attempts per shot" rule). The detailed descriptions were copied into `characters[]` so every
  keyframe prompt carries them.

## E04 — Reference images as conditioning: consistency vs composition

- **Hypothesis:** Passing the reference sheet as input images to FLUX.2 klein keeps the room and the
  people consistent across shots.
- **Change:** First keyframe pass with `refs` on 7 of 10 shots (contact sheet
  `outputs/keyframes_contact.jpg`).
- **Result:** Strong consistency: the same living room (sofas, duka stools, grass, window, portraits)
  appears in s05, s06, s07, s09, s10, and the grandfather is recognisably the same in s07, s09, s10.
  But the references also **dominated composition**: s04 ("children playing") became a stiff lineup
  copied from the cousins sheet; s06 (meant as a close-up of portraits) became the wide room shot.
- **Decision:** Use references where continuity matters (the room, the grandfather) and **drop them**
  where the shot's composition matters more (s04 action, s06 close-up). Retakes
  (`outputs/keyframes_retake.jpg`) fixed both. Rule of thumb: conditioning copies layout, not just identity.

## E05 — Describing an object's shape instead of naming it (jebena)

- **Hypothesis:** The model does not know the word "jebena"; the test image was a Western teapot with a
  lid. Describing the shape will work where the name does not.
- **Change:** s08 prompt: "a jebena (a black clay coffee pot with a round bulbous base, a long thin
  neck and a small straight spout, no lid, not a teapot)".
- **Result:** s08 keyframe shows a round-bodied clay pot with a spout and no lid — recognisably a jebena.
- **Decision:** For culturally specific objects, describe the form; keep the local name in brackets
  for human readers.

## E06 — Pronouncing ሳቅ (laughter): spelling variants

- **Hypothesis:** Addis AI reads ሳቅ as "ሳክ" (the ejective ቅ becomes plain k). A different spelling or
  a following vowel may produce the ejective.
- **Change:** s10 line with four spellings, same voice: A ሳቅ, B ሣቅ, C ሳቁ, D ሳቃችን.
  Files: `outputs/experiments/pronunciation_saq/`. Script: `pipeline/exp_pronunciation.py`.
- **Result (by ear, native speaker):** A (ሳቅ, the original spelling) is the correct one. C (ሳቁ) changes
  the meaning: it points to a person ("his laughter"), so it cannot be used however it sounds.
- **Decision:** Keep the original spelling A in s08 and s10. Lesson: a pronunciation fix by respelling
  must be checked for meaning, not only sound.

## E08 — Golden reference: an approved shot instead of a character sheet

- **Hypothesis:** User test 2 said the grandfather looks different in each picture and the final image
  shows **two identical old men**. The grandfather reference sheet shows him twice (front and
  three-quarter), and E04 showed that conditioning copies layout — so the model copied both figures.
  Using the single approved image (s09, which both testers said looks exactly right) as the reference
  should give one, consistent grandfather.
- **Change:** `keyframe_lock` on s09 (never regenerated); `refs: ["living_room", "shot:s09"]` on s07
  and s10 instead of the two-view sheet. Prompt for s10 also says "only one old man in the room".
- **Result:** s10 now has one grandfather, and he matches s09 (cap, glasses, moustache, white gabi);
  s07 also matches. Contact sheets: `outputs/test2_fixes.jpg`, `outputs/test2_fixes2.jpg`.
- **Decision:** For identity, a single approved shot beats a multi-view sheet with this model. Lock
  approved shots so later fixes cannot change them.

## E09 — Telling the model what is NOT there (flowers growing indoors)

- **Hypothesis:** After the grass fix, s05 and s10 showed daffodils and wildflowers growing out of the
  floor. FLUX.2 klein on Workers AI has no negative-prompt field, so the exclusion has to be in the
  prompt itself.
- **Change:** Appended "the floor has only flat scattered grass strands, no flowers anywhere, no plants
  growing indoors" to s05 and s10.
- **Result:** Both retakes have no flowers; the grass lies flat on the boards.
- **Decision:** When a model adds unwanted things, state the absence explicitly and concretely.

## E10 — A composed score when no GPU is available

- **Hypothesis:** A small deterministic synthesis stage can give the film an original score that
  follows the story's shape (the cue list), without any GPU — good enough to carry the film, if
  simpler than a generative model.
- **Change:** `pipeline/compose.py`: Tizita scale (C D Eb G Ab) at 72 bpm; additive "krar" plucks
  (higher partials decay faster), a bowed "masenqo" drone with vibrato, a soft "kebero" thump; four
  sections from `music.cues` (solo → fuller → warmest → solo, resolving on C); melody = seeded walk
  (seed 301); synthetic room reverb.
- **Result:** 82 s score in 6.3 s on the laptop CPU; cached by a hash of bpm, scale, seed, cues and
  the shot timeline, so it re-composes only when the edit's timing changes. Final mix measured
  −15.0 LUFS integrated, −1.0 dBFS true peak.
  By ear: <!-- your impression: does it fit? where does it work / not work? -->
- **Decision:** Ship the composed score (`music.engine = "composed"`); keep the ACE-Step stage in the
  code for when a GPU is available (`make film-gpu`).

## E07 — Re-take vs. rewording for a dropped syllable (s05)

- **Hypothesis:** "እንሰበሰብ ነበር" came out as "እሰበሰብ ነበር". TTS output varies between runs (E01), so a
  second take of the same text may fix it without rewording.
- **Change:** `narration_take: 2` on s05 (same text, new cache key, one new call).
- **Result:** Take 2 (`outputs/narration/s05_620a0ec00ce4.wav`) is acceptable. እን is spoken but
  weakly; the word should carry more stress, but the difference is small.
- **Decision:** Keep take 2. A re-take costs one call and changes nothing else (cache), so it is the
  cheapest first fix to try before rewording.
