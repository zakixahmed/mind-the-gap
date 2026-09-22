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
5. A new puzzle unlocks at midnight (London time) — the same one for everyone.
6. Want more? Practice rounds are unlimited and draw from all 272 stations.
   They don't count towards your streak.

## Running locally

The game is pure static files, so any local web server works:

```bash
cd public
python3 -m http.server 8000
# open http://localhost:8000
```

A server is required, not optional: the game fetches `data/stations.json`, and
browsers block that over `file://`. Nothing to install for the game itself. The Python environment below is only needed to regenerate data or map images.

## Regenerating the map data

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/build_stations.py   # → data/stations.json       (~5 min, see below)
python scripts/render_maps.py      # → public/maps/<slug>/1-6.webp
python scripts/build_schedule.py   # → data/schedule.json       (instant, offline)
```

**`render_maps.py`** fetches the raw OpenStreetMap features around each station
from the Overpass API and draws a label-free map, then writes six blur levels as
WebP. Responses cache to `data/raw/` so re-tuning the cartography needs no
network: `--offline` re-renders from cache, `--only slug,slug` does a few
stations, `--contact-sheet` writes a 6-up review image. A full run is 272
Overpass queries; the public instances are often busy, so it retries across
three mirrors, skips anything it cannot fetch, and lists the failures at the end
— run it again to fill the gaps. Budget an hour or more, and run it in the
background: `nohup python scripts/render_maps.py > render.log 2>&1 &`.

**`build_schedule.py`** writes the 100-day order the daily puzzle follows,
mixing famous and obscure stations with never three obscure in a row. Which
stations count as "famous" is an editable list at the top of the script rather
than a hidden constant; `--check` validates the existing schedule without
rewriting it. The launch date lives in `schedule.json` so the game and the
schedule cannot disagree about which day is puzzle #1.

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
| Map imagery | Drawn from raw OSM data via Overpass, not tiles | Tile licences forbid bulk pre-rendering, and tiles show station names. See ADR-008 |
| Blur method | Gaussian `[36, 20, 10, 5, 2, 0]`, stored as WebP | Non-linear so guess 3 is the turning point; WebP keeps the set at 16 MB. See ADR-009, ADR-010 |
| Daily seeding | London calendar-date arithmetic → index into `data/schedule.json` | No server, identical for everyone, correct across DST. See ADR-014 |
| Hosting | GitHub Pages from `public/` | Free, static, relative paths only |

## Licence and attribution

- **Code:** [MIT](LICENSE).
- **Station data:** [TfL Unified API](https://api.tfl.gov.uk) under the [TfL open data licence](https://tfl.gov.uk/info-for/open-data-users/) — *Powered by TfL Open Data. Contains OS data © Crown copyright and database rights 2016 and Geomni UK Map data © and database rights 2019.* Boroughs from [OpenStreetMap](https://www.openstreetmap.org/copyright) via Nominatim — *© OpenStreetMap contributors, ODbL 1.0.*
- **Map imagery:** drawn from [OpenStreetMap](https://www.openstreetmap.org/copyright) data retrieved via the [Overpass API](https://overpass-api.de) — *© OpenStreetMap contributors*, ODbL. No third-party tiles are used or redistributed. This attribution also appears in the app footer.

## Roadmap

- [x] Phase 1 — scaffold and docs skeleton
- [x] Phase 2 — station dataset (`data/stations.json`)
- [x] Phase 3 — map rendering, six blur levels per station
- [x] Phase 4 — game UI with one hardcoded puzzle
- [x] Phase 5 — daily logic, share grid, stats, countdown, 100-day schedule, practice mode
- [ ] Phase 6 — polish and playtest: how-to-play modal, light mode, footer attribution
- [ ] Phase 7 — deployment, real screenshots, `v0.1.0`

**Later, not in MVP:** archive mode for past puzzles, hard mode, distance-and-direction feedback on wrong guesses.

**Known limitation:** the schedule is 100 days and then repeats. Extending it is a matter of raising `LENGTH` in `build_schedule.py` and re-running.

**Deliberately out of scope:** accounts, leaderboards, multiplayer, user-generated puzzles, monetisation, any server.
