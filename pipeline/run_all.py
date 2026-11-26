"""One command for the whole pipeline:  python pipeline/run_all.py   (or: make film)

  validate → narration → keyframes → score (composed) → assemble

Every stage is cached by a hash of its inputs, so a re-run only regenerates what changed in
storyboard.json. Flags:
  --gpu        also run the Kaggle stages: Wan 2.2 clips for shots with motion "wan", and ACE-Step
               score candidates (used when music.engine is "acestep"). Off by default: no free GPU
               was available on the deadline day (FAILURES F09-F11).
  --radio      build only the radio cut (narration on black)
"""

from __future__ import annotations

import sys
import time

from common import load_storyboard, log_call


def stage(name: str, fn) -> None:
    print(f"\n== {name} ==")
    t = time.time()
    fn()
    print(f"   ({time.time() - t:.1f}s)")


def main() -> None:
    args = set(sys.argv[1:])
    import assemble
    import compose
    import keyframes
    import music
    import narration
    import shots

    t0 = time.time()
    stage("validate storyboard.json against schema", load_storyboard)
    stage("narration", narration.run)
    if "--radio" in args:
        stage("assemble radio cut", assemble.radio_cut)
        return
    stage("keyframes", keyframes.run)
    if "--gpu" in args:
        stage("shots (Wan 2.2 on Kaggle)", shots.run)
        stage("music (ACE-Step on Kaggle)", music.generate)
    stage("score (composed, no GPU)", compose.run)
    stage("assemble film (9:16 + 16:9)", lambda: assemble.film(["vertical", "horizontal"]))
    log_call("run_all", "pipeline", {"args": sorted(args)}, None, time.time() - t0, True)
    print(f"\nDone in {time.time() - t0:.0f}s → outputs/film/")


if __name__ == "__main__":
    main()
