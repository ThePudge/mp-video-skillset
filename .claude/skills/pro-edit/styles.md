# Style library (approved and learned looks)

pro-edit picks from these when a project has no `mp-studio/input/<project>/ref/` folder. `motion-reference`
and `learn-update` add new recipes here (reusable ones only; a project's own ref notes stay in
`mp-studio/work/<project>/ref_style.md`). The source videos are in `mp-studio/learn/done/`.

## Analyzed
- 4012950191610839212.mp4 (6.5 MB, from mp-studio/learn/, 2026-10-22): 35 s 9:16 talking head, "16 video effects Claude can create" showcase; a new effect every 1–2 s, persistent list HUD, emphasis captions, Instagram comment/DM CTA
- (mp-studio/learn/) 4001236891292805512.mp4 (3.4 MB): 35 s "Claude Motion Tips" — clean white cards, one-word captions; lessons logged in mp-studio/learn/LOG.md

- 4009793604077813282.mp4 (10.1 MB, from mp-studio/learn/, 2026-10-22): 75 s 9:16, SAME script as project one by another creator; split explainer layout — UI-mock illustration panel on top, speaker below, a new visual every ~2.5 s, boxed seam captions

- 3935263589509299675.mp4 (6.9 MB, from mp-studio/learn/, 2026-10-22): 77 s 9:16 English "how to write viral scripts" reel; alternates full-frame talking head and a pop-out window under a tall dark graphics canvas every ~4.5 s; single-word captions; script/list cards

## Pacing
- Showcase reels: avg shot 1.8–2.5 s; something changes on screen every 1–2 s (effect, caption size jump, overlay)
- Talking-head sections keep the speaker centred; overlays live in the top third, captions on the chest

- Explainer reels (tool/app/process topics): a new top-panel visual for every sentence (~2.5 s); with a visual per item the FULL list holds attention (75 s with all 6 tools kept)

- Pop-out rhythm: switch between full-frame and pop-out window on cuts every ~4–5 s; b-roll inserts full-frame

## Recipes

### depth moves (behind + in front of the speaker) — depth.py, built and tested 2026-10-23
- When: one signature moment per ~10–15 s, on the spoken word: tools named → logo orbit; a prompt/answer → Claude window from behind the head; a result number → 3D growth chart; "my reels/work" → reel fan; a transformation → before/after studio wipe; a section title → pixel title
- Look: dark tiles with white logos orbit on a tilted ellipse, far side blurred behind the head; light app window swings out at −12°; orange 3D bars + big counter; white-bordered reel cards fan 100°; white studio wipes in; title assembles from dots
- Build: `motion-kit/depth.py` + `depth.json`, matte bluekey (blue wall) or ai
- Seen in: synthetic test (mp-studio/work/dtest), confidence: medium (not yet approved by the owner)

### editorial + camera (restrained) — motion-kit, built 2026-10-23
- When: news, data, serious or premium topics; when "futuristic" would feel like an AI demo
- Look: paper #F3F0EA or charcoal #1C1C1E, flat brand accent, no glow/glass/gradients; article cards with a muted-yellow hand-drawn marker behind key phrases
- Motion: scenes rise in; `"camera": true` glides between scenes in one world, slow push on holds, overview at the end
- Seen in: mp-studio/work/camtest, confidence: medium

### full motion reel (voice only) — motion-kit, built and tested 2026-10-22
- When: the owner sends only a voice note / voice-over, or wants a faceless reel
- Look: `futuristic` = deep-space background (aurora blobs, perspective grid floor, HUD corners, particles, scan line), glass cards with a thin cyan edge and glow, cyan icons + brand-yellow keywords; `apple-dark/light` = SF-style glass cards, segmented tabs, soft blobs
- Motion: scene enters with blur 18 px → 0 + scale 1.06 → 1 (380 ms, expo.out), exits blur + scale 0.96 (240 ms); words blur-rise on a 70 ms stagger; icons draw on (700 ms); grids stagger 83 ms; tab pill slides 420 ms expo.inOut on the spoken word
- Density: a new scene every 2–4 s; captions (emphasis) under the stage, y ≈ 1500–1650
- Build: `voice-motion` skill → `motion-kit/kit.py` scene list (components: title, icon_card, icon_grid, tabs, stat, list, chat, notify, compare, flow, bars, quote, cta)
- Seen in: kit demo + mp-studio/work/vtest (synthetic voice), confidence: medium (not yet approved by the owner)
### dark title + accent pill (approved on project one, 2026-10-22)
- When: naming the product/tool; a "free"/benefit tag right after
- Look: dark #111111 box with white Vazirmatn Bold ~80 px, yellow #FFC400 pill with dark text ~88 px, centred at y 300 / 465 (1080x1920), on the background above the head
- Motion: pop — scale 70% → 106% in 220 ms → 100% at 320 ms, fade in 120 ms, fade out 200 ms; pill enters ~0.5 s after the title
- Density: once, on the name
- Build: ass-motion `{"type": "dark", ...}` + `{"type": "pill", ...}`, enter "pop"
- Seen in: project one, confidence: high (owner approved)

