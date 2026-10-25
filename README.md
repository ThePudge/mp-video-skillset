# MP Studio — edit reels with Claude

**Created by [@mohammadpour.bi](https://instagram.com/mohammadpour.bi)** · MIT license · [third-party notices](THIRD_PARTY_NOTICES.md)

Edit raw talking-to-camera videos (or just a voice note) into finished reels with Claude Code:
transcript cutting, punch-ins, captions, motion graphics, depth effects, music, Instagram-ready export.
Everything runs on your own computer. Nothing is uploaded anywhere.

## What's in this folder
```
MP Studio.exe      ← double-click this (the only file you need)
mp-studio/         ← everything else: the app, setup, fonts, your projects
  input/  work/  output/   your footage, Claude's working files, finished videos
  assets/  fonts/  learn/  brand, music, fonts, material to learn from
  app/  tools/  docs/      the program itself (start.bat + setup.bat in mp-studio/ are fallbacks)
README.md · LICENSE · CLAUDE.md, .claude/ (Claude's instructions and skills — keep them here)
```

## MP Studio (one window for everything)
Double-click **`MP Studio.exe`** (the MP icon, the only file you need). The first run installs what is missing; then MP Studio opens as an app window:
- **Home & setup** — health checks with one-click install/repair.
- **Project** — drop footage, voice notes, reference videos or links, real icons/screenshots, music; write the brief.
- **Brand & style** — your page, avatar, colours, theme, card style (glass / solid / outline / paper),
  motion feel (punchy 3D / playful), captions, and your own fonts with live previews.
- **Voice (صدا)** — clean the sound: room noise, hum, mouth clicks, harsh «س», warmth and clarity, even level; 15 s before/after preview.
- **Review** — Claude's plan, the cut table and a clickable storyboard (one card per spoken line); approve or note changes.
- **Outputs** — finished videos with caption and hashtags to copy. **Learn** — teach Claude new tricks.

Press **«ارسال به Claude»** and the Claude session continues by itself; approve in Review and it renders the final.

## Editing with Claude (main way)
1. Double-click **`MP Studio.exe`** once (it installs everything; or press install in MP Studio).
2. Open Claude Code in this folder. It loads [CLAUDE.md](CLAUDE.md), the skills in `.claude/skills/` and the Kinocut MCP server.
3. Put raw takes in `mp-studio/input/<project>/` and ask, e.g. "edit mp-studio/input/product-intro into a 60 s Persian reel with captions".
4. Optional: put videos whose style you want for that edit in `mp-studio/input/<project>/ref/`. Without a ref
   folder Claude chooses the best look for the script from its style library.
   Fonts (free and bought) go in [mp-studio/fonts/](mp-studio/fonts/README.md).
5. Optional: drop notes, feedback, tutorials or examples in `mp-studio/learn/inbox/` and say "learn from my inbox".
   Claude updates the skills and logs it in [mp-studio/learn/LOG.md](mp-studio/learn/LOG.md) ([mp-studio/learn/README.md](mp-studio/learn/README.md)).

## Install as a plugin: MP Claude Edit Skillset
Use the same skills from any folder, or share them, without cloning this repo. Windows only (setup uses winget and PowerShell).

```
claude plugin marketplace add ThePudge/video-editor
claude plugin install mp-claude-edit-skillset@mp-edit
```
Or in a Claude Code session: `/plugin marketplace add ThePudge/video-editor`, then `/plugin install mp-claude-edit-skillset@mp-edit`.

Then start a new session in the folder that holds your footage and say "edit my video". The first time, Claude gives
you the path of the plugin's `MP Studio.exe` to double-click (it installs FFmpeg, Python, Node.js, the Remotion and
HyperFrames skills and the Persian font into the plugin folder). Run it again after each plugin update.
The repository must be readable by whoever installs it (public, or shared with them on GitHub).

