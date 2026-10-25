"""Lite edit: a finished reel in two commands, so any coding agent (or a person) can run it.

  lite_edit.py prepare <project>            transcribe, cut silences from the audio, list retakes + caption cues
  lite_edit.py render  <project> [--final]  captions, keywords, punch-ins, CTA, music, SFX → output/<project>/

Between the two, the ONLY judgment step: open mp-studio/work/<project>/edit/LITE_TODO.md and
  1. drop false-start ranges it lists from edl.json (optional; keep the last clean take),
  2. write caption_fixes.json with corrected spelling (Persian Whisper text is often wrong),
     optionally marking one keyword per cue with *stars* (otherwise keywords are picked automatically).
Everything else comes from the brand in MP Studio (fonts, colours, caption style, page, CTA, music level).
The full Claude pipeline (pro-edit: plan, storyboard, HyperFrames panel, pop-out window, QC passes)
stays the "pro" mode; this is the dependable, weaker-model-friendly path.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PE = Path(__file__).resolve().parent                       # .claude/skills/pro-edit
REPO = PE.parents[2]
STUDIO = REPO / "mp-studio"
VU = PE.parent / "video-use" / "helpers"
TM = PE / "templates" / "ass-motion"
PY = sys.executable
PYR = Path(PY).relative_to(REPO).as_posix() if Path(PY).is_relative_to(REPO) else PY  # shown in LITE_TODO.md
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi", ".mts"}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def run(*cmd, quiet=False):
    print("→", " ".join(str(c) for c in cmd[1:3]), "…", flush=True)
    r = subprocess.run([str(c) for c in cmd], capture_output=quiet, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"failed: {' '.join(str(c) for c in cmd)}\n{(r.stderr or '')[-1500:] if quiet else ''}")
    return r.stdout if quiet else ""


def brand_for(project):
    sys.path.insert(0, str(STUDIO / "app"))
    try:
        import handoff  # merged brand (Studio brand.json + this project's settings.json)
        b = handoff.summary(project).get("brand", {})
    except Exception:
        b = {}
    defaults = {"language": "fa", "pace": "tight", "captions": "emphasis", "music_db": -20, "page": "", "cta": "",
                "colors": {"accent": "#FFC400", "text": "#FFFFFF", "dark": "#111111"},
                "fonts": {"captions": "Vazirmatn", "keyword": "Lalezar", "display": "Lalezar"}}
    if not b.get("page"):  # Studio brand not saved yet: take the handle from the older brand.md
        md = STUDIO / "assets" / "brand.md"
        m = re.search(r"@([A-Za-z0-9_.]+)", md.read_text(encoding="utf-8")) if md.exists() else None
        if m:
            b["page"] = m.group(1)
    return {**defaults, **b, "colors": {**defaults["colors"], **b.get("colors", {})},
            "fonts": {**defaults["fonts"], **{k: v for k, v in b.get("fonts", {}).items() if v}}}


def takes(project):
    """Speech clips in the owner's order (MP Studio → پروژه → ترتیب و نقش کلیپ‌ها; a retake replaces
    the clip above it) and the b-roll clips, from mp-studio/app/clips.py."""
    d = STUDIO / "input" / project
    sys.path.insert(0, str(STUDIO / "app"))
    import clips
    speech, broll = clips.plan(project)
    if not speech:
        sys.exit(f"no talking clips in {d} (all marked b-roll?)")
    return [d / f for f in speech], [d / f for f in broll]


def broll_spots(edl, broll, dur, cta_t0):
    """Cutaways: each b-roll clip (muted, up to 3 s) covers a jump cut, spread evenly between the hook
    (first 3 s) and the CTA. Returns finish.py "broll" entries on the output timeline."""
    if not broll:
        return []
    cuts, t = [], 0.0
    for r in edl["ranges"][:-1]:
        t += r["end"] - r["start"]
        if 3.0 < t < cta_t0 - 3.5:
            cuts.append(t)
    spots = []
    for i, f in enumerate(broll):
        want = 3.0 + (cta_t0 - 6.5) * (i + 1) / (len(broll) + 1)
        at = min(cuts, key=lambda c: abs(c - want)) if cuts else want
        if any(abs(at - s["t"]) < 3.5 for s in spots):
            at = want
        length = min(3.0, max(1.2, float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                             "default=nw=1:nk=1", f, quiet=True).strip() or 3) - 0.3))
        spots.append({"file": str(f), "t": round(at - 0.4, 2), "dur": round(length, 2), "from": 0.3})
    return spots


def prepare(project):
    E = STUDIO / "work" / project / "edit"
    E.mkdir(parents=True, exist_ok=True)
    b = brand_for(project)
    vids, broll = takes(project)
    (E / "lite_broll.json").write_text(json.dumps([str(f) for f in broll], ensure_ascii=False), encoding="utf-8")
    for v in vids:  # speech only: b-roll is often silent (screen recordings) and is never captioned
        if not (E / "transcripts" / f"{v.stem}.json").exists():
            run(PY, VU / "transcribe.py", v, "--edit-dir", E, "--language", b["language"])
    run(PY, VU / "pack_transcripts.py", "--edit-dir", E)
    # cut from the real audio, one take at a time, then join the takes in the owner's order
    # (b-roll is not cut into the talk: render shows it over jump cuts)
    ranges, sources, reports = [], {}, []
    pace = b["pace"] if b["pace"] in ("tight", "natural") else "tight"
    for v in vids:
        out = run(PY, PE / "cutplan.py", E, "--source", f"{v.stem}={v}", "--pace", pace, "--language", b["language"],
                  "--write", quiet=True)
        reports.append(out)
        part = json.loads((E / "edl.json").read_text(encoding="utf-8"))
        sources.update(part["sources"])
        ranges += part["ranges"]
    for i, r in enumerate(ranges):  # punch-ins hide the jump cuts
        r.update(zoom=1.0 if i % 2 == 0 else 1.1, zoom_y=0.35)
    edl = {"version": 1, "aspect": b.get("aspect", "9:16"), "grade": "neutral_punch", "sources": sources, "ranges": ranges}
    (E / "edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    cues = run(PY, TM / "captions.py", E, "raw", quiet=True)
    todo = f"""# Lite edit — {project}

