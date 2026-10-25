"""Person matte for a whole video (white = person), on the fastest device this computer has.

  matte.py <video> -o <matte.mp4> [--device auto|cpu|gpu] [--start N]

Uses the u2net_human_seg model that `npx hyperframes remove-background` downloads (Apache-2.0,
~/.cache/hyperframes/background-removal/models/). --device auto (default) times a few frames on every
runtime onnxruntime offers here — CUDA (NVIDIA), DirectML (any DirectX 12 GPU: Intel, AMD, NVIDIA), CPU —
picks the fastest and remembers it in ~/.cache/mp-studio/devices.json, so later runs start at once.
On the owner's laptop the Intel HD 620 (DirectML) did 0.59 s/frame vs 2.46 s on the CPU.
The matte keeps the video's size and frame count, so finish.py can use it directly:
  fx.json "matte": {"type": "video", "file": "matte/matte.mp4"}  (pop-out layout on any wall)
--start N skips the first N frames (resume: join the parts with ffmpeg concat).
No model yet, or no onnxruntime: falls back to `npx hyperframes remove-background` (CPU) + alpha extract.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

MODEL = Path.home() / ".cache" / "hyperframes" / "background-removal" / "models" / "u2net_human_seg.onnx"
CACHE = Path.home() / ".cache" / "mp-studio" / "devices.json"
S = 320  # model input size
ORDER = ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]
NAMES = {"CUDAExecutionProvider": "NVIDIA GPU (CUDA)", "DmlExecutionProvider": "GPU (DirectML)", "CPUExecutionProvider": "CPU"}


def probe(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    w, h, fps = r.stdout.strip().split(",")[:3]
    return int(w), int(h), fps


def frames(video, start=0, count=None):
    """Yields 320x320 RGB frames as bytes."""
    vf = (f"select=gte(n\\,{start})," if start else "") + f"scale={S}:{S}"
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf, "-fps_mode", "passthrough"]
    if count:
        cmd += ["-frames:v", str(count)]
    p = subprocess.Popen(cmd + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(S * S * 3)
        if len(b) < S * S * 3:
            break
        yield b
    p.stdout.close()
    p.wait()


def session(ort, prov):
    o = ort.SessionOptions()
    if prov == "CPUExecutionProvider":
        o.intra_op_num_threads = os.cpu_count() or 4
    if prov == "DmlExecutionProvider":  # DirectML wants these off
        o.enable_mem_pattern = False
        o.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(MODEL), sess_options=o, providers=[prov])


def make_infer(np, sess):
    name = sess.get_inputs()[0].name
    mean, std = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)

    def run(b):
        x = ((np.frombuffer(b, np.uint8).reshape(S, S, 3).astype(np.float32) / 255 - mean) / std).transpose(2, 0, 1)[None]
        m = sess.run(None, {name: x})[0][0, 0]
        m = (m - m.min()) / max(float(m.max() - m.min()), 1e-6)
        return (m * 255).astype(np.uint8).tobytes()
    return run


def pick(ort, np, video, want):
    avail = [p for p in ORDER if p in ort.get_available_providers()]
    if want == "cpu":
        return "CPUExecutionProvider", {}
    if want == "gpu":
        gpus = [p for p in avail if p != "CPUExecutionProvider"]
        if not gpus:
            print("no GPU runtime here (onnxruntime offers only the CPU); using the CPU")
        return (gpus or ["CPUExecutionProvider"])[0], {}
    key = f"{platform.node()}|{platform.processor()}|{ort.__version__}|{','.join(avail)}"
    try:
        c = json.loads(CACHE.read_text(encoding="utf-8")).get(key)
    except (OSError, ValueError):
        c = None
    if c and c["choice"] in avail:
        return c["choice"], c["s_per_frame"]
    if len(avail) == 1:
        return avail[0], {}
    sample = list(frames(video, start=0, count=7))
    speed = {}
    for p in avail:
        try:
            run = make_infer(np, session(ort, p))
            run(sample[0])  # warm-up (GPU kernels compile on the first frame)
            t = time.time()
            for b in sample[1:]:
                run(b)
            speed[p] = round((time.time() - t) / max(1, len(sample) - 1), 3)
        except Exception as e:  # noqa: BLE001 — a runtime that fails here is simply not used
            print(f"  {NAMES[p]}: not usable ({str(e).splitlines()[0][:80]})")
    choice = min(speed, key=speed.get)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        allc = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        allc = {}
    allc[key] = {"choice": choice, "s_per_frame": speed}
    CACHE.write_text(json.dumps(allc, indent=1), encoding="utf-8")
    return choice, speed


def fallback(video, out):
    """No model file or onnxruntime: the HyperFrames CLI (CPU), then its alpha channel as the matte."""
    tmp = out.with_suffix(".subject.webm")
    subprocess.run(["npx", "--yes", "hyperframes", "remove-background", str(video), "-o", str(tmp), "--quality", "fast"],
                   check=True, shell=os.name == "nt", env={**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1"})
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-i", str(tmp), "-vf", "alphaextract,format=gray",
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(out)], check=True)
    tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu"])
    ap.add_argument("--start", type=int, default=0)
    a = ap.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError:
        np = ort = None
    if ort is None or not MODEL.exists():
        print("matte: no onnxruntime or model yet → HyperFrames remove-background (CPU)")
        return fallback(a.video, a.output)
    W, H, fps = probe(a.video)
    prov, speed = pick(ort, np, a.video, a.device)
    print(f"matte: {NAMES[prov]}" + (f"  (s/frame: {', '.join(f'{NAMES[k]} {v}' for k, v in speed.items())})" if speed else ""))
    run = make_infer(np, session(ort, prov))
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{S}x{S}", "-r", fps,
                           "-i", "-", "-vf", f"scale={W}:{H}:flags=bicubic", "-c:v", "libx264", "-crf", "12",
                           "-pix_fmt", "yuv420p", str(a.output)], stdin=subprocess.PIPE)
    n, t = 0, time.time()
    for b in frames(a.video, start=a.start):
        wr.stdin.write(run(b))
        n += 1
        if n % 300 == 0:
            print(f"  {n} frames, {(time.time() - t) / n:.2f} s/frame", flush=True)
    wr.stdin.close()
    if wr.wait():
        sys.exit("matte: ffmpeg failed writing the matte")
    print(f"matte: {n} frames → {a.output} ({(time.time() - t) / max(n, 1):.2f} s/frame on {NAMES[prov]})")


if __name__ == "__main__":
    main()
