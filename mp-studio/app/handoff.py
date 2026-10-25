"""Claude's side of the MP Studio handoff (run with .venv/Scripts/python.exe from the repo root:
.venv/Scripts/python.exe mp-studio/app/handoff.py ...).

  handoff.py open <project> [--tab project] [--force]   start the server if needed, open MP Studio as an app window
  handoff.py set <project> <status> [--note "..."]      e.g. working / review / rendering / done
  handoff.py wait <project> [--for ready,approved,changes] [--timeout 3600]
                                                        block until the owner presses a button; prints what they sent
  handoff.py show <project>                              print handoff + brief + last decision (compact)

Run `wait` with the Bash tool's run_in_background: the session is woken when the owner presses
"Send to Claude" / "Approve" / "Send changes" in Studio, with no typing. The window is opened at most
once per 8 hours (the page itself follows the handoff and switches tabs), so it never piles up tabs.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
EDGE = [Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe"]
STAMP = ROOT / "work" / ".studio_window"
sys.path.insert(0, str(ROOT))


def up() -> bool:
    try:
        urllib.request.urlopen(URL + "/api/studio/about", timeout=2)
        return True
    except OSError:
        return False


def start_server():
    venv = ROOT.parent / ".venv" / "Scripts"  # .venv sits at the repo root, next to .claude/
    py = venv / ("pythonw.exe" if (venv / "pythonw.exe").exists() else "python.exe")
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    log = open(ROOT / "work" / "studio_server.log", "ab")
    subprocess.Popen([str(py), "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1", "--port", str(PORT)],
                     cwd=ROOT, stdout=log, stderr=log, creationflags=flags, env={**os.environ, "PYTHONUTF8": "1"})
    for _ in range(40):
        if up():
            return
        time.sleep(0.5)
    sys.exit("MP Studio server did not start; see work/studio_server.log")


def open_window(url: str):
    edge = next((p for p in EDGE if p.exists()), None)
    if edge:  # app mode: its own window, no tabs, no address bar
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1280,900"])
    elif sys.platform == "win32":
        os.startfile(url)  # noqa: S606
    else:
        import webbrowser
        webbrowser.open(url)


def api(path, method="GET", data=None):
    req = urllib.request.Request(URL + path, method=method, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_handoff(project, status, note="", by="claude"):
    p = ROOT / "work" / project / "handoff.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    h = {**read(p, {}), "status": status, "note": note, "by": by, "updated": time.time()}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    return h


def summary(project) -> dict:
    """`brand` is already merged with this project's settings.json (what the edit must use);
    `project_settings` shows which keys the project overrides."""
    w = ROOT / "work" / project
    brand, over = read(ROOT / "assets" / "brand.json", {}), read(w / "settings.json", {})
    merged = {**brand, **over, **{k: {**brand.get(k, {}), **over[k]} for k in ("colors", "fonts", "voice") if k in over}}
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import clips  # raw clips in the owner's order, role main / retake / broll
    return {"handoff": read(w / "handoff.json", {}), "brief": read(w / "brief.json", {}),
            "decision": read(w / "review" / "decision.json", {}), "brand": merged, "project_settings": over,
            "clips": clips.order(project)}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open"); o.add_argument("project"); o.add_argument("--tab", default="project"); o.add_argument("--force", action="store_true")
    s = sub.add_parser("set"); s.add_argument("project"); s.add_argument("status"); s.add_argument("--note", default="")
    w = sub.add_parser("wait"); w.add_argument("project"); w.add_argument("--for", dest="want", default="ready,approved,changes")
    w.add_argument("--timeout", type=float, default=3600)
    sh = sub.add_parser("show"); sh.add_argument("project")
    a = ap.parse_args()
    from app.engine import safe_name
    project = safe_name(a.project)

    if a.cmd == "open":
        (ROOT / "input" / project).mkdir(parents=True, exist_ok=True)
        if not (ROOT / "work" / project / "handoff.json").exists():
            write_handoff(project, "collecting")
        if not up():
            start_server()
        recent = STAMP.exists() and time.time() - STAMP.stat().st_mtime < 8 * 3600
        if a.force or not recent:
            open_window(f"{URL}/studio/#project={project}&tab={a.tab}")
            STAMP.parent.mkdir(exist_ok=True)
            STAMP.touch()
            print(f"MP Studio opened: {URL}/studio/  (project {project}, tab {a.tab})")
        else:
            print(f"MP Studio already open (the page follows project {project}); --force to open another window")
    elif a.cmd == "set":
        h = write_handoff(project, a.status, a.note)
        print(json.dumps(h, ensure_ascii=False))
    elif a.cmd == "wait":
        want = set(a.want.split(","))
        p = ROOT / "work" / project / "handoff.json"
        start = read(p, {}).get("updated", 0)
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            h = read(p, {})
            if h.get("status") in want and h.get("by") == "owner" and h.get("updated", 0) >= start:
                print(json.dumps(summary(project), ensure_ascii=False, separators=(",", ":")))
                return
            time.sleep(2)
        print(f"timeout: no owner action on {project} in {a.timeout:.0f}s")
        sys.exit(2)
    else:
        print(json.dumps(summary(project), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
