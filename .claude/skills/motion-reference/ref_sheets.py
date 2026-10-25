"""Cheap looks at a reference video, for learning its motion style.

  ref_sheets.py <video> --out <dir>                      overview: facts + cut times + one sheet (<= 30 thumbs)
  ref_sheets.py <video> --out <dir> --strip 12.4 1.2     one animation: 1.2 s from 12.4 s at 12 fps in one image
  ref_sheets.py <video> --out <dir> --strip 12.4 1.2 --fps 24
  ref_sheets.py <video> --out <dir> --hook --language fa  hook microscope: 0-10 s at 2 fps + the words under each frame
  ref_sheets.py https://www.instagram.com/reel/... --out <dir>   a link is downloaded first (yt-dlp, 720p)

Overview text tells pacing (shots, cuts/min, shot lengths); the sheet shows where graphics appear.
Strips show how one graphic enters/leaves frame by frame, labelled in ms, to copy its timing/easing.
The hook microscope (idea from taoufik123-collab/claude-watch, MIT) shows what is on screen while
each word of the first 10 s is spoken; words come from local Whisper, nothing is uploaded.
"""
import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

HOOK_SECONDS, HOOK_FPS = 10.0, 2.0

ap = argparse.ArgumentParser()
ap.add_argument("video", help="Video file or http(s) link")
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--strip", nargs=2, type=float, metavar=("START", "SPAN"))
ap.add_argument("--hook", action="store_true", help="Hook microscope over the first 10 s")
ap.add_argument("--language", help="Speech language for the hook words (fa, en, ...)")
ap.add_argument("--fps", type=float, default=12)
ap.add_argument("--thumbs", type=int, default=30)
ap.add_argument("--scene", type=float, default=0.2, help="cut threshold; raise if graphics count as cuts")
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)


def download(url: str) -> Path:
    """yt-dlp a public link into the out dir (720p is plenty for style study)."""
    dest = a.out / "source.%(ext)s"
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-playlist", "--no-warnings",
                        "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b", "--merge-output-format", "mp4",
                        "-o", str(dest), "--", url], capture_output=True, text=True, encoding="utf-8", errors="replace")
    got = next(iter(sorted(a.out.glob("source.mp4"))), None) or next(iter(sorted(a.out.glob("source.*"))), None)
    if "No module named yt_dlp" in r.stderr:
        sys.exit("yt-dlp is not installed yet: run setup.bat once, then try the link again.")
    if r.returncode or got is None:
        sys.exit(f"download failed (private or login-only posts can't be fetched; save the video and pass the file):\n"
                 f"{(r.stderr or r.stdout)[-800:]}")
    print(f"downloaded: {got}")
    return got


if urlparse(a.video).scheme in ("http", "https"):
    existing = next(iter(sorted(a.out.glob("source.mp4"))), None)
    a.video = existing or download(a.video)
else:
    a.video = Path(a.video)
stem = a.video.stem

info = json.loads(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation",
     "-of", "json", str(a.video)], capture_output=True, text=True, encoding="utf-8").stdout)
dur = float(info["format"]["duration"])
v = next(s for s in info["streams"] if s.get("codec_type") == "video")
w, h = v["width"], v["height"]
if any(abs(sd.get("rotation", 0)) == 90 for sd in v.get("side_data_list", [])):
    w, h = h, w


def grab(times, size):
    """Frames at the given times, scaled to `size` wide."""
    tmp = Path(tempfile.mkdtemp())
    frames = []
    for i, t in enumerate(times):
        p = tmp / f"{i:04}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(a.video), "-frames:v", "1",
                        "-vf", f"scale={size}:-2", "-q:v", "4", str(p)], check=True)
        if p.exists():
            frames.append((t, Image.open(p).convert("RGB")))
    shutil.rmtree(tmp, ignore_errors=True)
    return frames


