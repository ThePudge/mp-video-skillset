"""MP Studio: the one window for setup, uploads, brand & style, fonts, review/approval, outputs and
learning material. Claude and the owner hand work back and forth through small JSON files:

  assets/brand.json              brand & style (per computer, not in git)
  work/<project>/brief.json      what the video is for (filled in Studio)
  work/<project>/settings.json   this project's style/voice overrides (only keys that differ from brand.json)
  work/<project>/handoff.json    whose turn it is: collecting → ready → working → review → approved|changes → done
  work/<project>/review/         review.json (plan text + one card per line) and its stills/audio

Claude waits on handoff.json with app/handoff.py, so pressing "Send to Claude" or "Approve" in
Studio wakes the Claude session without typing anything.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import clips, engine as E

ROOT = E.ROOT
ASSETS, FONTS, LEARN = ROOT / "assets", ROOT / "fonts", ROOT / "learn"
BRAND = ASSETS / "brand.json"
REPO = ROOT.parent                       # repo root: .claude/ and .venv/ live there
SKILLS = REPO / ".claude" / "skills"
PY = sys.executable
CREATOR = {"name": "mohammadpour.bi", "url": "https://instagram.com/mohammadpour.bi",
           "line": "MP Studio — ساخته‌شده توسط @mohammadpour.bi"}

KINDS = {  # upload kind → folder inside input/<project>/ and accepted extensions
    "footage": ("", E.VIDEO_EXT),
    "voice": ("", {".ogg", ".opus", ".m4a", ".mp3", ".wav", ".aac", ".flac", ".amr"}),
    "ref": ("ref", E.VIDEO_EXT | {".jpg", ".jpeg", ".png", ".webp"}),
    "music": ("music", {".mp3", ".wav", ".m4a", ".ogg", ".flac"}),
    "asset": ("assets", {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".json", ".mp4", ".mov"}),
}
FONT_EXT = {".ttf", ".otf", ".zip"}
DEFAULT_BRAND = {
    "page": "", "name": "", "bio": "", "avatar": "", "logo": "", "language": "fa", "platforms": ["Instagram Reels"],
    "aspect": "9:16", "length": "45-60", "pace": "tight",
    "colors": {"accent": "#FFC400", "accent2": "#4DD8FF", "text": "#FFFFFF", "dark": "#111111"},
    "fonts": {"captions": "Vazirmatn", "keyword": "Lalezar", "display": "Lalezar", "contrast": ""},
    "theme": "futuristic", "card_style": "glass", "motion_feel": "punchy", "captions": "emphasis",
    "music_end": "level", "music_db": -20, "voice_preset": "clean", "voice": {}, "cta": "",
    "hook_rule": "open on the strongest line, never a greeting",
}
IDENTITY = {"page", "name", "bio", "avatar", "logo"}  # always brand-wide; everything else can be set per project
NESTED = ("colors", "fonts", "voice")
STATUSES = {"collecting", "ready", "working", "review", "approved", "changes", "rendering", "done"}

router = APIRouter()


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _proj(name: str):
    try:
        n = E.safe_name(name)
    except ValueError:
        raise HTTPException(400, "bad project name")
    return n, E.INPUT / n, E.WORK / n, E.OUTPUT / n


def _save_upload(f: UploadFile, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(f.file, out, 8 * 1024 * 1024)


# ---------------------------------------------------------------- about / health / setup

@router.get("/api/studio/about")
def about():
    return CREATOR


def _which(cmd):
    return shutil.which(cmd) is not None


def _node_major():
    try:
        v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        return int(v.lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


@router.get("/api/studio/health")
def health():
    home = Path.home()
    hf_cache = home / ".cache" / "huggingface" / "hub"
    checks = [
        ("python", "Python + packages", (REPO / ".venv" / ".installed").exists()),
        ("ffmpeg", "FFmpeg", _which("ffmpeg")),
        ("node", "Node.js 22+", _node_major() >= 22),
        ("browser", "Headless browser (motion graphics)", (home / ".cache" / "hyperframes" / "chrome").exists()),
        ("whisper", "Whisper model (transcription)", any(hf_cache.glob("models--Systran--faster-whisper-*")) if hf_cache.exists() else False),
        ("hyperframes", "HyperFrames skills", (SKILLS / "hyperframes").exists()),
        ("remotion", "Remotion skill", (SKILLS / "remotion-best-practices").exists()),
        ("gsap", "GSAP skills", (SKILLS / "gsap-core").exists()),
        ("fonts", "Free fonts (Vazirmatn, Lalezar)", (FONTS / "Vazirmatn-Bold.ttf").exists() and (FONTS / "Lalezar-Regular.ttf").exists()),
        ("sfx", "Sound-effect kit", (ASSETS / "sfx" / "whoosh.wav").exists()),
        ("brand", "Brand profile filled in", bool(_read(BRAND, {}).get("page"))),
    ]
    return [{"id": i, "label": l, "ok": bool(ok)} for i, l, ok in checks]


@router.post("/api/studio/setup")
def setup():
    """Run setup (installs only what is missing) in the background; its output streams to the job log."""
    from .server import start_job  # late import: server imports this module

    def fn(job):
        job["log"] = []
        script = ROOT / "tools" / "bootstrap.ps1"
        p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-SetupOnly"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             cwd=ROOT)
        for line in p.stdout:
            job["log"] = (job["log"] + [line.rstrip()])[-200:]
            job["message"] = line.strip()[:120]
        if p.wait():
            raise RuntimeError("setup failed: see the log")
        if not (ASSETS / "sfx" / "whoosh.wav").exists():
            subprocess.run([PY, str(SKILLS / "pro-edit" / "audio" / "sfx.py"), str(ASSETS / "sfx")], check=False)
        return {"ok": True}

    return start_job("_studio", "setup", fn)


# ---------------------------------------------------------------- brand & style

@router.get("/api/studio/brand")
def get_brand():
    return _merge(DEFAULT_BRAND, _read(BRAND, {}))


def _merge(base: dict, over: dict) -> dict:
    return {**base, **over, **{k: {**base.get(k, {}), **over.get(k, {})} for k in NESTED}}


@router.put("/api/studio/brand")
def put_brand(body: dict):
    b = {**get_brand(), **{k: v for k, v in body.items() if k in DEFAULT_BRAND}}
    b["page"] = str(b.get("page", "")).lstrip("@").strip()
    _write(BRAND, b)
    return b


@router.post("/api/studio/brand/avatar")
def brand_avatar(file: UploadFile, kind: str = "avatar"):
    """Profile photo (kind=avatar, cropped square) or logo (kind=logo, kept whole with transparency).
    Any image Pillow can read (png, jpg, jfif, webp, gif, bmp, tiff…) is converted to PNG, so the page,
    HyperFrames and ffmpeg all read it; phone HEIC photos get a clear message instead of a broken image."""
    from io import BytesIO
    from PIL import Image, ImageOps, UnidentifiedImageError
    if kind not in ("avatar", "logo"):
        raise HTTPException(400, "kind must be avatar or logo")
    data = file.file.read()
    try:
        im = ImageOps.exif_transpose(Image.open(BytesIO(data)))
    except (UnidentifiedImageError, OSError):
        ext = Path(file.filename or "").suffix.lower()
        hint = " (iPhone HEIC: export or screenshot it as JPG/PNG first)" if ext in (".heic", ".heif") else ""
        raise HTTPException(400, f"could not read this image{hint}")
    if kind == "avatar":
        im = ImageOps.fit(im.convert("RGB"), (512, 512), Image.LANCZOS)
    else:
        im = im.convert("RGBA")
        im.thumbnail((1024, 1024), Image.LANCZOS)
    (ASSETS / "logo").mkdir(parents=True, exist_ok=True)
    for old in (ASSETS / "logo").glob(f"{kind}.*"):
        old.unlink()
    dest = ASSETS / "logo" / f"{kind}.png"
    im.save(dest)
    b = get_brand()
    b[kind] = dest.relative_to(ROOT).as_posix()
    _write(BRAND, b)
    return {kind: b[kind], "file": dest.name}


@router.get("/brand-files/{file}")
def brand_file(file: str):
    p = (ASSETS / "logo" / Path(file).name)
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- fonts

def _organize():
    subprocess.run([PY, str(SKILLS / "pro-edit" / "fonts.py"), "organize"], cwd=ROOT, check=False,
                   capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})


@router.get("/api/studio/fonts")
def fonts():
    cat = FONTS / "catalog.json"
    if not cat.exists():
        _organize()
    return _read(cat, {})


@router.post("/api/studio/fonts")
def upload_fonts(files: list[UploadFile]):
    inbox = FONTS / f"_incoming_{int(time.time())}"
    saved = 0
    for f in files:
        name = Path(f.filename or "").name
        ext = Path(name).suffix.lower()
        if ext not in FONT_EXT:
            continue
        _save_upload(f, inbox / name)
        if ext == ".zip":
            with zipfile.ZipFile(inbox / name) as z:
                for m in z.namelist():  # only font files, never paths outside the inbox
                    if Path(m).suffix.lower() in {".ttf", ".otf"} and ".." not in Path(m).parts:
                        z.extract(m, inbox)
            (inbox / name).unlink()
        saved += 1
    _organize()
    return {"saved": saved, "catalog": _read(FONTS / "catalog.json", {})}


@router.get("/font-files/{file}")
def font_file(file: str):
    p = FONTS / Path(file).name
    if not p.is_file() or p.suffix.lower() not in {".ttf", ".otf"}:
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- projects: files, brief, handoff

@router.get("/api/studio/projects/{name}/files")
def files(name: str):
    n, inp, _, _ = _proj(name)
    out = {}
    for kind, (sub, exts) in KINDS.items():
        d = inp / sub if sub else inp
        out[kind] = sorted(p.name for p in d.glob("*") if p.is_file() and p.suffix.lower() in exts) if d.is_dir() else []
    links = inp / "ref" / "links.txt"
    out["links"] = [l for l in links.read_text(encoding="utf-8").splitlines() if l.strip()] if links.exists() else []
    return out


@router.get("/api/studio/projects/{name}/clips")
def get_clips(name: str):
    """Raw clips in the owner's order with a role each (main / retake / broll) — see app/clips.py."""
    return clips.order(_proj(name)[0])


