"""Which FFmpeg and video encoder to use on this computer — a hardware encoder when one works, else the CPU.

  from hw import FFMPEG, venc        # FFMPEG = path of an ffmpeg whose hardware encoder works (or "ffmpeg")
  [*venc("draft" | "preview" | "inter" | "final")]   # -c:v … args

Order: NVIDIA NVENC → Intel Quick Sync (QSV) → x264 on all CPU threads. Each run re-checks the encoder with a
0.2 s test (a GPU driver can be updated, reset or switched off between runs), so nothing breaks mid-edit.
NVENC needs a recent enough NVIDIA driver for the FFmpeg build: the newest builds may refuse an older driver,
while a portable build in mp-studio/bin/<build>/bin/ffmpeg.exe (e.g. BtbN 8.1) still works.
"inter" = intermediates that get re-encoded later (cut segments, base.mp4): hardware, near-lossless.
"final" = the delivered file: x264 (best quality per MB); MP_FINAL_GPU=1 → hardware.
MP_FFMPEG=<path> forces a build; MP_NO_GPU=1 forces the CPU.
python hw.py prints what was picked.
"""
import os
import subprocess
from pathlib import Path

BIN = Path(__file__).resolve().parents[3] / "mp-studio" / "bin"


def _ok(exe: str, codec: str) -> bool:
    try:
        r = subprocess.run([exe, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=256x256:d=0.2", "-vf", "format=nv12",
                            "-c:v", codec, "-f", "null", "-"], capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _pick() -> tuple:
    if os.environ.get("MP_NO_GPU"):
        return "ffmpeg", None
    cands = [os.environ["MP_FFMPEG"]] if os.environ.get("MP_FFMPEG") else \
        ["ffmpeg"] + [str(p) for p in sorted(BIN.glob("*/bin/ffmpeg.exe"), reverse=True)]
    for codec in ("h264_nvenc", "h264_qsv"):
        for exe in cands:
            if _ok(exe, codec):
                return exe, codec
    return "ffmpeg", None


FFMPEG, HW = _pick()
NVENC = HW == "h264_nvenc"


def venc(kind: str = "preview") -> list:
    if HW and (kind != "final" or os.environ.get("MP_FINAL_GPU")):
        if HW == "h264_nvenc":
            q = {"draft": ("p1", "30"), "preview": ("p5", "23"), "inter": ("p6", "17"), "final": ("p7", "19")}[kind]
            return ["-c:v", "h264_nvenc", "-preset", q[0], "-tune", "hq", "-rc", "vbr", "-cq", q[1], "-b:v", "0",
                    "-spatial-aq", "1", "-pix_fmt", "yuv420p"]
        q = {"draft": ("veryfast", "30"), "preview": ("faster", "23"), "inter": ("medium", "17"), "final": ("slow", "19")}[kind]
        return ["-c:v", "h264_qsv", "-preset", q[0], "-global_quality", q[1], "-pix_fmt", "nv12"]
    x = {"draft": ("ultrafast", "28"), "preview": ("veryfast", "23"), "inter": ("fast", "18"), "final": ("medium", "18")}[kind]
    return ["-c:v", "libx264", "-preset", x[0], "-crf", x[1], "-threads", "0", "-pix_fmt", "yuv420p"]


if __name__ == "__main__":
    print(f"ffmpeg: {FFMPEG}\nhardware encoder: {HW or 'none (CPU x264)'}\n"
          f"preview: {' '.join(venc('preview'))}\nfinal:   {' '.join(venc('final'))}")
