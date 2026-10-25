"""master.srt + motion.json -> master.ass: captions and motion cards in one animated libass file.

  ass_motion.py <edit_dir> [--width 1080 --height 1920]

No Node/HyperFrames needed, Persian shapes correctly. Coordinates are pixels; times are on the
OUTPUT timeline (take them from master.srt). EDL: "subtitles": "master.ass",
"subtitle_style": "Shadow=0" (styles live in the .ass), render WITHOUT --build-subtitles.

Captions (default "caption_mode": "emphasis", the owner's style): in master.srt mark the
keyword of a cue with stars — "تا *۱۰ تا ریلز*" → small white lead-in line + big accent keyword
line that pops. Cues without stars render plain white. "caption_mode": "plain" ignores stars.
"caption_mode": "glass" (light frosted, Apple-like: dark text, rounded box, white edge) or
"glass-futuristic" (dark frosted, neon cyan edge + glow, *keyword* glowing in the accent): one
rounded box per cue sized to its line, at "glass_y" (1440) or "word_y" inside pop-out windows;
"glass_size" px. Writes glass_mask.ass too — finish.py blurs the video inside the boxes (real frost).
"word_windows": [[t0, t1], ...] — cues starting inside switch to word mode (pop-out sections of a
mixed edit; the rest keeps "caption_mode"). "caption_mode": "word" (pop-out window layout): the cue as one short centred line at "word_y"
(default 1060, above the head that breaks out of the window), "word_size" px, *keyword* in the accent + keyword_font.
Font roles (family names from pro-edit/fonts.py): "font" captions, "keyword_font" the emphasis
keyword, "display_font" titles/cards/numbers — e.g. Peyda / Kalameh Black / Lalezar.
"caption_mode": "boxed" (split explainer layout): one line in a dark rounded box centred on
"caption_y" (the seam, 768 for a 768 px panel), *keyword* recoloured in the accent, "boxed_size" px.

motion.json:
{
  "style": {"font": "Vazirmatn", "accent": "#FFC400", "dark": "#111111", "text": "#FFFFFF",
            "caption_size": 84, "caption_margin_v": 410,
            "caption_mode": "emphasis", "keyword_size": 124, "lead_size": 72},
  "moments": [
    {"type": "dark",    "text": "Instagram Agent Skill", "start": 10.84, "end": 15.4, "y": 300},
    {"type": "pill",    "text": "کاملاً رایگان",          "start": 11.4,  "end": 15.4, "y": 465},
    {"type": "counter", "to": 11, "label": "ابزار مختلف",   "start": 17.7,  "end": 22.6, "y": 380},
    {"type": "dark",    "text": "پیج رو فالو کن",          "start": 61.0,  "end": 66.3, "y": 300, "enter": "drop"},
    {"type": "big",     "text": "۷۰٪",                     "start": 30.0,  "end": 32.0, "y": 380}
  ]
}
types: dark (dark box, light text) | pill (accent box, dark text) | big (huge accent text) |
       label (large outlined text) | counter (counts 1..to, lands with a pop, optional label)
       glow (soft accent circle: "radius", "blur", "alpha" hex 00=solid..FF=clear)
enter: "pop" (default, scale 70→106→100) | "drop" (slides down 120 px) | "fade"
Any moment may add "tags": raw ASS override tags appended last (e.g. "\\frz-4"), "size" (font px),
"x" (centre, px), and "layer": "behind" → written to master_behind.ass, which finish.py draws
UNDER the cut-out speaker (text behind the head, giant numbers, spotlight glow).
"""
import json
import re
import sys
from pathlib import Path

E = Path(sys.argv[1]).resolve()
W = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1080
H = int(sys.argv[sys.argv.index("--height") + 1]) if "--height" in sys.argv else 1920
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

spec = json.loads((E / "motion.json").read_text(encoding="utf-8")) if (E / "motion.json").exists() else {}
st = {"font": "Vazirmatn", "accent": "#FFC400", "dark": "#111111", "text": "#FFFFFF",
      "caption_size": 84, "caption_margin_v": 410, "persian_digits": True,
      "caption_mode": "emphasis", "keyword_size": 124, "lead_size": 72,
      "caption_y": 768, "boxed_size": 60, **spec.get("style", {})}


def col(hex_rgb):  # #RRGGBB -> &H00BBGGRR
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(s):
    h, s = divmod(max(0.0, s), 3600)
    m, s = divmod(s, 60)
    return f"{int(h)}:{int(m):02}:{s:05.2f}"