def sheet(frames, cols, label, path):
    tw, th = frames[0][1].size
    rows = -(-len(frames) // cols)
    img = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=max(14, tw // 12))
    except TypeError:
        font = ImageFont.load_default()
    for i, (t, f) in enumerate(frames):
        x, y = (i % cols) * tw, (i // cols) * th
        img.paste(f, (x, y))
        txt = label(i, t)
        d.rectangle([x, y, x + d.textlength(txt, font=font) + 6, y + font.size + 6], fill=(0, 0, 0))
        d.text((x + 3, y + 2), txt, fill=(255, 220, 0), font=font)
    img.save(path, quality=85)


def hook_words() -> list[dict]:
    """Word timings for the first 10 s, from local Whisper on a 10 s slice (cached in the out dir)."""
    clip = a.out / "hook_10s.mp4"
    tr = a.out / "transcripts" / "hook_10s.json"
    if not tr.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a.video), "-t", str(HOOK_SECONDS),
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(clip)], check=True)
        helper = Path(__file__).resolve().parents[1] / "video-use" / "helpers" / "transcribe.py"
        cmd = [sys.executable, str(helper), str(clip), "--edit-dir", str(a.out)]
        if a.language:
            cmd += ["--language", a.language]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    data = json.loads(tr.read_text(encoding="utf-8"))
    return [w for w in data.get("words", []) if w.get("type", "word") == "word"]


if a.hook:
    span = min(HOOK_SECONDS, dur)
    times = [i / HOOK_FPS for i in range(int(span * HOOK_FPS))]
    frames = grab(times, 160 if h > w else 240)
    path = a.out / f"{stem}.hook.jpg"
    sheet(frames, 10 if h > w else 5, lambda i, t: f"{t:.1f}s", path)
    words = hook_words()
    print(f"hook microscope: {path}  ({len(frames)} frames @ {HOOK_FPS:g} fps, 0-{span:.0f}s)")
    if words:
        print(f"first word at {words[0]['start']:.2f}s")
    for t in times:
        said = " ".join(w["text"].strip() for w in words if t <= w["start"] < t + 1 / HOOK_FPS)
        print(f"  {t:4.1f}s | {said}")
elif a.strip:
    start, span = a.strip
    n = max(2, min(36, round(span * a.fps)))
    times = [start + i / a.fps for i in range(n)]
    frames = grab(times, 240 if h > w else 320)
    path = a.out / f"{stem}.strip_{start:06.2f}.jpg"
    sheet(frames, 6 if h > w else 4, lambda i, t: f"+{round((t - start) * 1000)}ms", path)
    print(f"strip: {path}  ({len(frames)} frames @ {a.fps:g} fps from {start:.2f}s; labels = ms after start)")
else:
    # scene cuts (text only): pacing without looking at pixels
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(a.video), "-vf", f"select='gt(scene,{a.scene})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    cuts = [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    shots = len(cuts) + 1
    n = min(a.thumbs, max(6, int(dur)))
    times = [dur * (i + 0.5) / n for i in range(n)]
    frames = grab(times, 180 if h > w else 240)
    path = a.out / f"{stem}.overview.jpg"
    sheet(frames, 10 if h > w else 6, lambda i, t: f"{t:.1f}s", path)
    print(f"{stem}: {dur:.1f}s {w}x{h} {v.get('r_frame_rate')}")
    lengths = [b - a_ for a_, b in zip([0.0] + cuts, cuts + [dur])]
    print(f"shots: {shots}, {len(cuts) / (dur / 60):.1f} cuts/min, shot length avg {dur / shots:.1f}s / median "
          f"{statistics.median(lengths):.1f}s / shortest {min(lengths):.1f}s, first cut at "
          f"{cuts[0] if cuts else '-'}s")
    print(f"cuts at: {cuts[:60]}{' …' if len(cuts) > 60 else ''}")
    print(f"overview: {path}  ({len(frames)} thumbs, one every {dur / n:.1f}s)")