| Included | From | What for |
|---|---|---|
| `pro-edit` skill | this repo | The editing pipeline Claude follows: one plan, cheap drafts, one-image QC, brand profile in `mp-studio/assets/brand.md` |
| `video-use` skill | [browser-use/video-use](https://github.com/browser-use/video-use) (MIT), changed to use local Whisper | Conversational editing of raw footage |
| `remotion-best-practices` skill | [remotion-dev/skills](https://github.com/remotion-dev/skills), downloaded by setup | Motion graphics, animated captions |
| `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use` skills | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) (Apache-2.0), downloaded by setup | HTML/GSAP motion graphics, kinetic text, ready-made transitions and titles |
| `subject-cutout` skill | this repo, uses `hyperframes remove-background` | Text behind the speaker, dimmed/blurred/replaced background (people only) |
| `voice-motion` skill + `pro-edit/templates/motion-kit` | this repo, renders with HyperFrames; icons from [Lucide](https://lucide.dev) (ISC) and [Simple Icons](https://simpleicons.org) (CC0) | Send a voice note → full motion reel: futuristic / Apple-style glass scenes, SVG icons, segmented tabs, counters, charts, chat, notifications |
| Depth effects (`motion-kit/depth.py`) | ideas from [Charlie Hills' 9 video effects](https://charliehills.substack.com/p/9-video-effects-for-claude), rebuilt locally | Logo orbit around your head, Claude window from behind you, 3D growth chart, reel fan, before/after studio wipe, pixel title |
| Editorial theme, article highlight, camera mode | ideas from [Liamrjohnston/remotion-motion-graphics-skill](https://github.com/Liamrjohnston/remotion-motion-graphics-skill) (MIT) | Print-like restrained look, hand-drawn marker highlights, one-world camera moves |
| GSAP skills (5) | [greensock/gsap-skills](https://github.com/greensock/gsap-skills) (MIT), downloaded by setup | Correct GSAP timelines/eases for HyperFrames |
| 3D phone, physics drop, Lottie | [Three.js](https://threejs.org) (MIT), [Rapier](https://rapier.rs) (Apache-2.0), [lottie-web](https://github.com/airbnb/lottie-web) (MIT) | Real 3D objects, icons that fall and pile up, After Effects animations |
| `motion-reference` hook microscope + link download | idea from [taoufik123-collab/claude-watch](https://github.com/taoufik123-collab/claude-watch) (MIT), rebuilt with local Whisper | Study a reel's first 10 s frame by frame against its words; analyse reels from a link |
| `motion-reference` skill | this repo | Learns the style of a project's `mp-studio/input/<project>/ref/` videos for that edit |
| `learn-update` skill | this repo | Turns what you drop in `mp-studio/learn/inbox/` into skill updates, logged in `mp-studio/learn/LOG.md` |
| `pro-edit/templates/ass-motion` | this repo | Cards, counters, CTAs and captions as animated subtitles; works without HyperFrames |
| Kinocut MCP server | [KyaniteLabs/kinocut](https://github.com/KyaniteLabs/kinocut) (Apache-2.0), pip package | Ready-made editing tools for Claude |
| 15 content skills | [ootto-ai/claude-content-skills](https://github.com/ootto-ai/claude-content-skills) (MIT) | Hooks, scripts, on-screen text, captions, repurposing |

Remotion is free for individuals and small teams; larger companies need a [Remotion license](https://www.remotion.dev/license).

## The app
Double-click **`MP Studio.exe`** (runs the same setup first if needed).

The first run installs whatever is missing (takes 5–15 minutes, once):
- FFmpeg (via winget)
- Node.js 22+ (via winget, for Remotion and HyperFrames)
- Python 3.12 (via winget, only if not installed)
- Python packages into `.venv/`, plus NVIDIA GPU libraries (~1 GB) when an NVIDIA card is found

Whisper models download the first time you transcribe (small ≈ 0.5 GB, medium ≈ 1.5 GB, large-v3 ≈ 3 GB).
Later runs start in a few seconds. Needs Windows 10/11 with winget ("App Installer").

## Using it
1. **New project** → drop your raw videos (all takes) into the left panel.
2. **Prepare & transcribe** → makes constant-frame-rate working copies and a word-level transcript.
3. **Cut by text:**
   - click a word to jump there; drag or shift+click to select
   - `Delete` cuts / restores the selection, `✕` cuts a whole sentence, `Ctrl+Z` undoes
   - pauses longer than **Max pause** are cut automatically; click a `⏸` chip to keep one
4. **Play edit** previews the cut version without rendering.
5. **Render edit** → MP4 + SRT subtitles + contact sheet in `mp-studio/output/<project>/`.

## Folders (not in git — they stay on each computer)
| Folder | Contents |
|---|---|
| `mp-studio/input/<project>/` | Raw videos, never modified |
| `mp-studio/work/<project>/` | Proxies, transcripts, `cuts.json` (the edit decisions) |
| `mp-studio/output/<project>/` | Renders, subtitles, contact sheets |
| `mp-studio/assets/` | Logo, fonts, music |

`mp-studio/work/<project>/cuts.json` holds the edit as word ids (`clip:word`), so Claude can read and change the edit too.

## Tips for raw recordings
- Keep every take; clap or say "cut" between retakes so they are easy to find in the transcript.
- Record in the final orientation, or pick the crop (9:16, 16:9, 1:1) when rendering.

## Notes
- GPU: older NVIDIA cards (e.g. Quadro P3000, Pascal) run Whisper in `int8`; the app picks GPU and falls back to CPU automatically.
- Content skills from `ootto-ai/claude-content-skills` (hooks, scripts, captions, reel planning) are installed separately in `~/.claude/skills` on each machine.

## Other AI agents (free or cheap)
Claude Code gives the full "pro" edit. Other coding agents can run the **lite mode**: two commands,
the scripts make the decisions and the agent only fixes caption spelling (storyboard first, render after
approval). Step-by-step for free and paid platforms: [mp-studio/docs/GUIDE.md](mp-studio/docs/GUIDE.md). They read
[AGENTS.md](AGENTS.md) (`GEMINI.md`, `QWEN.md` and `.trae/rules/` point to it). Weaker models are
fine for lite mode; pro mode needs a model that can see images.
