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
- Date: 2026-09-12 (resolved 2026-09-22)
- Status: Accepted — the full set is 15.9 MB, comfortably under the threshold, so `public/maps/` is committed
- Context: GitHub Pages serves files from the repository, so the PNGs must be in git or fetched at deploy time. The brief sets a 50 MB threshold.
- Decision: Commit `public/maps/` by default. After the full render in phase 3, measure the total. Over 50 MB → ignore the folder, document regeneration in README, and consider a GitHub Action that renders on deploy.
- Consequences: Simplest possible deploy while the set is small. The `.gitignore` already contains the commented-out rule so the switch is one line.

## ADR-004: Commit identity and authorship
- Date: 2026-09-12
- Status: Accepted
- Context: Commits are created from an AI-assisted session but the repository is Zack's portfolio.
- Decision: Commits are authored as Zack Ahmed (local git config in this repo only). Each commit body ends with a Co-Authored-By trailer naming the assistant, which is the standard GitHub convention for pair-authored commits.
- Consequences: Authorship is honest on both sides; GitHub attributes the work to Zack's account and the trailer records the collaboration without hiding it.

## ADR-005: Station data from the TfL Unified API, boroughs from Nominatim
- Date: 2026-09-12
- Status: Accepted
- Context: The brief allowed either the TfL Unified API or an OpenStreetMap extract. The game needs, per station: coordinates, fare zone(s), lines served, borough, and which stations are adjacent (for the 🟨 share-grid rule).
- Decision: TfL for everything TfL has (`/Line/Mode/tube`, `/Line/{id}/StopPoints`, `/Line/{id}/Route/Sequence/{direction}`), because it is the authoritative source for zones, lines and route order, and it defines "London Underground" for us (11 lines, 272 stations) with no heuristics. OSM has none of the fare data and would need filtering to separate Tube from Overground, DLR and the Elizabeth line. TfL does not publish boroughs, so each station is reverse-geocoded once with OSM Nominatim (1 request/second, cached, identifying User-Agent as its policy requires).
- Consequences: 34 TfL requests and 272 Nominatim requests per full build, about five minutes. Two attributions to carry (TfL open data, OSM ODbL). Raw responses are cached under `data/raw/` and git-ignored, so the dataset is reproducible and inspectable but the repo stays small. Rejected alternative: point-in-polygon against London Datastore borough boundaries — deterministic, but needs a shapefile parser or GeoJSON download and would still need a second source for the 16 stations outside Greater London.

## ADR-006: Scope is London Underground only
- Date: 2026-09-12
- Status: Accepted
- Context: TfL's network also includes the Elizabeth line, Overground, DLR and trams, all with map presence and zones.
- Decision: Only stations served by mode `tube` are included. Stations shared with other modes (e.g. Stratford) are included as Tube stations, with only their Tube lines listed.
- Consequences: Matches the game's name and the brief. Adding other modes later is a one-line change to `get_tube_lines()` plus a re-render, but would need thought about how many obscure stations the schedule can absorb.

## ADR-007: `stations.json` carries adjacency and uses slugs as the primary key
- Date: 2026-09-12
- Status: Accepted
- Context: The share grid needs "adjacent station" and the map renderer needs a safe folder name per station. Both could be computed at runtime or stored.
- Decision: Store both. `slug` is derived from the display name (`King's Cross St. Pancras` → `kings-cross-st-pancras`), asserted unique at build time, and is the key the front end and the map folders share. `adjacent` is a list of slugs derived from TfL's ordered route sequences in both directions. Four same-named stations have TfL's abbreviations expanded (`Dist&Picc Line` → `District & Piccadilly`) so the autocomplete reads naturally.
- Consequences: The front end never sees a naptan id and does no graph work. The file is 79 KB uncompressed, fine for a single fetch. If a station is renamed the slug changes and its map folder must be re-rendered — acceptable for a dataset that changes every few years.

