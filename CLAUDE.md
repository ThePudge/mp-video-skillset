# Video Editor — instructions for Claude

The owner sends **raw videos of themself** (mostly Persian, sometimes English) and Claude edits them.
Claude is the editor; MP Studio (`MP Studio.exe`, http://127.0.0.1:8765) is an optional visual tool
for cutting by text and previewing.

## Environment
- Python: always `.venv/Scripts/python.exe` (never system Python). Created on the first run of `MP Studio.exe` (or Studio → Home → install).
  If `.venv` is missing, tell the owner to double-click `MP Studio.exe` — don't install packages yourself.
- FFmpeg/ffprobe on PATH. GPU Whisper uses `int8` (older NVIDIA cards can't do float16); CPU fallback is automatic.
- No API keys needed. Transcription is local Whisper. `ELEVENLABS_API_KEY` in `.env` switches video-use to hosted Scribe (better filler detection, uploads audio). Keys go in `.env` only — it is gitignored.

## MP Studio first (every edit)
The owner works in **MP Studio** (one app window: setup, uploads, brand & style, fonts, review, outputs).
Don't ask in chat for what Studio collects; hand work back and forth with `mp-studio/app/handoff.py`:
1. `.venv/Scripts/python.exe mp-studio/app/handoff.py open <project>` — starts the server if needed and opens the
   window once (never more often). Tell the owner in one line: add the files and the brief, then press
   «ارسال به Claude». Start `handoff.py wait <project> --for ready` with **run_in_background**; it wakes
   you with the brief + brand as JSON. Then `handoff.py set <project> working`.
2. Plan → **storyboard in Studio BEFORE any render**, not a chat essay: cut EDL + corrected captions +
   `cards.json` (layout/move per spoken line) + `plan.md`, then `pro-edit/storyboard.py <edit> --cards … --plan …`
   **without `--video`** (stills + audio straight from the raw takes, seconds). `handoff.py set <project> review`,
   one-line note in chat, then `wait --for approved,changes` in the background. Heavy work (panels, depth,
   finish, QC renders) only after approval.
   The brief's `mode` says which pipeline the owner picked: `pro` (this one) or `lite` (`pro-edit/lite_edit.py`,
   see `AGENTS.md`) — if `lite`, run lite mode even in Claude.
3. `changes` → apply `mp-studio/work/<project>/review/decision.json` (per-card notes), redo only those cards, review
   again. `approved` → `set rendering`, final render + `<video>.caption.txt` beside it in `mp-studio/output/`, `set done`.
**The owner's Studio buttons only save** («ذخیره و آماده برای Claude», «تأیید», «تغییرات»); then they paste
a sentence here, e.g. «پروژه‌ی «X» رو ادیت کن», «…: تأیید کردم، نسخه نهایی رو بساز», «…: یادداشت‌های بازبینی رو
اعمال کن». On any of these, first run `.venv/Scripts/python.exe mp-studio/app/handoff.py show <X>` (brief, brand,
review decision, status) and continue from that status — never ask for what it already contains.
Brand & style: `mp-studio/assets/brand.json` (Studio writes it). A project can override any style/voice key in
`mp-studio/work/<project>/settings.json` (Studio → Brand & style → «فقط پروژه‌ی …», or Voice → «استفاده در ادیت‌های این پروژه»);
the `brand` that `handoff.py show` prints is already merged — always use that, never brand.json alone.
motion-kit (`kit.py`, `depth.py`) merges it too when its spec/output lives under `mp-studio/work/<project>/`. If the owner answers in chat instead ("approved"),
stop the waiting task and `handoff.py set <project> approved|changes` so Studio shows the same state.
Send Persian text to the Studio API from Python (urllib/json), never `curl -d` in Git Bash: the shell
mangles it to "????".

## Which tool for what
| Task | Use |
|---|---|
| Quick dependable edit in two commands (also what other agents use, see `AGENTS.md`) | `pro-edit/lite_edit.py prepare / render` |
| Edit raw footage into a finished video (the default for any edit request) | `pro-edit` skill — token-lean pro pipeline; it drives the skills below |
| Cutting engine and its hard rules (cuts, retakes, fillers, grade, subtitles, overlays) | `video-use` skill (used by `pro-edit`) |
| Motion graphics: titles, lower-thirds, animated captions, logo intro/outro | `hyperframes` skills (HTML/GSAP, ~450 ready blocks in `hyperframes-registry`) or `remotion-best-practices` (React); both fetched by setup |
| Owner drops notes/feedback/tutorials/examples in `mp-studio/learn/inbox/` to improve the skills | `learn-update` skill → edits skills, logs in `mp-studio/learn/LOG.md`, pushes to main |
| Copy the style of reference videos (files in `mp-studio/input/<project>/ref/` or a pasted link), incl. a 0–10 s hook microscope | `motion-reference` skill → `mp-studio/work/<project>/ref_style.md`; no ref folder → pro-edit picks a look from `pro-edit/styles.md` |
| Owner sends a voice note / voice-over (no footage) → full motion-graphics reel | `voice-motion` skill (motion-kit + pro-edit captions/audio) |
| Pro UI motion: futuristic / Apple-style glass cards, SVG icons, segmented tabs, counters, charts, chat, notifications | `pro-edit/templates/motion-kit` (`kit.py`, scene list → HyperFrames) |
| Simple cards, counters, CTAs, or any motion when HyperFrames isn't installed | `pro-edit/templates/ass-motion` (animated libass, Persian-safe) |
| Graphics passing behind AND in front of the speaker: logo orbit, Claude window from behind the head, 3D growth chart, reel fan, before/after studio wipe, pixel title | `pro-edit/templates/motion-kit/depth.py` (`depth.json` → `base_depth.mp4`) |
| Editorial / news look, article highlights, cinematic camera, 3D phone, physics drop, Lottie | motion-kit components + `editorial` theme + `"camera": true` (README there) |
| Clean the voice: room noise, hum, mouth clicks, harsh «س», thin/boomy tone, uneven level | `pro-edit/audio/voice_clean.py` (presets light/clean/strong/podcast) — also MP Studio → صدا with before/after preview |
| Text behind the speaker, dimmed / blurred / replaced background | `subject-cutout` skill (local person cutout via `npx hyperframes remove-background`) |
| One-off operations: trim, convert, resize, extract audio, quick effects | `kinocut` MCP server (`.mcp.json`) |
| Hooks, scripts, on-screen text, captions/hashtags, covers, repurposing | content skills (`viral-hook-writer`, `reel-scripter`, `on-screen-text-writer`, `caption-and-hashtags`, …) |
| Owner wants to cut visually themself | the app: projects in `mp-studio/input/<project>/`, edit decisions in `mp-studio/work/<project>/cuts.json` (word ids `clip:word`) |

`content-factory` mentions Apify / Composio / Runway / auto-posting: never connect or post without the owner asking.
HyperFrames skills also offer HeyGen cloud features (`heygen ...`, cloud render, publish) and post-render feedback reports:
use only the free local commands unless the owner asks. Telemetry is off (`HYPERFRAMES_NO_TELEMETRY=1` in `.claude/settings.json`).

## Folders (gitignored, per machine)
- `mp-studio/input/<project>/` raw takes — never modify; their order + roles (main / retake / broll) are in
  `mp-studio/work/<project>/clips.json` (Studio → پروژه, drag to reorder) and in `handoff.py show` → `clips`
- `mp-studio/work/<project>/` proxies, transcripts, video-use `edit/` dirs
- `mp-studio/output/<project>/` renders
- `mp-studio/assets/` logo, music, brand.md
- `mp-studio/input/<project>/ref/` optional reference videos for that project (never edited or transcribed as takes)
- `mp-studio/fonts/` every font file (free + bought); files gitignored, `mp-studio/fonts/README.md` shared

For video-use, pass `--edit-dir mp-studio/work/<project>/edit` so its files stay out of `mp-studio/input/`.

## Working rules
- Voice pass first (transcript only, cheap), then look at frames only at cut points. Prefer contact sheets/timeline views over many single frames — images cost the most tokens.
- Confirm the edit plan in plain language before rendering.
- Persian text: files are UTF-8 (`PYTHONUTF8=1` is set in `.claude/settings.json`).
