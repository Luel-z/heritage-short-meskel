# Design

## Audience and intent (written before generating any pictures)

- **Who:** My mother's side of the family — the cousins who were children in my grandfather's house
  with me, and relatives now living abroad.
- **Where they watch:** On their phones, in the family chat (so vertical 9:16 first).
- **What they should feel at the end:** Warm nostalgia and recognition — "we were all together in that
  room." A reminder of what the family was, and an invitation to gather again.
- **Logline:** A child's memory of Meskel at grandfather's house — grass on the wooden floor, kitfo,
  coffee, and the whole family in one room.

## Why each shot exists

The reason for every shot is in `storyboard.json` (`shots[].reason`), so it travels with the shot.

## User test 1 — radio cut (narration on black, placeholder music)

- **File shown:** `outputs/film/radio_cut.mp4` (74 s)
- **Date:** 26 Nov 2026
- **Asked:** (1) What did you picture? (2) Where did you lose interest, or what felt too fast or too
  slow? (3) Does any Amharic line sound wrong? (4) What feeling did it leave you with, and is anything
  missing?

| | (1) Pictured | (2) Pace | (3) Lines | (4) Feeling / missing |
|---|---|---|---|---|
| **Respondent A** | The living room: grass on the wooden floor, grandparents' photos on the walls, the cousins squeezed around the dining table. | Line 7 (kids at the table, adults on sofas and duka stools) felt rushed for how much it describes. "We children played and waited" was over too quickly. | Nothing sounded wrong. | Warm and nostalgic. Missed the smell of incense and roasting coffee beans. |
| **Respondent B** | A child peeking into the kitchen while the grown-ups prepared kitfo. | The coffee ceremony line is the emotional peak but passes in a few seconds. The pause before the last line felt a bit too long. | "Young adults" sounded slightly translated; would expect something more natural, like the older cousins or the youth. | Comforting and a little sad. The Demera bonfire the night before is missing. |
| **Respondent C** | Their own grandfather's house. The Meskel flowers and the bonfire came to mind even though they aren't mentioned. | Opening paced well; the middle, with all its detail, felt fast; the ending felt right. | No line sounded wrong. "Still with me today" is lovely, though a proverb or a blessing might fit there. | A feeling of belonging. Missed the elders' blessings and the singing. |

**My own review of the same cut** (before the responses came in):
- ሳቅ is pronounced as "ሳክ" (s08, s10) → pronunciation experiment E06.
- s05 says "እሰበሰብ ነበር" instead of "እንሰበሰብ ነበር" → re-take, E07.
- My grandfather sat on the larger sofa wrapped in a traditional cotton gabi → added to his character
  description and to s07, s09, s10.
- The smell of incense with the coffee → added to the s08 line.

**What changed because of the test** (all in `storyboard.json`):

| Feedback | Change |
|---|---|
| A: s04 and s07 felt rushed; C: the middle felt fast | `min_duration_s`: s04 → 6.5 s, s07 → 10.5 s |
| B: the coffee ceremony passes in a few seconds | s08 → 10.5 s |
| B: the pause before the last line is too long | music-only s09 shortened from 5 s to 4 s |
| A: missed the smell of incense (matched my own note) | s08 narration now: "የእጣኑ ሽታ ከቡናው ጋር ተቀላቅሎ…"; incense smoke strengthened in the s08 image prompt |

Film length went from 74 s to 79 s.

**Considered and not adopted:** adding the Demera bonfire (B, C), ending with a proverb or blessing (C),
and rewording "young adults" (B). I decided to keep the film as it is on these three.

## User test 2 — near-final cut (pictures, temp music)

- **File shown:** `outputs/film/meskel_vertical.mp4` (79 s, Ken Burns shots, temporary music)
- **Date:** 26 Nov 2026
- **Asked:** (1) Does it feel like our grandfather's house and our Meskel — which picture felt most
  right, which wrong or strange? (2) Does the grandfather look believable, especially on the sofa with
  the gabi? (3) Does the middle still feel rushed, or is anything too slow? (4) Are the subtitles easy to
  read, do they cover anything important? (5) How did you feel at the end — would you forward it?

| | Person 1 | Person 2 |
|---|---|---|
| **(1) House / Meskel** | The house doesn't look like our grandfather's house. The Meskel part does look like Meskel, but the grass on the floor looks like it grew out of the wooden floor, not like it was laid down. The grandfather sitting alone felt the most right. | Agrees about the house. Too many pictures on the wall. The dining table is in the wrong place: it is shown in the centre of the sofa area, but there was a round centre table there, and the dining table should be off to one side. The ጀበና looks wrong. The final image felt right, but the other images feel different from each other, as if they show different places. |
| **(2) Grandfather** | Yes, where he sits alone he looks exactly right. | In the final image too. In the other pictures he looks different each time, so he doesn't feel like one consistent person. In the final image there are two old people who look the same. |
| **(3) Pace** | No feedback. | No feedback. |
| **(4) Subtitles** | Didn't cover anything important. | Same, nothing important covered. |
| **(5) Ending** | Would definitely forward it once some things are fixed. | Same, would forward it after the fixes. |

**What changed because of the test** (all in `storyboard.json`; regenerated only the affected shots):

| Feedback | Change |
|---|---|
| The house doesn't look like grandfather's (1, 2) | I described the real house (from a photo, as text only): lime-green wall, white wrought-iron door, iron pergola with orange trumpet flowers, terrazzo steps with white railings, stone-tile cladding → s01, s02 |
| Grass looks grown from the floor (1) | Prompt now: loose cut grass strands laid on the floorboards, boards visible between them → living-room reference, s05, s07, s08, s10 |
| Too many pictures on the wall (2) | Living-room reference asks for exactly two portraits (the model now draws four instead of ten) |
| Dining table in the wrong place; there was a round centre table (2) | Room layout rewritten: sofas around a low round centre table, dining table off to one side → reference, s05, s07, s10 |
| ጀበና looks wrong (2) | Shape described fully: spherical bottom, long upright neck, handle, spout, woven straw stopper → s08 |
| Grandfather different in each picture; two identical old men in the final image (2) | The approved s09 image (the one both liked) is **locked** and used as a golden reference for s07 and s10, replacing the two-view reference sheet that caused the duplicate → EXPERIMENTS E08 |
| Images feel like different places (2) | Same room reference with the corrected layout on s05, s07, s10 |

The pace and subtitles were not changed (no complaints).