@router.put("/api/studio/projects/{name}/clips")
def put_clips(name: str, body: list = Body(...)):
    return clips.save(_proj(name)[0], body)


@router.post("/api/studio/projects/{name}/upload")
def upload(name: str, kind: str, files: list[UploadFile]):
    n, inp, _, _ = _proj(name)
    if kind not in KINDS:
        raise HTTPException(400, "unknown kind")
    sub, exts = KINDS[kind]
    saved = []
    for f in files:
        fn = Path(f.filename or "").name
        if Path(fn).suffix.lower() in exts:
            _save_upload(f, (inp / sub if sub else inp) / fn)
            saved.append(fn)
    return {"saved": saved}


@router.post("/api/studio/projects/{name}/link")
def add_link(name: str, body: dict):
    n, inp, _, _ = _proj(name)
    url = str(body.get("url", "")).strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "a full http(s) link")
    p = inp / "ref" / "links.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(url + "\n")
    return {"ok": True}


@router.get("/api/studio/projects/{name}/brief")
def get_brief(name: str):
    n, _, work, _ = _proj(name)
    return _read(work / "brief.json", {"goal": "", "topic": "", "cta": "", "length": "", "platform": "", "notes": ""})


@router.put("/api/studio/projects/{name}/brief")
def put_brief(name: str, body: dict):
    n, _, work, _ = _proj(name)
    _write(work / "brief.json", body)
    return body


