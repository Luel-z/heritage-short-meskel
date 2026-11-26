# Ethics: consent, licences, labelling

## Consent

The film tells a real family memory. Real people are **depicted** (my grandfather, my grandmother in a
portrait, my cousins as children), but none of them is **voiced**: the narrator is a stock Addis AI
voice (`am-yohanes-calm`), not a clone of anyone's voice.

How likeness was handled:

- Family photos were used **only by me, as a visual reference** to write text descriptions
  (cap, glasses, moustache, gabi, braided hair). **No photo was uploaded to any model or API.** The
  photos are not in this repository (`references/private/` is git-ignored).
- The generated people are stylised, painted figures "inspired by", not reproductions of, real faces.
- The narration says only what I remember and wrote myself; no words are put in a real person's mouth.

**Consent record:**

| Who | Role in the film | Consent | Date |
|---|---|---|---|
| Me (the filmmaker) | author of the story and the narration text; the memory is my own | I consent to telling this story and publishing the film | 26 Nov 2026 |

Basis for the depicted family figures: the story is my own childhood memory, written by me. **No names
are used, no real photographs appear in the film, and no photo was given to any model.** The
grandfather, grandmother (portrait) and cousins on screen are generated, stylised figures described in
generic text, not likenesses produced from anyone's image, and no real person's voice is used.

## Licences

| Component | Licence / terms | Output use |
|---|---|---|
| FLUX.2 klein **4B** (Black Forest Labs) via Cloudflare Workers AI | Apache 2.0 (the 9B variant is non-commercial; I deliberately used 4B) | free to use |
| Wan 2.2 TI2V-5B (Alibaba) | Apache 2.0 | free to use |
| Score in the final film: `pipeline/compose.py` | written for this project; no model, no samples | original, mine |
| ACE-Step 1.5 (stage built, not used in the final cut) | MIT; trained on licensed, royalty-free and synthetic data | outputs usable commercially |
| Addis AI TTS (Addis Voices 2) | Terms §5 assign output rights to the user (voices themselves excluded); §6 allows Addis AI to train on inputs and outputs | narration usable; see privacy note |
| Gemini TTS (fallback, not in the final cut) | Google Gemini API terms; audio carries SynthID | — |
| FFmpeg | LGPL/GPL build | tool only |
| Nyala / Arial fonts (end card) | Windows system fonts | rendered into the image |

## Privacy

- Addis AI's standard terms allow training on submitted text. The narration contains no private
  details (no names, addresses or dates): it describes a holiday custom many Ethiopian families share.
  I accepted this trade-off for much better Amharic (EXPERIMENTS E02).
- Image prompts contain only generic descriptions, no names.
- API keys are in `.env`, which is git-ignored.

## Labelling plan

- The film ends with a visible end card: **"Made with AI"**, listing the image and voice models and
  stating that the music was composed in code.
- When posting, I switch on the platform's AI-content disclosure (YouTube "altered or synthetic
  content" / TikTok "AI-generated" label).
- Watermarks and provenance metadata from the providers are left intact.
- Style is described in words ("warm hand-painted illustration, gouache texture"); no living artist is named.
