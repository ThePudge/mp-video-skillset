"""Storyboard for MP Studio's Review tab: the plan in words, the cut table, and one card per spoken
line (a still of that beat, its words, layout, the one move, and the beat's audio to play).

  storyboard.py <edit_dir> [--cards cards.json] [--plan plan.md]     BEFORE any render (default, seconds):
                stills + audio straight from the raw takes through edl.json — review first, render after approval
  storyboard.py <edit_dir> --video <draft_or_preview.mp4> [...]     after a render (stills show the graphics)
  storyboard.py <edit_dir> --cuts-only        print the cut table as text (before any render)

cards.json (output timeline, written by Claude; omit it to get one card per caption line):
  [{"t0": 0.0, "t1": 2.4, "words": "…", "layout": "window", "move": "شمارنده ۱→۱۱ با پاپ",
    "sketch": {"kind": "شمارنده", "title": "۱۱ ابزار", "subtitle": "آیکن‌ها یکی‌یکی ظاهر می‌شوند"}}, …]
  layout: "full" (default) | "window" (pop-out under a panel) | "split"; sketch = the planned graphic,
  drawn in the panel area until the real panel exists. Each still is a MOCK-UP of the finished shot
  (storyframe.py): layout + master.ass captions/motion at that moment (if built) + sketch + motion tag.
Writes <edit_dir>/../review/ (stills, audio, review.json) — Studio shows it after
`mp-studio/app/handoff.py set <project> review`. Stills are small (540 px) so a 20-card board loads fast.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def words_of(edit: Path, src: str) -> list:
    t = edit / "transcripts" / f"{src}.json"
    if not t.exists():
        return []
    d = json.loads(t.read_text(encoding="utf-8"))
    return [w for w in d.get("words", []) if w.get("type", "word") == "word"]


def cut_table(edit: Path) -> list:
    """Every join: what was removed (source times) and the words on either side."""
    edl = json.loads((edit / "edl.json").read_text(encoding="utf-8"))
    rows, rs = [], edl["ranges"]
    for a, b in zip(rs, rs[1:]):
        wa, wb = words_of(edit, a["source"]), words_of(edit, b["source"])
        before = " ".join(w["text"].strip() for w in wa if w["end"] <= a["end"] + 0.05)[-40:]
        after = " ".join(w["text"].strip() for w in wb if w["start"] >= b["start"] - 0.05)[:40]
        gap = f"{a['end']:.2f}" if a["source"] == b["source"] else f"{a['source']}@{a['end']:.2f}"
        rows.append({"start": gap, "end": f"{b['start']:.2f}" if a["source"] == b["source"] else f"{b['source']}@{b['start']:.2f}",
                     "removed": round(b["start"] - a["end"], 2) if a["source"] == b["source"] else None,
                     "before": " ".join(before.split()[-3:]), "after": " ".join(after.split()[:3])})
    return rows


def srt_cards(edit: Path) -> list:
    """One card per spoken line: caption cues merged until ≥1.6 s or a sentence end."""
    srt = next((edit / n for n in ("master.srt", "raw.srt") if (edit / n).exists()), None)
    if not srt:
        sys.exit("no cards.json and no master.srt/raw.srt: write cards.json or run captions.py first")
    cues = []
    for b in srt.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = b.split("\n")
        if len(lines) < 3:
            continue
        m = re.findall(r"(\d+):(\d+):(\d+),(\d+)", lines[1])
        t = [int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000 for h, mi, s, ms in m]
        cues.append((t[0], t[1], " ".join(lines[2:]).replace("*", "")))
    cards, cur = [], None
    for t0, t1, txt in cues:
        if cur is None:
            cur = {"t0": t0, "t1": t1, "words": txt}
        else:
            cur["t1"], cur["words"] = t1, cur["words"] + " " + txt
        if cur["t1"] - cur["t0"] >= 1.6 or txt.rstrip().endswith((".", "!", "?", "؟", "…")):
            cards.append(cur)
            cur = None
    if cur:
        cards.append(cur)
    return cards


def source_map(edit: Path):
    """Output-timeline → (source video, source time) through the EDL ranges."""
    edl = json.loads((edit / "edl.json").read_text(encoding="utf-8"))
    segs, t = [], 0.0
    for r in edl["ranges"]:
        src = Path(edl["sources"][r["source"]])
        src = src if src.is_absolute() else (edit / src).resolve()
        d = r["end"] - r["start"]
        segs.append((t, t + d, src, r["start"], float(r.get("zoom") or 1.0)))
        t += d
    return segs


def pieces(segs, t0, t1):
    """Source pieces (video, from, to, zoom) that play during output [t0, t1)."""
    out = []
    for a, b, src, s0, z in segs:
        lo, hi = max(a, t0), min(b, t1)
        if hi - lo > 0.02:
            out.append((src, s0 + lo - a, s0 + hi - a, z))
    return out


def from_source(edit: Path, cards: list, cuts: list, plan_path):
    """Storyboard without rendering: one still (from the raw take, at the moment it plays in the edit)
    and the beat's spoken audio, already cut, per card. Seconds per card instead of minutes per render."""
    import storyframe  # same folder: mock-up of the finished shot (layout + captions/motion + sketch)
    segs = source_map(edit)
    brand = storyframe.load_brand(edit)
    fonts = edit.parents[2] / "fonts"
    rev = edit.parent / "review"
    rev.mkdir(parents=True, exist_ok=True)
    for f in rev.glob("card_*"):
        f.unlink()
    mocked = 0
    for i, c in enumerate(cards):
        mid = c["t0"] + (c["t1"] - c["t0"]) * 0.65  # late in the beat: the graphic has landed
        p_mid = pieces(segs, mid, mid + 0.05) or pieces(segs, c["t0"], c["t1"])
        still, audio = f"card_{i:02d}.jpg", f"card_{i:02d}.m4a"
        if p_mid:
            src, s, _, z = p_mid[0]
            mocked += storyframe.compose(edit, c, mid, src, s, z, brand, fonts, rev / still)
        ps = pieces(segs, c["t0"], c["t1"])
        if ps:
            ins, chain = [], []
            for k, (src, s, e, _) in enumerate(ps):
                ins += ["-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src)]
                chain.append(f"[{k}:a]")
            graph = "".join(chain) + f"concat=n={len(ps)}:v=0:a=1[a]"
            subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[a]",
                            "-c:a", "aac", "-b:a", "96k", str(rev / audio)], check=True)
        c.update(still=still, audio=audio if ps else "",
                 clip=" + ".join(dict.fromkeys(p[0].stem for p in ps)))  # which raw take(s) the beat comes from
    plan = Path(plan_path).read_text(encoding="utf-8") if plan_path else ""
    (rev / "review.json").write_text(json.dumps({"plan": plan, "cuts": cuts, "cards": cards, "video": "",
                                                 "stage": "storyboard"}, ensure_ascii=False, indent=1), encoding="utf-8")
    dec = rev / "decision.json"
    if dec.exists():
        shutil.move(str(dec), str(rev / "decision.prev.json"))
    print(f"storyboard (no render): {len(cards)} cards ({mocked} with motion mock-ups), {len(cuts)} cuts → {rev}  "
          f"(next: mp-studio/app/handoff.py set <project> review)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("--video", type=Path)
    ap.add_argument("--cards", type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--cuts-only", action="store_true")
    a = ap.parse_args()
    edit = a.edit_dir.resolve()
    cuts = cut_table(edit) if (edit / "edl.json").exists() else []
    if a.cuts_only:
        print(f"{'#':>3}  {'cut from':>12}  {'to':>12}  {'removed':>7}  before → after")
        for i, c in enumerate(cuts, 1):
            print(f"{i:>3}  {c['start']:>12}  {c['end']:>12}  {c['removed'] if c['removed'] is not None else '-':>7}  {c['before']} | {c['after']}")
        return
    cards = json.loads(a.cards.read_text(encoding="utf-8")) if a.cards else srt_cards(edit)
    if not a.video:  # fast path: review BEFORE any render — stills and audio straight from the raw takes
        return from_source(edit, cards, cuts, a.plan)
    if not a.video.exists():
        sys.exit(f"video not found: {a.video}")
    rev = edit.parent / "review"
    if rev.exists():
        for f in rev.glob("card_*"):
            f.unlink()
    rev.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cards):
        mid = c["t0"] + (c["t1"] - c["t0"]) * 0.65  # late in the beat: the graphic has landed
        still, audio = f"card_{i:02d}.jpg", f"card_{i:02d}.m4a"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{mid:.3f}", "-i", str(a.video), "-frames:v", "1",
                        "-vf", "scale=540:-2", "-q:v", "4", str(rev / still)], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{c['t0']:.3f}", "-to", f"{c['t1']:.3f}", "-i", str(a.video),
                        "-vn", "-c:a", "aac", "-b:a", "96k", str(rev / audio)], check=True)
        c.update(still=still, audio=audio)
    plan = a.plan.read_text(encoding="utf-8") if a.plan else ""
    (rev / "review.json").write_text(json.dumps({"plan": plan, "cuts": cuts, "cards": cards, "video": a.video.name},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    dec = rev / "decision.json"
    if dec.exists():
        shutil.move(str(dec), str(rev / "decision.prev.json"))
    print(f"review: {len(cards)} cards, {len(cuts)} cuts → {rev}  (next: mp-studio/app/handoff.py set <project> review)")


if __name__ == "__main__":
    main()
