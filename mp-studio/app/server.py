"""Local video editor: http://127.0.0.1:8765"""
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import engine as E

app = FastAPI(title="Video Editor")
STATIC = Path(__file__).parent / "static"

# ---------- jobs (one worker thread at a time: ffmpeg and Whisper both want the whole machine) ----------

JOBS: dict[str, dict] = {}
_lock = threading.Lock()


def start_job(project, kind, fn):
    job = {"id": uuid.uuid4().hex[:8], "project": project, "kind": kind, "status": "queued",
           "progress": 0.0, "message": "", "error": None, "result": None, "created": time.time()}
    JOBS[job["id"]] = job

    def run():
        with _lock:
            job["status"] = "running"
            try:
                job["result"] = fn(job)
                job["status"], job["progress"] = "done", 1.0
            except Exception as e:  # surfaced in the UI
                job["status"], job["error"] = "error", str(e)

    threading.Thread(target=run, daemon=True).start()
    return job


def _p(job):
    return lambda v: job.__setitem__("progress", round(v, 3))


def _m(job):
    return lambda m: job.__setitem__("message", m)


# ---------- api ----------

def _dirs(name):
    try:
        inp, work, outp = E.project_dirs(name)
    except ValueError:
        raise HTTPException(400, "bad project name")
    return inp, work, outp


@app.get("/api/projects")
def projects():
    return E.list_projects()


@app.post("/api/projects")
def create_project(body: dict):
    try:
        name = E.safe_name(body.get("name", ""))
    except ValueError:
        raise HTTPException(400, "bad project name")
    (E.INPUT / name).mkdir(parents=True, exist_ok=True)
    return E.project_info(name)


@app.get("/api/projects/{name}")
def project(name: str):
    inp, _, _ = _dirs(name)
    if not inp.is_dir():
        raise HTTPException(404)
    return E.project_info(name)


@app.post("/api/projects/{name}/upload")
def upload(name: str, files: list[UploadFile]):
    inp, _, _ = _dirs(name)
    inp.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        fn = Path(f.filename or "").name
        if Path(fn).suffix.lower() not in E.VIDEO_EXT:
            continue
        with open(inp / fn, "wb") as out:
            shutil.copyfileobj(f.file, out, 8 * 1024 * 1024)
        saved.append(fn)
    return {"saved": saved}


@app.post("/api/projects/{name}/process")
def process(name: str, body: dict):
    """Proxy + transcript for every clip that is missing one."""
    inp, work, _ = _dirs(name)
    model = body.get("model", "medium")
    language = body.get("language") or None
    force = bool(body.get("force"))

    def fn(job):
        work.mkdir(parents=True, exist_ok=True)
        clips = E.project_info(name)["clips"]
        steps = [(c, k) for c in clips for k in ("proxy", "transcript") if force or not c[k]]
        for i, (c, kind) in enumerate(steps):
            stem = Path(c["file"]).stem
            base, span = i / max(len(steps), 1), 1 / max(len(steps), 1)
            sub = lambda v: job.__setitem__("progress", round(base + v * span, 3))
            if kind == "proxy":
                job["message"] = f"Preparing {c['file']} (constant frame rate)…"
                E.make_proxy(inp / c["file"], work / f"{stem}.proxy.mp4", sub)
            else:
                prefix = f"{c['file']}: "
                E.transcribe(work / f"{stem}.proxy.mp4", work / f"{stem}.transcript.json",
                             model, language, sub, lambda m: job.__setitem__("message", prefix + m))
        return {"steps": len(steps)}

    return start_job(name, "process", fn)


@app.get("/api/projects/{name}/timeline")
def timeline(name: str):
    _, work, _ = _dirs(name)
    clips = E.load_timeline(name)
    cuts = E.load_cuts(work)
    return {"clips": [{k: c[k] for k in ("file", "stem", "duration", "language", "segments")} for c in clips],
            "cuts": cuts, "ranges": E.compute_ranges(clips, cuts)}


@app.put("/api/projects/{name}/cuts")
def put_cuts(name: str, cuts: dict):
    _, work, _ = _dirs(name)
    cuts = {**E.DEFAULT_CUTS, **cuts}
    E.save_cuts(work, cuts)
    return {"ranges": E.compute_ranges(E.load_timeline(name), cuts)}


@app.post("/api/projects/{name}/render")
def render(name: str, opts: dict):
    _, work, outp = _dirs(name)
    clips = E.load_timeline(name)
    cuts = E.load_cuts(work)
    ranges = E.compute_ranges(clips, cuts)
    if not ranges:
        raise HTTPException(400, "nothing to render: every word is removed")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    aspect = opts.get("aspect", "original")
    base = f"{name}_{aspect.replace(':', 'x')}_{stamp}"

    def fn(job):
        job["message"] = "Rendering…"
        out = outp / f"{base}.mp4"
        E.render(name, ranges, opts, out, _p(job))
        (outp / f"{base}.srt").write_text(E.make_srt(clips, cuts, ranges), encoding="utf-8")
        job["message"] = "Making contact sheet…"
        E.contact_sheet(out, outp / f"{base}.sheet.png")
        return {"file": out.name}

    return start_job(name, "render", fn)


@app.get("/api/projects/{name}/srt")
def srt(name: str):
    _, work, _ = _dirs(name)
    clips = E.load_timeline(name)
    cuts = E.load_cuts(work)
    return PlainTextResponse(E.make_srt(clips, cuts, E.compute_ranges(clips, cuts)))


@app.get("/api/jobs")
def jobs(project: str | None = None):
    js = [j for j in JOBS.values() if not project or j["project"] == project]
    return sorted(js, key=lambda j: j["created"], reverse=True)[:20]


@app.get("/api/jobs/{jid}")
def job(jid: str):
    if jid not in JOBS:
        raise HTTPException(404)
    return JOBS[jid]


# ---------- media (work/ and output/ only; FileResponse handles Range for seeking) ----------

@app.get("/media/{area}/{name}/{file}")
def media(area: str, name: str, file: str):
    _, work, outp = _dirs(name)
    base = {"work": work, "output": outp}.get(area)
    if base is None:
        raise HTTPException(404)
    p = (base / Path(file).name).resolve()
    if not p.is_file() or base.resolve() not in p.parents:
        raise HTTPException(404)
    return FileResponse(p)


# ---------- MP Studio (the main window); the text cutter stays at /index.html ----------

from . import studio  # noqa: E402

app.include_router(studio.router)


@app.get("/")
def home():
    return RedirectResponse("/studio/")


app.mount("/studio", StaticFiles(directory=STATIC / "studio", html=True), name="studio")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
