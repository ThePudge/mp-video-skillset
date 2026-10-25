# Fonts

Every font your videos use lives here, flat: `<Family>-<Style>.ttf`.

- **Included (free, SIL Open Font License):** Vazirmatn (captions) and Lalezar (heavy display
  for keywords and titles). Licences: `OFL-Vazirmatn.txt`, `OFL-Lalezar.txt`.
- **Your own fonts:** upload them in **MP Studio → Brand & Style → Fonts** (a `.ttf`/`.otf` or a
  whole `.zip`), or drop them anywhere in this folder and run
  `.venv/Scripts/python.exe .claude/skills/pro-edit/fonts.py organize`.
  It keeps one clean file per style, keeps Persian-digit (FaNum) versions, moves web fonts, PDFs
  and the original folders to `_source/`, and writes `catalog.json` with a suggested role per
  family: **captions** (legible), **display** (heavy keywords/titles), **contrast** (one
  calligraphic word).

Only the free fonts above are in git. Fonts you add stay on your computer (most Persian fonts
are commercial: their licence does not allow sharing the files), so copy this folder by hand to
another computer, or upload them there again.
