"""Stage: assemble. Builds the film from the storyboard with FFmpeg (deterministic, no AI).

  python assemble.py radio      narration + placeholder music on black, subtitles  (user test 1)
  python assemble.py film       pictures for every shot, exported 9:16 and 16:9

Timing is set by the narration (professionals cut picture to the voice): each shot lasts
LEAD + narration + TAIL seconds, or its min_duration_s if longer.

Picture per shot: a Wan 2.2 clip from outputs/shots/ if one exists for that keyframe, otherwise a
slow pan/zoom (Ken Burns) over the keyframe. Each shot segment is cached by a hash of its inputs, so
changing one shot re-renders only that segment.

Sound: narration placed on the timeline, the score (music.chosen, or a placeholder drone) ducked under
it with sidechaincompress, then loudness-normalised to -14 LUFS / -1 dBTP.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from common import OUTPUTS, ROOT, input_hash, load_storyboard, log_call
from narration import run as narration_run, wav_seconds

LEAD, TAIL = 0.6, 0.9          # silence before / after each narration line
END_CARD_S = 3.0
FPS = 24
SIZES = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
OUT = OUTPUTS / "film"
SEG = OUTPUTS / "segments"
SHOTS = OUTPUTS / "shots"       # Wan 2.2 clips, named <shot>_<keyframe-stem>.mp4
FONT_AM = "C:/Windows/Fonts/nyala.ttf"
FONT_EN = "C:/Windows/Fonts/arial.ttf"
SUB_STYLE = {
    # BorderStyle=3 = semi-transparent box behind the text: readable over bright painted frames
    "vertical": "FontName=Arial,FontSize=8,PrimaryColour=&H00FFFFFF,BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=60,MarginL=18,MarginR=18",
    "horizontal": "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=18",
}


# ---------------- timeline + subtitles ----------------

def timeline(board: dict, narr: dict[str, Path | None]) -> list[dict]:
    t, rows = 0.0, []
    for shot in board["shots"]:
        p = narr.get(shot["id"])
        speech = wav_seconds(p) if p else 0.0
        dur = max(shot.get("min_duration_s", 0.0), LEAD + speech + TAIL if p else 0.0)
        rows.append({"id": shot["id"], "start": t, "dur": dur, "narr": p, "speech": speech,
                     "sub": shot["subtitle_en"], "shot": shot})
        t += dur
    return rows


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def wrap(text: str, width: int = 40) -> str:
    """At most two lines of ~40 characters (Appendix B subtitle guidance)."""
    words, line1 = text.split(), ""
    while words and len(line1) + len(words[0]) + 1 <= max(width, len(text) // 2 + 1):
        line1 = f"{line1} {words.pop(0)}".strip()
    return line1 + ("\n" + " ".join(words) if words else "")


def write_srt(rows: list[dict], path: Path) -> None:
    lines, n = [], 0
    for r in rows:
        if not r["sub"]:
            continue
        n += 1
        a, b = r["start"] + LEAD, r["start"] + LEAD + r["speech"]
        lines += [str(n), f"{srt_time(a)} --> {srt_time(b)}", wrap(r["sub"]), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------- sound ----------------

def audio_inputs(rows: list[dict], board: dict, total: float) -> tuple[list[str], int]:
    """Narration files, then the music input. Returns (ffmpeg args, number of narration inputs)."""
    args: list[str] = []
    for r in rows:
        if r["narr"] is not None:
            args += ["-i", str(r["narr"])]
    n = sum(1 for r in rows if r["narr"] is not None)
    chosen = board["music"].get("chosen")
    if board["music"].get("engine", "composed") == "composed":
        from compose import run as compose_run
        args += ["-i", str(compose_run())]
    elif chosen and (ROOT / chosen).exists():
        args += ["-stream_loop", "-1", "-i", str(ROOT / chosen)]
    else:  # temp track until an ACE-Step score is chosen
        expr = "0.25*sin(2*PI*130.81*t)+0.18*sin(2*PI*196*t)*(0.6+0.4*sin(2*PI*0.1*t))"
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"aevalsrc={expr}:s=48000"]
    return args, n


def audio_filter(rows: list[dict], music_input: int, total: float) -> str:
    """Place each narration at its start, duck the music under the voice, normalise loudness."""
    parts, labels, k = [], [], 0
    for r in rows:
        if r["narr"] is None:
            continue
        ms = int((r["start"] + LEAD) * 1000)
        parts.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{k}]")
        labels.append(f"[n{k}]")
        k += 1
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{total:.3f}[voice]")
    parts.append("[voice]asplit[v1][v2]")
    parts.append(f"[{music_input}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
                 f"afade=t=in:d=2,afade=t=out:st={total - 3:.3f}:d=3,volume=0.35[mus]")
    parts.append("[mus][v1]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[ducked]")
    parts.append("[v2][ducked]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[aout]")
    return ";".join(parts)


# ---------------- picture ----------------

def kenburns_filter(kind: str, w: int, h: int, frames: int) -> str:
    """Crop the square keyframe to the target aspect around the centre, then slow pan/zoom."""
    crop = f"crop=ih*{w}/{h}:ih" if w < h else f"crop=iw:iw*{h}/{w}"
    n = max(frames - 1, 1)
    z, x, y = {
        "zoom_in": (f"1+0.10*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        "zoom_out": (f"1.10-0.10*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        "pan_left": ("1.08", f"(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),
        "pan_right": ("1.08", f"(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),
    }[kind]
    # upscale before zoompan to reduce the stair-step jitter zoompan has at low resolution
    return (f"{crop},scale={w * 2}:{h * 2}:flags=lanczos,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={FPS},setsar=1")


def clip_filter(w: int, h: int, dur: float) -> str:
    """Fit a Wan clip to the target aspect and stretch its last frame if the shot is longer."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},"
            f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setsar=1")


