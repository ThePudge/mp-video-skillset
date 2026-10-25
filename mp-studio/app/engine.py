"""Video work: proxies, transcription, cut ranges, rendering, subtitles, contact sheets."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".mts", ".3gp"}

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


_dll_dirs = set()


def _add_cuda_dlls():
    """pip's nvidia-cublas / nvidia-cudnn wheels ship DLLs that Windows won't find on its own.
    Called before each model load: the GPU wheels may finish installing while the app runs."""
    site = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for sub in ("cublas", "cudnn"):
        d = site / sub / "bin"
        if d.is_dir() and str(d) not in _dll_dirs:
            os.add_dll_directory(str(d))
            os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]
            _dll_dirs.add(str(d))


# ---------- projects ----------

def safe_name(name: str) -> str:
    name = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip().replace(" ", "-")
    if not name:
        raise ValueError("invalid name")
    return name[:60]


def project_dirs(name: str):
    name = safe_name(name)
    return INPUT / name, WORK / name, OUTPUT / name


def list_projects():
    INPUT.mkdir(exist_ok=True)
    out = []
    for d in sorted(INPUT.iterdir()):
        if d.is_dir():
            out.append(project_info(d.name))
    return out


def project_info(name: str):
    inp, work, outp = project_dirs(name)
    clips = []
    for f in sorted(inp.iterdir()) if inp.is_dir() else []:
        if f.suffix.lower() in VIDEO_EXT:
            stem = f.stem
            clips.append({
                "file": f.name,
                "proxy": (work / f"{stem}.proxy.mp4").exists(),
                "transcript": (work / f"{stem}.transcript.json").exists(),
            })
    outputs = []
    if outp.is_dir():
        for f in sorted(outp.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            outputs.append({"file": f.name, "size": f.stat().st_size})
    return {"name": name, "clips": clips, "outputs": outputs}


# ---------- ffmpeg helpers ----------

def probe_duration(path: Path) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


_encoder = None


def video_encoder():
    """h264_nvenc when the GPU can do it, else libx264."""
    global _encoder
    if _encoder is None:
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                           capture_output=True)
        _encoder = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "20"] if r.returncode == 0 \
            else ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    return _encoder


def run_ffmpeg(args, duration, on_progress):
    """Run ffmpeg with -progress on stdout and report 0..1."""
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-progress", "pipe:1", "-nostats"] + args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace")
    for line in p.stdout:
        if line.startswith("out_time_us=") and duration > 0:
            try:
                on_progress(min(1.0, int(line.split("=")[1]) / 1e6 / duration))
            except ValueError:
                pass
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError(err.strip()[-800:] or "ffmpeg failed")


def make_proxy(src: Path, dst: Path, on_progress):
    """Constant 30 fps, long side <= 1920, 48 kHz audio: phones record VFR, which drifts after cuts."""
    dur = probe_duration(src)
    vf = "fps=30,scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))'"
    tmp = dst.with_suffix(".tmp.mp4")
    run_ffmpeg(["-i", str(src), "-vf", vf, *video_encoder(), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", str(tmp)], dur, on_progress)
    tmp.replace(dst)


# ---------- transcription ----------

_models = {}  # size -> (model, "gpu"|"cpu", number of CUDA dll dirs known at load)


def _load_model(size):
    from faster_whisper import WhisperModel
    _add_cuda_dlls()
    # a CPU model loaded before the GPU libs arrived gets retried on GPU once they are there
    if size in _models and _models[size][1] == "cpu" and len(_dll_dirs) > _models[size][2]:
        del _models[size]
    if size not in _models:
        try:
            _models[size] = (WhisperModel(size, device="cuda", compute_type="int8"), "gpu", len(_dll_dirs))
        except Exception:
            _models[size] = (WhisperModel(size, device="cpu", compute_type="int8"), "cpu", len(_dll_dirs))
    return _models[size][:2]


def transcribe(src: Path, dst: Path, model_size: str, language, on_progress, on_message):
    on_message(f"Loading Whisper {model_size}…")
    model, dev = _load_model(model_size)
    on_message(f"Transcribing on {dev.upper()}…")
    try:
        segs, info = model.transcribe(str(src), language=language or None, word_timestamps=True,
                                      vad_filter=False, beam_size=5)
        segments = _collect(segs, info, on_progress)
    except RuntimeError as e:
        if dev != "gpu":
            raise
        # CUDA libs present but unusable at run time: fall back to CPU once
        on_message(f"GPU failed ({str(e)[:80]}), retrying on CPU…")
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _models[model_size] = (model, "cpu", len(_dll_dirs))
        segs, info = model.transcribe(str(src), language=language or None, word_timestamps=True,
                                      vad_filter=False, beam_size=5)
        segments = _collect(segs, info, on_progress)
    data = {"language": info.language, "duration": info.duration, "segments": segments}
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _collect(segs, info, on_progress):
    out = []
    for s in segs:
        words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
                 for w in (s.words or []) if w.word.strip()]
        if words:
            out.append({"s": round(s.start, 3), "e": round(s.end, 3), "words": words})
        if info.duration:
            on_progress(min(1.0, s.end / info.duration))
    return out


# ---------- cuts ----------

DEFAULT_CUTS = {"removed": [], "keptPauses": [], "maxPause": 0.6, "pad": 0.08}


def load_cuts(work: Path):
    f = work / "cuts.json"
    if f.exists():
        return {**DEFAULT_CUTS, **json.loads(f.read_text(encoding="utf-8"))}
    return dict(DEFAULT_CUTS)


def save_cuts(work: Path, cuts: dict):
    work.mkdir(parents=True, exist_ok=True)
    (work / "cuts.json").write_text(json.dumps(cuts, ensure_ascii=False, indent=1), encoding="utf-8")


def load_timeline(name: str):
    """All clips' words in order. Word id = 'clip:index'."""
    inp, work, _ = project_dirs(name)
    clips = []
    for c in project_info(name)["clips"]:
        stem = Path(c["file"]).stem
        tf = work / f"{stem}.transcript.json"
        if not tf.exists():
            continue
        t = json.loads(tf.read_text(encoding="utf-8"))
        words = [w for seg in t["segments"] for w in seg["words"]]
        clips.append({"file": c["file"], "stem": stem, "duration": t["duration"],
                      "language": t["language"], "segments": t["segments"], "words": words})
    return clips


