# Learn log

What Claude learned from `learn/inbox/` and which files it changed. Newest last.

## 2026-10-22 — first edit ("project one")
- learned: Whisper's Persian spelling needs hand correction before burning captions; source keys must equal file stems; captions belong on the shirt (MarginV ~470), not the face.
- changed: `.claude/skills/pro-edit/SKILL.md` — caption correction step, source-key rule, word-tail rule, ass-motion fallback, reference step
- changed: `.claude/skills/pro-edit/templates/ass-motion/` — reusable captions + motion cards (approved look)
- changed: `reference/style.md` — three approved recipes (dark title + pill, counter, follow/comment CTA)

## 2026-10-22 — 4001236891292805512.mp4 ("Claude Motion Tips", 35 s reel)
- learned: build effects on open-source libraries (p5.js + p5.brush, PixiJS filters, Anime.js, particle orbs); let music set pacing and land big moves on downbeats; keep a brand file with references
- changed: `.claude/skills/pro-edit/beats.py` — new beat/downbeat finder (librosa via ffmpeg decode)
- changed: `.claude/skills/pro-edit/SKILL.md` — music → beat-synced motion rule; open-source libraries in HyperFrames
- changed: `reference/style.md` — "numbered chapter card" recipe
- skipped: the "400 Claude videos" website (name not legible); brand-file tip already covered by assets/brand.md + reference/

## 2026-10-22 — 4012950191610839212.mp4 ("16 video effects Claude can create", 35 s reel)
- learned: showcase style — list HUD with highlighted item, emphasis captions (small lead-in + big yellow keyword), big number with lead-in, word behind the speaker, comment-box CTA, plus 11 named effects
- changed: `reference/style.md` — 5 recipes + effect catalogue; video moved to `reference/` (it is a style reference)
- changed: `.claude/skills/pro-edit/SKILL.md` — list videos get a progress overlay
- skipped: the creator's paid "system" pitch at the end
- question for owner: emphasis captions differ from the approved caption style — use them?

## 2026-10-22 — owner decision: emphasis captions as default
- learned: owner prefers the showcase caption style (small white lead-in + big yellow keyword) over plain 2–3-word white captions
- changed: `.claude/skills/pro-edit/templates/ass-motion/` — `caption_mode: "emphasis"` (default): *starred* keyword → big accent line with pop, lead-in 72 px, keyword 124 px, MarginV 410; `captions.py` also writes `master.clean.srt` for platform upload
- changed: `.claude/skills/pro-edit/SKILL.md` — star ~1 cue in 2–3; captions always via ass-motion; deliver the clean SRT
- changed: `.claude/skills/pro-edit/brand_template.md`, `reference/style.md` — emphasis captions are the default / approved recipe
- tested: project one frames — Persian shapes correctly, block stays off the face even on the 1.25 punch-in

## 2026-10-22 — owner request: re-edit project one with motion, cut-outs, zooms, music, SFX, VFX
- learned: plain blue wall keys cleanly with blueness B-(R+G)/2 (no AI); behind-text must overlap the head to read as depth; zoompan needs a 2x upscale to stay smooth
- changed: `.claude/skills/pro-edit/finish.py` — new finishing pass (cut-outs + behind layer, animated zooms, flash/glitch/vignette/grain, captions, voice clean-up, ducked music, SFX, loudnorm)
- changed: `.claude/skills/pro-edit/audio/` — `sfx.py` (synthesized SFX kit) and `music_bed.py` (placeholder bed)
- changed: `ass_motion.py` — `layer: behind`, `size`, `x`, `glow` type; `SKILL.md` stages 4.5–4.6; `requirements.txt` — rembg, mediapipe, pedalboard, noisereduce
- installed on this PC: HyperFrames CLI 0.8.185 (uses system Chrome), GPU libs, Whisper medium

## 2026-10-22 — 4009793604077813282.mp4 (75 s reel, same script as project one, another creator)
- learned: explainer edit of this exact script — split layout (UI-mock panel on top, speaker below), one illustration per sentence (~2.5 s), staggered icon grid (~83 ms per icon) with a live counter tag, boxed seam captions; with visuals per item the full 75 s list holds
- changed: `reference/style.md` — 4 recipes (split explainer layout, UI-mock illustration library mapped to the script, staggered icon grid + counter, boxed seam captions) + pacing note
- changed: `.claude/skills/pro-edit/SKILL.md` — offer the split explainer layout for tool/app/workflow videos
- moved: video to `reference/` (style reference)
- question for owner: in split layouts, boxed seam captions or the default emphasis captions?

