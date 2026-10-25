"""Motion kit: a scene list (JSON) -> a full HyperFrames project of pro motion graphics.

  kit.py build <spec.json> -o <project_dir>      write index.html + one composition per scene
  kit.py icons <word> [<word> ...]                search the icon library by meaning (Lucide tags)
  kit.py demo -o <project_dir>                    every component once (look book)

Then, in <project_dir>: `npx hyperframes check`, `npx hyperframes render --output motion.mp4`.
Claude writes only the short spec, never the HTML, so a whole video costs a few hundred tokens.

Themes: "futuristic" (deep space, neon accent, glass, aurora, perspective grid, HUD, particles),
"apple-dark", "apple-light" (SF-like glass cards, segmented tabs, soft shadows).
Icons: Lucide (ISC, 1,600+, pinned) by name, e.g. "scissors"; brand logos from Simple Icons (CC0)
as "brand:instagram". Fetched once into $ROOT/assets/icons/, inlined as SVG (they draw on).
Never Apple SF Symbols (their licence forbids use outside Apple apps).

spec.json (times in seconds on the OUTPUT timeline; a scene's "at" values are seconds inside it):
{
  "size": [1080, 1920], "theme": "futuristic", "accent": "#FFC400", "accent2": "#4DD8FF",
  "dir": "rtl", "digits": "fa",
  "fonts": {"body": "Vazirmatn-Bold.ttf", "display": "Lalezar-Regular.ttf"},   // files in mp-studio/fonts
  "avatar": "assets/logo/avatar.png",            // optional, project-relative, for "cta"
  "stage_y": [220, 1380],                        // vertical band for scenes (captions live below)
  "scenes": [
    {"type": "title", "t0": 0, "t1": 3.2, "kicker": "۳ ترفند", "text": "ادیت *حرفه‌ای* با هوش مصنوعی", "sub": "..."},
    {"type": "icon_card", "t0": 3.2, "t1": 6, "icon": "scissors", "title": "...", "sub": "..."},
    {"type": "icon_grid", "t0": 6, "t1": 9, "items": [{"icon": "mic", "label": "صدا"}, ...], "counter": "مهارت"},
    {"type": "tabs", "t0": 9, "t1": 14, "tabs": ["قبل", "حین", "بعد"], "at": [0.4, 1.8, 3.2],
       "panes": [{"icon": "clock", "text": "..."}, ...]},
    {"type": "stat", "t0": 14, "t1": 17, "value": 87, "suffix": "٪", "label": "...", "ring": 87},
    {"type": "list", "t0": 17, "t1": 22, "title": "...", "items": ["...", "..."], "at": [0.5, 1.6, 2.7]},
    {"type": "chat", "t0": 22, "t1": 26, "messages": [{"from": "them", "text": "..."}, {"from": "me", "text": "..."}], "at": [0.3, 1.6]},
    {"type": "notify", "t0": 26, "t1": 29, "items": [{"icon": "brand:instagram", "app": "Instagram", "title": "...", "body": "..."}], "at": [0.3]},
    {"type": "compare", "t0": 29, "t1": 32, "bad": {"icon": "x", "title": "...", "sub": "..."}, "good": {"icon": "check", "title": "...", "sub": "..."}, "at": 1.0},
    {"type": "flow", "t0": 32, "t1": 35, "nodes": [{"icon": "mic", "label": "صدا"}, {"icon": "sparkles", "label": "Claude"}, {"icon": "film", "label": "ویدیو"}]},
    {"type": "bars", "t0": 35, "t1": 38, "title": "...", "bars": [{"label": "...", "value": 30}, {"label": "...", "value": 90}]},
    {"type": "quote", "t0": 38, "t1": 41, "text": "...", "by": "..."},
    {"type": "cta", "t0": 41, "t1": 45, "handle": "page", "bio": "...", "keyword": "ادیت", "at": 1.2}
  ]
}
*stars* mark the accent keyword in "text"/"title". Optional per scene: "enter": "blur" | "rise" |
"zoom" (default blur), "accent" to recolour one scene.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]   # repo root (.claude/ lives here)
DATA = ROOT / "mp-studio"                      # everything else: fonts, assets, input, work, output
LUCIDE = "1.61.0"
SIMPLE_ICONS = "15.16.0"
ICON_DIR = DATA / "assets" / "icons"
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"

THEMES = {
    "futuristic": dict(bg="#05060B", ink="#EAF2FF", muted="#8A97B5", card="rgba(14,20,36,.62)",
                       line="rgba(120,200,255,.22)", track="rgba(255,255,255,.07)", pill="rgba(77,216,255,.18)",
                       radius=30, shadow="0 0 0 1px rgba(120,200,255,.18), 0 20px 60px rgba(0,0,0,.55), 0 0 60px rgba(77,216,255,.10)"),
    "apple-dark": dict(bg="#000000", ink="#F5F5F7", muted="#8E8E93", card="rgba(28,28,30,.78)",
                       line="rgba(255,255,255,.08)", track="#1C1C1E", pill="#3A3A3C",
                       radius=34, shadow="0 1px 0 rgba(255,255,255,.06) inset, 0 24px 60px rgba(0,0,0,.6)"),
    "apple-light": dict(bg="#F5F5F7", ink="#1D1D1F", muted="#6E6E73", card="rgba(255,255,255,.86)",
                        line="rgba(0,0,0,.06)", track="#E3E3E8", pill="#FFFFFF",
                        radius=34, shadow="0 1px 2px rgba(0,0,0,.06), 0 18px 50px rgba(0,0,0,.10)"),
    # Restrained, print-like (Liamrjohnston/remotion-motion-graphics-skill's rules): flat accents, no glow/glass
    "editorial": dict(bg="#F3F0EA", ink="#1B1A18", muted="#6B665E", card="#FFFFFF", line="rgba(0,0,0,.09)",
                      track="#E7E2DA", pill="#FFFFFF", radius=16, shadow="0 1px 2px rgba(0,0,0,.06), 0 14px 34px rgba(40,30,20,.10)"),
    "editorial-dark": dict(bg="#1C1C1E", ink="#F2F0EC", muted="#9A968F", card="#26262A", line="rgba(255,255,255,.08)",
                           track="#323236", pill="#3A3A3F", radius=16, shadow="0 1px 0 rgba(255,255,255,.05) inset, 0 16px 40px rgba(0,0,0,.45)"),
}
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


# ---------------------------------------------------------------- icons

def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read().decode("utf-8")


def icon_svg(name: str, size: int = 64, stroke: float = 1.8) -> str:
    """Inline SVG for a Lucide icon ("scissors") or a brand logo ("brand:instagram")."""
    brand = name.startswith("brand:")
    key = name.split(":", 1)[1] if brand else name
    path = ICON_DIR / ("simple" if brand else "lucide") / f"{key}.svg"
    if not path.exists():
        url = (f"https://unpkg.com/simple-icons@{SIMPLE_ICONS}/icons/{key}.svg" if brand
               else f"https://unpkg.com/lucide-static@{LUCIDE}/icons/{key}.svg")
        try:
            svg = _fetch(url)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"icon '{name}' not found ({e}). Search names with: kit.py icons <word>")
        if "<svg" not in svg:
            sys.exit(f"icon '{name}' not found. Search names with: kit.py icons <word>")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
    svg = re.sub(r'\s(width|height|class)="[^"]*"', "", svg, count=3)
    if brand:
        svg = svg.replace("<svg", f'<svg width="{size}" height="{size}" fill="currentColor"', 1)
    else:
        svg = svg.replace("<svg", f'<svg width="{size}" height="{size}" class="draw"', 1)
        svg = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{stroke}"', svg)
        svg = re.sub(r"<(path|circle|line|rect|polyline|polygon|ellipse)\b", r'<\1 pathLength="1"', svg)
    return re.sub(r"\s+", " ", svg)


def search_icons(words: list[str]) -> None:
    cache = ICON_DIR / "lucide-tags.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(_fetch(f"https://unpkg.com/lucide-static@{LUCIDE}/tags.json"), encoding="utf-8")
    tags = json.loads(cache.read_text(encoding="utf-8"))
    for w in words:
        w = w.lower()
        hits = [n for n, t in tags.items() if w in n] + [n for n, t in tags.items() if w not in n and any(w in x for x in t)]
        print(f"{w}: {' '.join(hits[:24]) or '(none)'}")


# ---------------------------------------------------------------- text helpers

def esc(s) -> str:
    return html.escape(str(s), quote=False)


def mark(s: str) -> str:
    """*keyword* -> accent span."""
    return re.sub(r"\*(.+?)\*", r'<span class="kw">\1</span>', esc(s))


def num(n, spec) -> str:
    s = f"{n:,}" if isinstance(n, int) else str(n)
    return s.translate(FA) if spec.get("digits") == "fa" else s


def js(s) -> str:
    return json.dumps(s, ensure_ascii=False)


# ---------------------------------------------------------------- motion helpers (GSAP lines)

FEEL = {"v": "punchy"}  # set per build from spec/brand: "punchy" (3D slam, no bounce) | "playful" (overshoot)


def pop(sel, t, y=34, d=0.42, s=0.9):
    if FEEL["v"] == "punchy":  # slams in from deep on its word and lands dead (no spring)
        return (f'tl.fromTo("{sel}", {{opacity:0, scale:0.32, y:{y * 2}, rotationX:28, transformPerspective:1400}}, '
                f'{{opacity:1, scale:1, y:0, rotationX:0, duration:{d}, ease:"expo.out"}}, {t:.3f});')
    return f'tl.fromTo("{sel}", {{opacity:0, y:{y}, scale:{s}}}, {{opacity:1, y:0, scale:1, duration:{d}, ease:"back.out(1.6)"}}, {t:.3f});'


def blur_in(sel, t, d=0.5, y=24):
    return (f'tl.fromTo("{sel}", {{opacity:0, y:{y}, filter:"blur(14px)"}}, '
            f'{{opacity:1, y:0, filter:"blur(0px)", duration:{d}, ease:"expo.out"}}, {t:.3f});')


def draw(sel, t, d=0.7):
    return (f'tl.fromTo("{sel} .draw *", {{strokeDasharray:1, strokeDashoffset:1}}, '
            f'{{strokeDashoffset:0, duration:{d}, ease:"power2.inOut", stagger:0.05}}, {t:.3f});')


def words_in(sel, t, stagger=0.07):
    return (f'tl.fromTo("{sel} .w", {{opacity:0, y:40, filter:"blur(12px)"}}, '
            f'{{opacity:1, y:0, filter:"blur(0px)", duration:0.55, ease:"expo.out", stagger:{stagger}}}, {t:.3f});')


def split_words(text: str) -> str:
    out = []
    for part in re.split(r"(\*.+?\*)", text):
        if not part:
            continue
        kw = part.startswith("*")
        for w in part.strip("*").split():
            out.append(f'<span class="w{" kw" if kw else ""}">{esc(w)}</span>')
    return " ".join(out)


def counter(sel, t, to, d, spec, suffix=""):
    fa = "true" if spec.get("digits") == "fa" else "false"
    return (f'(function(){{const o={{v:0}}; const el=document.querySelector("{sel}"); '
            f'tl.to(o, {{v:{to}, duration:{d}, ease:"power2.out", onUpdate:()=>{{let s=Math.round(o.v).toLocaleString("en-US"); '
            f'if({fa}) s=s.replace(/[0-9]/g,c=>"۰۱۲۳۴۵۶۷۸۹"[c]); el.textContent=s+{js(suffix)};}}}}, {t:.3f});}})();')


# ---------------------------------------------------------------- components: (html, [js lines])

def c_title(s, sid, spec):
    h = ""
    if s.get("kicker"):
        h += f'<div id="{sid}-k" class="chip">{mark(s["kicker"])}</div>'
    h += f'<div id="{sid}-h" class="h1">{split_words(s["text"])}</div>'
    if s.get("sub"):
        h += f'<div id="{sid}-s" class="sub">{mark(s["sub"])}</div>'
    j = [pop(f"#{sid}-k", 0.05)] if s.get("kicker") else []
    j += [words_in(f"#{sid}-h", 0.18), 'tl.fromTo("#%s-h .kw", {textShadow:"0 0 0px var(--accent)"}, {textShadow:"0 0 38px var(--accent)", duration:0.6, yoyo:true, repeat:1}, 0.7);' % sid]
    if s.get("sub"):
        j.append(blur_in(f"#{sid}-s", 0.75))
    return f'<div class="col center">{h}</div>', j


def c_icon_card(s, sid, spec):
    h = (f'<div id="{sid}-c" class="card col center" style="width:820px;padding:64px 56px">'
         f'<div id="{sid}-i" class="tile big">{icon_svg(s["icon"], 132, 1.6)}<div class="ring"></div></div>'
         f'<div id="{sid}-t" class="h2" style="margin-top:44px">{mark(s["title"])}</div>'
         + (f'<div id="{sid}-s" class="sub">{mark(s["sub"])}</div>' if s.get("sub") else "") + "</div>")
    j = [pop(f"#{sid}-c", 0.05, y=60), pop(f"#{sid}-i", 0.22, s=0.6), draw(f"#{sid}-i", 0.3),
         "" if FEEL["v"] == "punchy" else
         f'tl.fromTo("#{sid}-i .ring", {{rotation:0}}, {{rotation:180, duration:{max(1.0, s["t1"] - s["t0"]):.2f}, ease:"none"}}, 0);',
         blur_in(f"#{sid}-t", 0.45)]
    if s.get("sub"):
        j.append(blur_in(f"#{sid}-s", 0.62))
    return h, j


def c_icon_grid(s, sid, spec):
    items = s["items"]
    cols = s.get("cols", 4 if len(items) > 6 else 3)   # wide, short stages (a 1080x768 panel): "cols": 6
    cells = "".join(f'<div id="{sid}-g{i}" class="cell col center"><div class="tile">{icon_svg(it["icon"], 64)}</div>'
                    f'<div class="lbl">{esc(it.get("label", ""))}</div></div>' for i, it in enumerate(items))
    chip = (f'<div id="{sid}-n" class="chip big"><span id="{sid}-cnt">{num(0, spec)}</span> {esc(s["counter"])}</div>'
            if s.get("counter") else "")
    h = f'<div class="col center">{chip}<div class="grid" style="grid-template-columns:repeat({cols},1fr)">{cells}</div></div>'
    st = s.get("stagger", 0.083)
    j = [pop(f"#{sid}-n", 0.05)] if chip else []
    j += [f'tl.fromTo("#{sid} .cell", {{opacity:0, y:30, scale:0.7}}, {{opacity:1, y:0, scale:1, duration:0.4, ease:"back.out(1.8)", stagger:{st}}}, 0.25);',
          draw(f"#{sid}", 0.35, 0.6)]
    if chip:
        j.append(counter(f"#{sid}-cnt", 0.25, len(items), st * len(items) + 0.2, spec))
    return h, j


def c_tabs(s, sid, spec):
    tabs, at = s["tabs"], s.get("at", [0.4])
    w = min(300, 900 // len(tabs))
    seg = "".join(f'<div id="{sid}-tb{i}" class="seg-i" style="width:{w}px">{esc(t)}</div>' for i, t in enumerate(tabs))
    panes = "".join(
        f'<div id="{sid}-p{i}" class="pane col center"><div class="tile big">{icon_svg(p["icon"], 110)}</div>'
        f'<div class="h2" style="margin-top:36px">{mark(p["text"])}</div>'
        + (f'<div class="sub">{mark(p["sub"])}</div>' if p.get("sub") else "") + "</div>"
        for i, p in enumerate(s.get("panes", [])))
    rtl = spec.get("dir") == "rtl"
    h = (f'<div class="col center"><div id="{sid}-seg" class="seg"><div id="{sid}-pill" class="seg-pill" style="width:{w}px"></div>{seg}</div>'
         f'<div class="card panes" style="width:900px;height:560px;margin-top:48px">{panes}</div></div>')
    j = [pop(f"#{sid}-seg", 0.05), pop(f"#{sid} .panes", 0.15, y=50)]
    for k, t in enumerate(at):
        x = (-1 if rtl else 1) * k * w
        j.append(f'tl.to("#{sid}-pill", {{x:{x}, duration:0.42, ease:"expo.inOut"}}, {t:.3f});')
        j.append(f'tl.to("#{sid} .seg-i", {{color:"var(--muted)", duration:0.2}}, {t:.3f}); tl.to("#{sid}-tb{k}", {{color:"var(--ink)", duration:0.2}}, {t:.3f});')
        if k < len(s.get("panes", [])):
            if k:
                j.append(f'tl.to("#{sid}-p{k - 1}", {{opacity:0, x:{60 if rtl else -60}, filter:"blur(10px)", duration:0.3}}, {t:.3f});')
            j.append(f'tl.fromTo("#{sid}-p{k}", {{opacity:0, x:{-60 if rtl else 60}, filter:"blur(10px)"}}, {{opacity:1, x:0, filter:"blur(0px)", duration:0.45, ease:"expo.out"}}, {t + 0.08:.3f});')
            j.append(draw(f"#{sid}-p{k}", t + 0.15))
    return h, j


def c_stat(s, sid, spec):
    ring = s.get("ring")
    svg = ""
    if ring is not None:
        svg = ('<svg class="gauge" viewBox="0 0 200 200" width="560" height="560"><circle cx="100" cy="100" r="86" class="g-track"/>'
               f'<circle id="{sid}-arc" cx="100" cy="100" r="86" class="g-arc" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100"/></svg>')
    h = (f'<div class="col center" style="position:relative">{svg}<div class="statbox col center">'
         f'<div class="stat"><span id="{sid}-v">{num(0, spec)}</span><span class="kw">{esc(s.get("suffix", ""))}</span></div>'
         f'<div id="{sid}-l" class="sub" style="max-width:640px">{mark(s.get("label", ""))}</div></div></div>')
    d = s.get("count_s", 1.2)
    j = [pop(f"#{sid} .statbox", 0.05, s=0.8), counter(f"#{sid}-v", 0.15, s["value"], d, spec), blur_in(f"#{sid}-l", 0.5)]
    if ring is not None:
        j.append(f'tl.to("#{sid}-arc", {{strokeDashoffset:{100 - ring}, duration:{d}, ease:"power2.out"}}, 0.15);')
    return h, j


def c_list(s, sid, spec):
    items, at = s["items"], s.get("at") or [0.4 + i * 0.9 for i in range(len(s["items"]))]
    rows = "".join(
        f'<div id="{sid}-r{i}" class="row"><div class="dot">{num(i + 1, spec)}</div>'
        f'<div class="rtxt">{mark(t)}</div><div class="ok">{icon_svg("check", 34, 3)}</div></div>' for i, t in enumerate(items))
    title = f'<div id="{sid}-t" class="h2" style="margin-bottom:30px">{mark(s["title"])}</div>' if s.get("title") else ""
    h = f'<div class="card" style="width:900px;padding:48px">{title}{rows}</div>'
    j = [pop(f"#{sid} .card", 0.02, y=50), f'tl.fromTo("#{sid} .row", {{opacity:0, y:20}}, {{opacity:0.32, y:0, filter:"blur(3px)", duration:0.35, stagger:0.06}}, 0.15);']
    if title:
        j.append(blur_in(f"#{sid}-t", 0.1))
    for i, t in enumerate(at[:len(items)]):
        j.append(f'tl.to("#{sid}-r{i}", {{opacity:1, filter:"blur(0px)", backgroundColor:"var(--pill)", duration:0.3}}, {t:.3f});')
        j.append(f'tl.to("#{sid}-r{i} .dot", {{backgroundColor:"var(--accent)", color:"#000", scale:1.12, duration:0.25, ease:"back.out(2)"}}, {t:.3f});')
        j.append(f'tl.fromTo("#{sid}-r{i} .ok", {{opacity:0, scale:0.4}}, {{opacity:1, scale:1, duration:0.3, ease:"back.out(2.4)"}}, {t + 0.12:.3f});')
        if i:
            j.append(f'tl.to("#{sid}-r{i - 1}", {{backgroundColor:"rgba(0,0,0,0)", duration:0.3}}, {t:.3f});')
    return h, j


def c_chat(s, sid, spec):
    msgs, at = s["messages"], s.get("at") or [0.3 + i * 1.2 for i in range(len(s["messages"]))]
    rows = "".join(
        f'<div class="bwrap {m.get("from", "them")}"><div id="{sid}-ty{i}" class="typing"><i></i><i></i><i></i></div>'
        f'<div id="{sid}-b{i}" class="bubble">{mark(m["text"])}</div></div>' for i, m in enumerate(msgs))
    h = f'<div class="chat">{rows}</div>'
    j = []
    for i, t in enumerate(at[:len(msgs)]):
        j.append(f'tl.fromTo("#{sid}-ty{i}", {{opacity:0, scale:0.6}}, {{opacity:1, scale:1, duration:0.2}}, {max(0, t - 0.55):.3f});')
        j.append(f'tl.fromTo("#{sid}-ty{i} i", {{y:0}}, {{y:-8, duration:0.16, yoyo:true, repeat:1, stagger:0.08}}, {max(0, t - 0.45):.3f});')
        j.append(f'tl.to("#{sid}-ty{i}", {{opacity:0, scale:0.6, duration:0.12}}, {t:.3f});')
        j.append(pop(f"#{sid}-b{i}", t, y=24, s=0.7))
    return h, j


def c_notify(s, sid, spec):
    items, at = s["items"], s.get("at") or [0.3 + i * 0.9 for i in range(len(s["items"]))]
    cards = "".join(
        f'<div id="{sid}-n{i}" class="note"><div class="appic">{icon_svg(n.get("icon", "bell"), 46)}</div>'
        f'<div style="flex:1"><div class="nhead"><b>{esc(n.get("app", ""))}</b><span>{esc(n.get("time", "now"))}</span></div>'
        f'<div class="ntitle">{mark(n["title"])}</div><div class="nbody">{mark(n.get("body", ""))}</div></div></div>'
        for i, n in enumerate(items))
    h = f'<div class="col" style="gap:22px;width:940px">{cards}</div>'
    j = [f'tl.fromTo("#{sid}-n{i}", {{opacity:0, y:-140, scale:0.92}}, {{opacity:1, y:0, scale:1, duration:0.55, ease:"expo.out"}}, {t:.3f});'
         for i, t in enumerate(at[:len(items)])]
    return h, j


def c_compare(s, sid, spec):
    def side(k, d):
        return (f'<div id="{sid}-{k}" class="card col center cmp {k}"><div class="tile">{icon_svg(d.get("icon", "x" if k == "bad" else "check"), 64, 2.4)}</div>'
                f'<div class="h3">{mark(d["title"])}</div><div class="sub small">{mark(d.get("sub", ""))}</div></div>')
    h = f'<div class="cmpwrap">{side("bad", s["bad"])}<div class="vs">VS</div>{side("good", s["good"])}</div>'
    t = s.get("at", 1.0)
    j = [pop(f"#{sid}-bad", 0.05, y=50), pop(f"#{sid}-good", 0.2, y=50), pop(f"#{sid} .vs", 0.3, s=0.4),
         f'tl.to("#{sid}-bad", {{opacity:0.45, scale:0.94, filter:"grayscale(1)", duration:0.4}}, {t:.3f});',
         f'tl.to("#{sid}-good", {{scale:1.06, boxShadow:"0 0 0 2px var(--accent), 0 0 70px var(--accent)", duration:0.45, ease:"back.out(2)"}}, {t:.3f});',
         draw(f"#{sid}-good", t)]
    return h, j


def c_flow(s, sid, spec):
    nodes = s["nodes"]
    parts = []
    for i, n in enumerate(nodes):
        if i:
            parts.append(f'<div id="{sid}-l{i}" class="link"><div class="beam"></div></div>')
        parts.append(f'<div id="{sid}-f{i}" class="fnode col center"><div class="tile big">{icon_svg(n["icon"], 92)}</div>'
                     f'<div class="lbl big">{esc(n.get("label", ""))}</div></div>')
    # "layout": "row" lays the nodes side by side (right to left in RTL); default: row on short stages
    # (a 1080x940 panel), where a 3–4 node column overflows the top
    y0, y1 = spec.get("stage_y", [220, 1380])
    row = s.get("layout", "row" if y1 - y0 < 900 else "column") == "row"
    W = spec.get("size", [1080, 1920])[0]
    fit = min(1.0, (W - 160) / (len(nodes) * 230 + (len(nodes) - 1) * 84)) if row else 1.0  # ~230 px a node, 84 a beam
    h = f'<div class="flow{" row" if row else ""}" style="scale:{fit:.3f}">{"".join(parts)}</div>'
    step = s.get("step", 0.55)
    axis = "scaleX" if row else "scaleY"
    j = []
    for i in range(len(nodes)):
        t = 0.1 + i * step
        if i:
            j.append(f'tl.fromTo("#{sid}-l{i} .beam", {{{axis}:0}}, {{{axis}:1, duration:{step * 0.7:.2f}, ease:"power2.inOut"}}, {t - step * 0.6:.3f});')
        j += [pop(f"#{sid}-f{i}", t, s=0.6), draw(f"#{sid}-f{i}", t + 0.05)]
    return h, j


def c_bars(s, sid, spec):
    bars = s["bars"]
    top = max(b["value"] for b in bars) or 1
    cols = "".join(
        f'<div class="bcol col"><div class="bval" id="{sid}-v{i}">{num(0, spec)}</div>'
        f'<div class="bar"><div id="{sid}-b{i}" class="fill{" hi" if b.get("hi") or b["value"] == top else ""}" style="height:{b["value"] / top * 100:.1f}%"></div></div>'
        f'<div class="lbl">{esc(b["label"])}</div></div>' for i, b in enumerate(bars))
    title = f'<div class="h2" style="margin-bottom:40px">{mark(s["title"])}</div>' if s.get("title") else ""
    h = f'<div class="card col center" style="width:920px;padding:56px">{title}<div class="bars">{cols}</div></div>'
    j = [pop(f"#{sid} .card", 0.02, y=50)]
    for i, b in enumerate(bars):
        t = 0.3 + i * 0.12
        j.append(f'tl.fromTo("#{sid}-b{i}", {{scaleY:0}}, {{scaleY:1, duration:0.8, ease:"expo.out"}}, {t:.3f});')
        j.append(counter(f"#{sid}-v{i}", t, b["value"], 0.8, spec, b.get("suffix", "")))
    return h, j


def c_quote(s, sid, spec):
    h = (f'<div class="col center" style="max-width:900px"><div id="{sid}-q" class="qmark">“</div>'
         f'<div id="{sid}-h" class="h2 quote">{split_words(s["text"])}</div>'
         + (f'<div id="{sid}-by" class="sub">— {esc(s["by"])}</div>' if s.get("by") else "") + "</div>")
    j = [pop(f"#{sid}-q", 0.0, s=0.5), words_in(f"#{sid}-h", 0.2, 0.09)]
    if s.get("by"):
        j.append(blur_in(f"#{sid}-by", 0.9))
    return h, j


def c_cta(s, sid, spec):
    av = spec.get("avatar")
    s = {**s, "handle": s.get("handle") or spec.get("handle", ""), "bio": s.get("bio") or spec.get("bio", "")}
    pic = (f'<img src="{av}" class="avatar">' if av else f'<div class="avatar tile">{icon_svg("user", 70)}</div>')
    t = s.get("at", 1.2)
    h = (f'<div id="{sid}-c" class="card" style="width:900px;padding:48px">'
         f'<div style="display:flex;align-items:center;gap:28px">{pic}<div style="flex:1">'
         f'<div class="handle">@{esc(s.get("handle", ""))}</div><div class="sub small" style="margin:6px 0 0">{esc(s.get("bio", ""))}</div></div></div>'
         f'<div class="followbox"><div id="{sid}-f1" class="follow">{esc(s.get("follow", "دنبال کردن"))}</div>'
         f'<div id="{sid}-f2" class="follow done">{icon_svg("check", 36, 3)} {esc(s.get("following", "دنبال می‌کنی"))}</div></div>'
         + (f'<div class="comment"><span>{esc(s.get("comment_hint", "کامنت بنویس:"))}</span> <b id="{sid}-kw">{esc(s["keyword"])}</b></div>' if s.get("keyword") else "")
         + "</div>")
    j = [pop(f"#{sid}-c", 0.05, y=60),
         f'tl.fromTo("#{sid}-f1", {{scale:1}}, {{scale:0.94, duration:0.1, yoyo:true, repeat:1}}, {t - 0.2:.3f});',
         f'tl.to("#{sid}-f1", {{opacity:0, duration:0.15}}, {t:.3f});',
         f'tl.fromTo("#{sid}-f2", {{opacity:0, scale:0.9}}, {{opacity:1, scale:1, duration:0.3, ease:"back.out(2)"}}, {t:.3f});']
    if s.get("keyword"):
        j.append(f'tl.fromTo("#{sid}-kw", {{clipPath:"inset(0 0 0 100%)"}}, {{clipPath:"inset(0 0 0 0%)", duration:0.6, ease:"none"}}, {t + 0.6:.3f});')
    return h, j


def rough_marker(seed: int) -> str:
    """An irregular marker stroke (not a perfect rectangle), drawn behind a phrase."""
    r = random.Random(seed)
    top = [(x, r.uniform(1.5, 4.5)) for x in range(0, 101, 10)]
    bot = [(x, r.uniform(15.5, 19)) for x in range(100, -1, -10)]
    pts = [(r.uniform(-1.5, 1), r.uniform(4, 8))] + top + [(r.uniform(99, 101.5), r.uniform(9, 14))] + bot
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return f'<svg viewBox="0 0 100 20" preserveAspectRatio="none"><path d="{d}"/></svg>'


def c_article(s, sid, spec):
    """Article excerpt (editorial): ==phrase== gets a hand-drawn marker that wipes in behind it, in order."""
    n = [0]

    def hl(text):
        out = []
        for part in re.split(r"(==.+?==)", text):
            if part.startswith("=="):
                out.append(f'<span class="hl" id="{sid}-m{n[0]}">{rough_marker(n[0] * 7 + 3)}<span class="hlt">{esc(part[2:-2])}</span></span>')
                n[0] += 1
            else:
                out.append(mark(part))
        return "".join(out)

    body = "".join(f"<p>{hl(p)}</p>" for p in s.get("body", []))
    h = (f'<div id="{sid}-a" class="card article">'
         + (f'<div class="a-src">{esc(s["source"])}</div>' if s.get("source") else "")
         + f'<div class="a-head">{hl(s["headline"])}</div>'
         + (f'<div class="a-by">{esc(s["byline"])}</div>' if s.get("byline") else "")
         + (f'<div class="a-body">{body}</div>' if body else "") + "</div>")
    rtl = spec.get("dir", "rtl") == "rtl"
    frm = "inset(0 0 0 100%)" if rtl else "inset(0 100% 0 0)"
    at = s.get("at") or [0.9 + 0.7 * i for i in range(n[0])]
    j = [f'tl.fromTo("#{sid}-a", {{opacity:0, y:30, filter:"blur(8px)", rotationX:6, transformPerspective:1600}}, '
         f'{{opacity:1, y:0, filter:"blur(0px)", rotationX:0, duration:0.6, ease:"power2.out"}}, 0);',
         f'tl.fromTo("#{sid}-a", {{scale:1}}, {{scale:1.035, duration:{max(1.0, s["t1"] - s["t0"]):.2f}, ease:"none"}}, 0);']
    for i, t in enumerate(at[:n[0]]):
        j.append(f'tl.fromTo("#{sid}-m{i} svg", {{clipPath:"{frm}"}}, {{clipPath:"inset(0 0 0 0%)", duration:0.45, ease:"power1.inOut"}}, {t:.3f});')
    return h, j


LIBS = {"lottie": "https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie.min.js",
        "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"}
RAPIER = "https://cdn.jsdelivr.net/npm/@dimforge/rapier2d-compat@0.14.0/rapier.es.js"


def scene_libs(scenes) -> str:
    """Script tags a composition needs (HyperFrames lints that Three.js/Lottie load in the scene that uses them)."""
    need = {LIBS["lottie"] for s in scenes if s["type"] == "lottie"} | {LIBS["three"] for s in scenes if s["type"] == "phone3d"}
    return "".join(f'<script src="{u}"></script>' for u in sorted(need))


def build_ready(key, promise_js):
    """Tell the renderer to wait for async setup (Rapier wasm, textures) before the first frame."""
    return (f'window.__hf = window.__hf || {{}}; window.__hf.buildReady = window.__hf.buildReady || {{}}; '
            f'window.__hf.buildReady["{key}"] = {promise_js};')


def c_lottie(s, sid, spec):
    """A Lottie (After Effects) animation, e.g. from LottieFiles (download as Lottie JSON), seeked by HyperFrames."""
    size = s.get("size", 640)
    h = (f'<div class="col center"><div id="{sid}-l" style="width:{size}px;height:{size}px"></div>'
         + (f'<div id="{sid}-t" class="h2" style="margin-top:10px">{mark(s["title"])}</div>' if s.get("title") else "") + "</div>")
    j = [f'window.__hfLottie = window.__hfLottie || []; window.__hfLottie.push(lottie.loadAnimation({{container: document.getElementById("{sid}-l"), '
         f'renderer: "svg", loop: {str(bool(s.get("loop", False))).lower()}, autoplay: false, path: "{s["_src"]}"}}));',
         pop(f"#{sid}-l", 0.0, s=0.85)]
    if s.get("title"):
        j.append(blur_in(f"#{sid}-t", 0.35))
    return h, j


def c_phone3d(s, sid, spec):
    """A real 3D phone (Three.js): bevelled body, screen with an image or a title card, swings in and floats."""
    W, H = spec.get("size", [1080, 1920])
    y0, y1 = spec.get("stage_y", [220, 1380])
    cw, ch = W, y1 - y0
    dur = s["t1"] - s["t0"]
    img = s.get("_src", "")
    ac = s.get("accent", spec.get("accent", "#FFC400"))
    h = f'<canvas id="{sid}-c" width="{cw}" height="{ch}" style="position:absolute;left:0;top:0"></canvas>'
    j = [f"""(function(){{
  const cv=document.getElementById("{sid}-c"), r=new THREE.WebGLRenderer({{canvas:cv, antialias:true, alpha:true, preserveDrawingBuffer:true}});
  r.setPixelRatio(1); r.setSize({cw},{ch},false); r.outputColorSpace=THREE.SRGBColorSpace;
  const sc=new THREE.Scene(), cam=new THREE.PerspectiveCamera(30,{cw}/{ch},0.1,100); cam.position.set(0,0.3,16);
  sc.add(new THREE.HemisphereLight(0xffffff,0x334466,1.4)); const d=new THREE.DirectionalLight(0xffffff,2.2); d.position.set(3,4,6); sc.add(d);
  const rim=new THREE.DirectionalLight(new THREE.Color("{ac}"),2.5); rim.position.set(-5,1,-3); sc.add(rim);
  const sh=new THREE.Shape(), w=1.5, hh=3.1, rr=0.32; sh.moveTo(-w+rr,-hh); sh.lineTo(w-rr,-hh); sh.quadraticCurveTo(w,-hh,w,-hh+rr);
  sh.lineTo(w,hh-rr); sh.quadraticCurveTo(w,hh,w-rr,hh); sh.lineTo(-w+rr,hh); sh.quadraticCurveTo(-w,hh,-w,hh-rr); sh.lineTo(-w,-hh+rr); sh.quadraticCurveTo(-w,-hh,-w+rr,-hh);
  const body=new THREE.Mesh(new THREE.ExtrudeGeometry(sh,{{depth:0.28,bevelEnabled:true,bevelSize:0.06,bevelThickness:0.06,bevelSegments:6,curveSegments:24}}),
    new THREE.MeshStandardMaterial({{color:0x1b1d22,metalness:0.85,roughness:0.28}})); body.position.z=-0.14;
  const g=new THREE.Group(); g.add(body); sc.add(g);
  const tc=document.createElement("canvas"); tc.width=600; tc.height=1240; const x=tc.getContext("2d");
  const grad=x.createLinearGradient(0,0,0,1240); grad.addColorStop(0,"#101528"); grad.addColorStop(1,"#05060B"); x.fillStyle=grad; x.fillRect(0,0,600,1240);
  x.fillStyle="{ac}"; x.font="bold 88px body, sans-serif"; x.textAlign="center"; x.direction="{spec.get('dir', 'rtl')}"; x.fillText({js(s.get('screen_text', ''))},300,620);
  const tex=new THREE.CanvasTexture(tc); tex.colorSpace=THREE.SRGBColorSpace;
  const scr=new THREE.Mesh(new THREE.PlaneGeometry(2.86,5.96), new THREE.MeshBasicMaterial({{map:tex}})); scr.position.z=0.215; g.add(scr);
  const ready = "{img}" ? new Promise(res=>{{ new THREE.TextureLoader().load("{img}", t=>{{ t.colorSpace=THREE.SRGBColorSpace; scr.material.map=t; scr.material.needsUpdate=true; res(); }}, undefined, res); }}) : Promise.resolve();
  {build_ready(sid + "-tex", "ready")}
  const D={dur:.3f}, o={{t:0}}, e=p=>1-Math.pow(1-p,3);
  function draw(t){{ const p=e(Math.min(1,t/1.1)); g.rotation.y=-1.25+0.95*p+0.10*Math.sin(t*1.3); g.rotation.x=0.18*(1-p)+0.05*Math.sin(t*0.9);
    g.position.y=-0.6*(1-p)+0.08*Math.sin(t*1.6); g.scale.setScalar(0.75+0.25*p); r.render(sc,cam); }}
  tl.to(o,{{t:D,duration:D,ease:"none",onUpdate:()=>draw(o.t)}},0); draw(0);
}})();"""]
    if s.get("title"):
        h += f'<div id="{sid}-t" class="h2" style="position:absolute;bottom:20px;left:0;right:0;text-align:center">{mark(s["title"])}</div>'
        j.append(blur_in(f"#{sid}-t", 0.6))
    return h, j


def c_physics(s, sid, spec):
    """Icons drop, collide and pile up (Rapier 2D physics, simulated once up front, then replayed by time)."""
    W, H = spec.get("size", [1080, 1920])
    y0, y1 = spec.get("stage_y", [220, 1380])
    items = s.get("items") or ["sparkles", "zap", "heart", "star", "music", "camera"]
    n = s.get("count", len(items))
    size = s.get("tile", 150)
    dur, at = s["t1"] - s["t0"], s.get("at", 0.2)
    tiles = "".join(f'<div class="ph tile" id="{sid}-p{i}" style="width:{size}px;height:{size}px;border-radius:{size * .26:.0f}px;position:absolute;left:0;top:0">'
                    f'{icon_svg(items[i % len(items)], int(size * .5), 2)}</div>' for i in range(n))
    title = f'<div id="{sid}-t" class="h2" style="position:absolute;top:30px;left:0;right:0;text-align:center">{mark(s["title"])}</div>' if s.get("title") else ""
    h = f'<div style="position:absolute;inset:0">{title}{tiles}</div>'
    floor, sw = (y1 - y0) - 40, W
    j = [f"""(function(){{
  const n={n}, S=50, sz={size}, floor={floor}, at={at}, D={dur:.3f}, fps=60, steps=Math.ceil((D-at)*fps)+2;
  const els=[...Array(n)].map((_,i)=>document.getElementById("{sid}-p"+i)), frames=[];
  function R(a){{return function(){{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;}}}}
  const ready = import("{RAPIER}").then(m=>m.default.init().then(()=>{{
    const RA=m.default, w=new RA.World({{x:0,y:-22}}), rnd=R(5);
    w.createCollider(RA.ColliderDesc.cuboid({sw / 2}/S, 1).setTranslation({sw / 2}/S, -1).setFriction(0.8));
    w.createCollider(RA.ColliderDesc.cuboid(1, 40).setTranslation(-1+60/S, 20)); w.createCollider(RA.ColliderDesc.cuboid(1, 40).setTranslation({sw}/S+1-60/S, 20));
    const bodies=els.map((_,i)=>{{ const b=w.createRigidBody(RA.RigidBodyDesc.dynamic().setTranslation((140+rnd()*({sw}-280))/S, (floor+260+i*170)/S)
      .setRotation((rnd()-.5)*1.2).setAngvel((rnd()-.5)*6)); w.createCollider(RA.ColliderDesc.cuboid(sz/2/S, sz/2/S).setRestitution(0.35).setFriction(0.6), b); return b; }});
    for(let k=0;k<steps;k++){{ frames.push(bodies.map(b=>{{const p=b.translation(); return [p.x*S, floor-p.y*S, b.rotation()];}})); w.step(); }}
  }}));
  {build_ready(sid + "-physics", "ready")}
  const o={{t:0}};
  function draw(t){{ if(!frames.length) return; const k=Math.max(0,Math.min(frames.length-1,Math.round((t-at)*fps)));
    els.forEach((el,i)=>{{ const [x,y,r]=frames[k][i]; el.style.transform=`translate(${{x-sz/2}}px,${{y-sz/2}}px) rotate(${{-r}}rad)`; el.style.opacity=t<at?0:1; }}); }}
  tl.to(o,{{t:D,duration:D,ease:"none",onUpdate:()=>draw(o.t)}},0); ready.then(()=>draw(o.t));
}})();"""]
    if title:
        j.append(blur_in(f"#{sid}-t", 0.05))
    return h, j


COMPONENTS = {"article": c_article, "lottie": c_lottie, "phone3d": c_phone3d, "physics": c_physics, "title": c_title, "icon_card": c_icon_card, "icon_grid": c_icon_grid, "tabs": c_tabs, "stat": c_stat,
              "list": c_list, "chat": c_chat, "notify": c_notify, "compare": c_compare, "flow": c_flow,
              "bars": c_bars, "quote": c_quote, "cta": c_cta}


# ---------------------------------------------------------------- styles

def fonts_of(spec) -> dict:
    """Font roles -> files in mp-studio/fonts. Both roles always exist (the renderer has no Persian fallback)."""
    f = {"body": "Vazirmatn-Bold.ttf", "display": "Lalezar-Regular.ttf", **spec.get("fonts", {})}
    if not (DATA / "fonts" / f["display"]).exists():
        f["display"] = f["body"]
    return f


def css(spec, th) -> str:
    theme = spec.get("theme", "futuristic")
    ac = spec.get("accent", "#FFC400")
    flat = theme.startswith("editorial")
    ac2 = spec.get("accent2", "#4DD8FF" if theme == "futuristic" else th["ink"] if flat else "#0A84FF")  # Apple: system blue icons
    light = theme in ("apple-light", "editorial")
    f = fonts_of(spec)
    faces = "".join(f"@font-face {{ font-family: '{role}'; src: url('assets/fonts/{file}'); }}\n" for role, file in f.items())
    fut = theme == "futuristic"
    tile_bg = (f"linear-gradient(145deg, {ac2}33, {ac}22)" if fut else "var(--track)")
    hl = spec.get("highlight", "rgba(255,214,10,.42)" if theme != "editorial-dark" else "rgba(255,200,0,.30)")
    return faces + f"""