def run_ffmpeg(cmd: list[str], label: str, out: Path, cwd: Path | None = None, quiet: bool = False) -> None:
    t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    ok = res.returncode == 0
    log_call("assemble", "ffmpeg", {"target": label}, None, time.time() - t, ok,
             output=str(out.relative_to(ROOT)) if ok else None, error=None if ok else res.stderr[-600:])
    if not ok:
        raise SystemExit(f"ffmpeg failed ({label}):\n{res.stderr[-2000:]}")
    if not quiet:
        print(f"  {label}: {out.relative_to(ROOT)} in {time.time() - t:.1f}s")


def segment(row: dict, keyframe: Path, aspect: str) -> Path:
    """Render one shot's picture (no audio). Cached by its inputs."""
    w, h = SIZES[aspect]
    shot = row["shot"]
    clips = sorted(SHOTS.glob(f"{shot['id']}_{keyframe.stem}*.mp4")) if shot["motion"] == "wan" else []
    source = clips[-1] if clips else keyframe
    kind = shot.get("kenburns", "zoom_in")
    h_ = input_hash(source.name, round(row["dur"], 3), kind, aspect, FPS, "v2")
    out = SEG / f"{shot['id']}_{aspect}_{h_}.mp4"
    if out.exists():
        print(f"  {shot['id']} {aspect}: cached")
        return out
    SEG.mkdir(parents=True, exist_ok=True)
    frames = int(round(row["dur"] * FPS))
    if clips:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-vf", clip_filter(w, h, row["dur"])]
    else:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(source),
               "-vf", kenburns_filter(kind, w, h, frames), "-frames:v", str(frames)]
    cmd += ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", str(FPS), str(out)]
    run_ffmpeg(cmd, f"segment {shot['id']} {aspect} ({'wan' if clips else kind})", out)
    return out