Do the two things below, then show the owner a storyboard (seconds, no render):
`{PYR} .claude/skills/pro-edit/lite_edit.py storyboard "{project}"` → they review it in MP Studio → بازبینی.
Only after they approve: `{PYR} .claude/skills/pro-edit/lite_edit.py render "{project}" --final`

## 1. Retakes (optional)
The audio cut is in `edl.json` ({len(ranges)} ranges). If the report below shows the same line said twice,
delete the EARLIER range(s) from `edl.json` and keep the last clean take. If you changed ranges, list the
cues again before writing fixes (their numbers shift):
`{PYR} .claude/skills/pro-edit/templates/ass-motion/captions.py "{E}" raw`

```
{chr(10).join(reports).strip()}
```

## 2. Caption spelling
Write `caption_fixes.json` next to this file: {{"<cue number>": "corrected text"}}. "" drops a cue (stray word
from a cut take). Mark at most one keyword per cue with *stars* ("کاملاً *رایگانه*"); if you mark none, numbers
and long words are starred automatically. Keep half-spaces in words like «می‌کنه». Cues:

```
{cues.strip()}
```
"""
    (E / "LITE_TODO.md").write_text(todo, encoding="utf-8")
    print(f"\nprepared: {E / 'LITE_TODO.md'}  ({len(ranges)} ranges, captions listed)")


# never a keyword: verbs, pronouns and fillers (Whisper writes them in many spellings)
STOP = set("""میکنه می‌کنه میکنن می‌کنن کرده کردن کنه کنی بکنه داره دارن هست هستن نیست اینه اونه بود بودن شده
میشه می‌شه میده می‌ده میتونه می‌تونه میتونی می‌تونی خودت خودتو خودش اینجا اونجا یعنی دیگه اینقدر چیزی همه
the and that this with have""".split())


def auto_stars(master: Path, persian_digits: bool):
    """No *stars* written? Star a keyword in about every third cue: numbers first, else the longest
    content word (never a verb/filler). Persian videos also get Persian digits («۱۱», not «11»)."""
    blocks = master.read_text(encoding="utf-8").strip().split("\n\n")
    if persian_digits:
        blocks = ["\n".join(b.split("\n", 2)[:2] + [b.split("\n", 2)[2].translate(FA_DIGITS)]) for b in blocks]
    if any("*" in b.split("\n", 2)[2] for b in blocks):
        master.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return
    out = []
    for i, blk in enumerate(blocks):
        idx, timing, text = blk.split("\n", 2)
        words = text.split()
        pick = next((w for w in words if re.search(r"[0-9۰-۹]", w)), None)
        content = [w for w in words if w.strip(".,!?؟،").lower() not in STOP]
        if pick is None and i % 3 == 0 and content:
            pick = max(content, key=len) if len(max(content, key=len)) >= 5 else None
        if pick:
            text = text.replace(pick, f"*{pick}*", 1)
        out.append(f"{idx}\n{timing}\n{text}")
    master.write_text("\n\n".join(out) + "\n", encoding="utf-8")


def write_motion(E, b, dur):
    """Brand captions + a CTA card (handle, CTA line) in the last ~3 s → motion.json + master.ass.
    Built before the storyboard too, so the review shows exactly what will be burned in."""
    cap = b["captions"] if b["captions"] in ("boxed", "word", "glass", "glass-futuristic") else "emphasis"
    style = {"caption_mode": cap, "font": b["fonts"]["captions"], "keyword_font": b["fonts"]["keyword"],
             "display_font": b["fonts"]["display"], "accent": b["colors"]["accent"], "text": b["colors"]["text"],
             "dark": b["colors"]["dark"], "caption_y": 1400}
    moments, t0 = [], max(0.0, dur - 3.2)
    if b.get("page"):
        moments.append({"type": "label", "text": "@" + b["page"].lstrip("@"), "size": 70, "start": t0, "end": dur, "y": 170, "enter": "fade"})
    moments.append({"type": "dark", "text": b.get("cta") or "پیج رو فالو کن", "start": t0 + 0.1, "end": dur, "y": 300, "enter": "drop"})
    (E / "motion.json").write_text(json.dumps({"style": style, "moments": moments}, ensure_ascii=False, indent=1), encoding="utf-8")
    run(PY, TM / "ass_motion.py", E)
    return t0


def captions_ready(E, b):
    run(PY, TM / "captions.py", E, "fix")
    auto_stars(E / "master.srt", b["language"] == "fa")


def storyboard(project):
    """Review before any render: plan in words + one card per spoken line (still + audio from the raw
    takes), shown in MP Studio → بازبینی. Takes seconds."""
    E = STUDIO / "work" / project / "edit"
    if not (E / "edl.json").exists():
        sys.exit("run `prepare` first")
    b = brand_for(project)
    captions_ready(E, b)
    edl = json.loads((E / "edl.json").read_text(encoding="utf-8"))
    kept = sum(r["end"] - r["start"] for r in edl["ranges"])
    write_motion(E, b, kept)  # captions + CTA exactly as they will render → shown on the storyboard frames
    keys = sum("*" in blk for blk in (E / "master.srt").read_text(encoding="utf-8").split("\n\n"))
    page = ("@" + b["page"].lstrip("@")) if b.get("page") else "بدون پیج (در برند و استایل تنظیم کن)"
    plan = (f"حالت سبک (هوش مصنوعی ساده‌تر)\n"
            f"• طول: حدود {kept:.0f} ثانیه، {len(edl['ranges'])} تکه — مکث‌ها حذف شده؛ تکرارها را در جدول برش ببین\n"
            f"• زیرنویس: سبک «{b['captions']}» با فونت {b['fonts']['captions']} — {keys} کلمه‌ی کلیدی رنگی\n"
            f"• زوم‌های متناوب روی برش‌ها، موزیک ملایم زیر صدا، افکت صوتی روی برش‌ها و کلمه‌های کلیدی\n"
            f"• پایان: کارت CTA «{b.get('cta') or 'پیج رو فالو کن'}» و {page}\n"
            f"عکس‌ها از ویدیوی خام است (هنوز رندر نشده)؛ متن هر کارت همان زیرنویس نهایی است.")
    (E / "plan.md").write_text(plan, encoding="utf-8")
    run(PY, PE / "storyboard.py", E, "--plan", E / "plan.md")
    run(PY, STUDIO / "app" / "handoff.py", "set", project, "review", "--note", "storyboard (lite)", quiet=True)
    print(f"\nstoryboard ready → MP Studio → بازبینی. Render only after the owner approves:\n"
          f"  {PYR} .claude/skills/pro-edit/lite_edit.py render \"{project}\" --final")


def render(project, final):
    E = STUDIO / "work" / project / "edit"
    O = STUDIO / "output" / project
    O.mkdir(parents=True, exist_ok=True)
    b = brand_for(project)
    if not (E / "edl.json").exists():
        sys.exit("run `prepare` first")
    captions_ready(E, b)

    # cut (graded, no captions); its length drives the CTA timing
    mode = [] if final else ["--preview"]
    run(PY, VU / "render.py", E / "edl.json", "-o", E / "lite_cut.mp4", *mode, "--no-subtitles", "--no-loudnorm")
    base = "base.mp4" if final else "base_preview.mp4"
    dur = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                    E / base, quiet=True).strip())

    t0 = write_motion(E, b, dur)

    # music + SFX (generated when the owner has none), whoosh on every cut, pop on keywords
    music_dir, sfx_dir = STUDIO / "assets" / "music", STUDIO / "assets" / "sfx"
    music = sorted(f for f in music_dir.glob("*") if f.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}) if music_dir.is_dir() else []
    if not music:
        music_dir.mkdir(parents=True, exist_ok=True)
        bed = music_dir / "lite_bed.wav"
        run(PY, PE / "audio" / "music_bed.py", bed, "--length", f"{dur + 1:.1f}", "--stop", f"{t0:.2f}", quiet=True)
        music = [bed]
    if not (sfx_dir / "pop.wav").exists():
        run(PY, PE / "audio" / "sfx.py", sfx_dir, quiet=True)
    edl = json.loads((E / "edl.json").read_text(encoding="utf-8"))
    sfx, t = [], 0.0
    for r in edl["ranges"][:-1]:
        t += r["end"] - r["start"]
        sfx.append({"name": "whoosh_short", "t": round(max(0, t - 0.12), 2), "db": -24})
    for blk in (E / "master.srt").read_text(encoding="utf-8").strip().split("\n\n"):
        _, timing, text = blk.split("\n", 2)
        if "*" in text:
            h, m, s = timing.split("-->")[0].strip().replace(",", ".").split(":")
            sfx.append({"name": "pop", "t": round(int(h) * 3600 + int(m) * 60 + float(s), 2), "db": -26})
    sfx += [{"name": "pop", "t": round(t0 + 0.1, 2), "db": -20}, {"name": "ding", "t": round(t0 + 0.4, 2), "db": -24}]
    rel = lambda p: Path(__import__("os").path.relpath(p, E)).as_posix()
    fx = {"base": base, "front": "master.ass", "fonts_dir": rel(STUDIO / "fonts"), "vignette": True, "grain": 3,
          "voice": {"highpass": 80, "compress": True},
          "music": {"file": rel(music[0]), "db": b.get("music_db", -20) - 2, "duck": True},
          "sfx_dir": rel(sfx_dir), "sfx": sorted(sfx, key=lambda x: x["t"])}
    bfile = E / "lite_broll.json"
    spots = broll_spots(edl, [Path(p) for p in json.loads(bfile.read_text(encoding="utf-8"))] if bfile.exists() else [], dur, t0)
    if spots:  # cutaways over jump cuts, with a whoosh as each comes in
        fx["broll"] = spots
        fx["sfx"] = sorted(fx["sfx"] + [{"name": "whoosh_short", "t": round(max(0, s["t"] - 0.1), 2), "db": -22} for s in spots],
                           key=lambda x: x["t"])
    (E / "fx_lite.json").write_text(json.dumps(fx, ensure_ascii=False, indent=1), encoding="utf-8")
    name = f"{project}_lite{'' if final else '_preview'}.mp4"
    run(PY, PE / "finish.py", E, "--spec", "fx_lite.json", "-o", O / name, *([] if final else ["--preview"]))
    qc = run(PY, PE / "qc_sheet.py", O / name, "--edl", E / "edl.json", "--no-sheet", quiet=True)
    (O / name).with_suffix(".srt").write_text((E / "master.clean.srt").read_text(encoding="utf-8"), encoding="utf-8")
    print(qc.strip())
    print(f"\ndone: {O / name}" + ("" if final else "\nlooks right? run again with --final for full quality"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["prepare", "storyboard", "render"])
    ap.add_argument("project")
    ap.add_argument("--final", action="store_true", help="full-quality render (default: fast preview)")
    a = ap.parse_args()
    {"prepare": lambda: prepare(a.project), "storyboard": lambda: storyboard(a.project),
     "render": lambda: render(a.project, a.final)}[a.step]()
