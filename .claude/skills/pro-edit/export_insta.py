"""Instagram Reels export from a near-lossless master (finish.py --master): settings that survive Instagram's
own re-encode best (it re-encodes every upload; a low-bitrate file gives it little to work with).

  export_insta.py <master.mp4> -o <out.mp4> [--speed 1.1] [--srt in.srt --srt-out out.srt] [--mbps 12]

Video: 1080x1920 (scaled only if needed), 30 fps CFR, H.264 High@4.2, x264 slow, two-pass VBR (12 Mbps target,
16 Mbps peak, 24 Mbit buffer), 2 s closed GOP, bt709 limited range, +faststart.
Audio: AAC-LC 320 kb/s 48 kHz stereo, two-pass loudnorm to -14 LUFS / -1.5 dBTP (measured after any speed change).
--speed: plays the whole video faster with the pitch kept (atempo), e.g. 1.1 for a Trial Reel that is not the
same file as the main post; --srt rescales the subtitle times to match.
Upload the file itself from the phone's gallery (USB / AirDrop / Drive "download original"; not a messenger that
re-compresses), with Instagram → Settings → Data usage and media quality → "Upload at highest quality" on.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("master", type=Path)
ap.add_argument("-o", "--output", type=Path, required=True)
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--mbps", type=float, default=12.0)
ap.add_argument("--srt", type=Path)
ap.add_argument("--srt-out", type=Path)
a = ap.parse_args()

tmp = Path(os.environ.get("TEMP", ".")) / f"insta_{os.getpid()}"
sp = a.speed
vf = (f"setpts=PTS/{sp}," if sp != 1 else "") + ("scale=1080:1920:flags=lanczos:force_original_aspect_ratio=decrease,"
                                                  "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p")
tempo = f"atempo={sp}," if sp != 1 else ""
LN = "loudnorm=I=-14:TP=-1.5:LRA=11"

# loudness measured on the final (sped-up) audio
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(a.master), "-vn", "-af", f"{tempo}{LN}:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True)
m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
af = (f"{tempo}{LN}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
      f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")

b = a.mbps
x264 = ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-level:v", "4.2", "-b:v", f"{b}M",
        "-maxrate", f"{b * 4 / 3:.0f}M", "-bufsize", f"{b * 2:.0f}M", "-g", "60", "-keyint_min", "30", "-flags", "+cgop",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-passlogfile", str(tmp)]
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(a.master), "-vf", vf, *x264,
                "-pass", "1", "-an", "-f", "null", "NUL" if os.name == "nt" else "/dev/null"], check=True)
a.output.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(a.master), "-vf", vf, *x264, "-pass", "2",
                "-af", af, "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(a.output)],
               check=True)
for f in tmp.parent.glob(tmp.name + "*"):
    f.unlink(missing_ok=True)

if a.srt and a.srt_out:  # subtitle times follow the speed change
    def t2s(t):
        h, mi, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000

    def s2t(x):
        ms = round(x * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    txt = a.srt.read_text(encoding="utf-8")
    txt = re.sub(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)",
                 lambda mm: f"{s2t(t2s(mm.group(1)) / sp)} --> {s2t(t2s(mm.group(2)) / sp)}", txt)
    a.srt_out.write_text(txt, encoding="utf-8")

info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=codec_name,profile,width,height,r_frame_rate",
                       "-of", "compact=p=0:nk=1", str(a.output)], capture_output=True, text=True).stdout.split()
print(f"{a.output.name}: speed {sp}x · " + " | ".join(info))
