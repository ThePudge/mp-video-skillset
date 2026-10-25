"""Finishing pass on a cut video: cut-outs, animated zooms, VFX, captions/motion, music + SFX mix.

  finish.py <edit_dir> -o <out.mp4> [--spec fx.json] [--preview]

Input is the graded cut WITHOUT captions (render.py writes it as base_preview.mp4 / base.mp4).
Order: cut-out windows (background treatment + master_behind.ass under the speaker) → animated
zoom → flashes / glitches / vignette / grain → master.ass on top (captions + cards) → audio mix
(voice clean-up, ducked music, timed SFX) → two-pass loudnorm to -14 LUFS.

fx.json (times on the OUTPUT timeline, seconds):
{
  "base": "base_preview.mp4",
  "front": "master.ass", "behind": "master_behind.ass", "fonts_dir": "../../../fonts",
  "matte": {"type": "bluekey", "lo": 35, "hi": 60},     // blueness = B-(R+G)/2: >=hi is wall, <=lo is person
     // or {"type": "video", "file": "matte/matte.mp4"}: AI person matte (any wall), white = person, same timeline
  "cutouts": [{"t0": 10.8, "t1": 15.4, "brightness": -0.12, "saturation": 0.8, "blur": 0},
              {"t0": 0, "t1": 2.4, "color": "0x1F3A2C"}],   // color = flat background instead
  "zoom_center": [0.5, 0.42],
  "zooms": [{"t0": 0, "t1": 10.6, "z0": 1.0, "z1": 1.1, "ease": "inout"},
            {"t0": 14.1, "t1": 14.25, "z0": 1.0, "z1": 1.18, "ease": "out", "hold_to": 15.4}],
  "layout": {"type": "split", "panel": "../panel/panel.mp4", "panel_h": 768, "crop_y": 400},
     // or pop-out window (head breaks out of a rounded window, dark dotted canvas above, needs the matte):
     // {"type": "popout", "windows": [[5.0, 8.7], [18.2, 23.0]], "scale": 0.9, "box_y": 1240,
     //  "box_w": 960, "box_h": 560, "anchor_y": 790, "radius": 40, "canvas": "0x0E0E0E",
     //  "panel": "../panel/panel_dark.mp4", "panel_y": 140, "enter": "slide", "enter_s": 0.4}
     // panel = a HyperFrames film on the same timeline (dark theme), shown on the canvas above the window
  "broll": [{"file": "D:/…/input/<project>/screen.mp4", "t": 12.4, "dur": 2.6, "from": 0.3}],  // muted cutaways
  "grades": [{"t0": 13.7, "t1": 23.8, "look": "warm", "in": 0.5},               // warm | dark | any filter chain
             {"t0": 36.7, "t1": 41.8, "look": "dark", "wipe": true, "in": 0.7}], // wipe = grows from the top down
  "behind_video": "../hf_behind/renders/behind.webm",  // alpha video under the speaker inside every cut-out window
  "front_video": "../hf/renders/front.webm",           // alpha video over everything (HyperFrames cards + captions)
  "flash": [10.76, 25.7], "glitch": [[28.05, 28.2]], "vignette": true, "grain": 5,
  "voice": {"highpass": 80, "compress": true},
  "music": {"file": "../../../assets/music/bed.wav", "db": -22, "duck": true},
  "sfx_dir": "../../../assets/sfx",
  "sfx": [{"name": "whoosh", "t": 10.62, "db": -16}]
}
Relative paths resolve from the edit dir. matte "bluekey" needs a plain blue wall; for other
backgrounds use an AI matte video: subject-cutout/matte.py (picks the fastest CPU/GPU on this computer).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("edit_dir", type=Path)
ap.add_argument("-o", "--output", type=Path, required=True)
ap.add_argument("--spec", default="fx.json")
ap.add_argument("--preview", action="store_true", help="fast encode for review")
a = ap.parse_args()

E = a.edit_dir.resolve()
spec = json.loads((E / a.spec).read_text(encoding="utf-8"))
out = a.output.resolve()
base = E / spec.get("base", "base_preview.mp4")


def probe(p, entries):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return r.stdout.split()


W, H, fps_s = probe(base, "stream=width,height,r_frame_rate")
W, H = int(W), int(H)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=nw=1:nk=1", str(base)], capture_output=True, text=True).stdout)
rel = lambda p: os.path.relpath((E / p).resolve(), E).replace("\\", "/")
fonts = rel(spec.get("fonts_dir", "../../../fonts"))
g = []  # filter graph lines
inputs = ["-reinit_filter", "0", "-i", str(base)]  # 0 = cut (no mid-stream graph rebuild: it would reset frame counts); layout panel, music and SFX append theirs

# ---------- 1. cut-out windows ----------
cuts = sorted(spec.get("cutouts", []), key=lambda c: c["t0"])
parts, t = [], 0.0
for c in cuts:
    if c["t0"] > t:
        parts.append(("plain", t, c["t0"], None))
    parts.append(("cut", c["t0"], min(c["t1"], dur), c))
    t = min(c["t1"], dur)
if t < dur:
    parts.append(("plain", t, dur, None))

m = spec.get("matte", {"type": "bluekey", "lo": 35, "hi": 60})
lo, hi = m.get("lo", 35), m.get("hi", 60)
behind = spec.get("behind", "master_behind.ass")
has_behind = (E / behind).exists()
bvid = spec.get("behind_video")  # alpha video (e.g. HyperFrames WebM) drawn under the speaker in every cut-out window
bdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                             str((E / bvid).resolve())], capture_output=True, text=True).stdout or 0) if bvid else 0
# only windows the behind video reaches: a branch that never gets a frame stalls the whole graph
bwin = {i for i, p in enumerate(parts) if p[0] == "cut" and p[1] < bdur - 0.05}
ncut = len(bwin)


def alpha_input(path):
    """-i args for an alpha video: WebM needs the libvpx decoder to keep its alpha channel"""
    p = str((E / path).resolve())
    return (["-c:v", "libvpx-vp9", "-i", p] if p.lower().endswith(".webm") else ["-i", p])


if bvid and ncut:
    bidx = inputs.count("-i")
    inputs += alpha_input(bvid)
    g.append(f"[{bidx}:v]format=rgba,split={ncut}" + "".join(f"[bvs{k}]" for k in range(ncut)) + ";")

g.append("[0:v]setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709,"  # one set of tags for every segment
         f"split={len(parts)}" + "".join(f"[s{i}]" for i in range(len(parts))) + ";")
kcut = 0
for i, (kind, t0, t1, c) in enumerate(parts):
    trim = f"[s{i}]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS"
    if kind == "plain":
        g.append(f"{trim},format=yuv420p,setsar=1[p{i}];")
        continue
    bg = [f"eq=brightness={c.get('brightness', -0.15)}:saturation={c.get('saturation', 0.8)}"]
    if c.get("color"):  # flat background colour behind the speaker (hook / title moments)
        bg = [f"drawbox=x=0:y=0:w=iw:h=ih:color={c['color']}:t=fill"]
    elif c.get("blur"):
        bg.append(f"gblur=sigma={c['blur']}")
    if has_behind:  # ASS times are absolute: shift to the window, burn, shift back
        bg.append(f"setpts=PTS+{t0:.3f}/TB,subtitles={behind}:fontsdir={fonts},setpts=PTS-STARTPTS")
    g.append(f"{trim},format=rgb24,split=3[b{i}][f{i}][k{i}];")
    g.append(f"[b{i}]{','.join(bg)}[bg{i}];")
    if i in bwin:
        g.append(f"[bvs{kcut}]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS[bv{i}];"
                 f"[bg{i}][bv{i}]overlay=format=auto:eof_action=pass,format=rgb24[bgx{i}];")
        kcut += 1
    else:
        g.append(f"[bg{i}]null[bgx{i}];")
    # blueness B-(R+G)/2 in every channel → gray → wall (>=hi) 0, person (<=lo) 255
    g.append(f"[k{i}]colorchannelmixer=rr=-0.5:rg=-0.5:rb=1:gr=-0.5:gg=-0.5:gb=1:br=-0.5:bg=-0.5:bb=1,"
             f"format=gray,lut=y='clip(({hi}-val)*255/{hi - lo},0,255)',erosion,gblur=sigma=1.4[m{i}];")
    g.append(f"[f{i}][m{i}]alphamerge[fa{i}];")
    g.append(f"[bgx{i}][fa{i}]overlay=format=auto,format=yuv420p,setsar=1[p{i}];")
g.append("".join(f"[p{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[cv];")

# ---------- 1b. timed grades (warm / dark / any filter chain), faded or wiped top→down ----------
LOOKS = {"warm": "colortemperature=temperature=4500:mix=0.6,eq=saturation=1.08",
         "dark": "eq=brightness=-0.08:contrast=1.12:saturation=0.75:gamma=0.88,colorbalance=bs=0.05:bm=0.03,vignette=angle=PI/4"}
FPS = (lambda n, d=1.0: n / d)(*map(float, fps_s.split("/")))  # "30/1" → 30.0


def windowed(src, wins, apply, tag):
    """run `apply` only inside the time windows (frame-exact trims + concat), pass the rest through untouched.
    apply(label, s0, s1) → label of the processed window (s0/s1 = the window's start/end in seconds)."""
    nf = round(dur * FPS)
    spans, t = [], 0
    for a, b in sorted((max(0, round(a * FPS)), min(nf, round(b * FPS))) for a, b in wins):
        if b <= a:
            continue
        if spans and spans[-1][2] and a <= spans[-1][1]:  # merge overlapping windows
            spans[-1] = (spans[-1][0], max(b, spans[-1][1]), True)
            t = spans[-1][1]
            continue
        if a > t:
            spans.append((t, a, False))
        spans.append((max(a, t), b, True))
        t = b
    if t < nf:
        spans.append((t, nf, False))
    g.append(f"[{src}]split={len(spans)}" + "".join(f"[{tag}s{i}]" for i in range(len(spans))) + ";")
    outs = []
    for i, (fa, fb, on) in enumerate(spans):
        lab = f"{tag}t{i}"
        g.append(f"[{tag}s{i}]trim=start_frame={fa}:end_frame={fb},setpts=N/({fps_s})/TB[{lab}];")
        if on:  # a processed window must keep its exact frame count (mask sources can run a frame long)
            done = apply(lab, fa / FPS, fb / FPS, i)
            g.append(f"[{done}]trim=end_frame={fb - fa},setpts=N/({fps_s})/TB[{lab}x];")
            lab = f"{lab}x"
        outs.append(f"[{lab}]")
    g.append("".join(outs) + f"concat=n={len(spans)}:v=1:a=0[{tag}];")
    return tag


gcur = "cv"
for k, gr in enumerate(spec.get("grades", [])):
    t0, t1, d, d_out = gr["t0"], min(gr["t1"], dur), gr.get("in", 0.4), gr.get("out", 0.3)
    look = LOOKS.get(gr["look"], gr["look"])

    def grade(lab, s0, s1, i, k=k, t0=t0, t1=t1, d=d, d_out=d_out, look=look, gr=gr):
        if d <= 0.05 and d_out <= 0.05 and not gr.get("wipe"):  # hard in/out: just the look, no mask
            g.append(f"[{lab}]{look},format=yuv420p[{lab}g];")
            return f"{lab}g"
        a, b = max(0.0, t0 - s0), max(0.0, t1 - s0)  # window-local times (frame rounding can put s0 a hair past t0)
        mask = f"color=white:s={W}x{H}:r={fps_s}:d={s1 - s0:.3f}"
        if gr.get("wipe"):  # the graded part grows from the top edge down
            mask = (f"{mask}[{lab}w];color=black:s={W}x{H}:r={fps_s}:d={s1 - s0:.3f}[{lab}k];"
                    f"[{lab}w][{lab}k]overlay=x=0:y='{H}*clip((t-{a:.3f})/{d}\\,0\\,1)':eval=frame")
        else:
            mask += f",fade=t=in:st={a:.3f}:d={d}"
        mask += f",fade=t=out:st={b:.3f}:d={d_out}"
        g.append(f"[{lab}]format=gbrp,split[{lab}a][{lab}b];[{lab}b]{look},format=gbrp[{lab}l];{mask},format=gbrp[{lab}m];"
                 f"[{lab}a][{lab}l][{lab}m]maskedmerge,format=yuv420p[{lab}g];")
        return f"{lab}g"

    gcur = windowed(gcur, [(t0, t1 + d_out)], grade, f"gr{k}")
if gcur != "cv":
    g.append(f"[{gcur}]null[cv2];")

# ---------- 2. animated zoom ----------
EASE = {"linear": "{p}", "inout": "({p})*({p})*(3-2*({p}))", "out": "1-(1-({p}))*(1-({p}))",
        "in": "({p})*({p})"}
zooms = sorted(spec.get("zooms", []), key=lambda z: z["t0"])
cur = "cv2" if gcur != "cv" else "cv"
if zooms:
    expr = "1"
    for z in reversed(zooms):
        p = f"(it-{z['t0']})/{max(z['t1'] - z['t0'], 1e-3)}"
        ramp = f"{z['z0']}+({z['z1']}-{z['z0']})*({EASE[z.get('ease', 'inout')].format(p=p)})"
        expr = f"if(between(it,{z['t0']},{z['t1']}),{ramp},{expr})"
        if z.get("hold_to"):
            expr = f"if(between(it,{z['t1']},{z['hold_to']}),{z['z1']},{expr})"
    cx, cy = spec.get("zoom_center", [0.5, 0.42])

    def zoom(lab, s0, s1, i):
        # 2x upscale first: zoompan crops on whole pixels, so this halves the visible stepping
        e = expr.replace("it", f"(it+{s0:.4f})")  # window-local clock → output time
        g.append(f"[{lab}]scale={2 * W}:{2 * H}:flags=bicubic,zoompan=z='{e}':x='(iw-iw/zoom)*{cx}':"
                 f"y='(ih-ih/zoom)*{cy}':d=1:s={W}x{H}:fps={fps_s},setsar=1[{lab}z];")
        return f"{lab}z"

    # only where a zoom is active (the rest is zoom 1 = untouched), so long videos stay fast
    cur = windowed(cur, [(z["t0"], max(z["t1"], z.get("hold_to") or 0) + 1 / FPS) for z in zooms], zoom, "zv")

# ---------- 3. VFX ----------
# ---------- 2a. pop-out window layout: speaker in a rounded window, head breaking out on top ----------
lay = spec.get("layout")
if lay and lay.get("type") == "popout":
    wins = sorted(lay["windows"])
    sc = float(lay.get("scale", 0.9))
    bw, bh = int(lay.get("box_w", 960)), int(lay.get("box_h", 560))
    bx, by = (W - bw) // 2, int(lay.get("box_y", 1240))
    anchor = float(lay.get("anchor_y", 790))       # source y that lands on the window top (eyebrows: the head top breaks out)
    r = int(lay.get("radius", 40))
    sw, sh = round(W * sc / 2) * 2, round(H * sc / 2) * 2
    bw = min(bw, sw)  # vertical footage: the window can't be wider than the scaled speaker
    bx = (W - bw) // 2
    by -= by % 2
    # where the scaled speaker's top sits — kept on an even row: yuv420 chroma is shared by row
    # pairs, so an odd offset shifts colour by one row and draws a visible line at the window edge
    oy = 2 * round((by - anchor * sc) / 2)
    crop_x, crop_y = (sw - bw) // 2, by - oy
    # the head layer reaches `seam` px INTO the window, where it shows the same pixels: the matte's
    # soft bottom edge then blends into identical content instead of the dark canvas (no forehead line)
    seam = min(12, sh - crop_y)
    canvas = lay.get("canvas", "0x0E0E0E")
    pparts, t = [], 0.0
    for w0, w1 in wins:
        if w0 > t:
            pparts.append((False, t, w0))
        pparts.append((True, w0, min(w1, dur)))
        t = min(w1, dur)
    if t < dur:
        pparts.append((False, t, dur))
    g.append(f"[{cur}]split={len(pparts)}" + "".join(f"[q{i}]" for i in range(len(pparts))) + ";")
    fnum, fden = (fps_s.split('/') + ['1'])[:2]
    fps_f = float(fnum) / float(fden)
    for i, (win, t0, t1) in enumerate(pparts):
        L = t1 - t0
        trim = f"[q{i}]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS"
        if not win:
            g.append(f"{trim},format=yuv420p,setsar=1[pp{i}];")
            continue
        n = int(L * fps_f) + 2  # finite per window: an endless looped source makes concat buffer until OOM
        # rounded-corner mask and dotted canvas: drawn once, repeated for exactly this window's frames
        g.append(f"color=c=black:s={bw}x{bh}:r={fps_s}:d=0.04,format=gray,geq=lum='255*lte(pow(max(max({r}-X,X-{bw - 1 - r}),0),2)"
                 f"+pow(max(max({r}-Y,Y-{bh - 1 - r}),0),2),{r * r})',trim=end_frame=1,loop=loop={n}:size=1,"
                 f"setpts=N/({fps_s})/TB,trim=end_frame={n}[rm{i}];")
        g.append(f"color=c={canvas}:s={W}x{H}:r={fps_s}:d=0.04,format=yuv420p,"
                 f"geq=lum='if(lt(mod(X,26),3)*lt(mod(Y,26),3),lum(X,Y)+22,lum(X,Y))':cb=128:cr=128,trim=end_frame=1,"
                 f"loop=loop={n}:size=1,setpts=N/({fps_s})/TB,trim=end_frame={n}[cv{i}];")
        g.append(f"{trim},scale={sw}:{sh},format=rgb24,split=2[qa{i}][qb{i}];")
        g.append(f"[qa{i}]crop={bw}:{bh}:{crop_x}:{crop_y},format=rgba[win{i}];[win{i}][rm{i}]alphamerge=shortest=1[wr{i}];")
        if m.get("type") == "video":  # AI person matte (white = person) on the same timeline as the base
            midx_ = inputs.count("-i")
            inputs += ["-i", str((E / m["file"]).resolve())]
            g.append(f"[qb{i}]crop={bw}:{crop_y + seam}:{crop_x}:0[hc{i}];"
                     f"[{midx_}:v]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS,scale={sw}:{sh},format=gray,"
                     f"crop={bw}:{crop_y + seam}:{crop_x}:0,lut=y='clip((val-40)*255/180,0,255)',erosion,gblur=sigma=1.2[hm{i}];"
                     f"[hc{i}][hm{i}]alphamerge[head{i}];")
        else:
            g.append(f"[qb{i}]crop={bw}:{crop_y + seam}:{crop_x}:0,split[hc{i}][hk{i}];"
                     f"[hk{i}]colorchannelmixer=rr=-0.5:rg=-0.5:rb=1:gr=-0.5:gg=-0.5:gb=1:br=-0.5:bg=-0.5:bb=1,"
                     f"format=gray,lut=y='clip(({hi}-val)*255/{hi - lo},0,255)',erosion,gblur=sigma=1.2[hm{i}];"
                     f"[hc{i}][hm{i}]alphamerge[head{i}];")
        layer = f"[cv{i}]"
        if lay.get("panel"):  # optional HyperFrames canvas graphics, same timeline, above the window
            pidx = inputs.count("-i")
            inputs += ["-i", str((E / lay["panel"]).resolve())]
            g.append(f"[{pidx}:v]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS,scale={W}:-2,format=rgba[pv{i}];")
            g.append(f"{layer}[pv{i}]overlay=0:{int(lay.get('panel_y', 0))}[cp{i}];")
            layer = f"[cp{i}]"
        # "enter": "slide" — the window (and the head on it) rises from below the frame when the
        # edit switches from full frame into the pop-out layout
        dy = (f"+{H - by}*pow(max(0,1-t/{float(lay.get('enter_s', 0.4))}),2)"  # inside '...': commas need no escape
              if lay.get("enter") == "slide" and t0 > 0 else "")
        g.append(f"{layer}[wr{i}]overlay={bx}:'{by}{dy}':shortest=1[cw{i}];"
                 f"[cw{i}][head{i}]overlay={bx}:'{oy}{dy}':shortest=1,format=yuv420p,setsar=1[pp{i}];")
    g.append("".join(f"[pp{i}]" for i in range(len(pparts))) + f"concat=n={len(pparts)}:v=1:a=0[po];")
    cur = "po"

# ---------- 2b. split explainer layout: panel video on top, speaker crop below ----------
if lay and lay.get("type") == "split":
    ph, cy = int(lay.get("panel_h", 768)), int(lay.get("crop_y", 400))
    pidx = inputs.count("-i")
    inputs += ["-i", str((E / lay["panel"]).resolve())]
    g.append(f"[{cur}]crop={W}:{H - ph}:0:{cy}[spk];")
    g.append(f"[{pidx}:v]scale={W}:{ph},fps={fps_s},format=yuv420p,setsar=1,trim=0:{dur:.3f},setpts=PTS-STARTPTS[pan];")
    g.append("[pan][spk]vstack=inputs=2[lay];")
    cur = "lay"

# ---------- 2c. b-roll cutaways: full-frame, muted, over the talk (the speaker's audio keeps playing) ----------
for j, bl in enumerate(spec.get("broll", [])):
    bidx = inputs.count("-i")
    inputs += ["-ss", f"{float(bl.get('from', 0)):.3f}", "-t", f"{float(bl['dur']):.3f}", "-i", str((E / bl["file"]).resolve())]
    t0b, t1b = float(bl["t"]), float(bl["t"]) + float(bl["dur"])
    g.append(f"[{bidx}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps_s},format=yuv420p,"
             f"setsar=1,setpts=PTS-STARTPTS+{t0b:.3f}/TB[br{j}];"
             f"[{cur}][br{j}]overlay=eof_action=pass:enable='between(t,{t0b:.3f},{t1b:.3f})'[bc{j}];")
    cur = f"bc{j}"

fx = []
if spec.get("flash"):
    pulses = "+".join(f"0.55*exp(-pow((t-{t0})/0.05,2))" for t0 in spec["flash"])
    fx.append(f"eq=brightness='{pulses}':eval=frame")
for t0, t1 in spec.get("glitch", []):
    en = f"between(t,{t0},{t1})"
    fx.append(f"rgbashift=rh=-16:bh=16:rv=4:enable='{en}'")
    fx.append(f"noise=alls=45:allf=t:enable='{en}'")
if spec.get("vignette"):
    fx.append("vignette=angle=PI/5")
if spec.get("grain"):
    fx.append(f"noise=alls={spec['grain']}:allf=t+u")
g.append(f"[{cur}]{','.join(fx) or 'null'},format=yuv420p[pre];")
cur = "pre"
# frosted-glass captions: blur the picture only inside the caption boxes (mask drawn by libass from
# glass_mask.ass on black), then master.ass draws the tinted box, edge and text on top
if spec.get("glass", True) and (E / "glass_mask.ass").exists():
    g.append(f"[{cur}]split[gA][gB];[gB]gblur=sigma=24,eq=brightness=0.03:saturation=1.15[gBl];"
             f"color=c=black:s={W}x{H}:r={fps_s}:d={dur:.3f},format=rgb24,"
             f"subtitles=glass_mask.ass:fontsdir={fonts},format=gray[gM];"
             f"[gBl][gM]alphamerge[gG];[gA][gG]overlay=shortest=1:format=auto,format=yuv420p[gl];")
    cur = "gl"
front = spec.get("front", "master.ass")
sub = f"subtitles={front}:fontsdir={fonts}" if (E / front).exists() else "null"
fvid = spec.get("front_video")  # alpha video over everything (HyperFrames cards, UI, captions)
if fvid:
    fidx = inputs.count("-i")
    inputs += alpha_input(fvid)
    g.append(f"[{cur}]{sub},format=yuv420p[vs];[{fidx}:v]format=yuva420p[fv];"
             f"[vs][fv]overlay=format=auto:eof_action=pass,format=yuv420p[vout];")
else:
    g.append(f"[{cur}]{sub},format=yuv420p[vout];")

# ---------- 4. audio ----------
v = spec.get("voice", {})
voice = [f"highpass=f={v.get('highpass', 80)}"] if v.get("highpass", 80) else ["anull"]
if v.get("compress", True):
    voice.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2")
g.append(f"[0:a]{','.join(voice)},aresample=48000,aformat=channel_layouts=stereo,asplit=2[vo][vsc];")
mix = ["[vo]"]
mu = spec.get("music")
if mu:
    midx = inputs.count("-i")
    inputs += ["-i", str((E / mu["file"]).resolve())]
    g.append(f"[{midx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={mu.get('db', -22)}dB,"
             f"atrim=0:{dur:.3f}[mus];")
    if mu.get("duck", True):
        g.append("[mus][vsc]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=350[mus2];")
        mix.append("[mus2]")
    else:
        g.append("[vsc]anullsink;")
        mix.append("[mus]")
else:
    g.append("[vsc]anullsink;")
sdir = spec.get("sfx_dir", "../../../assets/sfx")
for j, s in enumerate(spec.get("sfx", [])):
    idx = inputs.count("-i")
    inputs += ["-i", str((E / sdir / f"{s['name']}.wav").resolve())]
    ms = max(0, round(s["t"] * 1000))
    g.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={s.get('db', -18)}dB,"
             f"adelay={ms}|{ms}[x{j}];")
    mix.append(f"[x{j}]")
