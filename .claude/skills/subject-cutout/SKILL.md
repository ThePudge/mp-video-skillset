---
name: subject-cutout
description: Cut the speaker out of their footage to put text or graphics BEHIND them, dim or blur the background, or replace it, all locally. Use when the owner asks for "text behind me", "title behind the person", "darken/blur the background", "remove/replace the background", "cut me out", "green-screen effect", or depth-layered motion graphics in a video-use edit.
---

# Subject cutout

Separates the person from the background so layers can sit between them. Runs
`npx hyperframes remove-background` (model `u2net_human_seg`, Apache-2.0, ~170 MB,
cached in `~/.cache/hyperframes`). Local only, nothing is uploaded. CPU is fine;
roughly real time to a few times slower than real time per clip.

**People only.** The model segments humans. Products, objects, animals: tell the owner
this skill can't track them (that needs SAM 2, not installed). It also can't erase the
person and fill the room behind them (that needs an inpainter).

## Needs
- Node.js 22+ (installed by the first run of `MP Studio.exe`) and FFmpeg with libvpx (the Gyan build has it).
- `$ROOT` = `${CLAUDE_PLUGIN_ROOT}` when installed as a plugin; if that shows unexpanded,
  the video-editor repo root. Run with `"$ROOT/.venv/Scripts/python.exe"`. If `npx` or
  `.venv` is missing, tell the owner to run `$ROOT\MP Studio.exe`.

## Whole-video person matte (fastest device)

For layouts that need the speaker separated for the WHOLE video (pop-out window on a non-blue wall):
`"$ROOT/.venv/Scripts/python.exe" "$ROOT/.claude/skills/subject-cutout/matte.py" <edit>/base_preview.mp4 -o <edit>/matte/matte.mp4`
→ a gray matte (white = person), same size and frame count; finish.py `"matte": {"type": "video", "file": "matte/matte.mp4"}`.
It times a few frames on every runtime this computer has (NVIDIA CUDA, DirectML = any DirectX 12 GPU incl. Intel,
CPU), uses the fastest and remembers it (`~/.cache/mp-studio/devices.json`). Run it in the background
(~0.5 s/frame on an Intel HD 620, ~1–2.5 s on a laptop CPU). The final base.mp4 has the same timing as
base_preview.mp4, so one matte serves both.

## Workflow inside a video-use edit

1. Make the edit as usual and render once (`render.py ... --preview` is enough), so
   `<edit>/clips_preview/` or `<edit>/clips_graded/` holds the segment files.
2. Pick the segment(s) that get the effect. Keep it short: a hook, a title, a key line.
   Cutting a whole video is slow and rarely what looks good.
3. Cut out the person:
   ```
   "$ROOT/.venv/Scripts/python.exe" "$ROOT/.claude/skills/subject-cutout/cutout.py" \
       --edl mp-studio/work/<project>/edit/edl.json --segment 0 [--clips clips_preview] \
       [--dim 0.4] [--blur 8] [--bg mp-studio/assets/<image-or-video>] [--plate]
   ```
   It reads the **rendered** segment, so the grade, size and timing match the base exactly,
   and writes `<edit>/cutouts/seg_NN/` with `subject.mov`, optional `background.mp4` /
   `plate.mov`, and `overlays.json` with `start_in_output` and `duration` already computed.
4. Build the middle layer (the text/graphic that goes behind the person) as a transparent
   overlay for the same window: HyperFrames `--format webm` (alpha), Remotion with alpha,
   or a PIL PNG sequence encoded with alpha (ProRes 4444 `.mov` or VP9 `.webm`).
   Keep important words where the person isn't: check the frames with `timeline_view.py`
   or a contact sheet; text covered by the speaker's head is unreadable.
5. Add the overlays to `edl.json` in this order (render.py stacks them in list order):
   ```
   background.mp4   (if --dim/--blur/--bg)     bottom
   your text/graphic overlay                   middle
   subject.mov                                 top
   ```
   All three share `start_in_output` and `duration` (the middle one may be shorter).
   Subtitles still render last, above everything.
6. Render the final, then check frames at the start, middle and end of the window for
   halos, a lagging edge or a visible double image.

Re-run step 3 whenever the cut, grade or segment order changes: the cutout is tied to the
exact rendered segment. For a segment rendered final (`clips_graded`) after testing with
`clips_preview`, re-run with the default `--clips`.

## Effects

| Owner asks for | Flags | Layers |
|---|---|---|
| Title / words behind me | none | base → text → `subject.mov` |
| Darker background, me normal | `--dim 0.4` | `background.mp4` → (text) → `subject.mov` |
| Blurred background (portrait-mode look) | `--blur 8` (+ `--dim 0.2`) | same |
| New background (image or video) | `--bg path` (+ `--dim`/`--blur`) | same |
| Graphics that must show *through* where I was | `--plate` | `plate.mov` sits on top of the graphic; read `media-use` remove-background notes first |

Start with `--dim 0.3–0.5`, `--blur 6–12`. Strong blur on a cheap matte shows the edge;
if the edge looks rough, lower the blur or add a little dim instead.

## Inside a HyperFrames composition

When the whole animated section is a HyperFrames slot, do the layering in HTML instead:
follow `media-use` → `audio/references/remove-background.md` (wrap the cutout `<video>`
in an untimed div, both videos `data-start="0"` and `data-media-start="0"`). Use
`remove-background ... -o subject.webm` there; it plays natively in the browser.

## Pitfalls
- **Different take behind the person:** two copies of the speaker. Only cut out over the
  same segment, or over an unrelated background.
- **Hair, fast hands, motion blur:** the matte is per frame and can flicker. Short
  windows, a little dim instead of strong blur, and don't zoom in on the edges.
- **Transparent WebM overlays** need the libvpx decoder; render.py already selects it for
  `.webm` overlays. ProRes `.mov` works with any FFmpeg.
- `--quality best` (default) keeps the cutout's colours closest to the base; `fast` is only
  for quick tests.
