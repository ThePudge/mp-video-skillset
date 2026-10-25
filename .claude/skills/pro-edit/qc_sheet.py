"""One-image, few-lines QC of a rendered edit.

Instead of many single frames (expensive to look at), this writes ONE small
contact sheet with a frame just before and after every cut, the middle of every
overlay, and the first/last moments, plus a short text report measured by
FFmpeg: duration vs EDL, loudness, leftover pauses, black flashes.

  qc_sheet.py work/<project>/edit/preview.mp4 --edl work/<project>/edit/edl.json

Writes <video>.qc.png next to the video (or -o PATH) and prints the report.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THUMB_W = 240
COLS = 6
MAX_FRAMES = 30


def duration_of(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def grab(video: Path, t: float) -> Image.Image:
    for back in (0.0, 0.25, 0.6):  # a seek at the very end can return no frame: step back and retry
        png = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t - back):.3f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={THUMB_W}:-2", "-f", "image2pipe", "-c:v", "png", "-"],
            capture_output=True, check=True,
        ).stdout
        if png:
            return Image.open(io.BytesIO(png)).convert("RGB")
    raise RuntimeError(f"no frame at {t:.2f}s in {video}")


def sample_points(edl: dict | None, dur: float) -> list[tuple[float, str]]:
    points: list[tuple[float, str]] = [(0.3, "start")]
    if edl:
        t = 0.0
        ranges = edl.get("ranges", [])
        for i, r in enumerate(ranges[:-1], start=1):
            t += float(r["end"]) - float(r["start"])
            points += [(t - 0.2, f"cut{i}-"), (t + 0.2, f"cut{i}+")]
        for i, ov in enumerate(edl.get("overlays") or [], start=1):
            points.append((float(ov["start_in_output"]) + float(ov["duration"]) / 2, f"ov{i}"))
    points.append((dur - 0.5, "end"))
    points = sorted({(round(min(max(t, 0.0), dur - 0.05), 2), tag) for t, tag in points})
    if len(points) > MAX_FRAMES:
        step = len(points) / MAX_FRAMES
        points = [points[int(i * step)] for i in range(MAX_FRAMES)]
    return points


def contact_sheet(video: Path, points: list[tuple[float, str]], out: Path) -> None:
    thumbs = [grab(video, t) for t, _ in points]
    th = thumbs[0].height
    rows = (len(thumbs) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * THUMB_W, rows * th), "black")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (img, (t, tag)) in enumerate(zip(thumbs, points)):
        x, y = (i % COLS) * THUMB_W, (i // COLS) * th
        sheet.paste(img, (x, y))
        label = f"{t:.2f}s {tag}"
        draw.rectangle([x, y, x + 7 * len(label), y + 12], fill="black")
        draw.text((x + 2, y), label, fill="yellow", font=font)
    sheet.save(out, optimize=True)


def measure(video: Path) -> dict:
    """Loudness, pauses and black frames in one decode pass."""
    err = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(video),
         "-af", "ebur128=peak=true:framelog=quiet,silencedetect=n=-35dB:d=0.5",
         "-vf", "blackdetect=d=0.08:pix_th=0.10", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    loud = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    pauses = [(float(s), float(d)) for s, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", err)]
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)
    return {
        "lufs": float(loud[-1]) if loud else None,
        "true_peak": float(peak[-1]) if peak else None,
        "pauses": [(round(end - d, 2), round(d, 2)) for end, d in pauses],
        "blacks": [(float(a), float(b)) for a, b in blacks],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Cheap QC: one contact sheet + measured report")
    ap.add_argument("video", type=Path)
    ap.add_argument("--edl", type=Path, help="edl.json, for cut points, overlays and expected length")
    ap.add_argument("-o", "--output", type=Path, help="PNG path (default: <video>.qc.png)")
    ap.add_argument("--no-sheet", action="store_true", help="Text report only (zero image tokens)")
    ap.add_argument("--draft", action="store_true", help="Draft render (no loudnorm): don't flag loudness")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"not found: {args.video}")
    edl = json.loads(args.edl.read_text(encoding="utf-8")) if args.edl else None
    dur = duration_of(args.video)
    issues: list[str] = []

    print(f"QC {args.video.name}  {dur:.2f}s")
    if edl:
        expected = sum(float(r["end"]) - float(r["start"]) for r in edl["ranges"])
        print(f"  length: EDL {expected:.2f}s, file {dur:.2f}s")
        if abs(expected - dur) > 0.5:
            issues.append(f"length off by {dur - expected:+.2f}s")

    m = measure(args.video)
    print(f"  loudness: {m['lufs']} LUFS (target -14), true peak {m['true_peak']} dBFS (max -1)")
    if m["lufs"] is not None and abs(m["lufs"] + 14) > 1.5 and not args.draft:
        issues.append(f"loudness {m['lufs']} LUFS")
    if m["true_peak"] is not None and m["true_peak"] > -0.5:
        issues.append(f"true peak {m['true_peak']} dBFS")
    for start, d in m["pauses"]:
        if 0.3 < start < dur - 1.0:
            issues.append(f"pause {d:.2f}s at {start:.2f}s")
    for a, b in m["blacks"]:
        issues.append(f"black frames {a:.2f}-{b:.2f}s")

    if not args.no_sheet:
        out = args.output or args.video.with_suffix(".qc.png")
        points = sample_points(edl, dur)
        contact_sheet(args.video, points, out)
        print(f"  sheet: {out}  ({len(points)} frames; labels: cutN- / cutN+ = just before / after cut N)")

    # delivery line: what Instagram cares about, in one line
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=codec_name,width,height,color_range,pix_fmt", "-of", "json", str(args.video)],
                                  capture_output=True, text=True).stdout or "{}").get("streams", [{}])[0]
    mb = args.video.stat().st_size / 1e6
    print(f"  delivery: {s.get('codec_name')} · {s.get('width')}x{s.get('height')} · color_range={s.get('color_range', '?')} · "
          f"{dur:.2f}s · {m['lufs']} LUFS · true peak {m['true_peak']} dB · {mb:.1f} MB")
    if not args.draft:
        if s.get("codec_name") != "h264":
            issues.append(f"codec {s.get('codec_name')} (Instagram wants h264)")
        if s.get("color_range") not in ("tv", None):
            issues.append(f"color_range {s.get('color_range')} (want tv / limited)")
    print("  issues: " + ("none" if not issues else ""))
    for i in issues:
        print(f"   - {i}")


if __name__ == "__main__":
    main()