#root {{ position:absolute; inset:0; direction:{spec.get('dir', 'rtl')}; color:var(--ink);
  font-family:'body', 'Inter', sans-serif; font-weight:700;
  --accent:{ac}; --accent2:{ac2}; --ink:{th['ink']}; --muted:{th['muted']}; --card:{th['card']};
  --line:{th['line']}; --track:{th['track']}; --pill:{th['pill']}; --r:{th['radius']}px; }}
.stage {{ position:absolute; left:0; right:0; display:flex; align-items:center; justify-content:center; }}
.col {{ display:flex; flex-direction:column; }} .center {{ align-items:center; text-align:center; }}
.card {{ background:var(--card); border-radius:var(--r); box-shadow:{th['shadow']}; {"" if flat else "backdrop-filter:blur(24px);"}
  border:1px solid var(--line); }}
.article {{ width:930px; padding:64px 60px 56px; text-align:start; }}
.a-src {{ font-family:Inter, 'body', sans-serif; font-size:28px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }}
.a-head {{ font-family:'display', 'body', serif; font-size:72px; line-height:1.28; margin:22px 0 18px; }}
.a-by {{ font-size:28px; color:var(--muted); font-weight:400; padding-bottom:26px; border-bottom:1px solid var(--line); }}
.a-body {{ font-size:38px; line-height:1.7; font-weight:400; margin-top:26px; }}
.hl {{ position:relative; display:inline-block; }}
.hl svg {{ position:absolute; left:-10px; right:-10px; top:12%; height:82%; width:calc(100% + 20px); z-index:0; overflow:visible; }}
.hlt {{ position:relative; z-index:1; }}
.hl path {{ fill:{hl}; }}
#world {{ position:absolute; left:0; top:0; transform-origin:0 0; }}
.wscene {{ position:absolute; }}
.h1 {{ font-family:'display', 'body', 'Inter', sans-serif; font-size:118px; line-height:1.18; max-width:960px; }}
.h2 {{ font-size:66px; line-height:1.3; }} .h3 {{ font-size:46px; margin-top:24px; }}
.sub {{ font-size:40px; color:var(--muted); font-weight:400; margin-top:26px; line-height:1.45; }} .small {{ font-size:32px; }}
.w {{ display:inline-block; }}
.kw {{ color:{"color-mix(in srgb, var(--accent) 62%, #000)" if light else "var(--accent)"}; {"text-shadow:0 0 30px " + ac + "66;" if fut else ""} }}
.chip {{ display:inline-flex; gap:12px; align-items:center; padding:12px 30px; border-radius:999px; font-size:36px;
  background:var(--pill); border:1px solid var(--line); margin-bottom:34px; }} .chip.big {{ font-size:46px; }}
