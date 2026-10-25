---
name: pro-edit
description: The default way to edit the owner's raw talking-to-camera footage into a finished reel or video, like a professional editor, with the fewest tokens. Runs ingest → transcript read → one plan → cut → polish (captions, grade, punch-ins, music, motion, cutouts) → measured QC → delivery, using video-use, HyperFrames/Remotion, subject-cutout and the content skills. Use for "edit mp-studio/input/<project>", "make a reel from these takes", "cut this video", "edit like a pro".
---

# Pro edit

Pipeline on top of `video-use` (its Hard Rules always apply; don't re-read its whole
SKILL.md, open the section a stage names).

**Paths.** `$ROOT` = `${CLAUDE_PLUGIN_ROOT}` when installed as the MP Claude Edit Skillset
plugin. If that text shows unexpanded, you are inside the video-editor repo: `$ROOT` = the
repo root. Footage, edits and renders always live in the current project folder.
Shell state doesn't persist, so start each Bash command with
`export PYTHONUTF8=1 HYPERFRAMES_NO_TELEMETRY=1; R="<$ROOT>"; PY="$R/.venv/Scripts/python.exe"; VU="$R/.claude/skills/video-use/helpers"; PE="$R/.claude/skills/pro-edit"; E=mp-studio/work/<project>/edit;`
and quote every path (`"$PY" "$VU/render.py" ...`); they may contain spaces.

## Token rules (follow at every stage)

1. **Text before pixels.** Decide from `takes_packed.md` and measured numbers. Never read
   transcript JSON. Never scan footage frame by frame.
2. **One image per review.** QC = one `qc_sheet.py` sheet (≤ 30 small thumbs) + its text
   report. `timeline_view.py` only on a cut the report or sheet flagged. `--no-sheet` when
   only audio/length changed.
3. **Ask once.** Brand answers live in `mp-studio/assets/brand.md`; edit decisions in `$E/project.md`.
   Read both first; never re-ask what they answer. All open questions go in ONE message.
4. **Render cheap until approved.** `--draft` for cuts, `--preview` for polish, final once.
5. **Reuse before building.** Motion: the project's references decide the look when
   `mp-studio/input/<project>/ref/` exists (`motion-reference` → `mp-studio/work/<project>/ref_style.md`); otherwise
   pick from the style library `$PE/styles.md` to fit the script (see "Choosing the look"); build them from `mp-studio/assets/templates/` first,
   then `$PE/templates/ass-motion`, then a `hyperframes-registry` block, then hand-built.
   Save every new piece the owner likes as a template (params in a `README.md` beside it)
   and list it in brand.md.
6. **Quiet commands.** Pipe long output through `tail`/`grep`; don't cat big files; don't
   echo files back after writing them.
7. **Sub-agents only for parallel motion slots** (one per slot, short self-contained brief,
   `model: sonnet`). Everything else stays in the main thread; no critic agent unless the
   owner asks for a "review".
8. **Load other skills only at their stage** (content skills for hook/caption text,
   `hyperframes*` for motion, `subject-cutout` for depth effects).

## Stage 0 — Setup check (seconds)

`$ROOT/.venv`, `ffmpeg`, `node` exist? If not: tell the owner to double-click
`$ROOT\MP Studio.exe` (give the full Windows path; it installs FFmpeg, Python, Node, the
Remotion and HyperFrames skills and the Persian font; Windows only), then stop. After a
plugin update `$ROOT` changes, so setup runs once more.
Create `mp-studio/input/ mp-studio/work/ mp-studio/output/ mp-studio/fonts/ mp-studio/assets/music/ mp-studio/assets/templates/` in the project if missing.
No `mp-studio/assets/brand.md`? Copy `$PE/brand_template.md` there and fill it in the Stage 2 message.
Videos in `mp-studio/input/<project>/ref/`? Run `motion-reference` on them first (once; it writes
`mp-studio/work/<project>/ref_style.md`, and the edit follows it). No `ref/` folder: choose the look yourself.
HyperFrames usable? `npx --no-install hyperframes --version` succeeds. If not, motion uses
`$PE/templates/ass-motion` and the owner is told once that `MP Studio.exe` (first run) adds HyperFrames.

