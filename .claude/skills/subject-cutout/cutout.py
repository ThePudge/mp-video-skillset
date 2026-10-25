"""Cut the person out of a video segment and build overlay layers for render.py.

Runs `npx hyperframes remove-background` (u2net_human_seg, local, no upload) and
writes, into one folder:

  subject.mov     the person with alpha (ProRes 4444), the TOP overlay
  plate.mov       (--plate) the surroundings with a person-shaped hole
  background.mp4  (--dim / --blur / --bg) an opaque background layer, the BOTTOM overlay
  overlays.json   the overlay entries for edl.json, in stacking order

EDL mode reads the already-rendered segment, so the cutout matches the grade,
scale and frame timing of the base video exactly:

  cutout.py --edl work/<project>/edit/edl.json --segment 3 --dim 0.4 --blur 8

Standalone mode takes any video (start_in_output is then 0; set it yourself):

  cutout.py some_clip.mp4 -o work/<project>/edit/cutouts/intro --bg assets/bg.jpg
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], env: dict | None = None) -> None:
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        sys.exit(f"command failed: {' '.join(cmd[:4])} ...\n{(proc.stderr or proc.stdout)[-1500:]}")


def probe(video: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration",
            "-of", "json", str(video),
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    s = data["streams"][0]
    return {
        "width": int(s["width"]),
        "height": int(s["height"]),
        "rate": s["r_frame_rate"],
        "frames": int(s["nb_frames"]) if s.get("nb_frames", "N/A").isdigit() else None,
        "duration": float(data["format"]["duration"]),
    }


def find_segment(clips_dir: Path, index: int) -> Path:
    hits = sorted(clips_dir.glob(f"seg_{index:02d}_*.mp4"))
    if not hits:
        sys.exit(
            f"no seg_{index:02d}_*.mp4 in {clips_dir}. Render the EDL first "
            f"(clips_graded = final render, clips_preview = --preview)."
        )
    return hits[0]


def segment_and_offset(edl_path: Path, index: int, clips: str) -> tuple[Path, float]:
    """The rendered segment file and where it starts in the output timeline.

    The offset sums the real durations of the earlier segment files, not the EDL
    ranges: concat uses the encoded durations, which are rounded to whole frames.
    """
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    n_ranges = len(edl["ranges"])
    if not 0 <= index < n_ranges:
        sys.exit(f"--segment must be 0..{n_ranges - 1}")
    clips_dir = edl_path.parent / clips
    if clips == "clips_draft":
        print("warning: draft clips are 720p; the final render is 1080p, so the cutout will not line up")
    offset = sum(probe(find_segment(clips_dir, i))["duration"] for i in range(index))
    return find_segment(clips_dir, index), offset


def build_background(src: Path, info: dict, out: Path, dim: float, blur: float, bg: Path | None) -> None:
    """Opaque bottom layer: the segment itself (or a replacement) dimmed and/or blurred."""
    w, h, dur = info["width"], info["height"], info["duration"]
    vf: list[str] = []
    if bg is None:
        inputs = ["-i", str(src)]
    else:
        # Images loop for the whole duration, videos loop if shorter
        is_image = bg.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        inputs = (["-loop", "1"] if is_image else ["-stream_loop", "-1"]) + ["-i", str(bg)]
        vf.append(f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1")
    if blur > 0:
        vf.append(f"gblur=sigma={blur}")
    if dim > 0:
        k = 1 - dim
        vf.append(f"colorchannelmixer=rr={k}:gg={k}:bb={k}")
    vf.append("format=yuv420p")
    run([
        "ffmpeg", "-y", *inputs, "-t", f"{dur:.3f}", "-vf", ",".join(vf),
        "-r", info["rate"], "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        str(out),
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description="Cut the person out of a segment for text-behind / background effects")
    ap.add_argument("video", nargs="?", type=Path, help="Any video (standalone mode)")
    ap.add_argument("--edl", type=Path, help="edl.json (EDL mode, with --segment)")
    ap.add_argument("--segment", type=int, help="Range index in the EDL (0-based)")
    ap.add_argument("--clips", default="clips_graded", choices=["clips_graded", "clips_preview", "clips_draft"],
                    help="Which rendered segment folder to read (default: clips_graded)")
    ap.add_argument("-o", "--out-dir", type=Path, help="Output folder (EDL mode default: <edit>/cutouts/seg_NN)")
    ap.add_argument("--plate", action="store_true", help="Also write plate.mov (surroundings with a hole)")
    ap.add_argument("--dim", type=float, default=0.0, help="Darken the background layer, 0..1 (e.g. 0.4)")
    ap.add_argument("--blur", type=float, default=0.0, help="Blur the background layer, gaussian sigma (e.g. 8)")
    ap.add_argument("--bg", type=Path, help="Replace the background with this image or video")
    ap.add_argument("--quality", default="best", choices=["fast", "balanced", "best"],
                    help="Cutout colour match over its own source (default: best)")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "coreml"])
    args = ap.parse_args()

    if args.edl:
        if args.segment is None:
            sys.exit("--edl needs --segment")
        src, offset = segment_and_offset(args.edl.resolve(), args.segment, args.clips)
        out_dir = args.out_dir or args.edl.parent / "cutouts" / f"seg_{args.segment:02d}"
    elif args.video:
        if not args.out_dir:
            sys.exit("standalone mode needs -o OUT_DIR")
        src, offset, out_dir = args.video, 0.0, args.out_dir
    else:
        ap.error("give a VIDEO, or --edl with --segment")
    if not 0 <= args.dim < 1:
        sys.exit("--dim must be between 0 and 1")

    npx = shutil.which("npx")
    if not npx:
        sys.exit("Node.js (npx) not found. Run setup.bat, then open a new terminal / Claude session.")

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    print(f"source: {src.name}  {info['width']}x{info['height']} @ {info['rate']}  {info['duration']:.2f}s"
          f"  → starts at {offset:.3f}s in the output")

    env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1"}
    subject = out_dir / "subject.mov"
    cmd = [npx, "--yes", "hyperframes", "remove-background", str(src.resolve()), "-o", str(subject),
           "--quality", args.quality, "--device", args.device]
    if args.plate:
        cmd += ["--background-output", str(out_dir / "plate.mov")]
    print("cutting out the person (first run downloads a ~170 MB model)...")
    run(cmd, env=env)

    got = probe(subject)
    if info["frames"] and got["frames"] and info["frames"] != got["frames"]:
        print(f"warning: cutout has {got['frames']} frames, source has {info['frames']}; check alignment at the end")

    layers: list[dict] = []
    if args.dim or args.blur or args.bg:
        background = out_dir / "background.mp4"
        build_background(src, info, background, args.dim, args.blur, args.bg)
        layers.append({"file": str(background), "role": "background"})
    if args.plate:
        layers.append({"file": str(out_dir / "plate.mov"), "role": "plate"})
    layers.append({"file": str(subject), "role": "subject (keep last, above your text/animation)"})

    overlays = [
        {"file": l["file"], "start_in_output": round(offset, 3), "duration": round(info["duration"], 3), "note": l["role"]}
        for l in layers
    ]
    (out_dir / "overlays.json").write_text(json.dumps(overlays, indent=2), encoding="utf-8")
    print(f"\nwrote {out_dir}")
    for o in overlays:
        print(f"  {Path(o['file']).name:16} start_in_output={o['start_in_output']}  duration={o['duration']}  ({o['note']})")
    print("Add these to edl.json \"overlays\" in this order; put any text/animation overlay just before subject.mov.")


if __name__ == "__main__":
    main()
