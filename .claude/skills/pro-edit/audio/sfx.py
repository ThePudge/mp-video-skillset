"""Synthesized sound effects (no downloads, no licences). 48 kHz stereo WAV.

  sfx.py <out_dir>            writes the whole kit
  sfx.py <out_dir> whoosh pop writes only those

Kit: whoosh (zoom/transition), whoosh_short (punch-in), riser (build into a reveal, 2 s),
impact (hit on a reveal), pop (card/keyword in), click (UI tap), ding (comment/notification),
glitch (RGB-split moment), swipe_up (CTA slide).
Place them in the EDL "sfx" list (see sfx_mix.py); keep them -14..-22 dB under the voice.
"""
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def t(d):
    return np.arange(int(SR * d)) / SR


def env(n, attack, release, curve=2.0):
    """Attack/release envelope over n samples (fractions of length)."""
    x = np.linspace(0, 1, n)
    a = np.clip(x / max(attack, 1e-4), 0, 1)
    r = np.clip((1 - x) / max(release, 1e-4), 0, 1)
    return (a * r) ** curve


def swept_noise(d, f0, f1, q=0.35):
    """Noise whose band glides f0 → f1 (FFT-domain mask per 20 ms frame, overlap-add)."""
    n = int(SR * d)
    noise = rng.standard_normal(n + 2048)
    hop, win = 480, 1920
    w = np.hanning(win)
    out = np.zeros(n + win)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    for i, start in enumerate(range(0, n, hop)):
        frac = start / max(n - 1, 1)
        fc = f0 * (f1 / f0) ** frac
        spec = np.fft.rfft(noise[start:start + win] * w)
        mask = np.exp(-0.5 * (np.log(np.maximum(freqs, 1) / fc) / q) ** 2)
        out[start:start + win] += np.fft.irfft(spec * mask) * w
    out = out[:n]
    return out / (np.abs(out).max() + 1e-9)


def tone(d, f0, f1=None, shape="sine"):
    f1 = f1 or f0
    tt = t(d)
    f = f0 * (f1 / f0) ** (tt / d)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) if shape == "sine" else 2 * ((ph / (2 * np.pi)) % 1) - 1


def stereo(x, width=0.0):
    if width:
        d = int(SR * 0.012 * width)
        return np.stack([x, np.concatenate([np.zeros(d), x[:-d or None]])], 1)
    return np.stack([x, x], 1)


KIT = {
    "whoosh": lambda: stereo(swept_noise(0.55, 300, 4500) * env(int(SR * .55), .55, .45, 1.6), 0.6),
    "whoosh_short": lambda: stereo(swept_noise(0.28, 600, 6000) * env(int(SR * .28), .4, .6, 1.4), 0.4),
    "riser": lambda: stereo(0.6 * swept_noise(2.0, 200, 7000, 0.5) * env(int(SR * 2), .97, .03, 2.5)
                            + 0.25 * tone(2.0, 180, 900, "saw") * env(int(SR * 2), .97, .03, 3), 0.8),
    "impact": lambda: stereo(0.9 * tone(0.9, 70, 38) * env(int(SR * .9), .005, .99, 3)
                             + 0.4 * swept_noise(0.9, 2500, 120, 0.8) * env(int(SR * .9), .002, .99, 6)),
    "pop": lambda: stereo(tone(0.09, 950, 280) * env(int(SR * .09), .03, .97, 2)),
    "click": lambda: stereo(0.7 * tone(0.025, 2600) * env(int(SR * .025), .02, .98, 3)
                            + 0.3 * rng.standard_normal(int(SR * .025)) * env(int(SR * .025), .01, .99, 8)),
    "ding": lambda: stereo((tone(0.7, 1320) + 0.5 * tone(0.7, 1980) + 0.25 * tone(0.7, 2640))
                           * env(int(SR * .7), .004, .996, 2.2) / 1.75, 0.3),
    "glitch": lambda: stereo(np.round(rng.standard_normal(int(SR * .16)) * 4) / 4
                             * np.repeat(rng.integers(0, 2, 16), int(SR * .16) // 16 + 1)[:int(SR * .16)] * 0.6),
    "swipe_up": lambda: stereo(swept_noise(0.35, 800, 9000, 0.3) * env(int(SR * .35), .3, .7, 1.5), 0.5),
}


def write(path, x, peak_db=-3.0):
    x = x / (np.abs(x).max() + 1e-9) * 10 ** (peak_db / 20)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[2:] or KIT:
        write(out / f"{name}.wav", KIT[name]())
    print(f"sfx → {out}: {', '.join(sys.argv[2:] or KIT)}")
