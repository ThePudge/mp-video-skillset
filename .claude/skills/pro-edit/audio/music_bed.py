"""Simple synthesized music bed (placeholder until the owner supplies a track). 48 kHz stereo WAV.

  music_bed.py <out.wav> --length 66 [--bpm 108] [--mood warm|drive] [--stop 60.5]

Warm lo-fi pad + sub bass + soft kick/hat in Am–F–C–G. --stop fades the music out by that time
(end it before the CTA). Basic by design: an owner track always wins; beats.py works on both.
"""
import argparse
import wave

import numpy as np

SR = 48000
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--length", type=float, required=True)
ap.add_argument("--bpm", type=float, default=108)
ap.add_argument("--mood", default="warm")
ap.add_argument("--stop", type=float)
a = ap.parse_args()

n = int(SR * a.length)
tt = np.arange(n) / SR
beat = 60 / a.bpm
bar = 4 * beat
rng = np.random.default_rng(3)

# Am F C G, root + triad (MIDI)
chords = [(45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62])]
hz = lambda m: 440 * 2 ** ((m - 69) / 12)

pad = np.zeros(n)
bass = np.zeros(n)
for i, start in enumerate(np.arange(0, a.length, bar)):
    root, notes = chords[i % 4]
    s, e = int(start * SR), min(n, int((start + bar) * SR))
    seg = tt[s:e] - start
    shape = np.minimum(1, seg / 0.4) * np.minimum(1, (bar - seg) / 0.3)
    for m in notes:
        for det in (-0.08, 0.08):  # two detuned voices per note
            ph = 2 * np.pi * hz(m + det) * seg
            pad[s:e] += (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)) * shape
    bass[s:e] += np.sin(2 * np.pi * hz(root - 12) * seg) * np.minimum(1, seg / 0.02) * np.exp(-seg * 0.6)

# low-pass the pad (FFT, gentle 1.8 kHz roll-off) for warmth
spec = np.fft.rfft(pad)
f = np.fft.rfftfreq(n, 1 / SR)
pad = np.fft.irfft(spec / (1 + (f / 1800) ** 4), n)

drums = np.zeros(n)
kick_len = int(SR * 0.35)
kt = np.arange(kick_len) / SR
kick = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 9)
hat = rng.standard_normal(int(SR * 0.05))
hat = np.diff(hat, prepend=0) * np.exp(-np.arange(hat.size) / SR * 90)
for k, bt in enumerate(np.arange(0, a.length, beat)):
    s = int(bt * SR)
    if k % 2 == 0 and s + kick_len < n:  # kick on 1 and 3
        drums[s:s + kick_len] += kick
    hs = int((bt + beat / 2) * SR)  # hat on the off-beats
    if hs + hat.size < n:
        drums[hs:hs + hat.size] += hat * (0.35 if a.mood == "warm" else 0.6)

mix = 0.45 * pad / (np.abs(pad).max() + 1e-9) + 0.35 * bass + 0.5 * drums * (0.6 if a.mood == "warm" else 1.0)
mix *= np.minimum(1, tt / 1.5)  # fade in
if a.stop:
    mix *= np.clip((a.stop - tt) / 1.5, 0, 1)  # out before the CTA
mix = mix / (np.abs(mix).max() + 1e-9) * 10 ** (-3 / 20)
st = np.stack([mix, np.concatenate([np.zeros(240), mix[:-240]])], 1)  # 5 ms Haas width
with wave.open(a.out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype("<i2").tobytes())
print(f"music bed → {a.out}: {a.length:.1f}s @ {a.bpm:g} BPM, {a.mood}" + (f", out by {a.stop}s" if a.stop else ""))