F, A, D, T = st["font"], col(st["accent"]), col(st["dark"]), col(st["text"])
# font roles (family names from fonts.py): captions = "font", emphasis keyword = "keyword_font",
# titles/cards/numbers = "display_font"; both default to "font"
KF, DF = st.get("keyword_font", F), st.get("display_font", F)
k = W / 1080  # sizes are designed for 1080 wide
styles = [
    f"Cap,{F},{round(st['caption_size'] * k)},{T},{T},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,{round(6 * k)},0,2,60,60,{st['caption_margin_v']},-1",
    f"Pill,{DF},{round(88 * k)},{D},{D},{A},{A},1,0,0,0,100,100,0,0,3,{round(22 * k)},0,5,60,60,0,-1",
    f"Dark,{DF if st['caption_mode'] != 'boxed' else F},{round(80 * k)},{T},{T},{D},{D},1,0,0,0,100,100,0,0,3,{round(20 * k)},0,5,60,60,0,-1",
    f"Big,{DF},{round(300 * k)},{A},{A},{D},&H00000000,1,0,0,0,100,100,0,0,1,{round(10 * k)},0,5,60,60,0,-1",
    f"Label,{DF},{round(96 * k)},{T},{T},{D},&H00000000,1,0,0,0,100,100,0,0,1,{round(7 * k)},0,5,60,60,0,-1",
    f"Word,{F},{round(st.get('word_size', 96) * k)},{T},{T},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,{round(5 * k)},0,5,60,60,0,-1",
]
head = (
    f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
    "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding\n" + "\n".join(f"Style: {s}" for s in styles) +
    "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)

POP = r"\fscx70\fscy70\t(0,220,\fscx106\fscy106)\t(220,320,\fscx100\fscy100)"
x = W // 2
ev = []


def rtl_runs(text, plain_tags="", key_tags=""):
    """*keyword* in the accent colour. Word order right-to-left comes from the styles' Encoding -1 (libass
    detects the base direction); with Encoding 1 a Persian line came out with its words left to right."""
    return re.sub(r"\*([^*]+)\*", lambda m: rf"{{{key_tags}\c{A}}}{m[1]}{{{plain_tags}\c{T}}}", text)


def caption(text, mode=None):
    """Emphasis captions: words in *stars* become the big accent keyword line, the rest a small
    white lead-in line above it. Cues without stars stay plain white.
    Boxed (split layout): one line in a dark rounded box on the seam, *keyword* in the accent colour."""
    text = text.replace("\n", " ")
    mode = mode or st["caption_mode"]
    if mode == "word":  # pop-out layout: one centred word between canvas and window
        y = round(st.get("word_y", 1060) * H / 1920)
        body = rtl_runs(text, rf"\fn{F}", rf"\fn{KF}")
        return rf"{{\an5\pos({W // 2},{y})\fscx92\fscy92\t(0,90,\fscx100\fscy100)}}{body}"
    if mode == "boxed":
        body = rtl_runs(text)
        return rf"{{\an5\pos({W // 2},{round(st['caption_y'] * H / 1920)})\fs{round(st['boxed_size'] * k)}\fad(60,60)}}{body}"
    if mode != "emphasis" or "*" not in text:
        return text.replace("*", "")
    key = " ".join(re.findall(r"\*([^*]+)\*", text)).strip()
    lead = re.sub(r"\s+", " ", re.sub(r"\*[^*]+\*", " ", text)).strip()
    big, small = round(st["keyword_size"] * k), round(st["lead_size"] * k)
    pop = r"\fscx88\fscy88\t(0,120,\fscx100\fscy100)"
    out = rf"{{\fs{small}}}{lead}\N" if lead else ""
    return out + rf"{{\fn{KF}\fs{big}\c{A}{pop}}}{key}"


def rrect(w, h, r):
    """ASS vector drawing of a rounded rectangle w×h with corner radius r (top-left origin)."""
    c = r * 0.45
    return (f"m {r} 0 l {w - r} 0 b {w - c} 0 {w} {c} {w} {r} l {w} {h - r} b {w} {h - c} {w - c} {h} {w - r} {h} "
            f"l {r} {h} b {c} {h} 0 {h - c} 0 {h - r} l 0 {r} b 0 {c} {c} 0 {r} 0")


_measure = {}


def text_width(text, size):
    """Caption width in px. No complex-text shaping in this Pillow build, so Persian is measured in
    isolated letter forms (~12 % too wide) — corrected below; the box padding absorbs the rest."""
    from PIL import ImageFont
    fdir = Path(st.get("fonts_dir") or Path(__file__).resolve().parents[5] / "mp-studio" / "fonts")
    key = (F, size)
    if key not in _measure:
        cat = fdir / "catalog.json"
        files = json.loads(cat.read_text(encoding="utf-8")).get(F, {}).get("styles", {}) if cat.exists() else {}
        name = files.get("Bold") or next(iter(files.values()), None) or "Vazirmatn-Bold.ttf"
        try:
            _measure[key] = ImageFont.truetype(str(fdir / name), size)
        except OSError:
            _measure[key] = None
    f = _measure[key]
    w = f.getlength(text) if f else len(text) * size * 0.5
    return w * (0.88 if re.search(r"[؀-ۿ]", text) else 1.0)


GLASS = {  # caption_mode → look (light = Apple-like frosted; futuristic = dark frosted, neon edge + glow)
    "glass": {"fill": "&H00FFFFFF", "fill_a": "&H38&", "edge": "&H00FFFFFF", "edge_a": "&H40&",
              "text": "&H00141414", "key": "&H000C59E8", "glow": None},  # keyword: deep orange #E8590C
    "glass-futuristic": {"fill": "&H00281410", "fill_a": "&H55&", "edge": "&H00FFD84D", "edge_a": "&H10&",
                         "text": "&H00FFFFFF", "key": "accent", "glow": "&H00FFD84D"},
}
glass_mask = []  # same boxes, solid: finish.py / storyframe.py blur the video only inside them


def glass_caption(text, a, b, y, look):
    """One rounded frosted-glass box per cue sized to its line; *keyword* tinted (futuristic: glowing)."""
    g = GLASS[look]
    size = round(st.get("glass_size", 70) * k)
    plain = text.replace("*", "").replace("\n", " ").strip()
    w = round(text_width(plain, size) + 2 * 46 * k)
    h = round(size * 1.55)
    r = round(h * 0.38)
    x0, y0 = (W - w) // 2, round(y - h / 2)
    shape = rrect(w, h, r)
    t = f"{ts(a)},{ts(b)}"
    fade = r"\fad(90,90)"
    if g["glow"]:  # soft neon halo outside the edge
        ev.append(f"Dialogue: 0,{t},Cap,,0,0,0,,{{\\an7\\pos({x0},{y0}){fade}\\bord{round(7 * k)}\\shad0\\blur{round(12 * k)}"
                  f"\\1a&HFF&\\3c{g['glow']}\\3a&H70&\\p1}}{shape}")
    ev.append(f"Dialogue: 0,{t},Cap,,0,0,0,,{{\\an7\\pos({x0},{y0}){fade}\\bord{max(1, round(2 * k))}\\shad0"
              f"\\1c{g['fill']}\\1a{g['fill_a']}\\3c{g['edge']}\\3a{g['edge_a']}\\p1}}{shape}")
    key_col = A if g["key"] == "accent" else (g["key"] or D)
    # futuristic: a soft halo around the keyword only (outline blurred, letters stay sharp)
    key_glow = rf"\3c{A}\3a&H90&\bord{max(1, round(2 * k))}\blur{max(1, round(2 * k))}" if g["glow"] else r"\bord0"
    body = re.sub(r"\*([^*]+)\*", lambda m: rf"{{\c{key_col}{key_glow}}}{m.group(1)}{{\c{g['text']}\bord0\blur0}}", text.replace("\n", " "))
    ev.append(f"Dialogue: 1,{t},Cap,,0,0,0,,{{\\an5\\pos({W // 2},{round(y)}){fade}\\fs{size}\\c{g['text']}\\bord0\\shad0}}{body}")
    glass_mask.append(f"Dialogue: 0,{t},Cap,,0,0,0,,{{\\an7\\pos({x0},{y0})\\bord0\\shad0\\1c&H00FFFFFF&\\1a&H00&\\p1}}{shape}")


srt = E / "master.srt"
if srt.exists():
    for block in srt.read_text(encoding="utf-8").strip().split("\n\n"):
        _, timing, text = block.split("\n", 2)
        a, b = [sum(float(p) * m for p, m in zip(re.split(r"[:]", t.strip().replace(",", ".")), (3600, 60, 1)))
                for t in timing.split("-->")]
        # "word_windows": cues starting inside a pop-out window switch to word captions
        in_win = any(w0 <= a < w1 for w0, w1 in st.get("word_windows", []))
        if st["caption_mode"] in GLASS:  # glass stays glass; in a pop-out window it sits above the window
            glass_caption(text, a, b, st.get("word_y", 1060) if in_win else st.get("glass_y", 1440), st["caption_mode"])
            continue
        mode = "word" if in_win else st["caption_mode"]
        sty = {"boxed": "Dark", "word": "Word"}.get(mode, "Cap")
        ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},{sty},,0,0,0,,{caption(text, mode)}")