def compute_ranges(clips, cuts):
    """Keep ranges per clip from kept words. Gaps longer than maxPause are cut unless kept;
    removed words always split a range."""
    removed = set(cuts.get("removed", []))
    kept_pauses = set(cuts.get("keptPauses", []))
    max_pause = float(cuts.get("maxPause", 0.6))
    pad = float(cuts.get("pad", 0.08))
    ranges = []
    for ci, clip in enumerate(clips):
        cur = None
        prev_kept_idx = None
        for wi, w in enumerate(clip["words"]):
            wid = f"{ci}:{wi}"
            if wid in removed:
                if cur:
                    ranges.append(cur)
                    cur = None
                prev_kept_idx = None
                continue
            s, e = max(0.0, w["s"] - pad), min(clip["duration"], w["e"] + pad)
            if cur is not None and prev_kept_idx is not None:
                gap = w["s"] - clip["words"][prev_kept_idx]["e"]
                if gap <= max_pause or f"{ci}:{prev_kept_idx}" in kept_pauses:
                    cur["e"] = e
                    prev_kept_idx = wi
                    continue
                ranges.append(cur)
            cur = {"clip": ci, "s": round(s, 3), "e": round(e, 3)}
            prev_kept_idx = wi
        if cur:
            ranges.append(cur)
    # padding can make neighbours overlap
    merged = []
    for r in ranges:
        if merged and merged[-1]["clip"] == r["clip"] and r["s"] <= merged[-1]["e"]:
            merged[-1]["e"] = max(merged[-1]["e"], r["e"])
        else:
            merged.append(dict(r))
    return merged


# ---------- render ----------