## Toolbox (who does what)

| Job | Tool |
|---|---|
| Cuts, grade, captions, overlays, render | `video-use` helpers (`$VU`) |
| Titles, kinetic text, lower-thirds, animated captions | `hyperframes` + `hyperframes-registry` skills, or `remotion-best-practices` |
| Pro UI scenes: glass cards, SVG icons (Lucide), Apple tabs, counters, gauges, charts, chat, notifications — futuristic or Apple look | `$PE/templates/motion-kit` (`kit.py` scene list → HyperFrames; README there); use it for panels and graphics windows too |
| Voice only, no footage → full motion reel | `voice-motion` skill |
| Simple cards, counters, CTAs; motion without HyperFrames | `$PE/templates/ass-motion` |
| Copy the style of the project's reference videos (`mp-studio/input/<project>/ref/`) | `motion-reference` skill → `mp-studio/work/<project>/ref_style.md` |
| Library of approved and learned looks to choose from | `$PE/styles.md` |
| Text behind the speaker, dim/blur/replace background | `subject-cutout` skill |
| One-off trims, conversions, quick effects | `kinocut` MCP tools |
| Owner's hand gestures (point, open palm, counting, spread, raised hand) → place graphics at the hand, on the gesture | `$PE/gestures.py <edit> --edl --sheet` (MediaPipe hands, all takes in parallel) → `gestures.json` + one sheet |
| Hardware: which FFmpeg + encoder (NVENC → Quick Sync → x264), re-checked each run | `$PE/hw.py` (render.py and finish.py use it; drafts/previews/intermediates on the GPU, the final on x264) |
| Clean person matte on any wall (clones, full-body shots) | `subject-cutout/rvm_matte.py` (Robust Video Matting, GPU via DirectML/CUDA) |
| Lip sync check against the RAW takes (run on the cut and on the final before delivering) | `$PE/avsync.py <edit> <video>` → picture vs sound offset per take, verdict (≤ 1 frame = in sync) |
| Recolour only the wall (person keeps their colour), camera push toward a speaker, slide the speaker down for a panel, an outro layer at its own time | finish.py cut-out `"hue"` + `"wipe"`, zoom `"center"`, `"shift"`, `"front_video": [main, {"file", "t"}]` (docstring) |
| A full ref remake: every UI card, caption and title as one HyperFrames layer timed to the cut's words | one Python script writes the HyperFrames page (every card and caption timed from the cut's words, remapped to the rendered base's real segment lengths) → alpha WebM layers → finish.py `"front_video"` / `"behind_video"` (+ `"grades"`); recipe in styles.md "editorial ref remake" |
| Hooks, scripts, captions/hashtags, covers, repurposing | content skills |

Use only local, free commands: no HeyGen cloud, publishing, Apify/Composio or auto-posting
unless the owner asks. Raw footage in `mp-studio/input/` is never modified.

## Choosing the look (no `ref/` folder)

Read the script (takes_packed.md) and pick from `$PE/styles.md`, then say which in the plan:
- explains a tool, app or workflow, many concrete items → **window + panel** (owner's preferred:
  HyperFrames illustration panel above the pop-out window ~90% of the time, full frame only for
  hook / best line / CTA) or the plain **split explainer**
- tips / steps / list, or a script worth showing on screen → **pop-out windows** alternating with
  full-frame every 3–4 s, list or script cards on the canvas
- opinion, story, hot take, one big idea → **full-frame** with emphasis captions, text behind the
  speaker, spotlight on the strongest line, punch-ins
- mixes are fine (v4 of project one: full-frame cut-outs + pop-out list sections).
Always: hook on screen at 0 s, something happens at least every 3 s in reels (owner rule), a stronger beat on the best line,
a clear CTA card at the end. Brand mp-studio/fonts/colours from brand.md.

## Stage 1 — Ingest (no reading yet)

```
$PY $VU/transcribe_batch.py mp-studio/input/<project> --edit-dir $E --language <brand language>
$PY $VU/pack_transcripts.py --edit-dir $E
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of csv=p=0 <each file>
```
Transcripts are cached; never re-run on unchanged files.

## Stage 2 — Read once, plan once

