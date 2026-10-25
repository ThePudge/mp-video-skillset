---
name: motion-reference
description: Learn the editing, hook and motion style of reference videos (files in a project's `mp-studio/input/<project>/ref/` folder, or Instagram/YouTube/TikTok links) and write it as recipes in `mp-studio/work/<project>/ref_style.md` that pro-edit follows for that edit (reusable recipes also go into the style library). Use when a project has a `ref/` folder, or the owner says "edit it like this video", "make motions like these", "copy this style", "watch this reel", or pastes a video link to learn from.
---

# Motion reference (per project)

The owner may put finished videos they like into `mp-studio/input/<project>/ref/` (any name; `.mp4/.mov/.webm`).
Claude studies each one **once**, cheaply, writes what it learned to `mp-studio/work/<project>/ref_style.md`,
and the edit of that project follows it. No `ref/` folder → pro-edit chooses the look itself from
the style library `.claude/skills/pro-edit/styles.md` ("Choosing the look" in pro-edit).

Paths: same as pro-edit (`$ROOT`, `$PY`; helper `$MR="$ROOT/.claude/skills/motion-reference"`).
Sheets go to `mp-studio/work/<project>/_ref/<video stem>/` (gitignored), never into `mp-studio/input/`.
Raw footage and ref videos in `mp-studio/input/` are never modified, moved or transcribed as takes
(transcribe the project folder itself, not `ref/`).

**Links work too.** Pass a public post URL instead of a file: it is downloaded once (720p) into
the `--out` folder as `source.mp4` and reused on later calls with the same `--out`. Private or
login-only posts can't be fetched: ask the owner to save the video into `ref/`. Never pass
browser cookies or log in for them.

## Per reference video (≈ 4–7 images total)

1. **Overview** — text + one image:
   `"$PY" "$MR/ref_sheets.py" "mp-studio/input/<project>/ref/<file>" --out "mp-studio/work/<project>/_ref/<stem>"`
   Read the printed pacing (shots, cuts/min, avg/median/shortest shot, first cut, cut times), then
   the overview sheet once.
   Note every graphic you see: what it is, roughly when, where on screen. Same-shot punch-in cuts
   barely register as cuts; count zoom changes on the sheet instead.
2. **Strips** — only for 2–4 distinct moves (not every occurrence):
   `--strip <start> <span>` around the move's first appearance (span 0.6–1.5 s, 12 fps;
   `--fps 24` for very fast moves). Read the ms labels: entrance length, overshoot, hold,
   exit, easing, direction.
3. **Hook microscope** — the first 10 s decide retention, so study them densely, once per video:
   `... --out "mp-studio/work/<project>/_ref/<stem>" --hook --language <fa|en>` → one sheet of 20 frames
   (2 fps) plus, per 0.5 s, the words being spoken (local Whisper on a 10 s slice; nothing uploaded).
   Note: first frame (face? text? motion?), when the first word lands, the opening line, when
   on-screen text appears and what it says vs. what is spoken, the first cut/zoom, and the hook
   pattern (bold claim, question, number/list, pattern interrupt, result-first, story open).
4. **Optional words** — when timing against speech matters beyond the hook, the transcript is cheap:
   `"$PY" "$VU/transcribe.py" "mp-studio/input/<project>/ref/<file>" --edit-dir "mp-studio/work/<project>/_ref/<stem>"`.
5. **Write** `mp-studio/work/<project>/ref_style.md` (format below). If a recipe is new and reusable, also
   add it to `.claude/skills/pro-edit/styles.md` (confidence: medium until the owner approves an edit).

Don't copy anyone's logo, watermark, music or exact text; learn the *language* (timing, layout,
colour roles, typography weight, rhythm) and rebuild it with the owner's brand and fonts.

## Recipe format (ref_style.md and styles.md)

```
## Analyzed
- <file> (<size MB>): <one line: format, length, pacing, overall feel>

## Pacing
- X cuts/min, avg shot X s (median Y s), an event every Y s, layout switches …, b-roll …

## Hook (0–10 s)
- Pattern: <bold claim | question | number/list | pattern interrupt | result-first | story open>
- Frame 0: <what is on screen>; first word at X s; opening line: "<…>"
- On-screen text: <when, what, how it differs from the spoken line>
- First cut/zoom at X s; anything that moves in the first second
- Rebuild for the owner: <how pro-edit opens this edit the same way>

### <short name, e.g. "keyword pop">
- When: <trigger — first line / numbers / keyword / list item / CTA>
- Look: <box/no box, colours by role, font role and weight, size as % of width, position>
- Motion: <enter: type + ms + easing/overshoot; hold; exit: type + ms>
- Density: <how often>
- Build: <finish.py layout / ass-motion moment JSON / HyperFrames block + parameters>
- Seen in: <files>, confidence: low|medium|high
```

Numbers over adjectives; the Build line must let pro-edit rebuild the move without re-watching.

## After writing

Tell the owner in a few lines what you learned and which moves need HyperFrames (masks, 3D,
particles, shape morphs, per-letter animation). Then continue the pro-edit plan.
