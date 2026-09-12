# Decision log

Lightweight ADRs. One entry per meaningful decision, newest at the bottom. Status is one of **Proposed**, **Accepted**, **Superseded by ADR-nnn**.

Template:

```
## ADR-nnn: Title
- Date: YYYY-MM-DD
- Status: Accepted
- Context: what question needed answering
- Decision: what was chosen
- Consequences: what that makes easier or harder
```

---

## ADR-001: Repository root is the game folder, not the parent portfolio folder
- Date: 2026-09-12
- Status: Accepted
- Context: The project lives inside a wider "Portfolio Website" folder. The game needs its own GitHub repository and GitHub Pages deployment.
- Decision: `git init` in `Mind the Gap - web game/` itself. The parent folder is untouched.
- Consequences: One repo per project, clean history, Pages can serve straight from `public/`. If the portfolio site later wants to embed the game, it links to the Pages URL rather than sharing a repo.

## ADR-002: Single-file front end with no framework and no build step
- Date: 2026-09-12
- Status: Accepted
- Context: The brief requires `public/index.html` with inline CSS and JS. Worth recording why that is a good fit rather than a constraint to work around.
- Decision: All markup, styles and logic live in one file. No bundler, no package.json for the front end.
- Consequences: The whole game is readable top to bottom, deploys anywhere that serves static files, and there is nothing to break in CI. The cost is that the file will grow to roughly a thousand lines; sections are separated with clear comment banners to keep it navigable. If it ever needs splitting, `<script src>` to sibling files is still build-free.

## ADR-003: Rendered map images are committed, size permitting
- Date: 2026-09-12
- Status: Proposed — revisit after phase 3
- Context: GitHub Pages serves files from the repository, so the PNGs must be in git or fetched at deploy time. The brief sets a 50 MB threshold.
- Decision: Commit `public/maps/` by default. After the full render in phase 3, measure the total. Over 50 MB → ignore the folder, document regeneration in README, and consider a GitHub Action that renders on deploy.
- Consequences: Simplest possible deploy while the set is small. The `.gitignore` already contains the commented-out rule so the switch is one line.

## ADR-004: Commit identity and authorship
- Date: 2026-09-12
- Status: Accepted
- Context: Commits are created from an AI-assisted session but the repository is Zack's portfolio.
- Decision: Commits are authored as Zack Ahmed (local git config in this repo only). Each commit body ends with a Co-Authored-By trailer naming the assistant, which is the standard GitHub convention for pair-authored commits.
- Consequences: Authorship is honest on both sides; GitHub attributes the work to Zack's account and the trailer records the collaboration without hiding it.