.tile {{ width:118px; height:118px; border-radius:32px; display:flex; align-items:center; justify-content:center; position:relative;
  background:{tile_bg}; border:1px solid var(--line); color:var(--accent2); {"box-shadow:0 0 40px " + ac2 + "33;" if fut else ""} }}
.tile.big {{ width:210px; height:210px; border-radius:56px; }}
.ring {{ position:absolute; inset:-18px; border-radius:50%; border:2px dashed {ac2 if fut else th['line']}; opacity:{.55 if fut else 0}; }}
.grid {{ display:grid; gap:40px 46px; margin-top:20px; }} .cell {{ gap:14px; }}
.lbl {{ font-size:30px; color:var(--muted); font-weight:400; max-width:200px; }} .lbl.big {{ font-size:38px; color:var(--ink); }}
.seg {{ position:relative; display:flex; padding:8px; border-radius:999px; background:var(--track); border:1px solid var(--line); }}
.seg-pill {{ position:absolute; top:8px; bottom:8px; {"right" if spec.get("dir", "rtl") == "rtl" else "left"}:8px; border-radius:999px;
  background:{("linear-gradient(135deg," + ac2 + "55," + ac + "44)") if fut else th['pill']};
  box-shadow:{"0 0 30px " + ac2 + "55" if fut else "0 3px 12px rgba(0,0,0,.18)"}; }}
