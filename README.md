# Mind the Gap

A daily puzzle game: guess the London Underground station from a heavily blurred map crop centred on it. Every wrong guess sharpens the image and unlocks a hint. Six guesses. One puzzle a day, the same for everyone.

Think Wordle meets Worldle, for London.

> **Status:** in development — see [docs/DEVLOG.md](docs/DEVLOG.md) for progress.

![Screenshot placeholder — gameplay GIF will go here after phase 6](docs/screenshot-placeholder.png)

## How to play

1. You are shown a blurred map centred on a mystery Tube station.
2. Type a station name and pick it from the autocomplete list (no free text, so no spelling disputes).
3. A wrong guess sharpens the map one level and reveals the next hint, in this order: **zone → line(s) → borough → first letter → number of letters**.
4. You have six guesses. Guess it and share your emoji grid:
   🟩 correct · 🟨 same line or an adjacent station · ⬛ wrong.
5. A new puzzle unlocks at midnight (London time).

## Running locally

The game is pure static files, so any local web server works:

```bash
cd public
python3 -m http.server 8000
# open http://localhost:8000
```

Nothing to install for the game itself. The Python environment below is only needed to regenerate data or map images.

## Regenerating the map data

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/build_stations.py   # → data/stations.json       (~5 min, see below)
python scripts/render_maps.py      # → public/maps/<slug>/1-6.png (phase 3)
```

**`build_stations.py`** pulls the 11 Underground lines, their stations and route
sequences from the TfL Unified API (34 requests), then reverse-geocodes each
station with OpenStreetMap's Nominatim to get its borough. Nominatim allows one
request per second, so a full run takes about five minutes; every response is
cached in `data/raw/` (git-ignored) so re-runs are instant and the raw evidence
for any record can be inspected. Flags: `--offline` rebuilds from the cache
only, `--no-borough` skips Nominatim for quick iteration. The script validates
the result (station count, zones, lines, boroughs, adjacency, coordinates) and
refuses to write `stations.json` if anything is missing. An optional
`TFL_APP_KEY` environment variable raises TfL's anonymous rate limit.

## Tech decisions

Short version — the reasoning lives in [docs/DECISIONS.md](docs/DECISIONS.md) and the structure in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Area | Choice | Why (one line) |
|------|--------|----------------|
| Front end | Single `public/index.html`, no framework, no build step | Small enough to read in one sitting; deploys anywhere |
| Data pipeline | Python 3 scripts in `scripts/` | Run once, commit the output; the game never calls an API |
| Station data | TfL Unified API + Nominatim for boroughs | Authoritative zones, lines and route order; OSM has none of those. See ADR-005 |
| Map tiles | _decided in phase 3_ | |
| Blur method | _decided in phase 3_ | |
| Daily seeding | Days since a fixed launch date → index into `data/schedule.json` | No server, identical for everyone |
| Hosting | GitHub Pages from `public/` | Free, static, relative paths only |

## Licence and attribution

- **Code:** [MIT](LICENSE).
- **Station data:** [TfL Unified API](https://api.tfl.gov.uk) under the [TfL open data licence](https://tfl.gov.uk/info-for/open-data-users/) — *Powered by TfL Open Data. Contains OS data © Crown copyright and database rights 2016 and Geomni UK Map data © and database rights 2019.* Boroughs from [OpenStreetMap](https://www.openstreetmap.org/copyright) via Nominatim — *© OpenStreetMap contributors, ODbL 1.0.*
- **Map tiles:** _source and licence recorded in phase 3; attribution also appears in the app footer._

## Roadmap

- [x] Phase 1 — scaffold and docs skeleton
- [x] Phase 2 — station dataset (`data/stations.json`)
- [ ] Phase 3 — map rendering, six blur levels per station
- [ ] Phase 4 — game UI with one hardcoded puzzle
- [ ] Phase 5 — daily logic, share grid, stats, countdown, 100-day schedule
- [ ] Phase 6 — polish and playtest: how-to-play modal, light mode, footer attribution
- [ ] Phase 7 — deployment, real screenshots, `v0.1.0`

**Later, not in MVP:** archive mode for past puzzles, hard mode, distance-and-direction feedback on wrong guesses.

**Deliberately out of scope:** accounts, leaderboards, multiplayer, user-generated puzzles, monetisation, any server.
