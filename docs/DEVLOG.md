# Devlog

One entry per working session, newest at the top. Each entry covers what was built, what broke, and what is next.

---

## 2026-09-22 — Session 3 (continued): Phase 5, daily logic and practice mode

**Review changes first**
- Blur softened from `[36, 20, 10, 5, 2, 0]` to `[13, 8, 4.5, 2.5, 1, 0]` and all 272 stations re-rendered (ADR-009 revised). The original made the first two of six guesses effectively unplayable.
- Puzzle model changed from daily-only to a shared daily plus unlimited practice rounds (ADR-013). Pure endless was considered and rejected: it would make the share grid pointless and streaks meaningless.

**Built**
- `scripts/build_schedule.py` → `data/schedule.json`: 100 days, 58 famous and 42 obscure, never three obscure in a row, opening on Waterloo, Westminster and London Bridge. The famous/obscure judgement is an editable list at the top of the script, and `--check` validates a schedule without rewriting it.
- Date seeding, share grid, localStorage stats with resume, countdown, and practice mode in `index.html` (ADR-013, ADR-014).
- `public/data/facts.json` with 20 facts, plus a fallback sentence composed from the station's own zone, borough and lines, so nothing is ever invented (ADR-015).

**Broke**
- The element cache derived property names from element ids, turning `guess-input` into `guessInput` while the code called `els.input` — so every listener silently attached to `undefined` and no guess could be submitted. Replaced with an explicit map that logs a missing element loudly.
- The PRACTICE badge showed on the daily screen: its CSS `display: inline-block` beats the browser's built-in `[hidden]` rule, so toggling the attribute did nothing. Fixed globally with `[hidden] { display: none !important; }`.
- A slug typo in the famous list (`heathrow-terminals-2-3` for `heathrow-terminals-2-and-3`) was caught by the script's own warning, which is exactly why it prints one.
- The first schedule opened on Pimlico and Morden — well-known, but a poor advertisement. Added a marquee list the opening days are drawn from.

**Verified**
- Driven headlessly at 375 px and 1280 px: a daily win records stats once and only once (a reload resumes the finished game without double-counting), the share text and emoji grid are correct, practice rounds leave stats untouched and return cleanly to the daily, and the console stays clean.
- Date maths checked in the browser across both 2026 DST transitions and a year boundary: two calendar days apart reads as exactly 2 in every case.

**Next**
- Phase 6: polish and playtest — walk through as a first-time player on a phone, list every friction point, fix them, then add the how-to-play modal, light mode toggle and footer attribution.

## 2026-09-22 — Session 3: Phase 4, the game UI

**Built**
- `public/index.html` (~700 lines, one file, no framework or build step): the complete core loop against one hardcoded puzzle (Baker Street). Progressive blur tied to guess count, station autocomplete, six guesses, the five-rung hint ladder, and a win/lose screen with the fact and an OpenStreetMap link. Dark theme throughout, laid out mobile-first.
- `scripts/build_stations.py` now also writes `public/data/stations.json` — trimmed to the eight fields the browser needs and minified to 50 KB — so `public/` is deployable on its own (ADR-011).
- Guess verdicts implement the share-grid rule (correct / shares a line or one stop away / neither), so phase 5's emoji grid can reuse the function unchanged.
- ADR-011 and ADR-012 logged; ARCHITECTURE now documents the front end.

**Broke**
- The first mobile layout put the search box below the fold on a 375 px screen: a full-width square map plus six empty guess rows ran past the viewport, so a first-time player landed on a page with nothing to type into. Fixed by capping the map at `52vh` and drawing only the guesses actually made plus one slim placeholder.
- On desktop the suggestion list opened upward and covered the map — exactly the thing the player needs while choosing. It now opens upward only on phones, where the on-screen keyboard covers everything below the input.
- Line chips used white text on every colour, which is close to unreadable on Circle yellow and Hammersmith & City pink. Chip text colour is now derived from the background's relative luminance rather than a hand-maintained list.

**Verified**
- Driven headlessly with Playwright at 375 px and 1280 px: a winning run, a losing run and the autocomplete, checking the blur advances to the right level, the hints appear in the right order, verdicts are right, the end screen renders and the console stays clean.

**Next**
- Phase 5: date seeding (days since launch → `data/schedule.json`), the emoji share grid, localStorage stats, the countdown, and a curated 100-day schedule mixing famous and obscure stations with no three obscure ones in a row.

---

## 2026-09-20 to 2026-09-22 — Session 2: Phase 3, map rendering (complete)

**Built**
- `scripts/render_maps.py`: fetches raw OpenStreetMap data for a 1 km square per station from the Overpass API, draws a label-free map with Pillow at 2x supersampling, and writes six blur levels. Flags: `--only`, `--offline`, `--contact-sheet`.
- Tile sources investigated and rejected — see ADR-008. Drawing from raw ODbL data instead means the only obligation is the "© OpenStreetMap contributors" attribution, and crucially the maps carry no station labels to give the answer away.
- Blur curve `[36, 20, 10, 5, 2, 0]` reviewed on five stations (Amersham, Bank, Hainault, Turnham Green, Westminster) and signed off.
- Output format switched from PNG to WebP after measuring: ~14 MB for the full set against ~95 MB, so the rendered maps can stay in the repository.