**Clip order & roles first.** `handoff.py show <project>` → `clips`: the owner's order (dragged in
Studio) with a role per file — `main` (the talk, edit in this order), `retake` (another try of the
`main` clip right above it: keep the best take of each line from the pair, never both), `broll`
(no talk: muted full-frame cutaways over jump cuts via finish.py `"broll": [{"file","t","dur","from"}]`,
1–3 s each, never over the hook or the CTA). `mp-studio/app/clips.py plan()` is lite mode's simpler split (a retake just replaces the clip above).

Read `takes_packed.md` once. In your head: retakes (same line said twice → keep the last
clean one), fillers, false starts, the strongest line (hook), the payoff, the CTA.
Then send ONE message to the owner:

- the structure as a numbered beat list with quotes and source times
  (e.g. HOOK → PROBLEM → 2–3 VALUE beats → PAYOFF → CTA), estimated length
- hook options only if the opening is weak (use `viral-hook-writer` sparingly)
- polish plan: captions, grade, punch-ins, music, 1–3 motion moments, any cutout effect
- only the questions brand.md/project.md don't answer, each with a default

Wait for "ok" or changes. That is the only planning round trip.

**Storyboard first, render later (owner rule — how a pro editor works).** Deliver that plan as a
Studio storyboard BEFORE any render: cut `edl.json` (cutplan.py, retakes dropped), corrected
captions (`captions.py raw/fix`), then `cards.json` (one card per spoken line: `t0`, `t1`, `words`,
`layout` full|window|split, `move` (what animates, shown as a tag) and `sketch` {kind, title,
subtitle} — the planned graphic, drawn on the card until the real panel exists) and `plan.md` (structure, look, music,
CTA), and run `$PY $PE/storyboard.py "$E" --cards "$E/cards.json" --plan "$E/plan.md"` **without
`--video`**: each card is a mock-up of the finished shot (`storyframe.py`: layout + zoom, the
sketch or a frame of the rendered panel, `master.ass` captions/motion if built, motion tag) with
the beat's audio — seconds, no render. Build `master.ass` (captions.py + ass_motion.py) first so the
captions on the cards are the real ones. `handoff.py set
<project> review`, wait for approved/changes. Only after approval: drafts, panels, depth effects,
finish, QC. A second storyboard with `--video` (rendered stills) is optional, for big visual changes.

## Stage 3 — Cut

Write `$E/edl.json` yourself for one or a few takes; use the video-use editor sub-agent
brief only for many takes (> 6 files). Rules beyond video-use's:
- **Pace** from brand.md: tight = remove pauses > 0.35 s, breaths, fillers ("اِ", "یعنی",
  "um", "so"), stutters; natural = keep pauses < 0.8 s.
- **Hook first**: the first range is the strongest line, no greeting, no "in this video".
- **Punch-ins** hide jump cuts: alternate `"zoom": 1.0` / `"zoom": 1.12` with
  `"zoom_y": 0.35` between consecutive ranges of the same shot; `1.25` for one emphasis line.
- `"aspect": "9:16"` (or brand aspect) at the top level when the source shape differs.
- **Source keys = file stems.** Each key in `"sources"` must be the video's file name without
  extension (the name of its transcript in `$E/transcripts/`). Any other key renders fine but
  silently drops that source's captions.
- **Word tails:** Whisper word times overlap by up to ~0.1 s. Start a range on the first word's
  start (not before it) when the previous word belongs to a cut take, or its tail leaks in.

```
$PY $VU/render.py $E/edl.json -o $E/draft.mp4 --draft --no-loudnorm
$PY $PE/qc_sheet.py $E/draft.mp4 --edl $E/edl.json --draft
```
**Start the cut from the audio, not Whisper's word times:**
`$PY $PE/cutplan.py "$E" --source <key>=<video> --pace <tight|natural> --language <fa|en> --write` →
pause-trimmed ranges cut in measured silence + a list of "suspicious words" (long, or containing a
silence = merged false starts / retakes / dropped phrases), each piece re-transcribed. Drop false-start
ranges; for a dropped phrase split the caption cue: `caption_fixes.json` `{"96": ["…", "…", "…"]}`.
Before the draft, `$PY $PE/storyboard.py "$E" --cuts-only` prints the cut table (words either side of
every join) — it goes into the Studio review. After it, **join check**:
`$PY $PE/joins.py "$E" --video "$E/draft.mp4" --language <fa|en>` → "N joins checked, 0 flags"
(a flag = the cut went through a word: move that EDL edge into silence, re-draft).
Fix flagged cuts (pause left, cut mid-word, black frame), re-draft. Max 2 passes.