g.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,atrim=0:{dur:.3f}[aout]")

script = E / "finish.filter.txt"
script.write_text("\n".join(g), encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hw import FFMPEG, venc as hw_venc  # GPU encoder for previews when NVENC works here; x264 for the final
venc = hw_venc("preview" if a.preview else "final")
tmp = out.with_suffix(".prenorm.mp4")
cmd = [FFMPEG, "-hide_banner", "-loglevel", os.environ.get("MP_FFLOG", "error"), "-y", *inputs, "-/filter_complex", script.name,
       "-map", "[vout]", "-map", "[aout]", *venc, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", str(tmp)]
print(f"finish: {len(parts)} parts ({len(cuts)} cut-outs), {len(zooms)} zooms, "
      f"{len(spec.get('sfx', []))} sfx, music={'yes' if mu else 'no'}")
r = subprocess.run(cmd, cwd=E)
if r.returncode:
    sys.exit(f"ffmpeg failed (graph: {script})")

# ---------- 5. loudness ----------
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video-use" / "helpers"))
import render  # noqa: E402  (video-use helper: two-pass loudnorm to -14 LUFS / -1 dBTP)

render.apply_loudnorm_two_pass(tmp, out, preview=a.preview)
tmp.unlink(missing_ok=True)
print(f"done: {out}")
