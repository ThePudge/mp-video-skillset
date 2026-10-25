"""Quarter-second check before showing anything: every 0.25 s of the edit, flag
  - captions or graphics in Instagram's hidden zones (top 210 px, right edge below halfway, bottom 400 px)
  - a caption touching a graphic
  - graphics cut off at the frame edge
  - stretches where nothing moves (≥ 2 s)

  safezone.py <final.mp4> [--ass <edit>/master.ass --fonts-dir <fonts>] [--base <video without graphics>] [--sheet]

Captions come from the .ass itself (rendered alone, so they are exact). Graphics = final minus --base
(e.g. base_preview.mp4 for an edit with overlays, motion_base.mp4 is NOT a base — it already has the
graphics); without --base only captions, edges-of-captions and stillness are checked. Use --base only
when no animated zoom was applied after it (zooms move every pixel). Ends with
"N frames checked, M flags"; --sheet writes <final>.zones.png with the flagged frames and the zones drawn.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FPS, SW = 4, 270  # sample rate; analysis width (height follows the aspect)


def frames(src, w, h, vf_extra=""):
    vf = f"fps={FPS},scale={w}:{h}" + (f",{vf_extra}" if vf_extra else "")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def caption_frames(ass, fonts, W, H, dur, w, h):
    fd = f":fontsdir='{Path(fonts).resolve().as_posix().replace(':', chr(92) + ':')}'" if fonts else ""
    a = Path(ass).resolve().as_posix().replace(":", "\\:")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}:d={dur:.3f}",
                          "-vf", f"subtitles='{a}'{fd},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w) > 40


def dilate(m, r=2):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--ass", type=Path)
    ap.add_argument("--fonts-dir", type=Path)
    ap.add_argument("--base", type=Path)
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                           "-of", "csv=p=0:s=,", str(a.video)], capture_output=True, text=True).stdout.split()
    W, H = map(int, info[0].split(",")[:2])
    dur = float(info[1]) if len(info) > 1 else float(info[0].split(",")[-1])
    w, h = SW, round(SW * H / W / 2) * 2
    k = w / W
    fin = frames(a.video, w, h)
    n = len(fin)
    zones = np.zeros((h, w), bool)
    zones[: round(210 * k * W / 1080)] = True                       # top 210 px (at 1080 wide)
    zones[h - round(400 * k * W / 1080):] = True                     # bottom 400 px
    zones[h // 2:, w - round(110 * k * W / 1080):] = True            # right edge below halfway (like/comment/share)
    cap = caption_frames(a.ass, a.fonts_dir, W, H, dur, w, h)[:n] if a.ass else np.zeros((n, h, w), bool)
    if len(cap) < n:
        cap = np.concatenate([cap, np.zeros((n - len(cap), h, w), bool)])
    gfx = None
    if a.base:
        base = frames(a.base, w, h)[:n]
        m = min(len(base), n)
        diff = np.abs(fin[:m].astype(np.int16) - base[:m].astype(np.int16)).max(-1) > 34
        gfx = diff & ~dilate(cap[:m], 3)
    flags = []
    border = np.zeros((h, w), bool)
    border[:2], border[-2:], border[:, :2], border[:, -2:] = True, True, True, True
    for i in range(n):
        t = i / FPS
        c = cap[i]
        if (c & zones).sum() > 6:
            flags.append((t, "caption in a hidden zone"))
        if gfx is not None and i < len(gfx):
            g = gfx[i]
            if (g & zones).sum() > 0.004 * zones.sum() and g.sum() < 0.8 * g.size:
                flags.append((t, "graphic in a hidden zone"))
            if (c & dilate(g, 2)).sum() > 8:
                flags.append((t, "caption touches a graphic"))
            if (g & border).sum() > 0.05 * border.sum() and g.sum() < 0.8 * g.size:
                flags.append((t, "graphic cut off at the frame edge"))
    # stillness: mean frame change below a whisper for ≥ 2 s
    motion = np.abs(np.diff(fin.astype(np.int16), axis=0)).mean(axis=(1, 2, 3))
    run = 0
    for i, mv in enumerate(motion, 1):
        run = run + 1 if mv < 0.6 else 0
        if run == 2 * FPS:
            flags.append(((i - run) / FPS, f"nothing moves for ≥ 2 s"))
    flags.sort()
    # report, grouping the same issue on neighbouring frames
    groups = []
    for t, why in flags:
        if groups and groups[-1][2] == why and t - groups[-1][1] <= 0.5:
            groups[-1][1] = t
        else:
            groups.append([t, t, why])
    for t0, t1, why in groups:
        print(f"  {t0:6.2f}–{t1:6.2f}s  {why}")
    print(f"{n} frames checked, {len(groups)} flags")
    if a.sheet and groups:
        thumbs = []
        for t0, _, why in groups[:12]:
            im = Image.fromarray(fin[min(n - 1, int(t0 * FPS))]).convert("RGBA")
            ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ov.paste(Image.new("RGBA", im.size, (255, 0, 0, 70)), mask=Image.fromarray((zones * 255).astype(np.uint8)))
            im = Image.alpha_composite(im, ov).convert("RGB")
            ImageDraw.Draw(im).text((4, 4), f"{t0:.2f}s {why}", fill="yellow")
            thumbs.append(im)
        sheet = Image.new("RGB", (w * min(6, len(thumbs)), h * ((len(thumbs) + 5) // 6)))
        for j, im in enumerate(thumbs):
            sheet.paste(im, ((j % 6) * w, (j // 6) * h))
        out = a.video.with_suffix(".zones.png")
        sheet.save(out)
        print(f"sheet: {out}")
    sys.exit(1 if groups else 0)


if __name__ == "__main__":
    main()