## 2026-10-22 — owner request: project one v3 in the split explainer layout
- learned: full list (88 s) works with one illustration per sentence; boxed seam captions need ≥72 px; panel elements must stay above y≈700 or they collide with the seam captions; v1/v2 caption «سه روز» was a mishearing of «هر روز» (the other creator's reading of the same script confirmed it)
- changed: `.claude/skills/pro-edit/finish.py` — `"layout": {"type": "split"}` (panel video on top, speaker crop below)
- changed: `ass_motion.py` — `caption_mode: "boxed"` (dark box on the seam, *keyword* in accent)
- changed: `.claude/skills/pro-edit/templates/split-explainer/` — panel builder example (16 scenes) + README; `SKILL.md` build steps
- installed on this PC: none new (render uses system Chrome via HYPERFRAMES_BROWSER_PATH; `browser ensure` download failed)

## 2026-10-22 — 3935263589509299675.mp4 (77 s English "viral scripts" reel) + owner fonts + Persian reel research
- learned: pop-out window layout — speaker in a rounded bottom window, head top breaking out above its edge (background removed there), tall dark dotted canvas above for script/list cards, single-word captions; alternating it with full-frame every ~4–5 s gives the rhythm
- changed: `.claude/skills/pro-edit/finish.py` — `"layout": {"type": "popout", "windows": [...]}` (vertical footage: scale 0.9, anchor_y 790; finite per-window masks — a looped mask split across windows ran out of memory)
- changed: `ass_motion.py` — `caption_mode: "word"` (word_y 1060, clear of the head), font roles `keyword_font` / `display_font` (+ `Word` style)
- changed: `.claude/skills/pro-edit/fonts.py` — lists family names in assets/fonts; `SKILL.md` font roles + Persian caption rules; `brand_template.md`, `assets/brand.md` font roles
- fonts: Peyda, Kalameh, Abar, Farhang are commercial (fontiran.com, desktop licence covers videos) — owner buys and drops files in assets/fonts; added Lalezar (OFL, Google Fonts) now + in `tools/bootstrap.ps1`
- research: Persian reel caption guides (capsync, editpars, mrribvar): simple medium/semibold face, short chunks, cut fillers, keep above platform UI, highlight keywords only, sync with cuts, test muted; no source named one "best" font — Vazirmatn/IRANSans widely used, Lalezar for display
- changed: `reference/style.md` — pop-out window, dark-canvas script/list cards, light CTA card recipes; video moved to `reference/`

## 2026-10-22 — owner requests: fonts folder, per-project refs, v4 layout, an event every 3 s
- learned: owner's preferred layout = v3-style illustration panel above the pop-out window ~90% of the video, full frame only for hook / best line / CTA, window slides in; something must happen at least every 3 s
- changed: `fonts/` (one folder for free + bought fonts, files gitignored, README shared); tools/bootstrap/docs point there
- changed: references are per project (`input/<project>/ref/` → `work/<project>/ref_style.md`); global `reference/` removed; learned recipes moved to `.claude/skills/pro-edit/styles.md` (style library); `motion-reference` rewritten; pro-edit "Choosing the look"
- changed: `finish.py` popout `panel_y`, `"enter": "slide"`; `ass_motion.py` `word_windows` (mixed caption modes); split-explainer panel template: dark theme + 18 scenes (s14 split into 3, s10 opening beat)
- tooling: Chrome `--version` hangs while Chrome is open → render HyperFrames with Edge

## 2026-10-22 — owner feedback on v4: forehead line, real page details; v4 final delivered
- learned: the pop-out seam showed as a line across the forehead (soft matte edge over the dark canvas + odd-row yuv420 offset); never use placeholder pages — the owner's page is @mohammadpour.bi
- changed: `.claude/skills/pro-edit/finish.py` — head layer overlaps the window by 12 px, window/head on even rows
- changed: `brand_template.md` + `assets/brand.md` — Instagram page line (handle, name, bio, avatar); split-explainer template — HANDLE/BIO/AVATAR constants; `styles.md` — window + panel approved
- delivered: output/project one/project one_final_v4.mp4 (88.7 s, -14.0 LUFS, QC clean)

## 2026-10-22 — learned data pushed
- changed: `learn/notes/` — per-video overview sheets, frame strips, transcripts and notes for the 4 studied reels (videos stay local in `learn/done/`)
- changed: `learn-update` SKILL — saves this evidence for every future video