## Stage 4 — Polish (in this order; skip what the plan didn't include)

1. **Grade**: brand preset in `"grade"`. Check skin on the next QC sheet only.
2. **Captions**: `--build-subtitles`; EDL `"subtitle_style"` = brand caption style,
   `"fonts_dir": "<absolute $ROOT>/fonts"` (Vazirmatn for Persian; setup downloads it).
   **Persian (or any shaky transcript): correct the text before burning it in.**
   `$PY "$PE/templates/ass-motion/captions.py" "$E" raw` prints the cues; write
   `$E/caption_fixes.json` (`{"index": "fixed text"}`, `""` drops a stray word from a cut take),
   then `captions.py "$E" fix` → `master.srt`. List the words you guessed for the owner to check.
   **Emphasis captions are the owner's default** (brand.md): in the same fixes, star the keyword
   of about 1 cue in 2–3 (`"کاملاً *رایگانه*"`: numbers, names, payoff/benefit words, the CTA
   keyword); `ass_motion.py` turns it into a small white lead-in + big yellow popping keyword.
   So captions always go through `$PE/templates/ass-motion` (EDL `"subtitles": "master.ass"`).
   Keep captions off the face (MarginV ~410 at 1080x1920 for a centred speaker).
   Persian caption rules (Persian reel guides agree): a simple medium/semibold face, never thin or
   decorative for body captions; drop spoken fillers («یعنی»، «خب»، «در واقع») from caption text
   when they add nothing; keep half-spaces (ZWNJ) in «می‌کنه»-type words; check it reads muted.
   **Fonts:** `$PY "$PE/fonts.py"` lists the family names in `$ROOT/mp-studio/fonts` (the owner drops bought fonts there); set roles in
   `motion.json` `"style": {"font": …, "keyword_font": …, "display_font": …}` from brand.md
   (owner's picks Peyda / Kalameh / Abar / Farhang once their files are in `mp-studio/fonts/`; else Vazirmatn +
   Lalezar). Never fetch commercial fonts from "free download" sites.
3. **Music**: EDL `"music": {"file": "../../../assets/music/x.mp3", "volume_db": -20, "duck": true}`.
   (Relative EDL paths resolve from `$E`.) Music sets the pacing, so time motion to it:
   `$PY "$PE/beats.py" <music> --offset <music start on output>` → downbeats/beats. Biggest
   move (hero reveal, scale-up) on a downbeat; pills, counters, punch-ins on beats between.
