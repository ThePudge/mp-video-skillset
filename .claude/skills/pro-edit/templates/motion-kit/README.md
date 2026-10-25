# motion-kit

Pro motion graphics from a short scene list: futuristic or Apple-style glass UI, 1,600+ real SVG
icons that draw on, segmented tabs, counters, gauges, chat, notifications. Claude writes only the
JSON spec (a few hundred tokens per video); `kit.py` writes the HyperFrames project.

```
$PY "$PE/templates/motion-kit/kit.py" icons money growth        # find icon names by meaning
$PY "$PE/templates/motion-kit/kit.py" build "$E/scenes.json" -o "mp-studio/work/<project>/motion"
cd "mp-studio/work/<project>/motion"; npx hyperframes check --json; npx hyperframes snapshot --at <mid of each scene> --no-end --describe false -o snaps
npx hyperframes render --output motion.mp4                     # ~7x real time on this laptop
$PY "$PE/templates/motion-kit/kit.py" demo -o mp-studio/work/kit-demo [--theme apple-dark]   # look book of every component
```
Rendering uses HyperFrames' hidden headless Chrome (setup installs it; else `npx hyperframes browser
ensure` once). Never point `HYPERFRAMES_BROWSER_PATH` at the owner's Chrome/Edge: it opens visible
windows and hangs while they browse. Batch looks: one `snapshot --at t1,t2,...` call, not one per frame. Spec format and every component: the docstring at the top of `kit.py`.

## Components
| type | use it for |
|---|---|
| `title` | hook / section title: kicker chip, words blur-rise in, *keyword* glows |
| `icon_card` | one idea = one icon + title + sub (icon draws on, ring rotates) |
| `icon_grid` | "N tools / N skills": icons pop on a stagger, chip counts up |
| `tabs` | Apple segmented control; the pill slides to each tab on its word, pane swaps |
| `stat` | a number: counts up, optional ring gauge fills |
| `list` | steps / tips: rows light up and tick on their words; upcoming rows blurred |
| `chat` | iMessage-style: typing dots, then the bubble |
| `notify` | iOS banner(s) drop in (likes, sales, DMs); `brand:instagram` icons |
| `compare` | before/after, wrong/right: loser greys out, winner glows |
| `flow` | A → B → C process, beams draw between nodes |
| `bars` | small bar chart, bars grow, values count |
| `quote` | a strong line, word by word |
| `cta` | profile card: Follow → Following, comment keyword types in |
| `article` | real article excerpt: `==phrase==` gets a hand-drawn marker that wipes in behind it, in order (`at`); best with `editorial` |
| `phone3d` | real 3D phone (Three.js): swings in, floats; `image` = a screenshot for the screen, else `screen_text` |
| `physics` | icons/logos drop, collide and pile up (Rapier 2D physics, simulated once, replayed by time) |
| `lottie` | a Lottie animation (LottieFiles → download → Lottie JSON) as `src`, optional `title` |

**Captions track** (spec key, not a scene): `"captions": {"cues": [{"t0", "t1", "text"}], "y": 875, "size": 52}` draws
light frosted-glass pills (backdrop blur, white edge, soft shadow), dark text, `*keyword*` on a soft accent pill, above
every scene. Chrome lays out the text, so Persian reads right to left even with English words mixed in (libass needs
`Encoding -1` for that). Used for the pop-out layout: captions inside the panel, just above the head breaking out.
Keep mixed English out of `*keyword*` titles: "YouTube *Agent Skill*" in an RTL title showed as «Agent YouTube Skill».

**Camera mode** (`"camera": true`, from Liam Johnston's cinematic-camera skill): all scenes live in
one big world laid out on a snake path; the camera glides to each on its cue (power3.inOut), holds
with a slow push while the action completes, scenes stay built, and `"camera_end": "overview"`
pulls out to show the whole system. Options: `camera_cols` (3), `camera_zoom` (1.0), `camera_push` (0.04).

## Depth effects (graphics behind AND in front of the speaker) — `depth.py`
Charlie Hills' 9-effects set, rebuilt locally: logo orbit, Claude window from behind the head,
3D growth chart behind you, reel fan, before/after (room → white studio), pixel title.
```
$PY "$PE/templates/motion-kit/depth.py" "$E" -o "$E/base_depth.mp4"      # spec: $E/depth.json (docstring)
$PY "$PE/templates/motion-kit/depth.py" "$E" --only 2 -o "$E/base_depth.mp4"   # redo one effect
```
Run it on the graded cut (`base_preview.mp4` / `base.mp4`), then finish.py with `"base": "base_depth.mp4"`.
Matte: `bluekey` (plain blue wall, instant) or `ai` (any background, ~1.8 s/frame on CPU: short windows).
Head position comes from the matte, so the effects place themselves. ~1 min render per effect.

## Themes
`futuristic` (deep space, neon cyan + brand accent, glass, aurora, perspective grid, HUD corners,
particles, scan line) · `apple-dark` · `apple-light` (SF-like glass cards, soft blobs) ·
`editorial` / `editorial-dark` (print-like: paper or charcoal, flat accents, no glow/glass/gradients —
for news, data, serious or premium topics; pairs with `article` and camera mode).
Icons: Lucide 1.61.0 (ISC) by name, brand logos from Simple Icons (CC0) as `brand:<name>`,
cached in `$ROOT/mp-studio/assets/icons/`. No Apple SF Symbols (licence).

`build` also writes `sfx_suggestions.json` (whoosh on scene changes, clicks on tabs/list ticks,
pops on reveals, dings on notifications) to paste into `fx.json` `"sfx"`.