@router.get("/api/studio/projects/{name}/settings")
def get_settings(name: str):
    """overrides = this project's settings.json; effective = brand.json with the overrides on top (what edits use)."""
    n, _, work, _ = _proj(name)
    over = _read(work / "settings.json", {})
    return {"overrides": over, "brand": get_brand(), "effective": _merge(get_brand(), over)}


@router.put("/api/studio/projects/{name}/settings")
def put_settings(name: str, body: dict):
    """Body: a full or partial settings dict. Only keys that differ from the brand are kept; {} removes the file."""
    n, _, work, _ = _proj(name)
    brand = get_brand()
    over = {}
    for k, v in body.items():
        if k not in DEFAULT_BRAND or k in IDENTITY:
            continue
        if k in NESTED:
            diff = {kk: vv for kk, vv in (v or {}).items() if brand[k].get(kk) != vv}
            if diff:
                over[k] = diff
        elif brand.get(k) != v:
            over[k] = v
    p = work / "settings.json"
    if over:
        _write(p, over)
    elif p.exists():
        p.unlink()
    return get_settings(name)


@router.get("/api/studio/projects/{name}/handoff")
def get_handoff(name: str):
    n, _, work, _ = _proj(name)
    return _read(work / "handoff.json", {"status": "collecting", "note": "", "updated": 0, "by": ""})


