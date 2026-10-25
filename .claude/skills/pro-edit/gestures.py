"""Find the owner's hand gestures in talking-head takes, so motion elements can land where and when
the hands move (a hand raised to «show» something, pointing, counting on fingers, a swipe, both
hands spreading apart).

Google MediaPipe hand landmarker (21 points per hand, local, CPU). The model is downloaded once to
mp-studio/models/hand_landmarker.task. All takes are analysed in parallel (one process per take).

  gestures.py <edit_dir> [--videos <dir with the takes or proxies>] [--fps 10] [--edl] [--sheet]

Writes <edit_dir>/gestures.json:
  {"<take stem>": [{"t0", "t1", "peak", "kind", "x", "y", "hands", "dir", "fingers", "words"}, …]}
  times are seconds in the take; x/y = the active hand at the peak (index fingertip for point), 0..1 of the frame
  kind: count (1–3 fingers held up — the owner counting items) | point (index finger out, "dir" = where) |
        spread (two hands move apart) | swipe (fast sideways move) | open (open palm held up, «this») |
        pinch (thumb + index together: small/precise) | raise (hand comes up, no clear pose) | move
--edl  also maps every gesture onto the cut (edl.json) → "out" times, and drops gestures that were cut.
--sheet one contact sheet of the gesture peaks (number, kind, time) → <edit_dir>/gestures.jpg
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from os import cpu_count
from pathlib import Path

import cv2
import numpy as np

W, H = 432, 768  # analysis size (9:16)
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v"}
MODEL = Path(__file__).resolve().parents[3] / "mp-studio" / "models" / "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
TIPS, PIPS = (8, 12, 16, 20), (6, 10, 14, 18)


def frames(path: Path, fps: float):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    p.wait()


def pose(lm) -> tuple:
    """(extended finger count incl. thumb, pose name) from 21 normalised landmarks."""
    d = lambda i, j: ((lm[i].x - lm[j].x) ** 2 + (lm[i].y - lm[j].y) ** 2) ** 0.5
    fingers = [d(t, 0) > d(p, 0) * 1.15 for t, p in zip(TIPS, PIPS)]
    thumb = d(4, 17) > d(3, 17) * 1.1 and d(4, 5) > d(0, 5) * 0.45
    n = sum(fingers) + thumb
    if d(4, 8) < d(0, 5) * 0.25 and not any(fingers[1:]):
        return n, "pinch"
    if fingers == [True, False, False, False]:
        return n, "point"
    if n >= 5 or sum(fingers) == 4:
        return n, "open"
    return n, "other"


def track(path: Path, fps: float) -> list:
    """Per frame: hands [{x, y, tipx, tipy, dx, dy, n, pose}] (normalised)."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    opts = vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODEL)),
                                        running_mode=vision.RunningMode.VIDEO, num_hands=2,
                                        min_hand_detection_confidence=0.5, min_tracking_confidence=0.5)
    out = []
    with vision.HandLandmarker.create_from_options(opts) as det:
        for i, f in enumerate(frames(path, fps)):
            r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(f)),
                                     int(i * 1000 / fps))
            hs = []
            for lm in r.hand_landmarks:
                n, ps = pose(lm)
                hs.append({"x": sum(p.x for p in lm) / 21, "y": sum(p.y for p in lm) / 21,
                           "tipx": lm[8].x, "tipy": lm[8].y, "dx": lm[8].x - lm[5].x, "dy": lm[8].y - lm[5].y,
                           "n": n, "pose": ps})
            out.append({"t": i / fps, "hands": hs})
    return out