## ADR-008: Draw the maps ourselves from raw OSM data rather than using map tiles
- Date: 2026-09-22
- Status: Accepted
- Context: The brief called for "a free static tile source whose licence permits this use". Two problems emerged. First, every standard tile style prints station names on the map, which would hand the player the answer at the sharpest level. Second, the licences forbid exactly what this game does. OpenStreetMap's tile usage policy lists under "You must not": "Bulk download ('scrape') tiles or offer prefetch features." CARTO's basemap terms prohibit "downloading or extracting map content in bulk" (9.c.i), "proxying or caching the content on the server side" (9.c.iii), and creating derivative works (15.d); their only static-image allowance is for "screenshots or other static images ... for illustrative, editorial or documentary purposes". Pre-rendering 1,632 cropped images and serving them from GitHub Pages does not fit inside that.
- Decision: Query the Overpass API for the raw OpenStreetMap *data* in a 1 km square around each station, and draw the map ourselves with Pillow — roads, rail, water, green space and buildings, no labels. The data is ODbL; the obligation is attribution ("© OpenStreetMap contributors") and nothing else. Overpass's usage policy allows a one-off job of this size comfortably: "less than 10,000 queries per day and download less than 1 GB data per day"; ours is 272 queries and about 400 MB, run once.
- Consequences: More code than pointing at a tile server, but we control the cartography, the maps are label-free by construction, and the licence position is clean and documented. The renderer is also reproducible offline from the cached responses. Cost: our maps are plainer than a professional basemap, which suits a blurred-image puzzle.

## ADR-009: Blur curve and per-level image sizes
- Date: 2026-09-22 (revised 2026-09-22 after playtesting)
- Status: Accepted — revised curve below supersedes the original
- Context: Six levels have to go from "almost nothing" to "fully legible" with guess 3 feeling like the turning point, and the whole set has to stay small.
- Decision: Gaussian radii `[36, 20, 10, 5, 2, 0]` — deliberately non-linear, with the big drop between levels 2 and 3. Reviewed on a five-station contact sheet (Amersham, Bank, Hainault, Turnham Green, Westminster) and signed off. Levels are stored at `[160, 160, 320, 640, 640, 640]` px: an image blurred at radius 36 carries no detail finer than that, so storing it small and letting the browser scale it up is visually identical and roughly ten times smaller.
- Consequences: The curve is a single constant to re-tune, and re-rendering from cache takes about a minute with no network.
- **Revision:** playing the finished UI showed the original curve was far too aggressive. Levels 1 and 2 were near-featureless colour washes — striking to look at, but they gave a player nothing to reason about, so the first two of six guesses were effectively wasted. The curve is now `[13, 8, 4.5, 2.5, 1, 0]`: guess 1 shows major roads, water and green space clearly enough to place a district, and the ramp to legibility happens across the middle guesses instead of all at the end. Level sizes rose to `[320, 384, 512, 640, 640, 640]` to match — at radius 13 the old 160 px storage, not the blur, would have been what limited the image. The full set grew from 15.9 MB to 20.7 MB, still comfortably inside ADR-003's threshold.

## ADR-013: A shared daily puzzle *and* unlimited practice rounds
- Date: 2026-09-22
- Status: Accepted — amends the brief
- Context: The brief specified one puzzle per day, identical for everyone. In review the preference changed to letting a player play as many rounds as they like. Pure endless play was considered and rejected: it would leave the share grid pointless (nobody else played your puzzle) and streaks meaningless, losing the two things that make the format social.
- Decision: Keep the shared daily puzzle as the headline round — it is what the share grid and streaks are built on — and add unlimited practice rounds on top, reachable from the end screen. Practice rounds draw from the full 272 stations, are not shareable and do not touch stats; only the daily counts.
- Consequences: One extra mode rather than a different game, and the daily logic, share grid and stats from phase 5 are unaffected. Practice needs its own lightweight state so an in-progress practice round cannot overwrite the day's saved daily game. The curated schedule stays worth doing, because it now only has to be good for the daily.


