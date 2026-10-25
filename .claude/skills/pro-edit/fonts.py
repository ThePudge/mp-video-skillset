"""Fonts: list them, or organize whatever the owner dropped into fonts/ (zips' folders, otf/ttf/web
versions, help PDFs) into one clean, flat set that libass, HyperFrames and MP Studio can all use.

  fonts.py                 list families (the INTERNAL names libass / HyperFrames must be given)
  fonts.py organize        flatten + dedupe into mp-studio/fonts/<Family>-<Style>.<ext>, write fonts/catalog.json
  fonts.py roles           print the suggested role per family (captions / display / contrast)

organize keeps ONE file per (family, style): .ttf over .otf, newest version when a family came in
several releases; FaNum (Persian digits) families stay separate. Everything else (web fonts, help
PDFs, macOS junk, the original folders) is moved to mp-studio/fonts/_source/ — kept, never deleted.
libass picks fonts by the internal family name, so use the printed names in motion.json / brand.json.
"""
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import ImageFont

FONTS = Path(__file__).resolve().parents[3] / "mp-studio" / "fonts"
SRC = FONTS / "_source"
KEEP_AT_ROOT = {"README.md", "catalog.json"}
EXT_RANK = {".ttf": 0, ".otf": 1}

# Role by family name (owner's picks first). captions = legible body; display = heavy keyword/titles;
# contrast = one calligraphic/serif word for contrast.
ROLE_HINTS = [("display", r"lalezar|abar|morabba|kalameh.*(black|heavy)"),
              ("contrast", r"golpayegani|croissant|farhang|nastaliq|shekasteh"),
              ("captions", r"vazir|kalameh|waw|peyda|yekan|iransans|instagram|estedad|shabnam|sahel")]


def name_of(f: Path):
    try:
        return ImageFont.truetype(str(f), 20).getname()
    except OSError:
        return None


def font_files(where: Path):
    for f in where.rglob("*"):
        if (f.is_file() and f.suffix.lower() in EXT_RANK and "__MACOSX" not in f.parts
                and not f.name.startswith("._") and SRC not in f.parents):
            yield f


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", s.title()) or "Font"


def role(fam: str) -> str:
    for r, pat in ROLE_HINTS:
        if re.search(pat, fam, re.I):
            return r
    return "display"


def catalog() -> dict:
    fams: dict = {}
    for f in sorted(FONTS.glob("*")):
        if f.suffix.lower() not in EXT_RANK:
            continue
        n = name_of(f)
        if not n:
            continue
        fam, style = n
        e = fams.setdefault(fam, {"styles": {}, "fanum": "fanum" in fam.lower(), "role": role(fam)})
        e["styles"][style] = f.name
    return fams


def organize():
    chosen: dict = {}
    for f in font_files(FONTS):
        n = name_of(f)
        if not n:
            continue
        rank = (EXT_RANK[f.suffix.lower()], -f.stat().st_mtime, len(str(f)))
        if n not in chosen or rank < chosen[n][0]:
            chosen[n] = (rank, f)
    SRC.mkdir(exist_ok=True)
    moved = 0
    for (fam, style), (_, f) in sorted(chosen.items()):
        dst = FONTS / f"{safe(fam)}-{safe(style)}{f.suffix.lower()}"
        if f.resolve() != dst.resolve():
            shutil.copy2(f, dst)
            moved += 1
    keep = {(FONTS / f"{safe(fam)}-{safe(style)}{f.suffix.lower()}").name for (fam, style), (_, f) in chosen.items()}
    keep |= KEEP_AT_ROOT | {p.name for p in FONTS.glob("OFL*")}
    for p in list(FONTS.iterdir()):
        if p.name == "_source" or p.name in keep:
            continue
        target = SRC / p.name
        if target.exists():
            target = SRC / f"{p.stem}-{len(list(SRC.iterdir()))}{p.suffix}"
        shutil.move(str(p), str(target))
    cat = catalog()
    (FONTS / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(chosen)} styles in {len(cat)} families ({moved} copied flat); originals in mp-studio/fonts/_source/")
    roles()


def roles():
    cat = json.loads((FONTS / "catalog.json").read_text(encoding="utf-8")) if (FONTS / "catalog.json").exists() else catalog()
    for r in ("captions", "display", "contrast"):
        fams = [f"{k} ({len(v['styles'])})" for k, v in cat.items() if v["role"] == r]
        print(f"{r:<9} {', '.join(fams) or '-'}")


def listing(d: Path):
    rows = [(*n, f.name) for f in sorted(d.glob("*")) if f.suffix.lower() in EXT_RANK and (n := name_of(f))]
    w = max((len(r[0]) for r in rows), default=6)
    for fam, style, name in rows:
        print(f"{fam:<{w}}  {style:<12}  {name}")
    if not rows:
        print(f"no fonts in {d}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "organize":
        organize()
    elif arg == "roles":
        roles()
    else:
        listing(Path(arg) if arg else FONTS)
