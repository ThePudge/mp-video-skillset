"""Voice note -> full motion video: the two mechanical steps around the normal pro-edit pipeline.

  voice.py prep <voice file> <edit_dir>        voice (.ogg/.opus/.m4a/.mp3/.wav/... or a video) -> <edit_dir>/voice.mp4
  voice.py mux <motion.mp4> <edit_dir>         motion graphics + the cut voice -> <edit_dir>/motion_base.mp4

prep wraps the voice in a black 1080x1920 30 fps carrier video, so transcription, the EDL cut
(fillers, pauses, retakes), captions.py and render.py work on it unchanged (source key "voice").
After the cut is rendered (`render.py ... --preview --no-subtitles --no-loudnorm` → base_preview.mp4),
build the graphics with kit.py on that timeline, then mux, then finish.py with
"base": "motion_base.mp4" (captions, music, SFX, voice clean-up, -14 LUFS).
"""
import subprocess
import sys
from pathlib import Path


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-1500:])


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout
    return float(out.strip())


if len(sys.argv) != 4 or sys.argv[1] not in ("prep", "mux"):
    sys.exit(__doc__)
cmd, src, edit = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
edit.mkdir(parents=True, exist_ok=True)

if cmd == "prep":
    out = edit / "voice.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30", "-i", str(src),
         "-map", "0:v", "-map", "1:a:0", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)])
    print(f"{out}  ({duration(out):.1f}s). Transcribe it, cut it with an EDL (source key \"voice\"), "
          f"render --preview --no-subtitles --no-loudnorm")
else:
    base = edit / "base_preview.mp4"
    if not base.exists():
        base = edit / "base.mp4"
    if not base.exists():
        sys.exit(f"no base_preview.mp4/base.mp4 in {edit}: render the voice cut first")
    vd, ad = duration(src), duration(base)
    if vd < ad - 0.1:
        print(f"warning: graphics {vd:.2f}s end before the voice ({ad:.2f}s); set the spec \"duration\" >= the voice")
    out = edit / "motion_base.mp4"
    # The graphics may run past the voice (a 2-3 s end card): pad the voice with silence to match
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-i", str(base), "-map", "0:v", "-map", "1:a",
         "-af", "apad", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{vd:.3f}", str(out)])
    print(f"{out}  ({vd:.2f}s, voice {ad:.2f}s): fx.json \"base\": \"motion_base.mp4\", then finish.py")