.seg-i {{ position:relative; z-index:1; text-align:center; padding:22px 0; font-size:38px; color:var(--muted); }}
.panes {{ position:relative; }} .pane {{ position:absolute; inset:0; justify-content:center; opacity:0; padding:40px; }}
.gauge {{ position:absolute; top:50%; left:50%; margin:-280px 0 0 -280px; transform:rotate(-90deg); }}
.g-track {{ fill:none; stroke:var(--track); stroke-width:10; }}
.g-arc {{ fill:none; stroke:var(--accent); stroke-width:10; stroke-linecap:round; {"filter:drop-shadow(0 0 12px " + ac + ");" if fut else ""} }}
.statbox {{ width:560px; height:560px; justify-content:center; }}
.statbox .sub {{ max-width:400px; font-size:34px; line-height:1.3; }}  /* the label stays inside the ring */
.stat {{ font-family:'display', 'body', 'Inter', sans-serif; font-size:190px; line-height:1; }}
.row {{ display:flex; align-items:center; gap:26px; padding:22px 24px; border-radius:24px; font-size:44px; }}
.dot {{ width:66px; height:66px; flex:none; border-radius:50%; display:flex; align-items:center; justify-content:center;
  background:var(--track); font-size:34px; }} .rtxt {{ flex:1; }} .ok {{ color:var(--accent); opacity:0; }}