ASPECTS = {
    "original": "",
    "9:16": "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1,",
    "16:9": "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',scale=1920:1080,setsar=1,",
    "1:1": "crop='min(iw,ih)':'min(iw,ih)',scale=1080:1080,setsar=1,",
}


def render(name, ranges, opts, out_path: Path, on_progress):
    _, work, _ = project_dirs(name)
    clips = load_timeline(name)
    used = sorted({r["clip"] for r in ranges})
    idx = {c: i for i, c in enumerate(used)}
    inputs = []
    for c in used:
        inputs += ["-i", str(work / f"{clips[c]['stem']}.proxy.mp4")]

    counts = {c: sum(1 for r in ranges if r["clip"] == c) for c in used}
    lines, seen = [], {c: 0 for c in used}
    for c in used:
        i, n = idx[c], counts[c]
        lines.append(f"[{i}:v]split={n}" + "".join(f"[v{c}_{k}]" for k in range(n)) + ";")
        lines.append(f"[{i}:a]asplit={n}" + "".join(f"[a{c}_{k}]" for k in range(n)) + ";")
    fade = 0.012
    vf_aspect = ASPECTS.get(opts.get("aspect", "original"), "")
    for j, r in enumerate(ranges):
        c = r["clip"]
        k = seen[c]
        seen[c] += 1
        d = r["e"] - r["s"]
        lines.append(f"[v{c}_{k}]trim={r['s']}:{r['e']},setpts=PTS-STARTPTS,{vf_aspect}format=yuv420p[sv{j}];")
        lines.append(f"[a{c}_{k}]atrim={r['s']}:{r['e']},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade},afade=t=out:st={max(0, d - fade):.3f}:d={fade}[sa{j}];")
    n = len(ranges)
    lines.append("".join(f"[sv{j}][sa{j}]" for j in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca];")
    af = []
    if opts.get("denoise"):
        af.append("afftdn=nf=-25")
    if opts.get("loudnorm", True):
        af.append("loudnorm=I=-14:TP=-1.5:LRA=11")
    lines.append(f"[ca]{','.join(af) or 'anull'},aresample=48000[outa]")

    script = work / "render.filter.txt"
    script.write_text("\n".join(lines), encoding="utf-8")
    total = sum(r["e"] - r["s"] for r in ranges)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.mp4")
    run_ffmpeg([*inputs, "-/filter_complex", str(script), "-map", "[cv]", "-map", "[outa]",
                *video_encoder(), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(tmp)], total, on_progress)
    tmp.replace(out_path)


# ---------- subtitles ----------

def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(clips, cuts, ranges, max_words=7, max_len=2.8):
    """Kept words re-timed onto the edited timeline, grouped into short caption lines."""
    removed = set(cuts.get("removed", []))
    timed, offset = [], 0.0
    for r in ranges:
        for wi, w in enumerate(clips[r["clip"]]["words"]):
            if f"{r['clip']}:{wi}" in removed or w["e"] <= r["s"] or w["s"] >= r["e"]:
                continue
            timed.append((offset + max(w["s"], r["s"]) - r["s"], offset + min(w["e"], r["e"]) - r["s"], w["w"]))
        offset += r["e"] - r["s"]
    cues, cur = [], []
    for t in timed:
        if cur and (len(cur) >= max_words or t[1] - cur[0][0] > max_len or t[0] - cur[-1][1] > 0.5):
            cues.append(cur)
            cur = []
        cur.append(t)
    if cur:
        cues.append(cur)
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{_ts(c[0][0])} --> {_ts(c[-1][1])}\n{' '.join(w for _, _, w in c)}\n")
    return "\n".join(out)


# ---------- contact sheet ----------

def contact_sheet(video: Path, dst: Path, cols=6, rows=5):
    dur = probe_duration(video)
    every = max(dur / (cols * rows), 0.5)
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-vf", f"fps=1/{every:.3f},scale=320:-2,tile={cols}x{rows}:padding=4:margin=4",
                    "-frames:v", "1", str(dst)], check=True)
