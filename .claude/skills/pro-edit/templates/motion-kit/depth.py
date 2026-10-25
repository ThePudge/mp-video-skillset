"""Depth effects: graphics that pass BEHIND and IN FRONT of the speaker (Charlie Hills-style).

  depth.py <edit_dir> [--spec depth.json] [--base base_preview.mp4] -o <edit_dir>/base_depth.mp4

Per effect window: the person is cut out (blue-wall key, or local AI matte), the effect is rendered
by HyperFrames twice as transparent layers (back, front), then
   video → back layer → person → front layer
is composited over the whole base in one pass. Use the output as finish.py "base" (captions,
zooms, music, SFX come after, so they stay on top). Head position is measured from the matte,
so effects place themselves around the head.

depth.json (times on the OUTPUT timeline, seconds):
{
  "matte": {"type": "bluekey", "lo": 35, "hi": 60},     // plain blue wall; or {"type": "ai"} (any background, slow on CPU)
  "accent": "#FFC400", "dir": "rtl", "digits": "fa",
  "fonts": {"body": "Vazirmatn-Bold.ttf", "display": "Lalezar-Regular.ttf"},
  "effects": [
    {"type": "logo_orbit", "t0": 3.2, "t1": 6.4, "logos": ["brand:claude", "brand:notion", "brand:openai", "brand:perplexity", "brand:googlegemini", "brand:slack"]},
    {"type": "claude_window", "t0": 8, "t1": 12, "side": "right", "prompt": "یه ریلز از این ویس بساز", "reply": "حتماً! سه صحنه پیشنهاد می‌کنم…"},
    {"type": "growth_chart", "t0": 14, "t1": 17.5, "value": 250000, "label": "دنبال‌کننده", "bars": [12, 20, 34, 58, 100]},
    {"type": "reel_fan", "t0": 19, "t1": 22, "images": [], "count": 7},          // images empty = frames of this video
    {"type": "before_after", "t0": 24, "t1": 27, "at": 0.6, "labels": ["قبل", "بعد"]},
    {"type": "pixel_title", "t0": 28, "t1": 31, "text": "ادیت حرفه‌ای"}
  ]
}
Windows of 2.5–4 s read best; keep one effect per sentence. Effects land on the spoken word
(t0 = cue start − 0.1 s). "ai" matte ≈ 1.8 s per frame on CPU: keep windows short.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402  (icons, fonts, digits)

GSAP = kit.GSAP


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd[:6]))} …\n{(r.stderr or r.stdout)[-1500:]}")
    return r.stdout


def probe(p: Path) -> dict:
    d = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                       "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(p)]))
    s = d["streams"][0]
    return {"w": s["width"], "h": s["height"], "rate": s["r_frame_rate"], "dur": float(d["format"]["duration"])}


def key_chain(lo, hi):
    """Blue wall → gray matte (person 255, wall 0). Same formula as finish.py."""
    return (f"colorchannelmixer=rr=-0.5:rg=-0.5:rb=1:gr=-0.5:gg=-0.5:gb=1:br=-0.5:bg=-0.5:bb=1,"
            f"format=gray,lut=y='clip(({hi}-val)*255/{hi - lo},0,255)',erosion,gblur=sigma=1.4")


def head_of(mask_png: Path, W: int, H: int) -> dict:
    """Top of head, its centre x and width, from one matte frame."""
    m = np.asarray(Image.open(mask_png).convert("L")) > 128
    rows = np.where(m.sum(1) > 0.012 * W)[0]
    if not len(rows):
        return {"x": W / 2, "top": H * 0.3, "w": W * 0.22, "cy": H * 0.38, "found": False}
    top = int(rows[0])
    band = m[top: top + int(0.07 * H)]
    xs = np.where(band.any(0))[0]
    cx = float(xs.mean()) if len(xs) else W / 2
    row = m[min(H - 1, top + int(0.06 * H))]
    hw = float(row.sum()) or W * 0.22
    return {"x": cx, "top": top, "w": hw, "cy": top + 0.62 * hw, "found": True}


# ---------------------------------------------------------------- effects: (html, css, js-body)
# js-body runs inside fonts.ready; `tl` is the effect timeline, `L` the layer being rendered,
# `R(seed)` a seeded PRNG, `ease` helpers. Elements carry data-depth="back" | "front".

JS_LIB = """
const L = document.getElementById('root').dataset.depth;
function R(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;}}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), lerp=(a,b,p)=>a+(b-a)*p;
const eOut=p=>1-Math.pow(1-p,3), eInOut=p=>p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2, eBack=p=>1+2.7*Math.pow(p-1,3)+1.7*Math.pow(p-1,2);
function clock(dur, draw){const o={t:0}; tl.to(o,{t:dur,duration:dur,ease:"none",onUpdate:()=>draw(o.t)},0); draw(0);}
"""


def fx_logo_orbit(e, W, H, hd, spec):
    logos = e.get("logos") or ["sparkles", "zap", "music", "camera", "star", "heart"]
    n, dur = len(logos), e["t1"] - e["t0"]
    tile = int(e.get("size", 0.11 * W))
    tiles = "".join(f'<div class="ot" id="ot{i}" data-depth="dyn">{kit.icon_svg(l, int(tile * .55), 2)}</div>' for i, l in enumerate(logos))
    css = f""".ot {{ position:absolute; left:0; top:0; width:{tile}px; height:{tile}px; border-radius:{tile * .26:.0f}px;
  display:flex; align-items:center; justify-content:center; background:#111318; color:#fff;
  box-shadow:0 10px 30px rgba(0,0,0,.45), inset 0 0 0 1.5px rgba(255,255,255,.14); }}"""
    cx, cy = hd["x"], hd["cy"] + hd["w"] * 0.35
    rx, ry, tilt = e.get("rx", 0.40 * W), e.get("ry", 0.075 * W), e.get("tilt", -9)
    js = f"""
