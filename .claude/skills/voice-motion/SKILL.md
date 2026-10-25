---
name: voice-motion
description: Turn a voice note or voice-over (no camera footage) into a full motion-graphics reel — futuristic or Apple-style animated scenes with real SVG icons, segmented tabs, counters, charts, chat and notification UI, emphasis captions, music and UI sound effects — all local. Use when the owner sends or drops a voice/audio file (.ogg .opus .m4a .mp3 .wav, "ویس"), says "make a video from my voice", "full motion", "faceless reel", or wants a video with no face in it.
---

# Voice → full motion video

Reuses pro-edit for everything except the picture: same paths (`$ROOT`, `$PY`, `$VU`, `$PE`,
`$E` = `mp-studio/work/<project>/edit`), token rules, brand profile and captions. Picture = `motion-kit`
(`$MK="$PE/templates/motion-kit"`, components and themes in its README). Always local; never
HeyGen cloud/avatars unless the owner asks.

## Steps

1. **Prep + transcribe** (no reading yet). Voice notes are usually noisy (phone mic, room): clean first —
   `"$PY" "$PE/audio/voice_clean.py" <file> -o "$E/voice_clean.wav" --preset <brand voice_preset or strong> --report`
   and prep that file instead. Voice file in `mp-studio/input/<project>/`:
   `"$PY" "$MK/voice.py" prep "mp-studio/input/<project>/<file>" "$E"` → `$E/voice.mp4` (black carrier),
   `"$PY" "$VU/transcribe.py" "$E/voice.mp4" --edit-dir "$E" --language <brand>`, `pack_transcripts.py`.
2. **Read once, plan once** (pro-edit Stage 2). One message: the beat list with quotes, length,
   theme (brand.md "Motion theme"; else futuristic for tech/AI/money, apple-light for lifestyle/
   education, apple-dark for product/tool talk), and per beat the component + icon idea, e.g.
   `HOOK → title · 3 tools → icon_grid · steps → list · 87% → stat · CTA → cta`. Wait for ok
   (skip if the owner said "just make it").
3. **Cut the voice** like footage (pro-edit Stage 3 rules: fillers, pauses, retakes, hook first):
   `$E/edl.json` with source `"voice": "voice.mp4"`, then
   `render.py "$E/edl.json" -o "$E/cut.mp4" --preview --no-subtitles --no-loudnorm` (→ `base_preview.mp4`).
4. **Captions** (pro-edit Stage 4.2): `captions.py "$E" raw` → fixes with *stars* → `fix`;
   `$E/motion.json` `{"style": {…brand fonts…, "caption_mode": "emphasis", "caption_margin_v": 410}, "moments": []}`
   → `ass_motion.py "$E"` → `master.ass`. Captions sit under the scenes: give the spec `"stage_y": [230, 1250]` so cards end above them, and never put captions below y 1520 (Instagram hides the bottom 400 px).
5. **Scenes**: write `$E/scenes.json` on the cut timeline from `master.srt` cue times — scenes
   abut, each starts on the first word of its beat, list/tabs/chat `at` on the spoken words
   (seconds inside the scene). `"duration"` = voice length + 2–3 s so the CTA holds ≥ 2.5 s.
   Find icons with `kit.py icons <meaning>`; never guess names. Persian: `"dir": "rtl", "digits": "fa"`.
   Avatar/handle/bio from brand.md, never a placeholder.
6. **Build, check, look once, render**:
   `kit.py build "$E/scenes.json" -o "mp-studio/work/<project>/motion"`; in that folder
   `npx hyperframes check --json` (fix errors; never set `HYPERFRAMES_BROWSER_PATH` to the owner's
   Chrome/Edge — it opens visible windows and hangs while they browse. If check says the browser
   was skipped, run `npx hyperframes browser ensure` once: hidden headless Chrome), one `snapshot --at <mid of each scene> --no-end --describe false -o snaps` and read
   its contact sheet(s) once, then `npx hyperframes render --output motion.mp4`.
7. **Mux + finish**: `"$PY" "$MK/voice.py" mux "mp-studio/work/<project>/motion/motion.mp4" "$E"`; `$E/fx.json`
   `{"base": "motion_base.mp4", "front": "master.ass", "fonts_dir": "<abs $ROOT>/fonts",
   "voice": {"highpass": 80, "compress": true}, "music": {…, "db": -22, "duck": true},
   "sfx_dir": "<abs $ROOT>/assets/sfx", "sfx": <motion/sfx_suggestions.json>, "grain": 3, "vignette": true}`
   → `finish.py "$E" -o "mp-studio/output/<project>/<project>_final.mp4"`; `qc_sheet.py … --no-sheet`.
   SFX kit missing: `audio/sfx.py "$ROOT/mp-studio/assets/sfx"`; no owner music: `audio/music_bed.py`.

## Pro rules (what makes it look expensive)

- **A new scene or beat every 2–4 s**; one idea per scene, max ~7 words of on-screen text.
- **Map meaning to component**: number → `stat`/`bars`, count of things → `icon_grid`, steps →
  `list`, options/phases → `tabs`, before/after → `compare`, process → `flow`, social proof →
  `notify`, dialogue/prompt → `chat`, punchline → `quote`, end → `cta`, a news claim or source →
  `article` (marker on the key phrase), an app/product → `phone3d`, "all the tools" → `physics`,
  a character/sticker moment → `lottie`. Serious/news/data topics: `editorial` theme + `"camera": true`.
- **Sync to the voice**: reveals land on the spoken word (cue start − 0.1 s); never animate on
  silence. Tabs/list/chat `at` = the word that names the item.
- **One theme, one accent** per video; *keyword* in accent only 1 per scene.
- **Sound on the visible action** only (sfx_suggestions does this); music ducked under the voice.
- **Frame 0 is the thumbnail**: the first scene starts at 0 and is already on screen (kit does it).
- Rendering is ~7× real time here: a 60 s reel ≈ 7 min. Snapshot first, render once.
