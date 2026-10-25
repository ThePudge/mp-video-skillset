"""First cut from the AUDIO, not from Whisper's word times — plus a retake finder.

  cutplan.py <edit_dir> --source <key>=<video> [--pace tight|natural] [--language fa] [--write]

Why: Whisper (especially in Persian) stretches words over short pauses and can fold two or three
attempts at a line into one long "word", so pauses and false starts hide in the transcript.
This tool:
  1. measures the real silences (ffmpeg silencedetect, -32 dB) and proposes EDL ranges that trim
     every pause longer than the pace allows down to ~0.12 s of air (edges padded 0.06 s into
     silence, so cuts never land on a word);
  2. flags transcript words that last longer than 1.2 s or contain a real silence (merged words =
     likely a false start / retake) and re-transcribes each piece between those silences on its
     own, so you can see "اگه می‌خوای راه… | اگه راهنمای کامل…" and keep the clean take;
  3. with --write, saves the proposal as <edit_dir>/edl.json (existing file → edl.prev.json).
Then: read the retake list, drop the false-start ranges from edl.json, render the draft, run joins.py.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACE = {"tight": 0.35, "natural": 0.8}   # pauses longer than this are trimmed
PAD, MIN_SIL = 0.06, 0.28


def silences(video: Path, noise="-32dB", d=MIN_SIL):
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-af", f"silencedetect=n={noise}:d={d}", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    ends = [(float(e), float(dd)) for e, dd in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", err)]
    return [(round(e - dd, 3), round(e, 3)) for e, dd in ends]


def duration(video: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                capture_output=True, text=True).stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("--source", required=True, help="key=video (key = transcript stem)")
    ap.add_argument("--pace", default="tight", choices=list(PACE))
    ap.add_argument("--language")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    edit = a.edit_dir.resolve()
    key, vid = a.source.split("=", 1)
    video = Path(vid).resolve()
    dur, sil = duration(video), silences(video)
    limit = PACE[a.pace]

    # 1. ranges = speech between silences longer than the pace allows
    cuts = [(s, e) for s, e in sil if e - s > limit or s < 0.05 or e > dur - 0.05]
    ranges, start = [], 0.0
    for s, e in cuts:
        if s > start + 0.05:
            ranges.append((round(max(0.0, start - (PAD if start > 0 else 0)), 2), round(min(dur, s + PAD), 2)))
        start = e
    if start < dur - 0.05:
        ranges.append((round(max(0.0, start - PAD), 2), round(dur, 2)))
    kept = sum(b - a_ for a_, b in ranges)
    print(f"{key}: {dur:.1f}s → {kept:.1f}s in {len(ranges)} ranges ({len(cuts)} pauses > {limit}s trimmed, pace {a.pace})")

    # 2. merged words that hide retakes
    tr = edit / "transcripts" / f"{key}.json"
    words = [w for w in json.loads(tr.read_text(encoding="utf-8")).get("words", []) if w.get("type", "word") == "word"] if tr.exists() else []
    suspects = []
    for w in words:
        inner = [(s, e) for s, e in sil if w["start"] + 0.05 < s and e < w["end"] - 0.05]
        if w["end"] - w["start"] > 1.2 or inner:
            suspects.append((w, inner))
    if suspects:
        print(f"\n{len(suspects)} suspicious word(s) — long or containing a silence (false start / retake?):")
        model = None
        for w, inner in suspects:
            cuts_in = [w["start"]] + [x for s, e in inner for x in (s, e)] + [w["end"]]
            pieces = [(cuts_in[i], cuts_in[i + 1]) for i in range(0, len(cuts_in) - 1, 2)]
            print(f"  «{w['text'].strip()}» {w['start']:.2f}-{w['end']:.2f}s ({w['end'] - w['start']:.1f}s), {len(inner)} silence(s) inside")
            if model is None:
                from faster_whisper import WhisperModel
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video-use" / "helpers"))
                from transcribe import _add_cuda_dlls
                _add_cuda_dlls()  # pip's cublas/cudnn DLLs: without this the GPU model loads but fails at encode
                try:
                    model = WhisperModel("medium", device="cuda", compute_type="int8")
                except Exception:  # noqa: BLE001
                    model = WhisperModel("medium", device="cpu", compute_type="int8")
            # re-hear a little context: from the silence before the word to the next one after it
            pre = max([e for s, e in sil if e <= w["start"] + 0.05] or [max(0.0, w["start"] - 2)])
            post = min([s for s, e in sil if s >= w["end"] - 0.05] or [min(dur, w["end"] + 2)])
            bounds = [pre] + [x for s, e in inner for x in (s, e)] + [post]
            for i in range(0, len(bounds) - 1, 2):
                p0, p1 = bounds[i], bounds[i + 1]
                f = Path(tempfile.mkdtemp()) / "piece.wav"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p0:.2f}", "-to", f"{p1:.2f}", "-i", str(video), "-ac", "1",
                                "-ar", "16000", str(f)], check=True)
                segs, _ = model.transcribe(str(f), language=a.language, beam_size=5)
                print(f"     {p0:6.2f}-{p1:6.2f}s  {' '.join(s.text.strip() for s in segs)}")
        print("  → if two pieces say the same line, keep the last clean one: drop the earlier range(s) from edl.json.")

    if a.write:
        p = edit / "edl.json"
        if p.exists():
            shutil.copy2(p, edit / "edl.prev.json")
        try:
            rel = Path(shutil.os.path.relpath(video, edit)).as_posix()
        except ValueError:
            rel = video.as_posix()
        edl = {"version": 1, "sources": {key: rel}, "ranges": [{"source": key, "start": s, "end": e} for s, e in ranges]}
        p.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
