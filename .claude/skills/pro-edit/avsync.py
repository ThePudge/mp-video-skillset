"""Lip-sync check against the RAW footage: for a short moment of every take in the edit, find where its raw
sound and its raw picture land in the edited video. If both land at the same time, picture and sound are in
sync for that take; the difference is the lip-sync error.

  avsync.py <edit_dir> <video> [--per-take 2] [--offset 0]

<video> = base.mp4 / preview / final (graphics are fine: the picture is compared on edges, in the speaker's
lower half). Raw takes are read from mp-studio/input/<project>/<source stem>.* (4K is fine). Times come from the
EDL with the same whole-frame rounding render.py uses. --offset: seconds the video starts later than the EDL
(e.g. an intro). Prints one line per sample and a verdict (|error| ≤ 1 frame = in sync).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H, SR = 108, 192, 16000


def frames(path, t0, n, vf=""):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t0, 0):.3f}", "-i", str(path), "-frames:v", str(n),
                        "-vf", f"{vf}scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W).astype(np.float32)


def audio(path, t0, dur):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t0, 0):.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                        "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32)


def edges(x):
    g = np.abs(np.diff(x, axis=1))[:-1, :] + np.abs(np.diff(x, axis=0))[:, :-1]
    g = g - g.mean()
    return g / (g.std() + 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("video", type=Path)
    ap.add_argument("--per-take", type=int, default=2)
    ap.add_argument("--offset", type=float, default=0.0)
    a = ap.parse_args()
    E = a.edit_dir.resolve()
    edl = json.loads((E / "edl.json").read_text(encoding="utf-8"))
    inp = E.parents[2] / "input" / E.parent.name
    fps = 30.0
    pos, picks, seen = 0.0, [], {}
    for r in edl["ranges"]:
        d = max(1, round((r["end"] - r["start"]) * fps)) / fps
        if d > 2.4 and seen.get(r["source"], 0) < a.per_take:
            seen[r["source"]] = seen.get(r["source"], 0) + 1
            picks.append((r, pos + d * 0.45 + a.offset, r["start"] + d * 0.45))
        pos += d
    errs = []
    for r, t_out, t_src in picks:
        raw = next((p for p in inp.glob(r["source"] + ".*") if p.is_file()), None)
        if raw is None:
            print(f"{r['source']}: raw file not found in {inp}")
            continue
        z, zy = float(r.get("zoom", 1.0)), float(r.get("zoom_y", 0.5))
        zc = "" if z == 1 else f"crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*{zy},"
        # picture: raw frame at t_src vs the edit's frames around t_out (lower half: the speaker, few graphics)
        f = edges(frames(raw, t_src, 1, zc)[0][90:185])
        cand = frames(a.video, t_out - 0.5, 31)
        sc = [(f * edges(c[90:185])).mean() for c in cand]
        lag_v = (int(np.argmax(sc)) - 15) / fps
        # sound: raw 1.2 s vs the edit's audio around t_out
        ra = audio(raw, t_src, 1.2)
        oa = audio(a.video, t_out - 0.5, 2.2)
        n = len(oa) + len(ra)
        xc = np.fft.irfft(np.fft.rfft(oa, n) * np.conj(np.fft.rfft(ra, n)), n)[: len(oa) - len(ra) + 1]
        lag_a = (int(np.argmax(xc)) / SR) - 0.5
        err = lag_v - lag_a
        sure = max(sc) >= 0.85  # below that the edit changed the picture there (zoom, shift, overlay): no verdict
        if sure:
            errs.append(err)
        print(f"{r['source'][-8:]}  edit {t_out:6.2f}s  picture {lag_v * 1000:+5.0f} ms  sound {lag_a * 1000:+5.0f} ms  "
              f"→ lip-sync error {err * 1000:+5.0f} ms  (picture match {max(sc):.2f}{'' if sure else ', skipped: picture changed here'})")
    # sample count vs picture length: the checks above seek by timestamps, but phones, Instagram and re-encoders
    # play audio samples in order; extra samples (e.g. AAC priming copied at every join) drift the voice late
    pk = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-count_packets", "-show_entries",
                         "stream=nb_read_packets,sample_rate", "-of", "csv=p=0", str(a.video)], capture_output=True, text=True).stdout.strip()
    vd = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0",
                               str(a.video)], capture_output=True, text=True).stdout or 0)
    extra = 0.0
    if pk and vd:
        sr, n = (int(x) for x in pk.split(","))
        extra = n * 1024 / sr - vd
        print(f"audio samples {n * 1024 / sr:.3f} s vs picture {vd:.3f} s → {extra * 1000:+.0f} ms "
              f"({'ok' if abs(extra) <= 0.1 else 'DRIFT on phones / after re-encode'})")
    if errs:
        worst = max(abs(e) for e in errs)
        ok = worst <= 1.5 / fps and abs(extra) <= 0.1
        print(f"worst error {worst * 1000:.0f} ms → {'IN SYNC (≤ 1 frame)' if ok else 'OUT OF SYNC'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
