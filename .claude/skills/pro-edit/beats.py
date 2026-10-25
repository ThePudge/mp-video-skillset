"""Beat map for music, so big moves land on downbeats.

  beats.py <music or video> [--offset S] [--json out.json]

Prints BPM, beat times and downbeats (every 4th beat, phase = the strongest of the first 4).
--offset shifts all times (where the music starts on the output timeline).
Use: hero reveal / biggest scale-up on a downbeat; smaller accents (pills, counters, punch-ins)
on beats in between; cuts may land a few frames before a beat.
"""
import argparse
import json
import subprocess
from pathlib import Path

import librosa
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("audio", type=Path)
ap.add_argument("--offset", type=float, default=0.0)
ap.add_argument("--json", type=Path)
a = ap.parse_args()

sr = 22050
# librosa only reads wav/flac itself; ffmpeg decodes anything (mp3, m4a, video) to raw PCM
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a.audio), "-vn", "-ac", "1", "-ar", str(sr),
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout
y = np.frombuffer(pcm, dtype=np.float32)
onset = librosa.onset.onset_strength(y=y, sr=sr)
tempo, frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr)
times = librosa.frames_to_time(frames, sr=sr)
strength = onset[frames] if len(frames) else np.array([])
phase = int(np.argmax([strength[i::4].mean() for i in range(min(4, len(strength)))])) if len(strength) >= 4 else 0
down = times[phase::4]

off = a.offset
r = lambda xs: [round(float(t) + off, 2) for t in xs]
bpm = float(np.atleast_1d(tempo)[0])
print(f"{a.audio.name}: {bpm:.0f} BPM, {len(times)} beats, {len(down)} downbeats")
print("downbeats:", r(down)[:40])
print("beats:", r(times)[:80])
if a.json:
    a.json.write_text(json.dumps({"bpm": round(bpm, 1), "beats": r(times), "downbeats": r(down)}, indent=1))
