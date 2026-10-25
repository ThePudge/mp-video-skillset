"""High-quality person matte for a whole video with Robust Video Matting (RVM, ResNet50, Apache-2.0):
hair and hands stay clean and the edge is stable frame to frame (the model carries state between frames).
Use it when the matte must survive a close look — clones, cut-out windows on full-body wide shots —
where matte.py's 320 px u2net is too coarse.

  rvm_matte.py <video> -o <matte.mp4> [--ratio 0.25] [--start S --dur D] [--device auto|gpu|cpu]

Runs on the GPU through onnxruntime (CUDA or DirectML), else the CPU. The model (~107 MB) is
downloaded once to mp-studio/models/. --ratio = internal downsample (0.25 for 1080x1920 full body,
0.4 for close-ups). The matte keeps the input's size, frame rate and (for the chosen span) frame count;
white = person. Encoded near-lossless gray H.264.
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

MODEL = Path(__file__).resolve().parents[3] / "mp-studio" / "models" / "rvm_resnet50_fp32.onnx"
URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.onnx"


def probe(video: Path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True).stdout.strip().split(",")
    return int(out[0]), int(out[1]), out[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--ratio", type=float, default=0.25)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--device", default="auto", choices=["auto", "gpu", "cpu"])
    a = ap.parse_args()
    import onnxruntime as ort
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        print("downloading RVM model (~107 MB, once)…")
        urllib.request.urlretrieve(URL, MODEL)
    avail = ort.get_available_providers()
    prov = [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in avail and a.device != "cpu"]
    sess = ort.InferenceSession(str(MODEL), providers=prov + ["CPUExecutionProvider"])
    print(f"RVM on {sess.get_providers()[0]}")
    w, h, fps = probe(a.video)
    span = (["-ss", f"{a.start:.3f}"] if a.start else []) + (["-t", f"{a.dur:.3f}"] if a.dur else [])
    dec = subprocess.Popen(["ffmpeg", "-v", "error", *span, "-i", str(a.video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", fps,
                            "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "8", "-pix_fmt", "yuv420p", str(a.out)],
                           stdin=subprocess.PIPE)
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    ratio = np.array([a.ratio], np.float32)
    n, t0, size = 0, time.time(), w * h * 3
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        src = np.frombuffer(buf, np.uint8).reshape(h, w, 3).transpose(2, 0, 1)[None].astype(np.float32) / 255
        fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3],
                                         "downsample_ratio": ratio})
        enc.stdin.write((np.clip(pha[0, 0], 0, 1) * 255).astype(np.uint8).tobytes())
        n += 1
        if n % 150 == 0:
            print(f"  {n} frames, {n / (time.time() - t0):.1f} fps", flush=True)
    dec.wait()
    enc.stdin.close()
    enc.wait()
    print(f"matte: {a.out}  ({n} frames, {n / max(time.time() - t0, 1e-3):.1f} fps)")
    if n == 0:
        sys.exit("no frames decoded")


if __name__ == "__main__":
    main()