def enter(m, y):
    kind = m.get("enter", "pop")
    if kind == "drop":
        return rf"\move({x},{y - round(120 * k)},{x},{y},0,250)\fad(150,200)"
    if kind == "fade":
        return rf"\pos({x},{y})\fad(200,200)"
    return rf"\pos({x},{y})\fad(120,200){POP}"


def ellipse(r):
    """ASS vector drawing of a circle with radius r (top-left origin)."""
    c, d = round(r * 0.45), 2 * r
    return (f"m 0 {r} b 0 {c} {c} 0 {r} 0 b {d - c} 0 {d} {c} {d} {r} "
            f"b {d} {d - c} {d - c} {d} {r} {d} b {c} {d} 0 {d - c} 0 {r}")


style_of = {"dark": "Dark", "pill": "Pill", "big": "Big", "label": "Label"}
def head_y(m):
    """"y": "head" → the line sits across the top of the speaker's head at this moment, measured from the
    blue-wall matte of the edit's base video (so behind-text really goes BEHIND the head, not above it)."""
    import subprocess
    import numpy as np
    from PIL import Image
    base = E / spec.get("base", "base_preview.mp4")
    if not base.exists():
        base = E / "base.mp4"
    lo, hi = spec.get("matte", {}).get("lo", 35), spec.get("matte", {}).get("hi", 60)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(m['start']) + 0.3:.2f}", "-i", str(base), "-frames:v", "1",
                          "-vf", f"format=rgb24,colorchannelmixer=rr=-0.5:rg=-0.5:rb=1:gr=-0.5:gg=-0.5:gb=1:br=-0.5:bg=-0.5:bb=1,"
                                 f"format=gray,lut=y='clip(({hi}-val)*255/{hi - lo},0,255)',scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    mask = np.frombuffer(raw, np.uint8).reshape(H, W) > 128 if len(raw) == W * H else None
    rows = np.where(mask.sum(1) > 0.012 * W)[0] if mask is not None else []
    if not len(rows):
        print(f"  head not found at {m['start']}s (no blue wall?): using y 690")
        return 690
    top = int(rows[0])
    # text centre just below the head top: the head cuts into the lower part of the word, which stays readable
    return int(top + m.get("size", 160) * 0.12)


