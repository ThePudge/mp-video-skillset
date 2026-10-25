# Learn

Drop anything here that Claude should learn from, into `inbox/`:

- your feedback or notes ("captions too fast", "I like hard cuts, no zooms")
- tutorials, articles, PDFs, screenshots of edits you like
- transcripts or scripts, example EDLs, other people's skills or prompts
- `links.md` with URLs to read

Then say "learn from my inbox" (or "update the skills"). Claude reads each item, updates the
skills, templates, brand profile or reference style, writes what changed in [LOG.md](LOG.md),
moves the item to `done/`, and pushes the skill changes to GitHub.

Videos whose style you want for ONE project go in `input/<project>/ref/`; videos here teach the
general style library (`.claude/skills/pro-edit/styles.md`).

`inbox/` and `done/` stay on this computer (gitignored); `LOG.md` and the skill changes are shared.
