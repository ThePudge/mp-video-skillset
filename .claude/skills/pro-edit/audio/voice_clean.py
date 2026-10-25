"""Voice cleaner: the basic sound fixes every talking-head video needs, all local.

  voice_clean.py <video-or-audio> -o <out.mp4|.m4a|.wav> [--preset clean] [options] [--start S --duration D]

Chain (in this order): high-pass (rumble) → de-hum (50/60 Hz + harmonics, auto-detected) → de-click
(mouth clicks) → noise reduction (learns the noise from the quietest half-second) → light gate between
words → EQ (mud cut, warmth, presence) → compressor → de-esser → limiter → two-pass loudness to --lufs.
A video keeps its picture (copied, not re-encoded); only the sound is replaced.

presets            denoise  deess  presence  warmth  compress  gate   use
  light              0.50    0.30     1.0      0.0     0.40    0.0    already clean mic, just polish
  clean (default)    0.75    0.50     2.0      1.0     0.60    0.3    normal room, lavalier / phone
  strong             0.95    0.50     2.5      0.5     0.70    0.6    noisy room, fan, AC, street
  podcast            0.70    0.60     2.0      2.5     0.85    0.3    close, warm, radio-like voice
Every value can be overridden: --denoise 0..1 --deess 0..1 --presence dB --warmth dB --compress 0..1
--gate 0..1 --dehum auto|50|60|off --lufs -16 (voice alone; the finished video is normalised to -14).

--start/--duration process only that window (a quick before/after preview); --report prints the
noise floor, loudness and peak before and after.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000
PRESETS = {
    "light": dict(denoise=0.50, deess=0.30, presence=1.0, warmth=0.0, compress=0.40, gate=0.0),
    "clean": dict(denoise=0.75, deess=0.50, presence=2.0, warmth=1.0, compress=0.60, gate=0.3),
    "strong": dict(denoise=0.95, deess=0.50, presence=2.5, warmth=0.5, compress=0.70, gate=0.6),
    "podcast": dict(denoise=0.70, deess=0.60, presence=2.0, warmth=2.5, compress=0.85, gate=0.3),
}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"ffmpeg failed: {(r.stderr or r.stdout)[-800:]}")
    return r


def decode(src: Path, start=None, dur=None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.3f}"] if start is not None else []) + ["-i", str(src)]
    cmd += (["-t", f"{dur:.3f}"] if dur else []) + ["-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    if not raw:
        sys.exit(f"no audio in {src}")
    return np.frombuffer(raw, np.float32).copy()


def frames_db(x, win=0.05):
    n = int(SR * win)
    k = len(x) // n
    rms = np.sqrt(np.mean(x[: k * n].reshape(k, n) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def noise_floor_db(x):
    """Level of the quietest 10% of 50 ms frames: the room / hiss between words."""
    return float(np.percentile(frames_db(x), 10))


def snr_db(x):
    """Speech-to-noise: loud speech frames (90th pct) above the room between words (10th pct)."""
    db = frames_db(x)
    return float(np.percentile(db, 90) - np.percentile(db, 10))


def quietest(x, length=0.5):
    """The quietest half-second (pure room noise) — what the denoiser learns from."""
    db = frames_db(x, 0.05)
    k = int(length / 0.05)
    if len(db) <= k:
        return x
    smooth = np.convolve(db, np.ones(k) / k, mode="valid")
    i = int(np.argmin(smooth)) * int(SR * 0.05)
    return x[i: i + int(SR * length)]


def detect_hum(x):
    """50 or 60 Hz mains hum, measured only in the quiet frames between words (a voice's own low notes
    must not count): a narrow peak at f0 AND at 2·f0 or 3·f0, well above the neighbouring bins."""
    n = int(SR * 0.05)
    k = len(x) // n
    fr = x[: k * n].reshape(k, n)
    db = 20 * np.log10(np.sqrt(np.mean(fr ** 2, axis=1)) + 1e-12)
    quiet = fr[db <= np.percentile(db, 25)].ravel()
    if len(quiet) < SR:
        return None
    seg = quiet[: SR * 20]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)

    def ratio(f):
        peak = spec[(freqs > f - 1) & (freqs < f + 1)].max(initial=0)
        side = np.median(spec[((freqs > f - 8) & (freqs < f - 3)) | ((freqs > f + 3) & (freqs < f + 8))])
        return 20 * np.log10((peak + 1e-9) / (side + 1e-9))
    best, score = None, 0.0
    for f0 in (50, 60):
        r0, rh = ratio(f0), max(ratio(2 * f0), ratio(3 * f0))
        if r0 > 12 and rh > 8 and r0 > score:
            best, score = f0, r0
    return best


def loudness(path: Path):
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None, float(p[-1]) if p else None)


def main():
    ap = argparse.ArgumentParser(description="Clean a voice recording (noise, hum, clicks, sibilance, level)")
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--preset", default="clean", choices=list(PRESETS))
    for k in ("denoise", "deess", "presence", "warmth", "compress", "gate"):
        ap.add_argument(f"--{k}", type=float)
    ap.add_argument("--dehum", default="auto", help="auto | 50 | 60 | off")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    p = {**PRESETS[a.preset], **{k: getattr(a, k) for k in PRESETS["clean"] if getattr(a, k) is not None}}

    tmp = Path(tempfile.mkdtemp())
    x = decode(a.src, a.start, a.duration)
    before_floor = noise_floor_db(x)

    # 1. high-pass, de-hum, de-click (ffmpeg)
    hum = {"off": None, "50": 50, "60": 60}.get(a.dehum, "auto")
    if hum == "auto":
        hum = detect_hum(x)
    pre = ["highpass=f=80:poles=2"]
    if hum:
        pre += [f"bandreject=f={hum * k}:width_type=q:w=30" for k in (1, 2, 3, 4)]
    pre.append("adeclick=w=55:o=75")
    sf.write(tmp / "in.wav", x, SR, subtype="FLOAT")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "in.wav"), "-af", ",".join(pre), "-c:a", "pcm_f32le", str(tmp / "pre.wav")])
    y, _ = sf.read(tmp / "pre.wav", dtype="float32")

    # 2. noise reduction, learned from the quietest moment
    if p["denoise"] > 0:
        import noisereduce as nr
        y = nr.reduce_noise(y=y, sr=SR, y_noise=quietest(y), stationary=False, prop_decrease=min(1.0, p["denoise"]),
                            n_std_thresh_stationary=1.5, time_mask_smooth_ms=60, freq_mask_smooth_hz=300).astype(np.float32)

    # 3. gate, EQ, compressor, limiter (pedalboard)
    from pedalboard import Compressor, Limiter, LowShelfFilter, NoiseGate, PeakFilter, Pedalboard
    chain = []
    if p["gate"] > 0:  # soft downward expansion between words, never a hard chop
        floor = noise_floor_db(y)
        chain.append(NoiseGate(threshold_db=floor + 6, ratio=1.5 + 2.5 * p["gate"], attack_ms=2, release_ms=180))
    chain += [PeakFilter(cutoff_frequency_hz=300, gain_db=-2.0, q=1.0)]                       # mud
    if p["warmth"]:
        chain.append(LowShelfFilter(cutoff_frequency_hz=160, gain_db=p["warmth"], q=0.7))
    if p["presence"]:
        chain.append(PeakFilter(cutoff_frequency_hz=4200, gain_db=p["presence"], q=0.9))     # clarity
    if p["compress"] > 0:
        chain.append(Compressor(threshold_db=-14 - 12 * p["compress"], ratio=1.5 + 3 * p["compress"], attack_ms=6, release_ms=120))
    chain.append(Limiter(threshold_db=-1.5, release_ms=80))
    y = Pedalboard(chain)(y, SR).astype(np.float32)
    sf.write(tmp / "eq.wav", y, SR, subtype="FLOAT")

    # 4. de-ess + two-pass loudness (ffmpeg)
    post = (f"deesser=i={min(1.0, p['deess']):.2f}:m=0.5:f=0.5:s=o," if p["deess"] > 0 else "")
    m = run(["ffmpeg", "-nostats", "-y", "-i", str(tmp / "eq.wav"), "-af",
             post + f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    js = json.loads(m[m.rindex("{"): m.rindex("}") + 1])
    ln = (f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "eq.wav"), "-af", post + ln + ",aresample=48000",
         "-ac", "2", "-c:a", "pcm_s16le", str(tmp / "clean.wav")])

    # 5. output: a video keeps its picture, audio files are written as asked
    out = a.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in VIDEO_EXT and a.src.suffix.lower() in VIDEO_EXT:
        vin = ["-ss", f"{a.start:.3f}"] if a.start is not None else []
        vin += ["-i", str(a.src)] + (["-t", f"{a.duration:.3f}"] if a.duration else [])
        run(["ffmpeg", "-v", "error", "-y", *vin, "-i", str(tmp / "clean.wav"), "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])
    elif out.suffix.lower() == ".wav":
        Path(tmp / "clean.wav").replace(out)
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "clean.wav"), "-c:a", "aac", "-b:a", "192k", str(out)])

    after = decode(out)
    print(f"voice ({a.preset}{', de-hum ' + str(hum) + ' Hz' if hum else ''}) → {out.name}")
    if a.report:
        sf.write(tmp / "before.wav", x, SR, subtype="FLOAT")
        bi, bp = loudness(tmp / "before.wav")
        ai, apk = loudness(out)
        print(f"  speech above room noise  {snr_db(x):5.1f} dB → {snr_db(after):5.1f} dB   (higher = cleaner)")
        print(f"  loudness     {bi} LUFS → {ai} LUFS   (target {a.lufs})")
        print(f"  true peak    {bp} dB → {apk} dB")
    print(json.dumps({"preset": a.preset, "hum": hum, "snr_before": round(snr_db(x), 1),
                      "snr_after": round(snr_db(after), 1), **{k: round(v, 2) for k, v in p.items()}}))


if __name__ == "__main__":
    main()