behind = []  # moments with "layer": "behind" go under the cut-out speaker (finish.py)
for m in spec.get("moments", []):
    if m.get("y") == "head":
        m["y"] = head_y(m) * 1920 / H
        print(f"  {m.get('text', m['type'])}: y={m['y']:.0f} (behind the head at {m['start']}s)")
    s, e, y, extra = float(m["start"]), float(m["end"]), round(m.get("y", 300) * H / 1920), m.get("tags", "")
    if m.get("size"):
        extra = rf"\fs{round(m['size'] * k)}" + extra
    if "x" in m:
        x = round(m["x"] * W / 1080)
    out = behind if m.get("layer") == "behind" else ev
    if m["type"] == "counter":
        to, step = int(m["to"]), min(0.05, 0.5 / max(int(m["to"]) - 1, 1))
        num = (lambda n: str(n).translate(FA)) if st["persian_digits"] else str
        for i in range(1, to):
            out.append(f"Dialogue: 3,{ts(s + (i - 1) * step)},{ts(s + i * step)},Big,,0,0,0,,{{\\pos({x},{y}){extra}}}{num(i)}")
        land = s + (to - 1) * step
        out.append(f"Dialogue: 3,{ts(land)},{ts(e)},Big,,0,0,0,,{{\\pos({x},{y})\\fad(0,200)\\fscx125\\fscy125\\t(0,180,\\fscx100\\fscy100){extra}}}{num(to)}")
        if m.get("label"):
            ev.append(f"Dialogue: 3,{ts(land + 0.15)},{ts(e)},Label,,0,0,0,,{{\\pos({x},{m.get('label_y', y + 220)})\\fad(150,200)}}{m['label']}")
    elif m["type"] == "glow":  # soft accent light, e.g. a spotlight behind the speaker
        r = round(m.get("radius", 420) * k)
        alpha = m.get("alpha", "60")
        out.append(f"Dialogue: 1,{ts(s)},{ts(e)},Big,,0,0,0,,{{\\an7\\pos({x - r},{y - r})\\bord0\\shad0\\1c{A}"
                   f"\\alpha&H{alpha}&\\blur{round(m.get('blur', 80) * k)}\\fad(300,300)\\p1}}{ellipse(r)}")
    else:
        out.append(f"Dialogue: 2,{ts(s)},{ts(e)},{style_of[m['type']]},,0,0,0,,{{{enter(m, y)}{extra}}}{m['text']}")
    x = W // 2

(E / "master.ass").write_text(head + "\n".join(ev) + "\n", encoding="utf-8-sig")
(E / "master_behind.ass").write_text(head + "\n".join(behind) + "\n", encoding="utf-8-sig")
if glass_mask:  # frosted glass: finish.py blurs the video inside these boxes, under master.ass
    (E / "glass_mask.ass").write_text(head + "\n".join(glass_mask) + "\n", encoding="utf-8-sig")
else:
    (E / "glass_mask.ass").unlink(missing_ok=True)
print(f"master.ass: {len(ev)} events, master_behind.ass: {len(behind)} events "
      f"({len(spec.get('moments', []))} motion moments)")
