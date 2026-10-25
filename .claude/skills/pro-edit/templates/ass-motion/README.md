# ass-motion

Captions + motion cards as one animated libass file. The fallback when HyperFrames isn't
installed, and the quickest way to do simple cards. Approved by the owner on "project one"
(2026-10-22): dark box title, yellow pill, ۱→۱۱ counter, follow/comment CTA cards.

```
$PY "$PE/templates/ass-motion/captions.py" "$E" raw     # prints cues; write caption_fixes.json
$PY "$PE/templates/ass-motion/captions.py" "$E" fix     # -> master.srt
$PY "$PE/templates/ass-motion/ass_motion.py" "$E"       # master.srt + motion.json -> master.ass
```
EDL: `"subtitles": "master.ass"`, `"subtitle_style": "Shadow=0"`, `"fonts_dir": "<abs $ROOT>/fonts"`;
render without `--build-subtitles`. Spec format and moment types: see the docstring of `ass_motion.py`.

Layout that worked at 1080x1920 (speaker centred, head ~y 600–1250): cards at y 300–600 on the
background above the head; captions MarginV 410, emphasis style (small white lead-in + big yellow keyword marked with *stars*), on the chest, clear of the face and the platform UI.
