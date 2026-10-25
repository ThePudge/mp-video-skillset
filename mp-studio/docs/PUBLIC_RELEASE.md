# Plan: public release (later)

Today this repo stays private and is the working copy. When it is time to share:

## 1. On GitHub (owner)
- Settings → Emails: turn on **Keep my email addresses private** and **Block command line pushes
  that expose my email**. Commits then use `82179805+ThePudge@users.noreply.github.com`
  (already used for every commit since the fonts organizer).
- Create a new, **empty** public repository, e.g. `mp-studio-public` (no README, no license: the
  first push brings them).

## 2. Fresh history (Claude)
The private history contains the old e-mail and early personal files, so the public repo starts
from one clean commit of the current tree, not a mirror:
```
git clone --no-local . ../mp-studio-public-export && cd ../mp-studio-public-export
git checkout --orphan public && git reset
# add only what is public (below), then:
git -c user.name="mohammadpour.bi" -c user.email="82179805+ThePudge@users.noreply.github.com" commit -m "MP Studio"
git remote add public https://github.com/ThePudge/mp-studio-public.git && git push public public:main
```

## 3. What goes public / stays private
| Public | Never public |
|---|---|
| `MP Studio.exe`, mp-studio/ code (app, tools, requirements*.txt, docs, the two free fonts) | `mp-studio/assets/` (brand.json, avatar, music, sfx renders) — already gitignored |
| .claude/skills/ (own + MIT third-party with their LICENSE files) | `mp-studio/fonts/*` except Vazirmatn, Lalezar and their OFL licences |
| .claude-plugin/ (author = mohammadpour.bi) | `mp-studio/learn/notes/` (transcripts/frames of other creators' reels) |
| CLAUDE.md, README.md, LICENSE, THIRD_PARTY_NOTICES.md, docs/ | `mp-studio/learn/LOG.md` entries that name private projects — review first |
| mp-studio/fonts/README.md + the two free fonts | mp-studio/input/, mp-studio/work/, mp-studio/output/ (footage, renders) — already gitignored |

## 4. Before pushing, check
- `git grep -n -i "gmail\|@gmail\|password\|token\|api_key"` returns nothing.
- `git ls-files fonts` lists only README.md, Vazirmatn-*.ttf, Lalezar-Regular.ttf, OFL-*.txt.
- Creator credit present: README top, MP Studio header/footer, plugin.json author, LICENSE.
- The plugin manifests point at the public repo URL.

## 5. After
- Keep working in the private repo; publish with a small script that repeats step 2 into the
  public repo's next commit (no shared history), or switch the public repo to be the main one.