const n={n}, cx={cx:.1f}, cy={cy:.1f}, rx={rx:.1f}, ry={ry:.1f}, tilt={tilt}*Math.PI/180, D={dur:.3f}, T={tile};
const els=[...Array(n)].map((_,i)=>document.getElementById('ot'+i));
clock(D, t=>{{
  const pin=eOut(clamp(t/0.8,0,1)), pout=clamp((t-(D-0.55))/0.55,0,1);
  const spin = (1-pin)*2.4 + t*0.55;            // fast spin-in, then a slow drift
  const rad = (0.25+0.75*eBack(pin)) * (1+0.9*pout*pout);
  els.forEach((el,i)=>{{
    const a = spin + i/n*Math.PI*2, ex=Math.cos(a)*rx*rad, ey=Math.sin(a)*ry*rad;
    const x = cx + ex*Math.cos(tilt) - ey*Math.sin(tilt), y = cy + ex*Math.sin(tilt) + ey*Math.cos(tilt);
    const near = Math.sin(a) > 0, depth = (Math.sin(a)+1)/2;
    const s = (0.62+0.48*depth)*pin;
    const show = (L==='front') === near;
    el.style.transform = `translate(${{x-T/2}}px,${{y-T/2}}px) scale(${{s}})`;
    el.style.filter = near ? 'none' : `blur(${{(1-depth)*4}}px)`;
    el.style.opacity = show ? (0.55+0.45*depth)*(1-pout) : 0;
    el.style.zIndex = Math.round(depth*100);
  }});
}});"""
    return tiles, css, js


def fx_claude_window(e, W, H, hd, spec):
    side = 1 if e.get("side", "right") == "right" else -1
    ww = int(e.get("width", 0.56 * W))
    # beside the head, overlapping it a little (so it reads as coming from behind), kept inside the frame
    x_end = hd["x"] + side * (hd["w"] * 0.5 + ww * 0.3)
    x_end = min(max(x_end, ww / 2 + 0.03 * W), W - ww / 2 - 0.03 * W)
    y = hd["cy"] - 0.05 * H
    logo = kit.icon_svg(e.get("logo", "brand:claude"), 38)
    lines = "".join(f'<div class="sk" style="width:{w}%"></div>' for w in (92, 78, 86, 54))
    html = f"""<div id="cw" data-depth="back" style="left:{x_end - ww / 2:.0f}px;top:{y - 0.13 * H:.0f}px;width:{ww}px">
  <div class="cw-bar"><i></i><i></i><i></i><span>{logo} {kit.esc(e.get("app", "Claude"))}</span></div>
  <div class="cw-body"><div id="cw-me" class="cw-me">{kit.esc(e.get("prompt", ""))}</div>
  <div id="cw-ai" class="cw-ai"><div class="cw-av">{logo}</div><div style="flex:1">
  <div id="cw-txt" class="cw-txt">{kit.esc(e.get("reply", ""))}</div>{lines}<div id="cw-sweep"></div></div></div></div></div>
