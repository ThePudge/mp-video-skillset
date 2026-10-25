"""Join check: listen again to 1.5 s around every cut of a rendered edit and flag clipped words.

  joins.py <edit_dir> --video <draft_or_preview.mp4> [--model medium] [--language fa]

All join windows are packed into one audio file (with silence between them) and transcribed in a
single local Whisper pass, so 30 joins cost about as much as one 45 s clip. A join is flagged when
a word straddles the cut point (the cut went through a word) or the words expected on either side
(from the source transcript) are not heard. Fix: move that EDL edge into true silence, re-render,
run again. Prints a table and "N joins checked, M flags".
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR, HALF, GAP = 16000, 0.75, 1.0


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower().replace("ي", "ی").replace("ك", "ک").replace("‌", ""))


def similar(a: str, b_set: set) -> bool:
    """Persian Whisper spelling wanders (یه که → ایکی): a near match counts as the same word."""
    return any(difflib.SequenceMatcher(None, a, b).ratio() >= 0.6 for b in b_set if b)


def loud_at(audio_cache: dict, path: Path, t: float) -> bool:
    """True when the SOURCE audio has speech within ±20 ms of t (−35 dBFS): an edge there cuts through a word."""
    if path not in audio_cache:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                             capture_output=True).stdout
        audio_cache[path] = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    x = audio_cache[path][max(0, int((t - 0.02) * SR)): int((t + 0.02) * SR)]
    return bool(len(x)) and 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9) > -35


def src_words(edit: Path, src: str) -> list:
    t = edit / "transcripts" / f"{src}.json"
    d = json.loads(t.read_text(encoding="utf-8")) if t.exists() else {}
    return [w for w in d.get("words", []) if w.get("type", "word") == "word"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--model", default="medium")
    ap.add_argument("--language")
    a = ap.parse_args()
    edit = a.edit_dir.resolve()
    edl = json.loads((edit / "edl.json").read_text(encoding="utf-8"))
    rs = edl["ranges"]
    joins, t, cache = [], 0.0, {}
    src_path = lambda k: (edit / edl["sources"][k]).resolve() if not Path(edl["sources"][k]).is_absolute() else Path(edl["sources"][k])
    for r_a, r_b in zip(rs, rs[1:]):
        t += float(r_a["end"]) - float(r_a["start"])
        sa, sb = src_words(edit, r_a["source"]), src_words(edit, r_b["source"])
        ea, sb_ = float(r_a["end"]), float(r_b["start"])
        wa = [w for w in sa if w["end"] <= ea + 0.08]
        wb = [w for w in sb if w["start"] >= sb_ - 0.08]
        # the EDL edge itself falls inside a (normal-length) word of the source transcript
        inside = [w["text"].strip() for w, e in [(w, ea) for w in sa] + [(w, sb_) for w in sb]
                  if w["start"] < e - 0.1 and w["end"] > e + 0.1 and w["end"] - w["start"] < 1.2]
        # Whisper stretches words over short pauses: only trust "inside a word" when the audio there is not silent
        if inside and not (loud_at(cache, src_path(r_a["source"]), ea) or loud_at(cache, src_path(r_b["source"]), sb_)):
            inside = []
        near = {norm(w["text"]) for w in sa if ea - 1.0 < w["end"] <= ea + 0.6} | {norm(w["text"]) for w in sb if sb_ - 0.6 <= w["start"] < sb_ + 1.0}
        loud = [f"{r['source'][:12]}@{e:.2f}" for r, e in ((r_a, ea), (r_b, sb_)) if loud_at(cache, src_path(r["source"]), e)]
        joins.append({"t": t, "before": wa[-1]["text"].strip() if wa else "", "after": wb[0]["text"].strip() if wb else "",
                      "inside": inside, "near": near, "loud": loud})
    if not joins:
        print("no joins (one range)")
        return

    # one packed audio: [window][1 s silence][window]...
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a.video), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.int16)
    parts, offsets, pos = [], [], 0.0
    for j in joins:
        s0, s1 = max(0, int((j["t"] - HALF) * SR)), min(len(audio), int((j["t"] + HALF) * SR))
        offsets.append((pos, j["t"] - s0 / SR))  # where this window starts in the pack, cut point inside it
        parts += [audio[s0:s1], np.zeros(int(GAP * SR), np.int16)]
        pos += (s1 - s0) / SR + GAP
    pack = Path(tempfile.mkdtemp()) / "joins.wav"
    with wave.open(str(pack), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(np.concatenate(parts).tobytes())

    from faster_whisper import WhisperModel
    try:
        model = WhisperModel(a.model, device="cuda", compute_type="int8")
    except Exception:  # noqa: BLE001 — no usable GPU
        model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(pack), language=a.language, word_timestamps=True, vad_filter=False, beam_size=5)
    heard = [(w.start, w.end, w.word.strip(), w.probability) for s in segs for w in (s.words or [])]

    flags = 0
    args_fa = (a.language or "").lower() not in ("", "en")
    print(f"{'#':>3}  {'at':>7}  {'before | after (expected)':<34}  heard around the cut")
    for i, (j, (start, cut)) in enumerate(zip(joins, offsets), 1):
        win = [h for h in heard if start - 0.05 <= h[0] < start + 2 * HALF + 0.05]
        cut_abs = start + cut
        # Whisper stretches a word's end to the next word when the cut removed the pause, so a word
        # "across" the cut only counts as clipped if it is misheard (not the expected word) or unsure.
        expected = {norm(j["before"]), norm(j["after"])}
        straddle = [h for h in win if h[0] < cut_abs - 0.12 and h[1] > cut_abs + 0.12
                    and (not similar(norm(h[2]), expected) or h[3] < 0.5)]
        texts = {norm(h[2]) for h in win}
        missing = [w for w in (j["before"], j["after"]) if w and norm(w) and not similar(norm(w), texts)]
        # a word heard right at the cut that the speaker never said there (a clipped "pause" → "paw")
        misheard = [h[2] for h in win if abs((h[0] + h[1]) / 2 - cut_abs) < 0.45 and j["near"] and not similar(norm(h[2]), j["near"])]
        # The deciding test is language-independent: sound at the edit point in the source audio = a word was
        # cut. Re-heard words are notes (Whisper's Persian spelling/timing is too loose to judge clipping).
        bad = bool(j["loud"]) or (not args_fa and (straddle or misheard or len(missing) == 2))
        flags += bool(bad)
        note = ("sound at the edit point: " + ", ".join(j["loud"]) + (" (" + ", ".join(j["inside"]) + ")" if j["inside"] else "")) if j["loud"] else ("CLIPPED: " + ", ".join(h[2] for h in straddle)) if straddle \
            else ("misheard at cut: " + ", ".join(misheard)) if misheard else ("not heard: " + ", ".join(missing)) if missing else "ok"
        print(f"{i:>3}  {j['t']:>6.2f}s  {(j['before'] + ' | ' + j['after'])[:34]:<34}  "
              f"{' '.join(h[2] for h in win)[:48]}  {'⚠ ' + note if bad else note}")
    print(f"{len(joins)} joins checked, {flags} flags")
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
