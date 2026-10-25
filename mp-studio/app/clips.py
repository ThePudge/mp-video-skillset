"""Raw clips of a project in the owner's order, with a role each — shared by MP Studio, handoff.py
and the edit scripts (no web dependencies).

  work/<project>/clips.json = [{"file": "take1.mp4", "role": "main"}, …]
  main   = the talk, played in this order
  retake = another try of the main clip right above it: the edit keeps the better take
           (lite mode: the retake replaces that clip; Claude picks the best lines from both)
  broll  = cutaway footage (screen recording, product shots…) shown over the talk, muted
New uploads are appended as main (by file name); deleted files drop out.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # mp-studio/
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".mts", ".3gp"}
ROLES = ("main", "retake", "broll")


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def order(project: str) -> list:
    inp, work = ROOT / "input" / project, ROOT / "work" / project
    present = sorted(p.name for p in inp.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT) if inp.is_dir() else []
    saved = [c for c in _read(work / "clips.json", []) if isinstance(c, dict) and c.get("file") in present]
    known = {c["file"] for c in saved}
    return [{"file": c["file"], "role": c.get("role") if c.get("role") in ROLES else "main"} for c in saved] + \
           [{"file": f, "role": "main"} for f in present if f not in known]


def save(project: str, body: list) -> list:
    current = order(project)
    present = {c["file"] for c in current}
    clean, seen = [], set()
    for c in body or []:
        f = (c or {}).get("file")
        if f in present and f not in seen:
            clean.append({"file": f, "role": c.get("role") if c.get("role") in ROLES else "main"})
            seen.add(f)
    clean += [c for c in current if c["file"] not in seen]
    work = ROOT / "work" / project
    work.mkdir(parents=True, exist_ok=True)
    (work / "clips.json").write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    return clean


def plan(project: str):
    """(speech clips in play order, b-roll clips). A retake replaces the main clip right above it."""
    speech, broll = [], []
    for c in order(project):
        if c["role"] == "broll":
            broll.append(c["file"])
        elif c["role"] == "retake" and speech:
            speech[-1] = c["file"]
        else:
            speech.append(c["file"])
    return speech, broll