def end_card(board: dict, aspect: str) -> Path:
    """The visible 'made with AI' card, drawn with Pillow (Amharic title in Nyala)."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = SIZES[aspect]
    out = SEG / f"endcard_{aspect}.png"
    img = Image.new("RGB", (w, h), (20, 14, 10))
    d = ImageDraw.Draw(img)
    s = w / 1080 if aspect == "vertical" else h / 1080
    lines = [
        ("መስቀል በአያቴ ቤት", FONT_AM, int(78 * s), (240, 214, 160)),
        (board["title"], FONT_EN, int(40 * s), (230, 225, 215)),
        ("", FONT_EN, int(30 * s), (0, 0, 0)),
        ("Made with AI", FONT_EN, int(46 * s), (255, 255, 255)),
        ("Images: FLUX.2 klein  ·  Voice: Addis AI", FONT_EN, int(28 * s), (190, 185, 175)),
        ("Music: " + ("composed in code (Tizita)" if board["music"].get("engine", "composed") == "composed"
                      else "ACE-Step 1.5") + "  ·  Edit: FFmpeg", FONT_EN, int(28 * s), (190, 185, 175)),
        ("", FONT_EN, int(30 * s), (0, 0, 0)),
        ("For my family", FONT_EN, int(34 * s), (240, 214, 160)),
    ]
    fonts = [(t, ImageFont.truetype(f, size), c) for t, f, size, c in lines]
    heights = [(f.getbbox(t or "A")[3] - f.getbbox(t or "A")[1]) + int(26 * s) for t, f, _ in fonts]
    y = (h - sum(heights)) // 2
    for (t, f, c), lh in zip(fonts, heights):
        if t:
            tw = d.textlength(t, font=f)
            d.text(((w - tw) / 2, y), t, font=f, fill=c)
        y += lh
    SEG.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def film(aspects: list[str]) -> list[Path]:
    from keyframes import run as keyframes_run

    board = load_storyboard()
    rows = timeline(board, narration_run())
    frames = keyframes_run()
    total = sum(r["dur"] for r in rows) + END_CARD_S
    OUT.mkdir(parents=True, exist_ok=True)
    srt = OUT / "film.srt"
    write_srt(rows, srt)
    results = []
    for aspect in aspects:
        w, h = SIZES[aspect]
        segs = [segment(r, frames[r["id"]], aspect) for r in rows]
        card = end_card(board, aspect)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for s in segs:
            cmd += ["-i", str(s)]
        cmd += ["-loop", "1", "-t", f"{END_CARD_S}", "-i", str(card)]
        a_args, n_voice = audio_inputs(rows, board, total)
        cmd += a_args
        base = len(segs) + 1                       # first audio input index
        music_idx = base + n_voice
        # video: concat segments + end card (fade in), then fade out at the very end, then subtitles
        vparts = [f"[{len(segs)}:v]scale={w}:{h},fps={FPS},format=yuv420p,setsar=1,fade=t=in:d=0.8[card]"]
        vparts.append("".join(f"[{i}:v]" for i in range(len(segs))) + "[card]"
                      + f"concat=n={len(segs) + 1}:v=1:a=0,fade=t=in:d=1,"
                        f"subtitles=film.srt:force_style='{SUB_STYLE[aspect]}'[vout]")
        # audio filter indexes are relative to all inputs: shift narration labels by `base`
        afilter = audio_filter(rows, music_idx, total)
        for k in reversed(range(n_voice)):
            afilter = afilter.replace(f"[{k}:a]", f"[{base + k}:a]")
        out = OUT / f"meskel_{aspect}.mp4"
        cmd += ["-filter_complex", ";".join(vparts) + ";" + afilter,
                "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(out)]
        run_ffmpeg(cmd, f"film {aspect}", out, cwd=OUT)
        results.append(out)
    print(f"  total {total:.1f}s")
    return results


def radio_cut() -> Path:
    board = load_storyboard()
    rows = timeline(board, narration_run())
    total = sum(r["dur"] for r in rows) + END_CARD_S
    OUT.mkdir(parents=True, exist_ok=True)
    write_srt(rows, OUT / "radio_cut.srt")
    a_args, n_voice = audio_inputs(rows, board, total)
    w, h = SIZES["vertical"]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a_args,
           "-f", "lavfi", "-t", f"{total:.3f}", "-i", f"color=c=black:s={w}x{h}:r={FPS}"]
    vf = f"[{n_voice + 1}:v]subtitles=radio_cut.srt:force_style='{SUB_STYLE['vertical']}'[vout]"
    out = OUT / "radio_cut.mp4"
    cmd += ["-filter_complex", audio_filter(rows, n_voice, total) + ";" + vf,
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-r", str(FPS), str(out)]
    # run inside OUT so the subtitles filter gets a plain relative path (Windows drive colons break it)
    run_ffmpeg(cmd, "radio_cut", out, cwd=OUT)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "film"
    if mode == "radio":
        radio_cut()
    elif mode == "film":
        film(sys.argv[2:] or ["vertical", "horizontal"])
    else:
        raise SystemExit("usage: assemble.py [radio|film] [vertical|horizontal]")
