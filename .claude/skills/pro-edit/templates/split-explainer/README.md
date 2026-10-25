# split-explainer

Top panel of the split explainer layout (approved on project one v3, 2026-10-22): a 1080x768
HyperFrames film, one scene per sentence, over the speaker crop (1080x1152), boxed seam captions.

`build_panel_example.py` is the project one v3 panel (16 scenes: logos connecting, task card,
app card + free badge, staggered 11-skill grid with live counter, post writer, comment, replies,
profile score, weekly calendar, what/when/who questions, viral card, reels grid + magnifier,
reel → scenario, scenario cards + tone/niche/audience chips, Claude chat with link, follow +
comment keyword). Copy it into `mp-studio/work/<project>/panel/`, run `npx hyperframes init` there first,
copy the fonts from `<repo>/mp-studio/fonts/` to the panel's own `assets/fonts/` (HyperFrames reads fonts from its own assets folder), then change SCENES and the times (from `$E/raw.srt`).

Helpers inside: `scene()` (boilerplate, fade in/out), `pop()` (rise + fade + overshoot),
`tick()` (check circle turns green). Card styles live in `COMMON_CSS`.
Render: `npx hyperframes check`, snapshot key times, `npx hyperframes render --output panel.mp4`
(no headless shell: set `HYPERFRAMES_BROWSER_PATH` to the installed Chrome).
Keep panel elements above y≈700: the seam captions sit on y 768.

Theme: `THEME = "light"` for the split layout (v3), `"dark"` to sit on the pop-out canvas (v4).
Every ≤3 s something must change; `npx hyperframes check` reports stillness longer than that.
If Chrome is already open, `chrome --version` can hang: render with Edge as HYPERFRAMES_BROWSER_PATH.
Owner page: set `HANDLE`, `BIO`, `AVATAR` at the top (from brand.md) and copy `mp-studio/assets/logo/avatar.png` to the panel's own `assets/avatar.png`.
