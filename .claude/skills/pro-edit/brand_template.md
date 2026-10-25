# Brand profile

Filled once with the owner, then read at the start of every edit instead of asking again.
Change a line only when the owner asks. Lives at `mp-studio/assets/brand.md` (per computer).

- Instagram page: @<handle> — name — bio; profile photo mp-studio/assets/logo/avatar.png (shown in profile/follow scenes and the CTA, never a placeholder like your.page)
- Language: fa            # fa | en | mixed — passed to transcription and captions
- Platforms: Instagram Reels, YouTube Shorts
- Aspect: 9:16            # EDL "aspect"
- Target length: 45-60 s
- Pace: tight             # tight (reels: cut all pauses > 0.35 s) | natural (talks: keep pauses < 0.8 s)
- Punch-in zoom: yes, 1.12 on alternate segments, zoom_y 0.35
- Grade: neutral_punch    # grade.py preset or raw filter
- Captions: on, EMPHASIS style (owner choice 2026-10-22): small white lead-in line (72 px) + big accent-yellow keyword line (124 px, pops); cues without a keyword plain white 84 px; Vazirmatn Bold, black outline, MarginV 410 (on the chest, never the face); Persian spelling hand-corrected
- Caption style: built by pro-edit/templates/ass-motion (caption_mode "emphasis"); mark the keyword per cue with *stars*
- Colors: #FFFFFF text, #FFC400 accent, #111111 dark
- Fonts: Vazirmatn (Persian), Inter (English)
- Logo: mp-studio/assets/logo/logo.png   # optional
- Music: mp-studio/assets/music/<file>, -20 dB, ducked   # or "none"
- Motion style: clean kinetic text, 1 accent per ~8 s, no stock whooshes
- Motion theme: futuristic   # motion-kit: futuristic | apple-dark | apple-light; accent2 #4DD8FF
- Hook rule: open on the strongest line, never on a greeting
- CTA: <what the owner wants viewers to do>
- Templates made so far: (list mp-studio/assets/templates/<name>/ as they are created)
- Font roles: captions (legible, medium/semibold) · keyword + titles (heavy display) · one contrast word (serif/calligraphic); names from `pro-edit/fonts.py`. Owner's picks: Peyda, Kalameh, Abar, Farhang (commercial, fontiran.com) — free fallback Vazirmatn + Lalezar