.chat {{ width:920px; display:flex; flex-direction:column; gap:22px; }}
.bwrap {{ position:relative; display:flex; flex-direction:column; min-height:98px; }}
.bwrap.me {{ align-items:flex-start; }} .bwrap.them {{ align-items:flex-end; }}
.bwrap .typing {{ position:absolute; top:0; }} .me .typing {{ inset-inline-start:0; }} .them .typing {{ inset-inline-end:0; }}
.bubble {{ max-width:720px; padding:26px 36px; border-radius:44px; font-size:42px; line-height:1.4; font-weight:400; }}
.me .bubble {{ background:{"linear-gradient(135deg," + ac2 + "," + ac2 + "BB)" if fut else "var(--ink)" if flat else "#0A84FF"}; color:{th['bg'] if flat else "#fff"}; }}
.them .bubble {{ background:var(--track); color:var(--ink); }}
.typing {{ display:flex; gap:10px; padding:26px 32px; border-radius:44px; background:var(--track); opacity:0; }}
.typing i {{ width:16px; height:16px; border-radius:50%; background:var(--muted); display:block; }}
.note {{ display:flex; gap:26px; align-items:center; padding:30px 34px; border-radius:42px; background:var(--card);
  border:1px solid var(--line); box-shadow:{th['shadow']}; backdrop-filter:blur(30px); }}
.appic {{ width:96px; height:96px; flex:none; border-radius:24px; display:flex; align-items:center; justify-content:center;
  background:{"linear-gradient(135deg,#F58529,#DD2A7B,#8134AF)" if fut else "var(--ink)" if flat else "linear-gradient(135deg," + ac2 + ",#5E5CE6)"}; color:{th['bg'] if flat else "#fff"}; }}