**Broke**
- Multipolygon water rendered as nothing: the Thames arrives as ~31 separate ways clipped to the bbox, not a closed ring. Added `stitch()` to chain open segments end-to-end.
- A dropped network connection killed a whole 272-station run. The renderer now skips the station, carries on, and lists failures at the end so a re-run fills the gaps.
- Public Overpass instances were heavily loaded all weekend (504s, timeouts). Added two mirrors with rotation on retry.
- Progress lines were buffered when redirected to a log file, so `tail render.log` showed only errors. Fixed with line buffering.

- The full run took three sessions of wall-clock time spread over two days, entirely because the public Overpass instances were saturated. The render itself is a few minutes of CPU. Five stations needed a second pass; the skip-and-continue behaviour meant that cost one extra command rather than a restart.

**Result**
- 272 stations, 1,632 images, 15.9 MB (60 KB per station) — well under the 50 MB threshold, so ADR-003 resolves to "commit the maps" and the repository stays self-contained with no CI render step.
- Spot-checked Richmond, Stockwell, Wanstead, Epping and Canary Wharf: rivers, rail, parks and docks all read clearly at level 6 and are unrecognisable at level 1.

**Next**
- Phase 4: the game UI with one hardcoded puzzle — full core loop (autocomplete, six guesses, hint ladder, win/lose screen) against a single station, then screenshots at 375 px and 1280 px.

## 2026-09-12 — Session 1 (continued): Phase 2, station dataset

**Built**
- `scripts/build_stations.py` (≈330 lines, every function docstringed): fetches lines, stations and route sequences from TfL, reverse-geocodes boroughs with Nominatim, derives slugs and adjacency, validates, and writes `data/stations.json`. Caches every response in `data/raw/`; `--offline` and `--no-borough` flags for iteration.
- `data/stations.json`: 272 stations, 11 lines, all with zones, lines, borough and adjacency. Spot-checked Bank, Amersham, Turnham Green, Heathrow Terminal 4 and Hainault against tfl.gov.uk station pages.
- ADR-005 to ADR-007; README and ARCHITECTURE updated with the schema and attribution.

**Broke**
- Neither the cloud workspace nor the sandboxed shell on the Mac is allowed to reach api.tfl.gov.uk or openstreetmap.org, so the script has to be run from a normal Terminal. API shapes were verified first with tiny sample requests through the in-app browser (Waterloo & City line: 2 stations), and the script was unit-tested against a cached fixture before the real run.
- First real run failed validation on 22 stations with "no zone": TfL writes boundary zones as `"2+3"`, not `"2/3"`. Fixed `parse_zones` to accept both.
- 41 stations came back with no borough: Nominatim reports Westminster and the City of London under `city`, not `city_district`, because they are cities. Added that fallback and made a missing borough a validation error so it cannot recur silently.
- TfL's raw name `Paddington (H&C Line)-Underground` needed an extra suffix rule and a small override table for the four abbreviated disambiguators.
- macOS's system Python warned about urllib3 2.x with LibreSSL; pinned `urllib3<2`.

**Next**
- Phase 3: `scripts/render_maps.py`. Choose a tile source whose licence allows bulk pre-rendering (OSM's own tile servers do not), show the licence before rendering, tune the six-level blur curve on five stations, then stop for review.

## 2026-09-12 — Session 1: Phase 1, scaffold and docs skeleton

**Built**
- Git repository initialised on `main` in the game folder, with the commit identity set locally.
- Folder layout: `public/` (with `maps/`), `data/`, `scripts/`, `docs/`.
- `.gitignore` for Python, virtual environments, OS and editor files, pipeline scratch folders, plus a commented-out rule for `public/maps/` in case the render set outgrows 50 MB.
- `LICENSE` (MIT) with an explicit note that map tiles and station data carry their own licences.
- `requirements.txt` pinned to `requests` and `Pillow` — the only two libraries the pipeline should need.
- Placeholder `public/index.html` so the repo is runnable from the first commit.
- README outline with every required section; ARCHITECTURE with the build-time/run-time split, file layout, and planned date-seeding logic; DECISIONS with ADR-001 to ADR-004; this devlog; CHANGELOG.

**Broke**
- The sandboxed shell on the Mac initially could not delete files, so git could not remove its own `HEAD.lock` and temporary object files after the first commit. Fixed by granting delete permission for the folder; the commit itself was intact (`git fsck` clean).

**Next**
- Phase 2: `scripts/build_stations.py` → `data/stations.json`. Decide TfL Unified API vs. OpenStreetMap extract (leaning TfL for zones and lines, with a borough lookup from London Datastore boundaries), validate the station count, and spot-check five stations against a source Zack can verify.