def events(tr: list, fps: float) -> list:
    """Group frames with a raised / moving / posed hand into gesture events."""
    ev, cur, prev = [], None, None
    for fr in tr:
        hs = fr["hands"]
        speed, dx, spread = 0.0, 0.0, 0.0
        if hs and prev and prev["hands"]:
            a = hs[0]
            b = min(prev["hands"], key=lambda q: (q["x"] - a["x"]) ** 2 + (q["y"] - a["y"]) ** 2)
            dx = a["x"] - b["x"]
            speed = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5 * fps
            if len(hs) == 2 and len(prev["hands"]) == 2:
                spread = (abs(hs[0]["x"] - hs[1]["x"]) - abs(prev["hands"][0]["x"] - prev["hands"][1]["x"])) * fps
        up = [h for h in hs if h["y"] < 0.62]  # above the lower chest (face ≈ 0.25–0.5 in a 9:16 talking head)
        posed = [h for h in up if h["pose"] in ("point", "open", "pinch")]
        active = bool(up) and (speed > 0.3 or bool(posed) or abs(spread) > 0.4 or len(up) == 2)
        if active:
            if cur is None:
                cur = {"t0": fr["t"], "frames": []}
            cur["frames"].append({"t": fr["t"], "speed": speed, "dx": dx, "spread": spread, "hands": up})
            cur["t1"] = fr["t"]
        elif cur is not None and fr["t"] - cur["t1"] > 0.3:
            ev.append(cur)
            cur = None
        prev = fr
    if cur is not None:
        ev.append(cur)
    res = []
    for e in ev:
        fr = e["frames"]
        if e["t1"] - e["t0"] < 0.3:
            continue
        top = lambda f: min(f["hands"], key=lambda h: h["y"])
        poses = [top(f)["pose"] for f in fr]
        counts = [top(f)["n"] for f in fr if top(f)["pose"] != "pinch"]
        main_pose = max(set(poses), key=poses.count)
        held = poses.count(main_pose) / len(poses)
        n_mode = max(set(counts), key=counts.count) if counts else 0
        mean_speed = sum(f["speed"] for f in fr) / len(fr)
        dx = sum(f["dx"] for f in fr)
        sp = sum(f["spread"] for f in fr) / fps
        if sp > 0.12:
            kind = "spread"
        elif abs(dx) > 0.2 and mean_speed > 0.6:
            kind = "swipe"
        elif main_pose == "point" and held > 0.4:
            kind = "point"
        elif main_pose == "pinch" and held > 0.4:
            kind = "pinch"
        elif 1 <= n_mode <= 3 and counts.count(n_mode) / len(fr) > 0.5 and mean_speed < 0.5 and main_pose != "open":
            kind = "count"
        elif main_pose == "open" and held > 0.4:
            kind = "open"
        elif mean_speed < 0.6:
            kind = "raise"
        else:
            kind = "move"
        pk = max(fr, key=lambda f: f["speed"] * 0.3 + (1 - top(f)["y"]))  # highest hand, a little speed
        h = top(pk)
        pt = kind == "point"
        x, y = (h["tipx"], h["tipy"]) if pt else (h["x"], h["y"])
        if pt:
            d = "up" if -h["dy"] > abs(h["dx"]) else "right" if h["dx"] > 0 else "left"
        else:
            d = "right" if dx > 0.1 else "left" if dx < -0.1 else "-"
        res.append({"t0": round(e["t0"], 2), "t1": round(e["t1"], 2), "peak": round(pk["t"], 2), "kind": kind,
                    "x": round(x, 2), "y": round(y, 2), "hands": len(pk["hands"]), "dir": d,
                    "fingers": n_mode if kind == "count" else None})
    return res


def one(args):
    path, fps = args
    return path.stem, events(track(path, fps), fps)


def to_out(edl: dict, stem: str, t: float):
    pos = 0.0
    for r in edl["ranges"]:
        if r["source"] == stem and r["start"] <= t <= r["end"]:
            return round(pos + t - r["start"], 2)
        pos += r["end"] - r["start"]
    return None


def words_at(edit: Path, stem: str, t0: float, t1: float) -> str:
    p = edit / "transcripts" / f"{stem}.json"
    if not p.exists():
        return ""
    ws = json.loads(p.read_text(encoding="utf-8")).get("words", [])
    return " ".join(w["text"].strip() for w in ws if w.get("type", "word") == "word" and w["end"] > t0 and w["start"] < t1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("--videos", type=Path, help="folder of takes (default: ../proxy if present)")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--edl", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    edit = a.edit_dir.resolve()
    vdir = a.videos or (edit.parent / "proxy" if (edit.parent / "proxy").is_dir() else None)
    if vdir is None:
        sys.exit("pass --videos <folder of takes>")
    vids = sorted(p for p in Path(vdir).iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not MODEL.exists():  # Google's official MediaPipe model, once (~8 MB)
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    with ProcessPoolExecutor(max_workers=min(len(vids), cpu_count() or 4)) as pool:
        res = dict(pool.map(one, [(v, a.fps) for v in vids]))
    edl = json.loads((edit / "edl.json").read_text(encoding="utf-8")) if a.edl and (edit / "edl.json").exists() else None
    n, kinds = 0, {}
    for stem, evs in res.items():
        for e in evs:
            e["words"] = words_at(edit, stem, e["t0"] - 0.3, e["t1"] + 0.3)
            if edl:
                e["out"] = to_out(edl, stem, e["peak"])
        if edl:
            res[stem] = [e for e in evs if e["out"] is not None]
        for e in res[stem]:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        n += len(res[stem])
    (edit / "gestures.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n} gestures in {len(res)} takes {kinds} → {edit / 'gestures.json'}")
    if a.sheet and n:
        sheet(res, {v.stem: v for v in vids}, edit / "gestures.jpg")


def sheet(res, paths, out: Path, cols=6, tw=180):
    items = [(s, e) for s, evs in res.items() for e in evs][:36]
    th = tw * 16 // 9
    rows = (len(items) + cols - 1) // cols
    canvas = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for i, (s, e) in enumerate(items):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{e['peak']:.2f}", "-i", str(paths[s]), "-frames:v", "1",
                            "-vf", f"scale={tw}:{th}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
        if len(r.stdout) == tw * th * 3:
            im = np.frombuffer(r.stdout, np.uint8).reshape(th, tw, 3).copy()
            cv2.circle(im, (int(e["x"] * tw), int(e["y"] * th)), 9, (0, 255, 255), 2)
            label = f"{i + 1} {e['kind']}{e['fingers'] or ''} " + (f"@{e['out']}" if "out" in e else f"{s[-5:]} {e['peak']}")
            cv2.rectangle(im, (0, 0), (tw, 16), (0, 0, 0), -1)
            cv2.putText(im, label, (3, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
            y, x = (i // cols) * th, (i % cols) * tw
            canvas[y:y + th, x:x + tw] = im
    cv2.imwrite(str(out), canvas, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"sheet: {out}")


if __name__ == "__main__":
    main()
