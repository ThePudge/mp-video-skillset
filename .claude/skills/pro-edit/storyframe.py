"""One storyboard frame = a mock-up of the finished shot, built in about a second from the raw take:

  layout applied   full frame (with the EDL punch-in zoom) | "window" (pop-out window on the dark
                   canvas) | "split" (panel on top, speaker below)
  panel area       a frame of the rendered HyperFrames panel when one exists (work/<p>/panel/*.mp4),
                   else a SKETCH card from cards.json: {"sketch": {"title", "subtitle", "kind"}}
  captions/motion  master.ass burned at that exact moment when it exists (captions with keywords,
                   ass-motion cards, CTA) — else the card's words as a caption
  motion tag       the card's "move" in a small tag, so the owner reads what will animate

Used by storyboard.py (no render needed). Persian text goes through libass, so it shapes correctly.
"""
import json
import subprocess
from pathlib import Path

W, H = 1080, 1920
WIN = dict(scale=0.9, box_y=1240, box_w=960, box_h=560, anchor_y=790)
PANEL_Y = {"window": 140, "split": 0}
PANEL_H = 768


def _col(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _ts(s):
    m, s = divmod(max(0.0, s), 60)
    return f"0:{int(m):02}:{s:05.2f}"


def _esc(p: Path) -> str:  # filter-graph path (relative, forward slashes) — run with cwd set
    return p.as_posix().replace(":", r"\:").replace("'", r"\'")


def layout_filter(layout: str, zoom: float) -> str:
    """ffmpeg graph from a 1080x1920 frame [0:v] to [lay]."""
    if layout == "window":
        sc, bw, bh, by = WIN["scale"], WIN["box_w"], WIN["box_h"], WIN["box_y"]
        sw, sh = round(W * sc / 2) * 2, round(H * sc / 2) * 2
        oy = 2 * round((by - WIN["anchor_y"] * sc) / 2)
        # canvas made FROM the frame (painted over), so canvas and window share one timestamp
        return (f"[0:v]scale={W}:{H},format=yuv420p,split[c0][w0];"
                f"[c0]drawbox=x=0:y=0:w=iw:h=ih:color=0x0E0E0E:t=fill,"
                f"geq=lum='if(lt(mod(X,26),3)*lt(mod(Y,26),3),lum(X,Y)+22,lum(X,Y))':cb=128:cr=128[cv];"
                f"[w0]scale={sw}:{sh},crop={bw}:{bh}:{(sw - bw) // 2}:{by - oy}[win];"
                f"[cv][win]overlay={(W - bw) // 2}:{by}[lay]")
    if layout == "split":
        return (f"[0:v]scale={W}:{H},format=yuv420p,split[c0][s0];"
                f"[c0]crop={W}:{PANEL_H}:0:0,drawbox=x=0:y=0:w=iw:h=ih:color=0x0E0E0E:t=fill[top];"
                f"[s0]crop={W}:{H - PANEL_H}:0:400[spk];[top][spk]vstack[lay]")
    z = max(1.0, zoom)
    return f"[0:v]crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.35,scale={W}:{H}[lay]"


def sketch_ass(card: dict, layout: str, brand: dict, with_caption: bool) -> str:
    """ASS for the parts that don't exist yet: planned graphic (sketch card), motion tag, caption."""
    f = brand.get("fonts", {})
    cap_font, disp = f.get("captions") or "Vazirmatn", f.get("display") or "Lalezar"
    acc, dark, text = (_col(brand.get("colors", {}).get(k, d)) for k, d in
                       (("accent", "#FFC400"), ("dark", "#111111"), ("text", "#FFFFFF")))
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Card,{disp},84,&H00111111,&H00111111,&H00F2F2F2,&H00F2F2F2,1,0,0,0,100,100,0,0,3,34,0,5,80,80,0,1\n"
            f"Style: Sub,{cap_font},50,{text},{text},{dark},{dark},1,0,0,0,100,100,0,0,1,4,0,5,80,80,0,1\n"
            f"Style: Kind,{cap_font},40,{dark},{dark},{acc},{acc},1,0,0,0,100,100,0,0,3,14,0,5,80,80,0,1\n"
            f"Style: Tag,{cap_font},38,{text},{text},&H80000000,&H80000000,1,0,0,0,100,100,0,0,3,14,0,7,40,40,40,1\n"
            f"Style: Cap,{cap_font},84,{text},{text},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,0,2,60,60,410,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev, T = [], f"{_ts(0)},{_ts(5)}"
    sk = card.get("sketch") or {}
    if sk:
        cy = (PANEL_Y.get(layout, 0) + PANEL_H // 2) if layout in PANEL_Y else 420
        if sk.get("kind"):
            ev.append(f"Dialogue: 2,{T},Kind,,0,0,0,,{{\\pos({W // 2},{cy - 170})}}{sk['kind']}")
        if sk.get("title"):
            ev.append(f"Dialogue: 2,{T},Card,,0,0,0,,{{\\pos({W // 2},{cy})}}{sk['title']}")
        if sk.get("subtitle"):
            ev.append(f"Dialogue: 2,{T},Sub,,0,0,0,,{{\\pos({W // 2},{cy + 130})}}{sk['subtitle']}")
    if card.get("move"):
        ev.append(f"Dialogue: 3,{T},Tag,,0,0,0,,▶ {card['move']}")
    if with_caption and card.get("words"):
        words = card["words"].replace("*", "")
        # where captions sit in each layout: above the window / on the seam / on the chest
        pos = {"window": f"{{\\an5\\pos({W // 2},1080)}}", "split": f"{{\\an5\\pos({W // 2},{PANEL_H})}}"}.get(layout, "")
        ev.append(f"Dialogue: 1,{T},Cap,,0,0,0,,{pos}{words}")
    return head + "\n".join(ev) + "\n"


def panel_video(edit: Path):
    for name in ("panel_dark.mp4", "panel.mp4"):
        p = edit.parent / "panel" / name
        if p.exists():
            return p
    return None


def compose(edit: Path, card: dict, out_mid: float, src: Path, src_t: float, zoom: float,
            brand: dict, fonts: Path, out: Path):
    """Write one 540-px mock-up frame of the finished shot to `out`."""
    layout = {"popout": "window", "window": "window", "split": "split"}.get(str(card.get("layout", "")).split()[0].lower()
                                                                          if card.get("layout") else "", "full")
    master = edit / "master.ass"
    sk_file = edit.parent / "review" / f"_{out.stem}.ass"
    sk_file.write_text(sketch_ass(card, layout, brand, with_caption=not master.exists()), encoding="utf-8-sig")
    rel = lambda p: _esc(Path(__import__("os").path.relpath(p, edit)))
    g = [layout_filter(layout, zoom if layout == "full" else 1.0)]
    inputs = ["-ss", f"{src_t:.3f}", "-i", str(src)]
    cur = "lay"
    pv = panel_video(edit) if layout in PANEL_Y else None
    if pv:  # real panel graphics at this moment
        inputs += ["-ss", f"{out_mid:.3f}", "-i", str(pv)]
        g.append(f"[1:v]scale={W}:-2[pv];[{cur}][pv]overlay=0:{PANEL_Y[layout]}[lp]")
        cur = "lp"
    mask = edit / "glass_mask.ass"
    if master.exists() and mask.exists():  # frosted-glass captions: blur inside the boxes, like finish.py
        shift = f"setpts=PTS+{out_mid:.3f}/TB"
        g.append(f"[{cur}]split=3[gA][gB][gK];[gB]gblur=sigma=24,eq=brightness=0.03:saturation=1.15[gBl];"
                 f"[gK]format=rgb24,drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill,{shift},"
                 f"subtitles={rel(mask)}:fontsdir={rel(fonts)},setpts=PTS-STARTPTS,format=gray[gM];"
                 f"[gBl][gM]alphamerge[gG];[gA][gG]overlay=format=auto[gl]")
        cur = "gl"
    burn = []
    if master.exists():  # exact captions + ass-motion cards at this moment
        burn.append(f"setpts=PTS+{out_mid:.3f}/TB,subtitles={rel(master)}:fontsdir={rel(fonts)},setpts=PTS-STARTPTS")
    burn.append(f"subtitles={rel(sk_file)}:fontsdir={rel(fonts)}")
    g.append(f"[{cur}]{','.join(burn)},scale=540:-2[out]")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(g), "-map", "[out]",
                        "-frames:v", "1", "-q:v", "4", str(out)], cwd=edit, capture_output=True, text=True)
    sk_file.unlink(missing_ok=True)
    if r.returncode:  # never block the review on a mock-up: fall back to the plain still
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{src_t:.3f}", "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=540:-2", "-q:v", "4", str(out)], check=True)
        return False
    return True


def load_brand(edit: Path) -> dict:
    studio = edit.parents[2]
    import sys
    sys.path.insert(0, str(studio / "app"))
    try:
        import handoff
        return handoff.summary(edit.parent.name).get("brand", {})
    except Exception:
        return {}
