# Cowork prompt: build "Mind the Gap"

Paste everything below the line into a new Cowork session with the project folder selected. Also save this file as `BRIEF.md` in that folder so future sessions have it.

---

I want you to build a daily puzzle web game called **Mind the Gap** in this folder, and document the whole build on GitHub as we go. Read this brief fully before doing anything, then propose a plan and wait for my approval before writing files.

## About me
BE and MSc in Computer Science. Comfortable with Python, SQL, JavaScript and basic web dev. This is a portfolio project, so code quality, README quality and commit history all matter. Explain decisions briefly as you make them.

## The game
Players guess a London Underground station from a heavily blurred map crop centred on it. Each wrong guess sharpens the image and unlocks a hint. Six guesses. One puzzle per day, identical for everyone. Think Wordle meets Worldle, for London.

### Core loop (MVP, must ship)
- Daily puzzle seeded by date: puzzle number = days since a fixed launch date, mapped to a curated schedule. No backend needed.
- Six blur levels: guess 1 shows the most blurred image, guess 6 the sharpest. Guess 3 should feel like "I nearly have it".
- Autocomplete search over the full station list. No free text input, to avoid spelling disputes.
- Hint ladder, one per wrong guess in this order: zone → line(s) → borough → first letter → number of letters.
- Win/lose screen showing the answer, one interesting fact, and a link to the station on OpenStreetMap.
- Share button that copies an emoji grid (🟩 correct, 🟨 same line or adjacent, ⬛ wrong) with the puzzle number, and uses the Web Share API on mobile.
- Local stats in localStorage: current streak, max streak, games played, win %, guess distribution.
- Countdown to the next puzzle.
- "How to play" modal on first visit.
- Mobile-first, responsive, dark mode by default with a light toggle.

### Explicitly out of scope for MVP
Accounts, leaderboards, multiplayer, user-generated puzzles, monetisation, any server. Do not add these.

### Later (do not build now, leave hooks where cheap)
Archive mode for past puzzles, hard mode, distance-and-direction feedback on wrong guesses.

## Tech constraints
- Front end: a single `public/index.html` with CSS and JS inline. No frameworks, no build step.
- Data pipeline: Python 3 scripts in `scripts/`. Use a virtual environment and a `requirements.txt`.
- Station data: TfL Unified API (StopPoint endpoints) or an OpenStreetMap extract. Tell me which you chose and why.
- Map tiles: a free static tile source whose licence permits this use. Show me the licence before rendering the full set. Include attribution in the app footer.
- Output: pre-rendered PNGs at `public/maps/<slug>/1.png … 6.png` so the deployed game is pure static files.
- Deploy target: GitHub Pages from the `public/` folder (or Vercel if simpler). Make it work with a relative base path.

## Repository and documentation requirements
Set up git in this folder at the very start and keep everything documented as you go. I will do the actual push to GitHub myself; you prepare everything.

- `README.md`: what the game is, screenshot/GIF placeholder, how to play, how to run locally, how to regenerate the map data, tech decisions, licence and attribution, roadmap.
- `docs/ARCHITECTURE.md`: how the pieces fit, the date-seeding logic, the file layout, how blur levels are generated.
- `docs/DECISIONS.md`: an ADR-style log. One short entry per meaningful decision (data source, tile source, blur method, share grid format). Append to it every session.
- `docs/DEVLOG.md`: a dated entry at the end of every session summarising what was built, what broke, and what's next.
- `CHANGELOG.md` following Keep a Changelog.
- `.gitignore` for Python, venv, OS files and the rendered maps if they exceed 50 MB (then document how to regenerate them).
- `LICENSE`: MIT for the code, with a note that map tiles and station data carry their own licences.
- Commit early and often with clear conventional-commit messages (`feat:`, `fix:`, `docs:`, `chore:`). Each commit should leave the project in a runnable state.
- Docstrings in every Python function and comments in the JS where logic is non-obvious, especially date seeding and blur mapping.

## Build order
Work through these as separate phases. At the end of each phase, commit, update `docs/DEVLOG.md`, show me what you built, and stop for my review before moving on.