### number counter
- When: a spoken number ("11 tools")
- Look: huge yellow Persian digits ~300 px at y 380, white label under it
- Motion: counts up over 0.5 s landing on the spoken number, lands at 125% → 100% in 180 ms; label fades in 150 ms later
- Build: ass-motion `{"type": "counter", "to": N, "label": "..."}`
- Seen in: project one, confidence: high (owner approved)

### follow + comment CTA
- When: the CTA lines
- Look: dark box "follow" at y 300, yellow pill with the comment keyword at y ~475
- Motion: dark box drops 120 px in 250 ms; pill pops on the spoken keyword; both hold to the end
- Build: ass-motion `{"type": "dark", "enter": "drop"}` + `{"type": "pill"}`
- Seen in: project one, confidence: high (owner approved)

### list HUD (progress overlay) — from mp-studio/learn/ showcase
- When: list videos ("16 effects", "11 tools"), whole list section
- Look: small title (2 lines, white bold) + two-column list in the top ~20%, items small white; the item being spoken turns accent yellow
- Motion: list fades in once; highlight jumps item to item on the spoken word (no animation needed)
- Build: ass-motion — one small `label` line per item at fixed positions (`"tags": "\\fs34"`), highlight = a second event with `"tags": "\\fs34\\c&H00C4FF&"` over the spoken window; or HyperFrames for a polished panel
- Seen in: 4012950191610839212, confidence: medium (not yet approved by owner)

### emphasis captions (lead-in + keyword) — DEFAULT caption style (owner, 2026-10-22)
- When: all social captions on talking heads
- Look: lead-in words small white (72 px) on the line above; the keyword big, bold, accent yellow (124 px) below ("10 trial reels.", "automatically.", "carousels"); cues without a keyword plain white 84 px; block at MarginV 410 (1080x1920), on the chest
- Motion: keyword pops in (88→100% in 120 ms); lead-in just appears
- Build: ass-motion, `caption_mode: "emphasis"` (default); mark the keyword in caption_fixes.json with stars: `"کاملاً *رایگانه*"`
- Picking keywords: one per cue at most, on ~1 cue in 2–3: numbers, product/tool names, payoff and benefit words, the CTA keyword; never fillers or verbs like "is/has"
- Seen in: 4012950191610839212, confidence: high (owner chose it as default)

### big number with lead-in
- When: a number is spoken ("46", "11")
- Look: small white lead-in ("to get all") above a huge yellow number, centred on the chest
- Motion: number pops; holds while the sentence lasts
- Build: ass-motion `counter` (or `big`) + a `label` above; same family as the approved counter
- Seen in: 4012950191610839212, confidence: medium

### word behind the speaker ("depth")
- When: one emphasis word per video
- Look: huge accent word whose first half sits behind the head/body and second word in front ("depth" behind, "scatter" in front)
- Build: plain blue wall → `finish.py` cut-out window + ass-motion `"layer": "behind"` (title ~y 690 size 190, giant number ~y 560 size 640); other backgrounds → `subject-cutout`
- Seen in: 4012950191610839212; approved on project one v2 (2026-10-22), confidence: high

### comment-box CTA
- When: "comment X and I'll send it"
- Look: fake Instagram comment field ("Add a comment…") appears, then a DM bubble ("Sent it to you")
- Motion: field slides up, keyword types in, DM bubble pops in
- Build: HyperFrames (UI mock + typing); ass-motion fallback = `dark` box "Add a comment…" then `pill` with the keyword
- Seen in: 4012950191610839212, confidence: medium

### numbered chapter card
- When: tips/list videos, between items
- Look: full white screen, "No.1" small, then the item title large in a thin serif/sans; next beat shows the visual
- Motion: hard cut in, ~1 s hold, hard cut out; captions continue as single centred words
- Build: ass-motion `label` on a white full-frame box, or a 1 s white still with text in the EDL
- Seen in: 4001236891292805512, confidence: low

