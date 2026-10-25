"""Captions on the edited timeline, with hand-corrected text.

  captions.py <edit_dir> raw         EDL + transcripts -> raw.srt, and prints "index: text" per cue
  captions.py <edit_dir> fix         raw.srt + caption_fixes.json -> master.srt

caption_fixes.json: {"<cue index>": "corrected text", ...}; "" drops the cue, missing keeps Whisper's text.
A list splits the cue evenly over its time: {"96": ["بفهمی چه محتوایی", "بسازی و چه *سناریویی*", "بگیری. این"]}
— for words Whisper folded into one long cue (cutplan.py lists those).
Mark the emphasis keyword with stars ("تا *۱۰ تا ریلز*"); ass_motion.py makes it the big accent line.
Whisper's Persian spelling is poor, so for fa always correct every cue before burning captions in.
"""
import json
import sys
from pathlib import Path

E = Path(sys.argv[1]).resolve()
mode = sys.argv[2] if len(sys.argv) > 2 else "raw"

if mode == "raw":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "video-use" / "helpers"))
    import render  # noqa: E402  (video-use helper)

    edl = json.loads((E / "edl.json").read_text(encoding="utf-8"))
    missing = [k for k in edl["sources"] if not (E / "transcripts" / f"{k}.json").exists()]
    if missing:
        sys.exit(f"EDL source keys without a transcript (keys must equal the video file stem): {missing}")
    render.build_master_srt(edl, E, E / "raw.srt")
    for b in (E / "raw.srt").read_text(encoding="utf-8").strip().split("\n\n"):
        idx, _, text = b.split("\n", 2)
        print(f"{idx}: {text}")
else:
    fixes = {}
    f = E / "caption_fixes.json"
    if f.exists():
        fixes = {int(k): v for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
    out, n = [], 0
    def t2s(t):
        h, m, rest = t.strip().split(":")
        sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

    def s2t(v):
        ms = round(v * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    for b in (E / "raw.srt").read_text(encoding="utf-8").strip().split("\n\n"):
        idx, timing, text = b.split("\n", 2)
        fix = fixes.get(int(idx), text)
        parts = fix if isinstance(fix, list) else [fix]  # a list splits the cue evenly over its time
        a, z = (t2s(x) for x in timing.split("-->"))
        for k, part in enumerate(parts):
            part = part.strip().rstrip(".")
            if part:
                n += 1
                out.append(f"{n}\n{s2t(a + (z - a) * k / len(parts))} --> {s2t(a + (z - a) * (k + 1) / len(parts))}\n{part}")
    (E / "master.srt").write_text("\n\n".join(out) + "\n", encoding="utf-8")
    # platform subtitle upload: same cues without the *emphasis* marks
    (E / "master.clean.srt").write_text("\n\n".join(out).replace("*", "") + "\n", encoding="utf-8")
    print(f"master.srt: {n} cues ({sum('*' in o for o in out)} with an emphasis keyword); master.clean.srt for upload")