<div id="cw-chip" data-depth="front" style="left:{hd['x'] - side * 0.05 * W - 110:.0f}px;top:{hd['top'] + 2.6 * hd['w']:.0f}px">{logo}<b>{kit.esc(e.get("app", "Claude"))}</b></div>"""
    css = f"""#cw {{ position:absolute; border-radius:28px; background:#FAF9F7; color:#1d1b19; overflow:hidden;
  box-shadow:0 30px 80px rgba(0,0,0,.45); font-size:{0.03 * W:.0f}px; }}
.cw-bar {{ display:flex; gap:10px; align-items:center; padding:18px 22px; background:#EFECE6; direction:ltr; }}
.cw-bar i {{ width:16px; height:16px; border-radius:50%; background:#d9d4cc; display:block; }}
.cw-bar span {{ margin-left:14px; display:flex; gap:10px; align-items:center; font-family:Inter; font-size:26px; color:#D97757; }}
.cw-body {{ padding:28px; }} .cw-me {{ background:#ECE7DF; border-radius:22px; padding:18px 24px; margin-bottom:24px; }}
.cw-ai {{ display:flex; gap:18px; position:relative; }} .cw-av {{ color:#D97757; flex:none; }}
.cw-txt {{ margin-bottom:14px; }} .sk {{ height:20px; border-radius:10px; background:#E4DFD7; margin:12px 0; }}
#cw-sweep {{ position:absolute; top:0; bottom:0; width:40%; background:linear-gradient(90deg,rgba(255,255,255,0),rgba(255,255,255,.75),rgba(255,255,255,0)); }}
#cw-chip {{ position:absolute; width:220px; display:flex; gap:12px; align-items:center; justify-content:center; padding:16px;
  border-radius:999px; background:rgba(255,255,255,.18); color:#fff; border:1.5px solid rgba(255,255,255,.35);
  backdrop-filter:blur(14px); font-family:Inter; font-size:30px; box-shadow:0 10px 30px rgba(0,0,0,.25); }}"""
    dx = hd["x"] - x_end
    js = f"""
tl.fromTo("#cw", {{x:{dx:.0f}, scale:0.55, rotationY:{side * 35}, opacity:0, transformPerspective:1400}},
  {{x:0, scale:1, rotationY:{-12 * side}, opacity:1, duration:0.75, ease:"expo.out"}}, 0.05);
tl.fromTo("#cw-me", {{opacity:0, y:16}}, {{opacity:1, y:0, duration:0.3}}, 0.6);
tl.fromTo("#cw-ai", {{opacity:0}}, {{opacity:1, duration:0.2}}, 1.0);
tl.fromTo("#cw-txt", {{clipPath:"inset(0 0 0 100%)"}}, {{clipPath:"inset(0 0 0 0%)", duration:1.0, ease:"none"}}, 1.05);
tl.fromTo("#cw .sk", {{scaleX:0, transformOrigin:"{"right" if spec.get("dir") == "rtl" else "left"} center"}}, {{scaleX:1, duration:0.35, stagger:0.18, ease:"power2.out"}}, 1.4);
tl.fromTo("#cw-sweep", {{xPercent:-120}}, {{xPercent:260, duration:0.9, ease:"power1.inOut", repeat:1, repeatDelay:0.2}}, 1.5);
tl.fromTo("#cw-chip", {{opacity:0, scale:0.6, y:20}}, {{opacity:1, scale:1, y:0, duration:0.4, ease:"back.out(2)"}}, 0.9);
tl.to(["#cw","#cw-chip"], {{opacity:0, duration:0.3}}, {e['t1'] - e['t0'] - 0.32:.2f});"""
    return html, css, js


def fx_growth_chart(e, W, H, hd, spec):
    bars = e.get("bars") or [12, 20, 34, 58, 100]
    n, top = len(bars), max(bars)
    bw, gap = 0.13 * W, 0.05 * W
    total = n * bw + (n - 1) * gap
    x0, base_y, hmax = (W - total) / 2, hd["top"] + 2.9 * hd["w"], 0.42 * H
    cols = "".join(
        f'<div class="b3" id="b{i}" data-depth="back" style="left:{x0 + i * (bw + gap):.0f}px;top:{base_y - hmax:.0f}px;width:{bw:.0f}px;height:{hmax:.0f}px">'
        f'<div class="b3f" id="bf{i}" style="height:{v / top * 100:.1f}%"><i class="b3t"></i><i class="b3s"></i></div></div>' for i, v in enumerate(bars))
    num = f'<div id="gnum" data-depth="back" style="top:{max(40, hd["top"] - 0.2 * H):.0f}px"><span id="gval">0</span><small>{kit.esc(e.get("label", ""))}</small></div>'
    html = cols + num  # no wrapper div: HyperFrames clips nested wrappers to zero size
    ac = spec.get("accent", "#FFC400")
    css = f""".b3 {{ position:absolute; display:flex; align-items:flex-end; }}
.b3f {{ position:relative; width:100%; transform-origin:bottom; background:linear-gradient({ac}, #FF8A00); border-radius:6px 6px 0 0; }}
.b3t {{ position:absolute; left:0; right:0; top:-26px; height:26px; background:#FFE38A; transform:skewX(-45deg); transform-origin:bottom left; }}
.b3s {{ position:absolute; top:-26px; bottom:0; right:-26px; width:26px; background:#C46A00; transform:skewY(-45deg); transform-origin:top left; }}
#gnum {{ position:absolute; left:0; right:0; text-align:center; color:#fff; font-family:'display','body',sans-serif;
  font-size:{0.16 * W:.0f}px; line-height:1; text-shadow:0 8px 30px rgba(0,0,0,.4); }}
#gnum small {{ display:block; font-family:'body',sans-serif; font-size:{0.045 * W:.0f}px; margin-top:12px; opacity:.9; }}"""
    fa = "true" if spec.get("digits") == "fa" else "false"
    js = f"""
tl.fromTo("#root .b3f", {{scaleY:0}}, {{scaleY:1, duration:1.3, ease:"power3.out", stagger:0.12}}, 0.15);
tl.fromTo("#gnum", {{opacity:0, y:30}}, {{opacity:1, y:0, duration:0.4, ease:"back.out(1.8)"}}, 0.1);
(function(){{const o={{v:0}}, el=document.getElementById('gval'); tl.to(o,{{v:{e.get('value', 100)}, duration:1.8, ease:"power3.out", onUpdate:()=>{{
  let s=Math.round(o.v).toLocaleString('en-US'); if({fa}) s=s.replace(/[0-9]/g,c=>'۰۱۲۳۴۵۶۷۸۹'[c]).replace(/,/g,'٬'); el.textContent=s; }}}}, 0.15);}})();
tl.to("#root .b3, #gnum", {{opacity:0, duration:0.3}}, {e['t1'] - e['t0'] - 0.32:.2f});"""
    return html, css, js


def fx_reel_fan(e, W, H, hd, spec, images):
    n = len(images)
    cw, ch = 0.2 * W, 0.2 * W * 16 / 9
    cards = "".join(f'<div class="rf" id="rf{i}" data-depth="back"><img src="{src}"></div>' for i, src in enumerate(images))
    css = f""".rf {{ position:absolute; left:{hd['x'] - cw / 2:.0f}px; top:{hd['cy'] - ch * 0.55:.0f}px; width:{cw:.0f}px; height:{ch:.0f}px;
  border-radius:22px; overflow:hidden; border:4px solid #fff; box-shadow:0 18px 40px rgba(0,0,0,.45); transform-origin:50% 180%; }}
.rf img {{ width:100%; height:100%; object-fit:cover; display:block; }}"""
    spread = e.get("spread", 100)
    js = "".join(
        f'tl.fromTo("#rf{i}", {{rotation:0, scale:0.5, opacity:0}}, {{rotation:{-spread / 2 + spread * i / max(1, n - 1):.1f}, scale:1, opacity:1, '
        f'duration:0.7, ease:"back.out(1.5)"}}, {0.1 + 0.06 * abs(i - (n - 1) / 2):.2f});' for i in range(n))
    js += f'tl.to("#root .rf", {{rotation:0, scale:0.4, opacity:0, duration:0.4, ease:"power2.in"}}, {e["t1"] - e["t0"] - 0.45:.2f});'
    return cards, css, js


def fx_before_after(e, W, H, hd, spec):
    rtl = spec.get("dir", "rtl") == "rtl"
    labels = e.get("labels") or []
    lab = "".join(f'<div class="bal" id="bal{i}" data-depth="front">{kit.esc(t)}</div>' for i, t in enumerate(labels[:2]))
    html = f"""<div id="studio" data-depth="back"><div id="floor"></div><div id="shadow"></div></div>
<div id="wline" data-depth="front"></div>{lab}"""
    css = f"""#studio {{ position:absolute; inset:0; background:radial-gradient(ellipse at 50% 38%, #FFFFFF 0%, #F1F1F3 55%, #DCDCE0 100%); }}
#floor {{ position:absolute; left:0; right:0; bottom:0; height:24%; background:linear-gradient(#ECECEF, #D9D9DE); }}
#shadow {{ position:absolute; left:{hd['x'] - 0.3 * W:.0f}px; width:{0.6 * W:.0f}px; bottom:3%; height:6%; border-radius:50%;
  background:radial-gradient(closest-side, rgba(0,0,0,.28), rgba(0,0,0,0)); }}
#wline {{ position:absolute; top:0; bottom:0; width:6px; background:#fff; box-shadow:0 0 24px rgba(255,255,255,.9); }}
.bal {{ position:absolute; top:{0.08 * H:.0f}px; padding:12px 30px; border-radius:999px; font-family:'body',sans-serif; font-size:{0.04 * W:.0f}px;
  background:rgba(0,0,0,.55); color:#fff; }} #bal0 {{ {"right" if rtl else "left"}:60px; }} #bal1 {{ {"left" if rtl else "right"}:60px; background:#111; }}"""
    at, d = e.get("at", 0.6), e.get("wipe_s", 0.9)
    frm, to = ("inset(0 0 0 100%)", "inset(0 0 0 0%)") if rtl else ("inset(0 100% 0 0)", "inset(0 0% 0 0)")
    x0, x1 = (W, -6) if rtl else (-6, W)
    js = f"""
tl.fromTo("#studio", {{clipPath:"{frm}"}}, {{clipPath:"{to}", duration:{d}, ease:"power2.inOut"}}, {at});
tl.fromTo("#wline", {{x:{x0}, opacity:1}}, {{x:{x1}, duration:{d}, ease:"power2.inOut"}}, {at});
tl.set("#wline", {{opacity:0}}, {at + d});
tl.fromTo("#bal0", {{opacity:0, y:-20}}, {{opacity:1, y:0, duration:0.3}}, 0.05); tl.to("#bal0", {{opacity:0, duration:0.2}}, {at});
tl.fromTo("#bal1", {{opacity:0, y:-20}}, {{opacity:1, y:0, duration:0.3}}, {at + d});"""
    return html, css, js


def fx_pixel_title(e, W, H, hd, spec):
    ac = spec.get("accent", "#FFC400")
    box_h = 0.12 * H
    y = max(30, hd["top"] - box_h - 0.03 * H)
    html = f'<canvas id="px" data-depth="{e.get("layer", "front")}" width="{W}" height="{H}"></canvas>'
    css = "#px { position:absolute; left:0; top:0; }"
    js = f"""
const cv=document.getElementById('px'), g=cv.getContext('2d'), off=document.createElement('canvas');
off.width={W}; off.height={int(box_h)}; const o=off.getContext('2d');
let fs={0.13 * W:.0f}; o.font=`${{fs}}px display, body, sans-serif`; o.direction='{spec.get("dir", "rtl")}';
const txt={kit.js(e["text"])}; while(o.measureText(txt).width>{0.9 * W:.0f} && fs>30){{fs-=4; o.font=`${{fs}}px display, body, sans-serif`;}}
o.fillStyle='#fff'; o.textAlign='center'; o.textBaseline='middle'; o.fillText(txt,{W / 2},{box_h / 2:.0f});
const step={e.get("step", 9)}, px=o.getImageData(0,0,off.width,off.height).data, dots=[], rnd=R(11);
for(let yy=0;yy<off.height;yy+=step) for(let xx=0;xx<off.width;xx+=step) if(px[(yy*off.width+xx)*4+3]>128)
  dots.push({{x:xx, y:yy+{y:.0f}, sx:rnd()*{W}, sy:{y + box_h:.0f}+rnd()*{0.25 * H:.0f}, d:rnd()*0.5+xx/{W}*0.3}});
const D={e['t1'] - e['t0']:.3f};
clock(D, t=>{{ g.clearRect(0,0,{W},{H}); const out=clamp((t-(D-0.45))/0.45,0,1);
  for(const p of dots){{ const k=eInOut(clamp((t-0.1-p.d)/0.75,0,1));
    const x=lerp(p.sx,p.x,k), yy=lerp(p.sy,p.y,k)-out*60, r=(step*0.42)*(0.4+0.6*k);
    g.globalAlpha=(0.25+0.75*k)*(1-out); g.fillStyle=k>0.98?'{ac}':'#fff'; g.beginPath(); g.arc(x,yy,r,0,6.2832); g.fill(); }} }});"""
    return html, css, js


EFFECTS = {"logo_orbit": fx_logo_orbit, "claude_window": fx_claude_window, "growth_chart": fx_growth_chart,
           "reel_fan": fx_reel_fan, "before_after": fx_before_after, "pixel_title": fx_pixel_title}


# ---------------------------------------------------------------- build + render

def write_project(d: Path, layer, W, H, dur, html, css, js, spec):
    (d / "compositions").mkdir(parents=True, exist_ok=True)
    (d / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    fonts = kit.fonts_of(spec)
    for f in set(fonts.values()):
        shutil.copy2(kit.DATA / "fonts" / f, d / "assets" / "fonts" / f)
    faces = "".join(f"@font-face {{ font-family:'{r}'; src:url('assets/fonts/{f}'); }}\n" for r, f in fonts.items())
    (d / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "assets": "assets"}}), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps({"id": d.name, "name": d.name}), encoding="utf-8")
    loads = ",".join(f"document.fonts.load('700 60px {r}')" for r in fonts)
    (d / "compositions" / "fx.html").write_text(f"""<template>
  <style>{faces}
#root {{ position:absolute; inset:0; font-family:'body', Inter, sans-serif; font-weight:700; direction:{spec.get('dir', 'rtl')}; }}
#root > *, #root [data-depth] {{ position:absolute; }}
#root[data-depth=back] [data-depth=front], #root[data-depth=front] [data-depth=back] {{ visibility:hidden !important; }}
{css}</style>
  <div id="root" data-composition-id="fx" data-depth="{layer}" data-width="{W}" data-height="{H}" data-layout-allow-overflow data-layout-allow-overlap>{html}</div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    Promise.all([{loads}]).then(() => {{
{JS_LIB}
{js}
      window.__timelines["fx"] = tl;
    }});
  </script>
</template>
""", encoding="utf-8")
    (d / "index.html").write_text(f"""<!doctype html>
<html><head><meta charset="UTF-8" /><meta name="viewport" content="width={W}, height={H}" />
<script src="{GSAP}"></script>
<style>* {{ margin:0; padding:0; box-sizing:border-box; }} html, body {{ width:{W}px; height:{H}px; overflow:hidden; background:transparent; }}</style>
</head><body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{H}">
    <div id="fx-host" data-composition-id="fx" data-composition-src="compositions/fx.html" data-start="0" data-duration="{dur:.3f}"
      data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
  </div>
  <script>window.__timelines["main"] = gsap.timeline({{ paused: true }});</script>
</body></html>
""", encoding="utf-8")


def render(d: Path, out: Path):
    # Uses HyperFrames' own hidden headless Chrome (setup runs `hyperframes browser ensure`): no windows open
    env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1"}
    cmd = ["npx", "--yes", "hyperframes", "render", ".", "--format", "webm", "--output", str(out)]
    for attempt in range(3):  # the preview server sometimes picks a browser-blocked port (ERR_UNSAFE_PORT): retry
        r = subprocess.run(cmd, cwd=d, env=env, shell=sys.platform == "win32", capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode == 0 or "ERR_UNSAFE_PORT" not in (r.stdout + r.stderr):
            break
    if r.returncode:
        sys.exit(f"render failed in {d}:\n{(r.stderr or r.stdout)[-1500:]}")
    if not out.exists():
        sys.exit(f"render produced no {out}")


def main():
    ap = argparse.ArgumentParser(description="Depth effects around the speaker")
    ap.add_argument("edit_dir", type=Path)
    ap.add_argument("--spec", default="depth.json")
    ap.add_argument("--base", default="base_preview.mp4")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--only", type=int, help="rebuild only effect N (0-based); others reuse their renders")
    a = ap.parse_args()
    E = a.edit_dir.resolve()
    spec = kit.apply_brand(json.loads((E / a.spec).read_text(encoding="utf-8")), E)  # MP Studio colours/fonts fill the gaps
    base = E / a.base
    info = probe(base)
    W, H = info["w"], info["h"]
    m = spec.get("matte", {"type": "bluekey"})
    work = E / "depth"
    layers = []  # (t0, dur, back, subject_or_None, front)
    for i, e in enumerate(spec["effects"]):
        if e["type"] not in EFFECTS:
            sys.exit(f"unknown effect {e['type']} (have: {', '.join(EFFECTS)})")
        t0, dur = float(e["t0"]), float(e["t1"]) - float(e["t0"])
        d = work / f"e{i:02d}_{e['type']}"
        d.mkdir(parents=True, exist_ok=True)
        back, front, subj = d / "back.webm", d / "front.webm", d / "subject.mov"
        if a.only is not None and a.only != i and (back.exists() or front.exists()):
            layers.append((t0, dur, back if back.exists() else None, subj if subj.exists() and m.get("type") == "ai" else None,
                           front if front.exists() else None))
            continue
        clip, mask = d / "clip.mp4", d / "mask.png"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}", "-i", str(base), "-t", f"{dur:.3f}", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", str(clip)])
        if m.get("type") == "ai":
            sh(["npx", "--yes", "hyperframes", "remove-background", str(clip), "-o", str(subj), "--quality", "best"],
               env={**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1"}, shell=sys.platform == "win32")
            sh(["ffmpeg", "-y", "-v", "error", "-i", str(subj), "-vf", "alphaextract", "-frames:v", "1", str(mask)])
        else:
            sh(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-vf", "format=rgb24," + key_chain(m.get("lo", 35), m.get("hi", 60)),
                "-frames:v", "1", str(mask)])
            subj = None
        hd = head_of(mask, W, H)
        print(f"[{i}] {e['type']} {t0:.2f}-{t0 + dur:.2f}s  head x={hd['x']:.0f} top={hd['top']:.0f} w={hd['w']:.0f}"
              f"{'' if hd['found'] else '  (no person found: centred defaults)'}")
        if e["type"] == "reel_fan":
            imgs = e.get("images") or []
            (d / "assets").mkdir(exist_ok=True)
            srcs = []
            if imgs:
                for k, p in enumerate(imgs):
                    dst = d / "assets" / f"r{k}{Path(p).suffix}"
                    shutil.copy2((E / p) if not Path(p).is_absolute() else p, dst)
                    srcs.append(f"assets/{dst.name}")
            else:
                cnt = e.get("count", 7)
                for k in range(cnt):
                    tt = info["dur"] * (k + 0.5) / cnt
                    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{tt:.2f}", "-i", str(base), "-frames:v", "1",
                        "-vf", "scale=360:-2", str(d / "assets" / f"r{k}.jpg")])
                    srcs.append(f"assets/r{k}.jpg")
            parts = fx_reel_fan(e, W, H, hd, spec, srcs)
        else:
            parts = EFFECTS[e["type"]](e, W, H, hd, spec)
        html = parts[0]
        has = {"back": 'data-depth="back"' in html or 'data-depth="dyn"' in html,
               "front": 'data-depth="front"' in html or 'data-depth="dyn"' in html}
        out = {}
        for layer in ("back", "front"):
            if not has[layer]:
                continue
            pd = d / layer
            write_project(pd, layer, W, H, dur, *parts, spec)
            render(pd, d / f"{layer}.webm")
            out[layer] = d / f"{layer}.webm"
        for layer in ("back", "front"):
            if layer not in out and (d / f"{layer}.webm").exists():
                (d / f"{layer}.webm").unlink()
        layers.append((t0, dur, out.get("back"), subj, out.get("front")))

    # ---------- one compositing pass over the whole base
    inputs, g, n = ["-i", str(base)], [], 1
    cur = "[0:v]"
    bluekey = m.get("type") != "ai"
    if bluekey:
        g.append(f"[0:v]split=2[vb][vk];[vk]format=rgb24,split=2[kc][km];[km]{key_chain(m.get('lo', 35), m.get('hi', 60))}[mk];"
                 f"[kc][mk]alphamerge,split={len(layers)}" + "".join(f"[pp{i}]" for i in range(len(layers))) + ";")
        cur = "[vb]"
    for i, (t0, dur, back, subj, front) in enumerate(layers):
        en = f"enable='between(t,{t0:.3f},{t0 + dur:.3f})'"
        for kind, src in (("b", back), ("s", subj), ("f", front)):
            if kind == "s" and bluekey:
                g.append(f"{cur}[pp{i}]overlay=format=auto:{en}[v{i}s];")
                cur = f"[v{i}s]"
                continue
            if src is None:
                continue
            if src.suffix == ".webm":
                inputs += ["-c:v", "libvpx-vp9"]
            inputs += ["-i", str(src)]
            g.append(f"[{n}:v]setpts=PTS-STARTPTS+{t0:.3f}/TB[i{n}];{cur}[i{n}]overlay=format=auto:eof_action=pass:{en}[v{i}{kind}];")
            cur, n = f"[v{i}{kind}]", n + 1
    g.append(f"{cur}format=yuv420p[out]")
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", "".join(g), "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", info["rate"], "-c:a", "copy", str(a.output.resolve())])
    print(f"done: {a.output}  ({len(layers)} depth effects) → fx.json \"base\": \"{a.output.name}\"")


if __name__ == "__main__":
    main()