@router.put("/api/studio/projects/{name}/handoff")
def put_handoff(name: str, body: dict):
    n, _, work, _ = _proj(name)
    status = body.get("status")
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")
    h = {**get_handoff(name), "status": status, "note": body.get("note", ""), "by": "owner", "updated": time.time()}
    _write(work / "handoff.json", h)
    return h


# ---------------------------------------------------------------- review (storyboard + plan)

@router.get("/api/studio/projects/{name}/review")
def review(name: str):
    n, _, work, _ = _proj(name)
    return _read(work / "review" / "review.json", {})


@router.post("/api/studio/projects/{name}/review/decision")
def decision(name: str, body: dict):
    n, _, work, _ = _proj(name)
    approve = body.get("decision") == "approve"
    d = {"decision": "approve" if approve else "changes", "general": body.get("general", ""),
         "cards": {str(k): v for k, v in (body.get("cards") or {}).items() if str(v).strip()}, "at": time.time()}
    _write(work / "review" / "decision.json", d)
    return put_handoff(name, {"status": "approved" if approve else "changes", "note": d["general"]})


@router.get("/blob/{area}/{name}/{token}")
def blob(area: str, name: str, token: str):
    """Media for in-page players, sent as plain bytes under an address with no .mp4/.m4a in it, so download
    managers (IDM) don't hijack it; the page wraps the bytes into a playable Blob. token = url-safe base64 name."""
    import base64
    n, _, work, outp = _proj(name)
    base = {"work": work, "output": outp, "review": work / "review"}.get(area)
    if base is None:
        raise HTTPException(404)
    try:
        fname = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400)
    p = (base / Path(fname).name).resolve()
    if not p.is_file() or base.resolve() not in p.parents:
        raise HTTPException(404)
    return FileResponse(p, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})


@router.get("/review-media/{name}/{file}")
def review_media(name: str, file: str):
    n, _, work, _ = _proj(name)
    base = work / "review"
    p = (base / Path(file).name).resolve()
    if not p.is_file() or base.resolve() not in p.parents:
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- voice cleaner (pro-edit/audio/voice_clean.py)

VOICE_KEYS = ("denoise", "deess", "presence", "warmth", "compress", "gate")


@router.get("/api/studio/projects/{name}/voice")
def voice_sources(name: str):
    n, inp, work, outp = _proj(name)
    src = [p.name for p in sorted(inp.glob("*")) if p.is_file() and p.suffix.lower() in KINDS["footage"][1] | KINDS["voice"][1]]
    done = [p.name for p in sorted(outp.glob("*_voice.*"))] if outp.is_dir() else []
    return {"sources": src, "done": done}