## ADR-010: WebP rather than PNG for the map images
- Date: 2026-09-22
- Status: Accepted — supersedes the PNG output named in the brief
- Context: The brief specified `public/maps/<slug>/1.png … 6.png`. Measured on the densest station, a palette-quantised PNG at 640 px was about 150 KB, putting the full set near 95 MB — well past the 50 MB threshold in ADR-003, which would have forced the maps out of the repository and into a build step.
- Decision: WebP at quality 80. The same image is about 41 KB; the full set is 15.9 MB (60 KB per station).
- Consequences: The repo stays self-contained and GitHub Pages serves the images directly, with no CI render step. WebP is supported by every browser released in the last several years, which is an acceptable floor for a hobby puzzle game. Changing back is a one-line edit plus a re-render from cache.

## ADR-011: `public/` carries its own trimmed copy of the station data
- Date: 2026-09-22
- Status: Accepted
- Context: The deploy target is the `public/` folder alone, but the canonical station list lives in `data/`. Options were a build-time copy, a symlink (which GitHub Pages will not follow), or moving the data into `public/` entirely.
- Decision: `scripts/build_stations.py` writes both — `data/stations.json` (canonical, indented, every field including naptan ids and build metadata) and `public/data/stations.json` (minified, only the eight fields the browser uses, 50 KB).
- Consequences: `public/` can be deployed as-is with nothing else alongside it, and the file the player downloads carries no dead weight. The cost is two files that must not drift; they are written by the same function in the same run, so they cannot.

## ADR-012: Enter never submits free text
- Date: 2026-09-22
- Status: Accepted
- Context: The brief rules out free-text entry to avoid spelling disputes. The obvious implementation — match the typed string against the station list on submit — still lets a player type `Tottenham Court Rd` and be told they are wrong.
- Decision: The input is a combobox over the station list. Enter commits only the currently highlighted suggestion; with nothing highlighted it does nothing but prompt. Matching folds case, accents and punctuation, so `st johns wood`, `King's Cross` and `kings cross` all find their station.
- Consequences: There is no code path that can reject a guess for spelling, because there is no path that accepts a string. The cost is that a player must always pick from the list, which is also what makes the game feel fair.

## ADR-014: Date seeding compares calendar dates, never elapsed time
- Date: 2026-09-22
- Status: Accepted
- Context: The puzzle number is "days since launch, in London". The tempting implementations — subtracting timestamps and dividing by 86,400,000, or adding 24 hours to find the next puzzle — are both wrong twice a year, when a London day is 23 or 25 hours long, and wrong all year for players outside the UK.
- Decision: Format "now" as a London calendar date with `Intl.DateTimeFormat("en-CA", {timeZone: "Europe/London"})`, which yields `YYYY-MM-DD`, then subtract two `Date.UTC(...)` values built from those date parts. That compares calendar days as calendar days and never meets a DST transition. The countdown to the next puzzle finds the exact instant the London date changes by bisecting over UTC milliseconds — about sixteen iterations, and correct on clock-change nights.
- Consequences: A player in Sydney gets the same puzzle as a player in Southwark on the same London day, which is the point. Verified in the browser across both 2026 DST transitions and a year boundary.

## ADR-015: Facts are optional, and the fallback is generated from the station record
- Date: 2026-09-22
- Status: Accepted
- Context: The win screen shows "one interesting fact". Writing 272 of them — or even 100 — is a large content job, and a half-remembered fact confidently displayed is worse than none.
- Decision: `public/data/facts.json` holds only facts we are confident of (20 at the time of writing). For every other station the game composes a sentence from the station's own record: zone, borough and lines. The file can grow over time and the game never shows an invented claim.
- Consequences: Every station has something to show from day one, and nothing in the game asserts anything the data does not support. Adding a fact is a one-line edit with no code change.
