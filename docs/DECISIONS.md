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