@router.post("/api/studio/projects/{name}/voice")
def voice_clean(name: str, body: dict):
    """preview: 15 s from `start` → work/<p>/voice_before.m4a + voice_after.m4a (A/B);
    otherwise the whole file → output/<p>/<stem>_voice.mp4 (picture copied) or .m4a."""
    from .server import start_job
    n, inp, work, outp = _proj(name)
    src = inp / Path(str(body.get("file", ""))).name
    if not src.is_file():
        raise HTTPException(400, "pick a file from the project")
    preview = bool(body.get("preview"))
    start = float(body.get("start") or 0)
    script = SKILLS / "pro-edit" / "audio" / "voice_clean.py"
    args = [PY, str(script), str(src), "--preset", body.get("preset", "clean"), "--dehum", str(body.get("dehum", "auto")),
            "--lufs", str(float(body.get("lufs", -16))), "--report"]
    for k in VOICE_KEYS:
        if (body.get("settings") or {}).get(k) is not None:
            args += [f"--{k}", str(float(body["settings"][k]))]
    work.mkdir(parents=True, exist_ok=True)
    if preview:
        out = work / "voice_after.m4a"
        args += ["-o", str(out), "--start", f"{start:.2f}", "--duration", "15"]
    else:
        video = src.suffix.lower() in E.VIDEO_EXT
        out = outp / f"{src.stem}_voice{'.mp4' if video else '.m4a'}"
        args += ["-o", str(out)]

    def fn(job):
        job["message"] = "در حال پاک‌سازی صدا…"
        if preview:  # the untouched 15 s, for an honest A/B
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", "15", "-i", str(src), "-vn",
                            "-c:a", "aac", "-b:a", "192k", str(work / "voice_before.m4a")], check=True)
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                           env={**os.environ, "PYTHONUTF8": "1"})
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout)[-600:])
        lines = r.stdout.strip().splitlines()
        report = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else {}
        return {"file": out.name, "area": "work" if preview else "output", "report": report,
                "text": "\n".join(l for l in lines if not l.startswith("{"))}

    return start_job(n, "voice", fn)


# ---------------------------------------------------------------- outputs

@router.get("/api/studio/projects/{name}/outputs")
def outputs(name: str):
    n, _, _, outp = _proj(name)
    if not outp.is_dir():
        return []
    items = []
    for v in sorted(outp.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        cap = v.with_suffix(".caption.txt")
        items.append({"file": v.name, "mb": round(v.stat().st_size / 1e6, 1), "time": v.stat().st_mtime,
                      "srt": v.with_suffix(".srt").name if v.with_suffix(".srt").exists() else "",
                      "caption": cap.read_text(encoding="utf-8") if cap.exists() else ""})
    return items


# ---------------------------------------------------------------- learn

@router.get("/api/studio/learn")
def learn_list():
    inbox = LEARN / "inbox"
    return sorted(p.name for p in inbox.glob("*") if p.is_file()) if inbox.is_dir() else []


@router.post("/api/studio/learn")
def learn_upload(files: list[UploadFile]):
    saved = []
    for f in files:
        fn = Path(f.filename or "").name
        if fn:
            _save_upload(f, LEARN / "inbox" / fn)
            saved.append(fn)
    return {"saved": saved}


@router.post("/api/studio/learn/link")
def learn_link(body: dict):
    url, note = str(body.get("url", "")).strip(), str(body.get("note", "")).strip()
    if not url and not note:
        raise HTTPException(400, "a link or a note")
    p = LEARN / "inbox" / f"note-{time.strftime('%Y%m%d-%H%M%S')}.md"
    _write_text = f"{url}\n\n{note}\n".strip() + "\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_write_text, encoding="utf-8")
    return {"saved": p.name}


# ---------------------------------------------------------------- open a folder (only these)

@router.post("/api/studio/open")
def open_folder(body: dict):
    area, project = body.get("area"), body.get("project")
    dirs = {"fonts": FONTS, "learn": LEARN / "inbox", "assets": ASSETS}
    if project:
        n, inp, work, outp = _proj(project)
        dirs |= {"input": inp, "output": outp, "work": work}
    d = dirs.get(area)
    if d is None:
        raise HTTPException(400)
    d.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(d)  # noqa: S606 (fixed, known folders only)
    return {"ok": True}