4. **Motion** (reels: something happens every 3–4 s — a card, cut-out, layout switch, punch, counter;
   talks: ~1 per 8 s; or the density in `ref_style.md`): pick the
   moment by word timestamp from the transcript; reveal lands on the spoken payoff word.
   Use the recipes in `ref_style.md` / `$PE/styles.md` (look, timing, easing, position).
   Spawn all slots in parallel.
   - HyperFrames for kinetic text/titles/lower-thirds (`--format webm` for alpha),
     Remotion if a React template exists. HyperFrames is HTML, so open-source creative-coding
     libraries drop in for textures and generative accents (p5.js + p5.brush brushstrokes,
     PixiJS filters, Anime.js, particle orbs): start from an existing project, recolour to brand.
   - **List videos** ("5 tips", "11 tools"): a small list overlay at the top, current item
     highlighted in the accent colour as it is spoken, reads as structure and keeps people watching.
   - **Explainer videos** (a tool, app or workflow): offer the *split explainer layout* from
     `$PE/styles.md` — UI-mock panel on top (HyperFrames), speaker below, a new visual per
     sentence. With a visual per item, keep the full list instead of trimming it.
     Build: a HyperFrames project at 1080x768 with one scene per sentence timed from `raw.srt`
     (generate the scene files from a Python script so boilerplate stays identical; example:
     project one v3 `mp-studio/work/<project>/panel/build_panel.py`), `npx hyperframes check`, snapshot a
     sheet of key times, render `panel.mp4` (if the headless browser is missing:
     `HYPERFRAMES_BROWSER_PATH` = installed Chrome). Then `fx.json` `"layout": {"type": "split",
     "panel": "../panel/panel.mp4", "panel_h": 768, "crop_y": 400}` and captions with
     `motion.json` `"style": {"caption_mode": "boxed", "caption_y": 768}` (owner choice for this
     layout). SFX: a soft pop (-24 dB) on every panel scene change, clicks on ticks.
   - **Pop-out window** (reference: the speaker in a rounded window at the bottom, head top
     breaking out above it, tall dark graphics canvas above): `fx.json` `"layout": {"type":
     "popout", "windows": [[t0, t1], …]}` on the graphics-heavy sentences, full-frame in between
     (switch on cuts every ~4–5 s — that alternation is the rhythm); captions `"caption_mode":
     "word"`; canvas graphics as ass-motion moments or a HyperFrames `"panel"`. Needs a matte:
     blue wall → bluekey; any other wall → `subject-cutout/matte.py` (fastest CPU/GPU, run in the background) and
     `"matte": {"type": "video", "file": "matte/matte.mp4"}` (punch-in zooms off: the matte doesn't follow them).
   - **No HyperFrames, or simple cards/counters/CTAs:** `$PE/templates/ass-motion` — write
     `$E/motion.json` (dark box, accent pill, big text, counter; pop/drop/fade entrances; times
     on the output timeline from `master.srt`), run `ass_motion.py "$E"`, then set EDL
     `"subtitles": "master.ass"`, `"subtitle_style": "Shadow=0"` and render WITHOUT
     `--build-subtitles` (captions are inside the .ass).
5. **Depth effects** (text behind the speaker, dim/blur/replace background):
   `subject-cutout` skill, on short windows only. **Plain blue/green wall:** no AI needed —
   `finish.py` keys it (`"matte": {"type": "bluekey"}`) and draws `"layer": "behind"` motion
   moments under the speaker. Put behind-text where the head overlaps it (title ~y 690, giant
   number ~y 560 at 1080x1920) or it just reads as text above the head. Best: `"y": "head"` on a behind
   moment — ass_motion measures the head top from the blue-wall matte at that moment.
   **Signature depth moves** (graphics behind AND in front of you, 1 per ~10–15 s, on the spoken
   word): `$PE/templates/motion-kit/depth.py` — `logo_orbit` (tools named), `claude_window` (a
   prompt/answer), `growth_chart` (a result number), `reel_fan` (your content/portfolio),
   `before_after` (transformation), `pixel_title` (section title). Write `$E/depth.json`, run it on
   `base_preview.mp4`, then finish.py with `"base": "base_depth.mp4"`.
5b. **Voice** (every edit, unless the brand's `voice_preset` is `off` — skip the whole step then): clean the cut's
   sound before depth effects and finish — `$PY "$PE/audio/voice_clean.py" "$E/base.mp4" -o "$E/base_voice.mp4" --preset <voice_preset>
   --lufs -16 --report`, plus `--denoise --deess --presence --warmth --compress --gate <v>` from `voice.settings` and
   `--dehum <voice.dehum>` when the brand has them (the owner's Studio → صدا sliders) (picture copied; denoise learned from the quietest moment, de-hum only if mains hum is
   heard between words, de-click, de-ess, warmth/presence EQ, compressor), then use `base_voice.mp4` as the
   base for depth.py / finish.py (set finish `"voice": {"highpass": 0, "compress": false}` so it isn't done twice).
   Report the speech-above-noise gain in one line. Noisy room → `strong`; the owner can tune it in Studio → صدا.
6. **Finish** (when the plan has zooms, cut-outs, VFX, music or SFX): render the cut with
   `--preview --no-subtitles --no-loudnorm` (→ `$E/base_preview.mp4`), write `$E/fx.json`, then
   `$PY "$PE/finish.py" "$E" -o "$E/preview.mp4" --preview` (spec in its docstring):
   animated zooms (slow push-ins on long takes, ~150 ms punches on keywords, a zoom-out reveal into
   a new section), cut-out windows, white flash on section changes, 2-frame glitch on one word,
   vignette + light grain, captions/cards, voice clean-up, ducked music, timed SFX, -14 LUFS.
   SFX kit: `$PY "$PE/audio/sfx.py" mp-studio/assets/sfx` (whoosh, whoosh_short, riser, impact, pop, click,
   ding, glitch, swipe_up), -14..-22 dB, on every cut-out/flash/card/keyword moment, never on
   every cut. No owner track: `$PY "$PE/audio/music_bed.py" mp-studio/assets/music/bed.wav --length <s>
   --bpm <n> --stop <CTA start>` (basic; say so). Final: same with `"base": "base.mp4"`, no --preview.

```
$PY $VU/render.py $E/edl.json -o $E/preview.mp4 --preview --build-subtitles
$PY $PE/qc_sheet.py $E/preview.mp4 --edl $E/edl.json
```
**Quarter-second check** before the owner sees anything:
`$PY $PE/safezone.py "$E/preview.mp4" --ass "$E/master.ass" --fonts-dir "<abs $ROOT>/fonts" [--base "$E/base_preview.mp4"] --sheet`
(captions/graphics in Instagram's hidden zones — top 210 px, right edge below halfway, bottom 400 px —,
caption touching a graphic, cut-off edges, ≥ 2 s with nothing moving). Fix every flag, re-check, until
"N frames checked, 0 flags". Then build the Studio storyboard (`storyboard.py`) for review.
Look at the sheet once: captions readable and inside the safe zone, overlays on the right
frames, punch-ins not cutting off the head, grade consistent. Max 2 fix passes; then list
what's left to the owner instead of looping.

## Stage 5 — Approve, deliver, remember

Tell the owner: length, what changed, the measured numbers (LUFS, issues: none), and the
preview path. You can't hear audio; say so once. On approval:

```
$PY $VU/render.py $E/edl.json -o mp-studio/output/<project>/<project>_final.mp4 --build-subtitles
$PY $PE/qc_sheet.py mp-studio/output/<project>/<project>_final.mp4 --edl $E/edl.json --no-sheet
```
Copy `$E/master.clean.srt` (no *emphasis* marks) next to it as `<project>_final.srt`. If asked: `caption-and-hashtags` for post text,
`cover-thumbnail-brief` for the cover; `cross-platform-reformatter` for other platforms
(re-render with a different `"aspect"`, same EDL).
Append 3–6 lines to `$E/project.md`: decisions, owner preferences learned, open issues.
Anything that is a lasting preference goes into `mp-studio/assets/brand.md`.

## Reel rules (Studio settings decide the defaults)

- **Show, don't tell:** one big graphic per spoken line, changing on the exact word, timed from the
  CUT's transcript (never the raw take). No text slides, no bullet lists, no labels above things.
- **Motion feel** (brand.json `motion_feel`): `punchy` = objects slam in from depth and land with no
  bounce, leave by dropping into depth, no idle drift or slow zoom while a shot holds; `playful` = overshoot.
- **Real things, never stand-ins:** use the project's `mp-studio/input/<project>/assets/` (real app icons,
  screenshots, the owner's posted work) before any drawn version; never the same example twice.
- **The hook is the animation:** the hook text builds on the first words, inside the safe area —
  not a title card on top.
- **Music** (brand.json `music_end`): `level` = ~12 dB under the voice and level to the last frame
  (loop the bars, no early fade); `fade` = out before the CTA.
- **Delivery:** H.264 1080x1920, limited range (render.py tags it), -14 LUFS; report qc_sheet's
  `delivery:` line (codec · size · color_range · length · LUFS · peak · MB).

## Pro defaults (taste, override when the material says so)

- Reels: 30–60 s; tutorials/talks: no hard limit, natural pace.
- Cut on the end of a thought, not mid-breath; keep reactions and laughs.
- B-roll/screen inserts: if the owner gives them, cover jump cuts with them before zooming.
- Captions on for social (most watch muted), 2–3 words, never covering the face.
- One look per video; no transitions between same-shot cuts (hard cut + punch-in reads pro;
  crossfades read amateur).
- Music under speech, never competing; out before the CTA lands.