Other effects named in the showcase, to build with HyperFrames/subject-cutout when asked: headline wall (torn-paper newspaper strips), green screen (person over another clip), phone mockup (screen inserted next to speaker), digital zoom (camera viewfinder HUD + zoom), UI world (person inside an app frame), frame break (object breaking out of a frame), doodle boil (hand-drawn wobbling outline around the person), sticky text (label stuck to a moving hand), before/after light wipe, pullback reveal (zoom out into the editor UI), orbit.

### spotlight (best-part section)
- When: the strongest moment / "the craziest part"
- Look: wall darkened (-0.38) and desaturated, blurred; soft yellow glow circle behind the speaker; the key word huge behind the head
- Motion: flash + impact on entry, zoom-out reveal 1.2→1.0 in 0.7 s, 2-frame glitch on the key word
- Build: `finish.py` cut-out window (brightness -0.38, saturation 0.35, blur 16) + ass-motion `glow` (radius 430, blur 90, alpha 70) + `big` behind
- Seen in: project one v2, confidence: high (owner approved)

### split explainer layout
- When: explaining a tool, app, workflow or list (e.g. "Instagram Agent Skill", "11 skills")
- Look: top ~40% = light canvas (off-white #F4F2EE, faint grid-paper lines, soft orange radial glow centre); bottom ~60% = speaker, cropped; seam between them carries the captions
- Motion: the top panel changes on every sentence; elements enter with a short rise (≈20 px) + fade + slight overshoot, 150–250 ms
- Build: HyperFrames (HTML/CSS composition 1080x768 for the panel, rendered to video) stacked over the speaker crop with ffmpeg `vstack`; speaker cropped to 1080x1152 around the face
- Seen in: 4009793604077813282, confidence: medium (not yet approved by owner)

### UI-mock illustration per sentence
- When: inside the split layout, one per sentence, matched to its meaning
- Look: clean flat UI cards with soft shadows, rounded 16–24 px, small orange tag chips ("جدید", "۲۰ فرمول تست‌شده"), real-looking app icons/logos
- Library seen (maps 1:1 to the project one script): Claude logo ↔ Instagram logo with a connecting line and a check; to-do card whose rows tick; "Instagram Agent Skill" app card + green «رایگان» badge; 4-column skill-icon grid with a live "N مهارت" counter; new-post card with hook text; comment thread typing replies; profile card with stats + optimise buttons; weekly content calendar; question list ("چی/چه زمانی/با چه افرادی منتشر کنی") ticking one by one; reels thumbnail grid with "TOP" badges; reel → scenario arrow; hook/content/CTA scenario cards fanning out; dark Claude chat with the link pasted; profile card whose Follow button turns to "Following" + comment field with the keyword
- Build: HyperFrames, one HTML card component per idea, reused across videos (save each to mp-studio/assets/templates/ when approved)
- Seen in: 4009793604077813282, confidence: medium

### staggered icon grid + live counter
- When: a spoken count of things ("یازده تا اسکیل")
- Look: 4-column grid of rounded coloured app icons with tiny labels; an orange tag chip above showing "N مهارت"
- Motion: icons pop one every ~83 ms (rise + fade + slight scale), label fades just after its icon; the tag counts up with each icon; whole grid ≈ 0.9 s, landing on the spoken number
- Build: HyperFrames (GSAP stagger 0.083 s); ass-motion fallback = counter + label only
- Seen in: 4009793604077813282 (measured with a 12 fps strip), confidence: high on timing

### boxed seam captions (variant)
- When: split layout only (captions sit on the seam between panel and speaker)
- Look: 1–2 words in a dark rounded box (#1E1E1E ~90%), white bold Vazirmatn; keyword in the same box in yellow/orange (not bigger)
- Motion: box swaps per cue, no animation
- Build: ass-motion `Dark` style with per-word `\c` on the keyword, positioned at the seam y
- Seen in: 4009793604077813282, confidence: medium — differs from the default emphasis captions; ask the owner which to use in split layouts

### pop-out window (head breaks the frame)
- When: while showing graphics (scripts, lists, cards) — the upper ~65% becomes a graphics canvas; alternate with full-frame every ~4–5 s for rhythm
- Look: dark canvas #0E0E0E with a faint dot grid; speaker in a rounded window (radius ~40 px) across the bottom ~30%; the speaker's head top breaks out ABOVE the window edge (background removed above the edge); one word caption centred just above the window
- Build: `finish.py` `"layout": {"type": "popout", "windows": [[t0, t1], ...]}` (scale 0.9, box_y 1240, anchor_y 790 = eyebrows on the window edge for vertical footage; needs the blue-wall matte); captions `motion.json` `"caption_mode": "word"`; canvas graphics as ass-motion moments or a HyperFrames `"panel"`
- Seen in: 3935263589509299675, confidence: medium (built and tested on project one, not yet approved)

### script / list cards on a dark canvas
- Look: glassy dark card with a thin light border, title mixing bold sans + italic serif ("The *Desire Hook* Method"), red accent bars (#C8102E); numbered list where upcoming items are blurred and the current item has a red left edge + lighter row
- Motion: highlight steps to the item being spoken; blurred items un-blur when reached
- Build: HyperFrames card in the pop-out canvas (Persian: Farhang/Abar for the contrasting title word, Peyda/Kalameh bold for the rest)
- Seen in: 3935263589509299675, confidence: medium

### CTA card, light
- Look: switch to a light background for the last 6 s: "Comment «X» to get the video" with the keyword in a red highlight box, a preview card of the freebie
- Seen in: 3935263589509299675, confidence: low

### window + panel (project one v4 — owner's preferred layout, 2026-10-22)
- When: explainer / list reels by default; ~88–90% of the video
- Look: dark dotted canvas; a HyperFrames illustration panel (1080x768, dark theme: white cards on #0E0E0E) at y≈140; speaker in the rounded bottom window with the head top breaking out; word captions (keyword in Lalezar yellow) between panel and window
- Full frame only 2–3 times: the hook (first ~3 s), the strongest line (spotlight + behind word + glitch), the CTA at the end
- Motion: window slides up from the bottom (0.4 s, ease-out) + whoosh each time the edit enters the layout; a new panel scene or beat at least every 3 s (`npx hyperframes check` flags stillness > 3 s)
- Build: panel = `templates/split-explainer/build_panel_example.py` with `THEME = "dark"`; `finish.py` `"layout": {"type": "popout", "windows": [...], "panel": "../panel/panel_dark.mp4", "panel_y": 140, "enter": "slide"}`; captions `"caption_mode": "emphasis"` + `"word_windows"` = the pop-out windows
- Seam: the head layer overlaps the window by 12 px and sits on even rows, or a line shows across the forehead
- Seen in: project one v4 (owner approved, final delivered 2026-10-22), confidence: high

### light pop-out + glass captions (new-video, owner approved 2026-10-23)
- When: explainer/tool reels on a plain light (non-blue) wall; the owner asked for "top of my head outside the box" and a bigger graphics area
- Look: light panel 1080x940 at y 40 (apple-light theme, paper cards, stage y 175–830 so nothing sits under Instagram's top bar); speaker in a rounded window (box_y 1260, 960x560, radius 44, eyebrows on the top edge, scale 0.9) with the head top breaking out; canvas #F5F5F7
- Captions: light frosted-glass pills inside the panel at y 875 (just above the head), dark text, keyword on a soft accent pill (motion-kit `"captions"` track)
- Matte: AI person matte (`finish.py` `"matte": {"type": "video"}`) — u2net_human_seg via `hyperframes remove-background`, or onnxruntime-directml on the Intel GPU (~4x faster than CPU on this laptop); punch-in zooms off (the matte doesn't follow them)
- Flows: horizontal, right to left, scaled to fit (vertical columns overflow a 940 px panel)
- Seen in: new-video final, confidence: high (owner approved)

### glass captions — light and futuristic (owner request, 2026-10-24)
- When: any caption track; MP Studio → برند و استایل → زیرنویس «شیشه‌ای» / «شیشه‌ای فضایی»
- Look (glass): rounded box sized to the line (corner ≈ 38 % of height), white frost ~78 % with a thin white edge, dark text, keyword deep orange #E8590C
- Look (glass-futuristic): dark navy frost ~67 %, neon cyan edge (#4DD8FF) with a soft outer glow, white text, keyword in the brand accent with a faint halo
- Real frost: the video is blurred only inside the boxes (glass_mask.ass → finish.py / storyframe.py), so the background shows through softly
- Motion: fade 90 ms in/out per cue; at glass_y 1440 on full frame, word_y 1060 inside pop-out windows
- Build: ass-motion `"caption_mode": "glass"` or `"glass-futuristic"` (`glass_size` 70 px)
- Seen in: tested on project one copies, confidence: medium until approved on a delivered video