1. **Scaffold and docs skeleton.** Folder structure, git init, README outline, all docs files created with headings, `.gitignore`, `LICENSE`, `requirements.txt`. First commit.
2. **Station dataset.** `scripts/build_stations.py` → `data/stations.json` with name, slug, lat, lon, zones, lines, borough. Validate the count and spot-check five stations against a source I can verify.
3. **Map rendering.** `scripts/render_maps.py` that produces six blur levels per station. Run it on five stations only, show me the images, and wait for me to confirm the blur curve feels right before rendering everything.
4. **Game UI with one hardcoded puzzle.** Full core loop against a single station. Open it in a browser and give me a screenshot at 375 px and 1280 px wide.
5. **Daily logic, share grid, stats, countdown.** Plus `data/schedule.json`: a curated 100-day order mixing famous and obscure stations, no three obscure ones in a row.
6. **Polish and playtest.** Walk through as a first-time player on a phone-sized viewport, list every friction point, then fix them. Add the how-to-play modal, light mode, footer attribution.
7. **Deployment prep.** GitHub Pages config, final README with real screenshots, tag `v0.1.0`, and give me the exact commands to push.

## Working rules
- Ask before deleting or overwriting anything I created.
- If a step needs a choice I haven't specified, pick the simplest option, do it, and log the decision in `docs/DECISIONS.md` rather than blocking on me.
- Keep files small and readable over clever.
- At the end of every session, update this `BRIEF.md` with a "Status" section listing what is done and what is next, so the next session can pick up cleanly.

Start with your plan for phase 1.

---

## Status

_Updated at the end of every session. Newest first._

### 2026-09-20 — after session 2 (phase 3, part-done)

**Done**
- `scripts/render_maps.py` written, reviewed and committed. Blur curve signed off on five stations. WebP chosen over PNG (ADR-010). Thames/multipolygon stitching, mirror rotation and failure-tolerance all fixed.
- 94 of 272 stations fetched, cached in `data/raw/` and rendered to `public/maps/<slug>/1-6.webp`.

**Next — start here**
1. In Terminal: `cd ~/Documents/'Portfolio Website '/'Mind the Gap - web game'` then `source .venv/bin/activate` then `nohup python scripts/render_maps.py > render.log 2>&1 &`. It resumes from the cache at station 95. Check with `tail -3 render.log`. Re-run if it ends with a FAILED line.
2. Commit `public/maps/`, check the total against the 50 MB threshold (ADR-003 is still *Proposed* pending this number), update README/ARCHITECTURE/CHANGELOG, close out phase 3.
3. Phase 4: game UI with one hardcoded puzzle; screenshots at 375 px and 1280 px.

**Open questions / notes for next session**
- Public Overpass instances have been slow and flaky; the renderer tolerates it but the full run takes an hour or more. Keep the Mac awake.
- Network: api.tfl.gov.uk and openstreetmap.org are blocked from Claude's shells, so anything needing the network runs in Zack's own Terminal.
- Delete permission on the folder must be granted each session so git can remove its lock files.

### 2026-09-12 — after session 1 (phase 2)

**Done**
- Phase 2 complete: `scripts/build_stations.py` → `data/stations.json` (272 stations, validated, spot-checked). ADR-005 to ADR-007 logged. Raw API responses cached in `data/raw/` (git-ignored) on Zack's Mac.

**Next**
- Phase 3: map rendering. Pick a tile source with a licence that permits bulk pre-rendering, show the licence, render five stations at six blur levels, get sign-off on the blur curve, then render all 272.

**Open questions / notes for next session**
- Network: api.tfl.gov.uk and openstreetmap.org are blocked from Claude's shells; scripts that need the network run in Zack's own Terminal (`source .venv/bin/activate` first). Tile downloads in phase 3 will be the same.
- Delete permission on the folder must be granted each session so git can remove its lock files.

### 2026-09-12 — after session 1 (phase 1)

**Done**
- Phase 1 complete: git repo on `main`, folder layout, `.gitignore`, `LICENSE`, `requirements.txt`, placeholder `public/index.html`, README outline, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (ADR-001 to ADR-004), `docs/DEVLOG.md`, `CHANGELOG.md`. Two commits.

**Next**
- Phase 2: station dataset. Write `scripts/build_stations.py` → `data/stations.json`; choose TfL Unified API vs. OSM extract and log it; validate the count; spot-check five stations against a verifiable source. Stop for review.

**Open questions / notes for next session**
- Borough is not in TfL's station data; plan is point-in-polygon against London Datastore borough boundaries (check licence — expected to be OGL v3).
- Tile source licence must be shown before the full render (phase 3).