.nhead {{ display:flex; justify-content:space-between; font-size:28px; color:var(--muted); font-weight:400; }}
.nhead b {{ color:var(--ink); font-weight:700; }} .ntitle {{ font-size:38px; margin-top:6px; }} .nbody {{ font-size:32px; color:var(--muted); font-weight:400; }}
.cmpwrap {{ display:flex; align-items:center; gap:26px; }} .cmp {{ width:410px; padding:54px 30px; }}
.cmp.bad .tile {{ color:#FF5A5F; }} .cmp.good .tile {{ color:var(--accent); }}
.vs {{ font-size:44px; color:var(--muted); }}
.flow {{ display:flex; flex-direction:column; align-items:center; }}
.flow.row {{ flex-direction:row; align-items:flex-start; }}
.flow.row .link {{ width:64px; height:6px; margin:73px 10px 0; }}
.flow.row .beam {{ transform-origin:{"right" if spec.get("dir", "rtl") == "rtl" else "left"}; }}
.link {{ width:6px; height:110px; margin:16px 0; background:var(--track); border-radius:6px; overflow:hidden; }}
.beam {{ width:100%; height:100%; transform-origin:top; background:linear-gradient(var(--accent2), var(--accent));
  {"box-shadow:0 0 18px " + ac2 + ";" if fut else ""} }}
.fnode {{ gap:16px; }}
.bars {{ display:flex; gap:44px; align-items:flex-end; height:620px; }} .bcol {{ align-items:center; gap:16px; height:100%; }}
.bar {{ flex:1; width:120px; display:flex; align-items:flex-end; background:var(--track); border-radius:28px; overflow:hidden; }}
.fill {{ width:100%; border-radius:28px; transform-origin:bottom; background:var(--muted); }}
.fill.hi {{ background:linear-gradient(var(--accent), var(--accent2)); {"box-shadow:0 0 40px " + ac + "88;" if fut else ""} }}
.bval {{ font-size:46px; }}
.qmark {{ font-size:260px; line-height:.6; color:var(--accent); height:150px; font-family:'display', 'body', sans-serif; }}
.quote {{ font-size:76px; }}
.avatar {{ width:150px; height:150px; border-radius:50%; object-fit:cover; flex:none; border:4px solid var(--accent); }}
.handle {{ font-family:Inter, sans-serif; font-size:44px; direction:ltr; text-align:{"right" if spec.get("dir", "rtl") == "rtl" else "left"}; }}
.followbox {{ position:relative; height:104px; margin-top:36px; }}
.follow {{ position:absolute; inset:0; border-radius:28px; display:flex; align-items:center; justify-content:center; gap:14px;
  font-size:42px; background:{"linear-gradient(135deg," + ac2 + "," + ac + ")" if fut else "var(--ink)" if flat else "#0A84FF"}; color:{"#05060B" if fut else th['bg'] if flat else "#fff"}; }}
.follow.done {{ background:var(--track); color:var(--ink); opacity:0; }}
.comment {{ margin-top:22px; padding:24px 34px; border-radius:999px; border:2px solid var(--line); font-size:38px; color:var(--muted); font-weight:400; }}
.comment b {{ color:var(--accent); font-weight:700; display:inline-block; }}
""" + CARD_STYLES.get(spec.get("card_style", "glass"), "").replace("SOLID", SOLID.get(theme, "#16161A"))


SOLID = {"futuristic": "#0F1526", "apple-dark": "#1C1C1E", "apple-light": "#FFFFFF", "editorial": "#FFFFFF", "editorial-dark": "#26262A"}
CARD_STYLES = {  # card_style from MP Studio: glass (default, frosted) | solid | outline | paper
    "glass": "",
    "solid": ".card, .note {{ background:SOLID; backdrop-filter:none; }}".replace("{{", "{").replace("}}", "}"),
    "outline": (".card, .note { background:transparent; backdrop-filter:none; box-shadow:none; "
                "border:2px solid color-mix(in srgb, var(--ink) 38%, transparent); }"),
    "paper": (".card, .note { background:#FFFDF8; color:#1B1A18; --ink:#1B1A18; --muted:#6B665E; --track:#EEE9E1; --pill:#F4EFE6; "
              "backdrop-filter:none; box-shadow:0 2px 0 rgba(0,0,0,.05), 0 22px 44px rgba(0,0,0,.28); }"
              " .card .kw, .note .kw { color:color-mix(in srgb, var(--accent) 62%, #000); text-shadow:none; }"
              " .card .tile { color:#1B1A18; background:#EEE9E1; box-shadow:none; } .note .appic { color:#fff; background:#1B1A18; }"),
}


def background(spec, th, total, W, H):
    """Global animated background (one clip on the root). Deterministic: seeded positions, timeline tweens."""
    theme = spec.get("theme", "futuristic")
    ac, ac2 = spec.get("accent", "#FFC400"), spec.get("accent2", "#4DD8FF")
    rnd = random.Random(7)
    if theme == "futuristic":
        blobs = [(ac2, 0.18, 0.22, 900), ("#7C4DFF", 0.85, 0.40, 1000), (ac, 0.40, 0.88, 760)]
        parts = "".join(f'<i class="pt" style="left:{rnd.uniform(0, W):.0f}px;top:{rnd.uniform(0, H):.0f}px;'
                        f'width:{(sz := rnd.choice([3, 4, 6]))}px;height:{sz}px;opacity:{rnd.uniform(.25, .8):.2f}"></i>' for _ in range(46))
        el = ("".join(f'<div id="blob{i}" class="blob" style="background:radial-gradient(circle,{c}55 0%,{c}00 65%);'
                      f'width:{s}px;height:{s}px;left:{x * W - s / 2:.0f}px;top:{y * H - s / 2:.0f}px"></div>' for i, (c, x, y, s) in enumerate(blobs))
              + '<div id="floor"></div><div id="parts">' + parts + '</div>'
              + '<div class="hud tl"></div><div class="hud tr"></div><div class="hud bl"></div><div class="hud br"></div><div id="scan"></div>')
        style = f"""
#bg {{ position:absolute; inset:0; overflow:hidden; background:radial-gradient(ellipse at 50% 30%, #0B1230 0%, {th['bg']} 70%); }}
.blob {{ position:absolute; border-radius:50%; }}
#floor {{ position:absolute; left:-50%; right:-50%; bottom:-6%; height:46%; transform:perspective(600px) rotateX(62deg); transform-origin:bottom;
  background-image:linear-gradient({ac2}40 2px, transparent 2px), linear-gradient(90deg, {ac2}40 2px, transparent 2px);
  background-size:90px 90px; -webkit-mask-image:linear-gradient(to top, #000 10%, transparent 90%); mask-image:linear-gradient(to top, #000 10%, transparent 90%); }}
.pt {{ position:absolute; border-radius:50%; background:{ac2}; box-shadow:0 0 8px {ac2}; }}
.hud {{ position:absolute; width:70px; height:70px; border:3px solid {ac2}66; }}
.hud.tl {{ top:60px; left:60px; border-right:0; border-bottom:0; }} .hud.tr {{ top:60px; right:60px; border-left:0; border-bottom:0; }}
.hud.bl {{ bottom:60px; left:60px; border-right:0; border-top:0; }} .hud.br {{ bottom:60px; right:60px; border-left:0; border-top:0; }}
#scan {{ position:absolute; left:0; right:0; top:0; height:180px; background:linear-gradient({ac2}00, {ac2}14, {ac2}00); }}
"""
        sweeps = max(1, int(total // 6))
        js_ = [f'tl.to("#blob0", {{x:260, y:180, duration:{total:.2f}, ease:"sine.inOut"}}, 0);',
               f'tl.to("#blob1", {{x:-300, y:-220, duration:{total:.2f}, ease:"sine.inOut"}}, 0);',
               f'tl.to("#blob2", {{x:180, y:-260, duration:{total:.2f}, ease:"sine.inOut"}}, 0);',
               f'tl.fromTo("#floor", {{backgroundPosition:"0px 0px"}}, {{backgroundPosition:"0px {int(total * 60)}px", duration:{total:.2f}, ease:"none"}}, 0);',
               f'tl.to("#parts", {{y:-{int(total * 14)}, duration:{total:.2f}, ease:"none"}}, 0);',
               f'tl.fromTo("#scan", {{y:-200}}, {{y:{H}, duration:2.2, ease:"none", repeat:{sweeps - 1}, repeatDelay:{6 - 2.2:.1f}}}, 0.5);']
    elif theme.startswith("editorial"):
        # flat paper / charcoal: a faint dot grid gives the camera something to travel over; nothing glows
        dot = "rgba(0,0,0,.10)" if theme == "editorial" else "rgba(255,255,255,.07)"
        el = '<div id="paper"></div>'
        if spec.get("canvas"):  # e.g. "popout": identical to finish.py's dotted canvas so a panel blends in
            style = f"""
#bg {{ position:absolute; inset:0; overflow:hidden; background:#0E0E0E; }}
#paper {{ position:absolute; inset:0;
  background:linear-gradient(90deg, transparent 3px, #0E0E0E 3px) 0 -{spec.get("panel_y", 0)}px/26px 26px,
             linear-gradient(transparent 3px, #0E0E0E 3px) 0 -{spec.get("panel_y", 0)}px/26px 26px, #242424; }}
"""
            js_ = []
        else:
            style = f"""
#bg {{ position:absolute; inset:0; overflow:hidden; background:{th['bg']}; }}
#paper {{ position:absolute; inset:-60px; background:radial-gradient({dot} 1.6px, transparent 1.7px) 0 0/34px 34px; }}
"""
            js_ = [f'tl.fromTo("#paper", {{x:0, y:0}}, {{x:-30, y:-50, duration:{total:.2f}, ease:"none"}}, 0);']
    else:
        light = theme == "apple-light"
        cs = [ac2, "#BF5AF2", ac] if not light else ["#A0C4FF", "#FFC6FF", "#FDFFB6"]
        el = "".join(f'<div id="blob{i}" class="blob" style="background:radial-gradient(circle,{c}{"55" if light else "30"} 0%,{c}00 65%);'
                     f'width:1100px;height:1100px;left:{x * W - 550:.0f}px;top:{y * H - 550:.0f}px"></div>'
                     for i, (c, x, y) in enumerate(zip(cs, (0.15, 0.9, 0.5), (0.2, 0.5, 0.95))))
        style = f"""
#bg {{ position:absolute; inset:0; overflow:hidden; background:{th['bg']}; }}
.blob {{ position:absolute; border-radius:50%; }}
"""
        js_ = [f'tl.to("#blob{i}", {{x:{dx}, y:{dy}, duration:{total:.2f}, ease:"sine.inOut"}}, 0);'
               for i, (dx, dy) in enumerate(((220, 160), (-260, -200), (160, -220)))]
    return el, style, js_


# ---------------------------------------------------------------- build

def scene_file(s, sid, spec, th, W, H, comp_css, first=False):
    kind = s["type"]
    if kind not in COMPONENTS:
        sys.exit(f"unknown scene type '{kind}' (have: {', '.join(COMPONENTS)})")
    inner, lines = COMPONENTS[kind](s, sid, spec)
    dur = round(s["t1"] - s["t0"], 3)
    y0, y1 = spec.get("stage_y", [220, 1380])
    enter = s.get("enter", "rise" if spec.get("theme", "").startswith("editorial") else "blur")
    a = {"blur": '{opacity:0, scale:1.06, filter:"blur(18px)"}', "rise": "{opacity:0, y:120}", "zoom": "{opacity:0, scale:0.7}"}[enter]
    accent = f'#root {{ --accent:{s["accent"]}; }}' if s.get("accent") else ""
    body = "\n".join("    " + l for l in lines)
    if first:
        # Frame 0 is the thumbnail: play the scene's build from its settled point (0.9 s in), no entrance
        skip = 0.9
        enter_js = (f"const build = gsap.timeline({{ paused: true }});\n    {{ const tl = build;\n{body}\n    }}\n"
                    f'    tl.add(build.tweenFromTo({skip}, {skip} + {dur}, {{ duration: {dur}, ease: "none" }}), 0);')
    else:
        enter_js = (f'tl.fromTo("#{sid}", {a}, {{opacity:1, scale:1, y:0, filter:"blur(0px)", duration:0.38, ease:"expo.out"}}, 0);\n'
                    + body)
    exit_js = (f'tl.to("#{sid}", {{opacity:0, scale:0.7, y:90, rotationX:-22, transformPerspective:1400, duration:0.26, ease:"power3.in"}}, {max(dur - 0.28, 0.3):.3f});'
               if FEEL["v"] == "punchy" else
               f'tl.to("#{sid}", {{opacity:0, scale:0.96, filter:"blur(14px)", duration:0.24, ease:"power2.in"}}, {max(dur - 0.26, 0.3):.3f});')
    return f"""<template>
  {scene_libs([s])}<style>{comp_css}{accent}</style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
    <div id="{sid}" class="stage" style="top:{y0}px;height:{y1 - y0}px"><div style="transform:scale({s.get("fit", spec.get("fit", 1))});flex:none">{inner}</div></div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {enter_js}
    {exit_js}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""


def world_file(scenes, spec, W, H, comp_css, total):
    """Cinematic camera: every scene lives in one big world; the camera travels to each on its cue,
    holds with a slow push while the action completes, and (optionally) pulls out to show the whole
    system at the end. Scenes stay built after their beat, so the world reads as one connected place."""
    cols = spec.get("camera_cols", 3)
    gx, gy = W * 1.08, H * 0.78
    pos = []
    for i in range(len(scenes)):
        r, c = divmod(i, cols)
        c = c if r % 2 == 0 else cols - 1 - c            # snake path: the camera never jumps back across
        pos.append((c * gx, r * gy))
    y0, y1 = spec.get("stage_y", [220, 1380])
    ww, wh = (cols - 1) * gx + W, ((len(scenes) - 1) // cols) * gy + H
    divs, js = [], []
    for i, (s, (x, y)) in enumerate(zip(scenes, pos), start=1):
        sid = f"s{i}"
        if s["type"] not in COMPONENTS:
            sys.exit(f"unknown scene type '{s['type']}' (have: {', '.join(COMPONENTS)})")
        inner, lines = COMPONENTS[s["type"]](s, sid, spec)
        divs.append(f'<div class="wscene" style="left:{x:.0f}px;top:{y:.0f}px;width:{W}px;height:{H}px">'
                    f'<div id="{sid}" class="stage" style="top:{y0}px;height:{y1 - y0}px">{inner}</div></div>')
        body = "\n".join("      " + l for l in lines)
        dur = s["t1"] - s["t0"]
        if s["t0"] == 0:   # frame 0 = thumbnail: start from the built state
            js.append(f"    {{ const c = gsap.timeline({{ paused: true }}); {{ const tl = c;\n{body}\n    }}\n"
                      f'    tl.add(c.tweenFromTo(0.9, {0.9 + dur:.3f}, {{ duration:{dur:.3f}, ease:"none" }}), 0); }}')
        else:
            js.append(f"    {{ const c = gsap.timeline(); {{ const tl = c;\n{body}\n    }} tl.add(c, {s['t0']}); }}")
    # camera keys: centre each scene's stage, arrive just as its beat starts, push in slowly while it holds
    z, push = spec.get("camera_zoom", 1.0), spec.get("camera_push", 0.0 if FEEL["v"] == "punchy" else 0.04)
    cy_stage = (y0 + y1) / 2
    cam = []
    for i, (s, (x, y)) in enumerate(zip(scenes, pos)):
        tx, ty = W / 2 - (x + W / 2) * z, H / 2 - (y + cy_stage) * z
        move = 0.0 if i == 0 else min(0.75, max(0.45, (s["t1"] - s["t0"]) * 0.25))
        start = max(0.0, s["t0"] - move * 0.55)
        if i == 0:
            cam.append(f'tl.set("#world", {{x:{tx:.1f}, y:{ty:.1f}, scale:{z}}}, 0);')
        else:
            cam.append(f'tl.to("#world", {{x:{tx:.1f}, y:{ty:.1f}, scale:{z}, duration:{move:.2f}, ease:"power3.inOut"}}, {start:.3f});')
        nxt = scenes[i + 1] if i + 1 < len(scenes) else None
        nmove = min(0.75, max(0.45, (nxt["t1"] - nxt["t0"]) * 0.25)) if nxt else 0
        hold0 = start + move
        hold1 = (nxt["t0"] - nmove * 0.55 - 0.02) if nxt else s["t1"] - (1.7 if spec.get("camera_end") == "overview" else 0)
        if hold1 - hold0 > 0.6:
            zz = z * (1 + push)
            cam.append(f'tl.to("#world", {{x:{W / 2 - (x + W / 2) * zz:.1f}, y:{H / 2 - (y + cy_stage) * zz:.1f}, scale:{zz:.3f}, '
                       f'duration:{hold1 - hold0:.2f}, ease:"sine.inOut"}}, {hold0:.3f});')
    if spec.get("camera_end") == "overview" and len(scenes) > 1:
        k = min(W / ww, H / wh) * 0.92
        cam.append(f'tl.to("#world", {{x:{(W - ww * k) / 2:.1f}, y:{(H - wh * k) / 2:.1f}, scale:{k:.3f}, duration:1.0, '
                   f'ease:"power3.inOut"}}, {total - 1.6:.3f});')
    return f"""<template>
  {scene_libs(scenes)}<style>{comp_css}</style>
  <div id="root" data-composition-id="world" data-width="{W}" data-height="{H}" data-layout-allow-overflow data-layout-allow-overlap>
    <div id="world" style="width:{ww:.0f}px;height:{wh:.0f}px">{"".join(divs)}</div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
    {chr(10).join('    ' + c for c in cam)}
    window.__timelines["world"] = tl;
  </script>
</template>
"""


def load_brand(where: Path | None = None) -> dict:
    """brand.json, with work/<project>/settings.json on top when `where` lies inside a project's work folder."""
    def rd(p):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    b, over = rd(DATA / "assets" / "brand.json"), {}
    if where is not None:
        try:
            rel = Path(where).resolve().relative_to((DATA / "work").resolve())
            over = rd(DATA / "work" / rel.parts[0] / "settings.json") if rel.parts else {}
        except ValueError:
            pass
    return {**b, **over, **{k: {**b.get(k, {}), **over[k]} for k in ("colors", "fonts", "voice") if k in over}}


def apply_brand(spec: dict, where: Path | None = None) -> dict:
    """Fill what the spec leaves out from the owner's MP Studio brand (theme, card style, feel, colours, fonts),
    using the project's own settings when `where` (the spec or output path) is inside mp-studio/work/<project>/."""
    b = load_brand(where)
    for k in ("theme", "card_style", "motion_feel"):
        if b.get(k):
            spec.setdefault(k, b[k])
    # the CTA/profile card uses the owner's page, bio and photo from MP Studio (never a placeholder)
    if b.get("page"):
        spec.setdefault("handle", b["page"])
    if b.get("bio"):
        spec.setdefault("bio", b["bio"])
    if b.get("avatar") and (DATA / b["avatar"]).exists():
        spec.setdefault("_brand_avatar", str(DATA / b["avatar"]))
    col = b.get("colors", {})
    if col.get("accent"):
        spec.setdefault("accent", col["accent"])
    if col.get("accent2") and spec.get("theme", "futuristic") == "futuristic":
        spec.setdefault("accent2", col["accent2"])
    if b.get("language"):
        spec.setdefault("dir", "ltr" if b["language"] == "en" else "rtl")
        spec.setdefault("digits", "en" if b["language"] == "en" else "fa")
    if "fonts" not in spec and b.get("fonts"):
        try:
            cat = json.loads((DATA / "fonts" / "catalog.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cat = {}

        def pick(fam, prefer):
            st = cat.get(fam, {}).get("styles", {})
            for w in prefer:
                for name, f in st.items():
                    if name.replace(" ", "").lower() == w:
                        return f
            return next(iter(st.values()), None)
        body = pick(b["fonts"].get("captions", ""), ["bold", "semibold", "medium", "regular"])
        disp = pick(b["fonts"].get("display", ""), ["black", "extrabold", "heavy", "bold", "regular"])
        spec["fonts"] = {k: v for k, v in (("body", body), ("display", disp)) if v}
    return spec


def captions_file(spec, th, W, H, comp_css) -> str:
    """Caption track above the scenes: "captions": {"cues": [{"t0", "t1", "text"}], "y": 880, "size": 54}.
    Light frosted-glass pill (backdrop blur, white edge, soft shadow), dark text, *keyword* in a soft amber pill.
    Browser text layout, so Persian reads right to left and mixed Persian/English stays in order."""
    c = spec["captions"]
    y, size = c.get("y", H - 80), c.get("size", 54)
    els, js = [], []
    for i, q in enumerate(c["cues"]):
        els.append(f'<div class="cap" id="c{i}">{mark(q["text"])}</div>')
        js.append(f'tl.fromTo("#c{i}", {{opacity:0, scale:.94, y:8}}, {{opacity:1, scale:1, y:0, duration:.14, ease:"back.out(2)"}}, {q["t0"]});')
        js.append(f'tl.to("#c{i}", {{opacity:0, duration:.06}}, {max(q["t0"] + 0.15, q["t1"] - 0.06):.3f});')
    return f"""<template>
  <style>{comp_css}
#root {{ position:absolute; inset:0; }}
.cap {{ position:absolute; left:50%; top:{y}px; translate:-50% -50%; opacity:0; white-space:nowrap;
  direction:{spec.get("dir", "rtl")}; font-family:'body', sans-serif; font-weight:800; font-size:{size}px; line-height:1.25;
  color:#1D1D1F; padding:{round(size * .26)}px {round(size * .62)}px; border-radius:999px;
  background:linear-gradient(180deg, rgba(255,255,255,.78), rgba(255,255,255,.52));
  backdrop-filter:blur(20px) saturate(1.7); -webkit-backdrop-filter:blur(20px) saturate(1.7);
  border:1.5px solid rgba(255,255,255,.95);
  box-shadow:0 12px 34px rgba(30,30,60,.14), 0 2px 6px rgba(30,30,60,.08), inset 0 1px 0 rgba(255,255,255,1); }}
.cap .kw {{ color:#1D1D1F; text-shadow:none; filter:none; padding:0 {round(size * .28)}px; border-radius:999px;
  background:linear-gradient(180deg, color-mix(in srgb, var(--accent) 45%, white), color-mix(in srgb, var(--accent) 75%, white)); }}
  </style>
  <div id="root" data-composition-id="cap" data-width="{W}" data-height="{H}">
    {"".join(els)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + l for l in js)}
    window.__timelines["cap"] = tl;
  </script>
</template>
"""


def build(spec: dict, out: Path) -> None:
    apply_brand(spec, out)
    FEEL["v"] = spec.get("motion_feel", "punchy")
    W, H = spec.get("size", [1080, 1920])
    th = THEMES[spec.get("theme", "futuristic")]
    scenes = sorted(spec["scenes"], key=lambda s: s["t0"])
    total = round(spec.get("duration") or max(s["t1"] for s in scenes), 3)
    out.mkdir(parents=True, exist_ok=True)
    # Minimal project files instead of `hyperframes init`: init also copies its skills into the
    # user's ~/.claude/skills and ~/.agents/skills (even with --skip-skills), outside this project.
    if not (out / "hyperframes.json").exists():
        (out / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "assets": "assets"}}), encoding="utf-8")
        (out / "meta.json").write_text(json.dumps({"id": out.name, "name": out.name}), encoding="utf-8")
    comp = out / "compositions"
    if comp.exists():
        for f in comp.glob("s*.html"):
            f.unlink()
    comp.mkdir(exist_ok=True)
    fonts = out / "assets" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for file in set(fonts_of(spec).values()):
        src = DATA / "fonts" / file
        if not src.exists():
            sys.exit(f"font {file} not in {ROOT / 'fonts'} (list them with pro-edit/fonts.py)")
        shutil.copy2(src, fonts / file)
    # media a scene points at (Lottie JSON, phone screen image) is copied into the project's assets/
    for s in scenes:
        src = s.get("src") if s["type"] == "lottie" else s.get("image") if s["type"] == "phone3d" else None
        if src:
            p = Path(src)
            p = p if p.is_absolute() else (Path.cwd() / p)
            if not p.exists():
                sys.exit(f"{s['type']}: file not found: {src}")
            dst = out / "assets" / ("lottie" if s["type"] == "lottie" else "img") / p.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            s["_src"] = dst.relative_to(out).as_posix()
        elif s["type"] == "lottie":
            sys.exit("lottie scene needs \"src\": a Lottie JSON file (LottieFiles → download → Lottie JSON)")
    if not spec.get("avatar") and spec.get("_brand_avatar"):  # brand photo → this project's assets
        (out / "assets").mkdir(parents=True, exist_ok=True)
        shutil.copy2(spec["_brand_avatar"], out / "assets" / "avatar.png")
        spec["avatar"] = "assets/avatar.png"
    libs = sorted({LIBS["lottie"] for s in scenes if s["type"] == "lottie"} | {LIBS["three"] for s in scenes if s["type"] == "phone3d"})
    comp_css = css(spec, th)
    hosts = []
    if spec.get("camera"):
        (comp / "world.html").write_text(world_file(scenes, spec, W, H, comp_css, total), encoding="utf-8")
        hosts.append(f'      <div id="world-host" data-composition-id="world" data-composition-src="compositions/world.html" '
                     f'data-start="0" data-duration="{total}" data-track-index="1" data-track-kind="graphics" '
                     f'data-width="{W}" data-height="{H}"></div>')
        scenes_iter = []
    else:
        scenes_iter = scenes
    for i, s in enumerate(scenes_iter, start=1):
        sid = f"s{i}"
        (comp / f"{sid}.html").write_text(scene_file(s, sid, spec, th, W, H, comp_css, first=s["t0"] == 0), encoding="utf-8")
        hosts.append(f'      <div id="{sid}-host" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
                     f'data-start="{s["t0"]}" data-duration="{round(s["t1"] - s["t0"], 3)}" data-track-index="1" '
                     f'data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>')
    if spec.get("captions"):
        (comp / "cap.html").write_text(captions_file(spec, th, W, H, comp_css), encoding="utf-8")
        hosts.append(f'      <div id="cap-host" data-composition-id="cap" data-composition-src="compositions/cap.html" '
                     f'data-start="0" data-duration="{total}" data-track-index="2" data-track-kind="graphics" '
                     f'data-width="{W}" data-height="{H}"></div>')
    bg_el, bg_css, bg_js = background(spec, th, total, W, H)
    (comp / "bg.html").write_text(f"""<template>
  <style>#root {{ position:absolute; inset:0; }} {bg_css}</style>
  <div id="root" data-composition-id="bg" data-width="{W}" data-height="{H}">
    <div id="bg">{bg_el}</div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + l for l in bg_js)}
    window.__timelines["bg"] = tl;
  </script>
</template>
""", encoding="utf-8")
    index = f"""<!doctype html>
<html lang="{"fa" if spec.get("dir", "rtl") == "rtl" else "en"}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="{GSAP}"></script>
    {"".join(f'<script src="{u}"></script>' for u in libs)}
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html, body {{ width:{W}px; height:{H}px; overflow:hidden; background:{th['bg']}; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
      <div id="bg-host" data-composition-id="bg" data-composition-src="compositions/bg.html" data-start="0" data-duration="{total}"
        data-track-index="0" data-track-kind="graphics" data-width="{W}" data-height="{H}" data-layout-ignore></div>
{chr(10).join(hosts)}
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    (out / "index.html").write_text(index, encoding="utf-8")
    sfx = [{"name": "whoosh_short", "t": round(max(0.0, s["t0"] - 0.08), 2), "db": -20} for s in scenes[1:]]
    sfx += [{"name": "pop", "t": round(s["t0"] + 0.25, 2), "db": -24} for s in scenes if s["type"] in ("icon_card", "stat", "cta", "compare")]
    ui = {"tabs": "click", "list": "click", "chat": "pop", "notify": "ding"}
    for s in scenes:
        if s["type"] in ui:
            at = s.get("at") or []
            sfx += [{"name": ui[s["type"]], "t": round(s["t0"] + t, 2), "db": -22} for t in (at if isinstance(at, list) else [at])]
    (out / "sfx_suggestions.json").write_text(json.dumps(sorted(sfx, key=lambda x: x["t"]), indent=1), encoding="utf-8")
    print(f"{spec.get('theme', 'futuristic')}: {len(scenes)} scenes, {total}s, {W}x{H} → {out}")
    print(f"next: cd \"{out}\" && npx hyperframes check && npx hyperframes render --output motion.mp4")
    print("sfx_suggestions.json: whoosh on scene changes, pops on reveals (paste into fx.json \"sfx\")")


DEMO = {
    "theme": "futuristic", "accent": "#FFC400", "accent2": "#4DD8FF", "dir": "rtl", "digits": "fa",
    "fonts": {"body": "Vazirmatn-Bold.ttf", "display": "Lalezar-Regular.ttf"},
    "scenes": [
        {"type": "title", "t0": 0, "t1": 3, "kicker": "۳ ترفند", "text": "ادیت *حرفه‌ای* با هوش مصنوعی", "sub": "فقط با یک ویس"},
        {"type": "icon_card", "t0": 3, "t1": 6, "icon": "scissors", "title": "حذف *مکث‌ها*", "sub": "خودکار و دقیق"},
        {"type": "icon_grid", "t0": 6, "t1": 9.5, "counter": "ابزار", "items": [
            {"icon": "mic", "label": "صدا"}, {"icon": "captions", "label": "زیرنویس"}, {"icon": "sparkles", "label": "افکت"},
            {"icon": "music", "label": "موزیک"}, {"icon": "zoom-in", "label": "زوم"}, {"icon": "palette", "label": "رنگ"},
            {"icon": "layers", "label": "لایه"}, {"icon": "wand-sparkles", "label": "جادو"}]},
        {"type": "tabs", "t0": 9.5, "t1": 14.5, "tabs": ["ضبط", "ادیت", "انتشار"], "at": [0.4, 1.9, 3.4],
         "panes": [{"icon": "video", "text": "فقط *ضبط* کن"}, {"icon": "wand-sparkles", "text": "Claude *ادیت* می‌کنه"}, {"icon": "send", "text": "آماده *انتشار*"}]},
        {"type": "stat", "t0": 14.5, "t1": 17.5, "value": 87, "suffix": "٪", "label": "زمان ادیت کمتر", "ring": 87},
        {"type": "list", "t0": 17.5, "t1": 22, "title": "مراحل", "items": ["ویس بفرست", "Claude صحنه می‌سازه", "ویدیو تحویل بگیر"], "at": [0.6, 1.7, 2.8]},
        {"type": "chat", "t0": 22, "t1": 25.5, "messages": [{"from": "me", "text": "یه ریلز از این ویس بساز"}, {"from": "them", "text": "آماده‌ست ✨"}], "at": [0.8, 2.3]},
        {"type": "notify", "t0": 25.5, "t1": 28, "items": [{"icon": "brand:instagram", "app": "Instagram", "title": "۱۲۰۰ لایک جدید", "body": "ریلزت ترکوند"}], "at": [0.3]},
        {"type": "compare", "t0": 28, "t1": 31, "bad": {"title": "ادیت دستی", "sub": "۴ ساعت"}, "good": {"title": "با Claude", "sub": "۱۰ دقیقه"}, "at": 1.0},
        {"type": "flow", "t0": 31, "t1": 34, "nodes": [{"icon": "mic", "label": "ویس"}, {"icon": "sparkles", "label": "Claude"}, {"icon": "clapperboard", "label": "ویدیو"}]},
        {"type": "bars", "t0": 34, "t1": 37, "title": "بازدید", "bars": [{"label": "قبل", "value": 2}, {"label": "بعد", "value": 18, "suffix": "K"}]},
        {"type": "quote", "t0": 37, "t1": 40, "text": "ادیت خوب *دیده نمی‌شه*، حس می‌شه", "by": "یک تدوینگر"},
        {"type": "cta", "t0": 40, "t1": 44, "handle": "your.page", "bio": "ادیت با هوش مصنوعی", "keyword": "ادیت", "at": 1.2},
    ],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("spec", type=Path)
    b.add_argument("-o", "--out", type=Path, required=True)
    i = sub.add_parser("icons")
    i.add_argument("words", nargs="+")
    d = sub.add_parser("demo")
    d.add_argument("-o", "--out", type=Path, required=True)
    d.add_argument("--theme", default="futuristic", choices=list(THEMES))
    a = ap.parse_args()
    if a.cmd == "build":
        build(json.loads(a.spec.read_text(encoding="utf-8")), a.out.resolve())
    elif a.cmd == "icons":
        search_icons(a.words)
    else:
        build({**DEMO, "theme": a.theme}, a.out.resolve())


if __name__ == "__main__":
    main()
