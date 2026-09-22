# Architecture

How the pieces of Mind the Gap fit together. Sections marked _(pending)_ are filled in as the relevant phase lands.

## Overview

Two halves that never talk to each other at runtime:

```
  build time (Python, run by a developer)          run time (browser, static files only)
  ┌──────────────────────────────────┐             ┌──────────────────────────────────┐
  │ scripts/build_stations.py        │             │ public/index.html                │
  │   TfL / OSM  ──►  data/stations.json ─────────►│   loads stations.json            │
  │                                  │             │   picks today's slug from        │
  │ scripts/render_maps.py           │             │   data/schedule.json             │
  │   OSM data ──► public/maps/<slug>/1..6.webp ──►│   shows maps/<slug>/<n>.webp    │
  └──────────────────────────────────┘             └──────────────────────────────────┘
```

The deployed site is `public/` and nothing else. No server, no API calls, no build step.

## File layout

```
.
├── public/               everything that gets deployed (GitHub Pages root)
│   ├── index.html        the whole game: markup, CSS and JS inline
│   └── maps/<slug>/      1.webp … 6.webp, most blurred to sharpest
├── public/data/
│   └── stations.json     trimmed, minified copy the browser fetches
├── data/
│   ├── stations.json     canonical: name, slug, naptan, lat, lon, zones, lines, borough, adjacent
│   └── schedule.json     ordered list of slugs — puzzle N shows schedule[N]
├── scripts/
│   ├── build_stations.py fetches and normalises station data
│   └── render_maps.py    fetches tiles, crops around each station, writes blur levels
├── docs/                 this file, the decision log and the devlog
└── requirements.txt      pipeline dependencies only
```

`public/` is self-contained: `scripts/build_stations.py` writes a second,
trimmed copy of the station list to `public/data/stations.json` (50 KB minified,
naptan ids and build metadata removed). `data/stations.json` stays the
canonical, readable, fully-annotated version. Deploying means copying `public/`
and nothing else.

## Station data (`data/stations.json`)

Built by `scripts/build_stations.py`. Top level is `{"meta": …, "stations": […]}`;
`meta` carries the generation timestamp, the count, a map of line id → display
name, and the attribution strings. One station record looks like:

```json
{
  "name": "Turnham Green",
  "slug": "turnham-green",
  "naptan": "940GZZLUTNG",
  "lat": 51.495227, "lon": -0.254568,
  "zones": [2, 3],
  "lines": ["district", "piccadilly"],
  "borough": "Hounslow",
  "adjacent": ["acton-town", "chiswick-park", "gunnersbury", "hammersmith-district-and-piccadilly", "stamford-brook"]
}
```

- `slug` names the map folder (`public/maps/<slug>/`) and is asserted unique.
- `lines` use TfL ids; the front end owns the display names and colours.
- `adjacent` lists every station one stop away on any line, derived from TfL's
  ordered route sequences. This is what the 🟨 share-grid rule uses.
- `borough` is a London borough, `City of Westminster` / `City of London`, or
  the county for the 16 stations outside Greater London (Essex, Hertfordshire,
  Buckinghamshire).
- Same-named stations keep TfL's disambiguator, spelled out: `Edgware Road
  (Bakerloo)` and `Edgware Road (Circle)`, `Hammersmith (District &
  Piccadilly)` and `Hammersmith (Hammersmith & City)`, `Paddington` and
  `Paddington (Hammersmith & City)`.

## Date seeding _(pending — phase 5)_

Planned logic, to be confirmed when implemented:

1. Fix a launch date constant, e.g. `LAUNCH = 2026-10-01` (London local date).
2. `puzzleNumber = floor((todayLondonMidnight − LAUNCH) / 86 400 000)`.
3. `slug = schedule[puzzleNumber % schedule.length]`.
4. "Today" is computed in the `Europe/London` timezone so a player in another timezone still gets the same puzzle as everyone else on the same London day.

Edge cases to handle: BST/GMT switches (use `Intl.DateTimeFormat` with `timeZone: 'Europe/London'` rather than raw `Date` arithmetic), and a schedule shorter than the day count (wrap with modulo, and log it as a known limitation until the schedule is extended).

## Map rendering

`scripts/render_maps.py` produces `public/maps/<slug>/1.webp … 6.webp` for all 272 stations, 15.9 MB in total.

For each station it asks the Overpass API for the raw OpenStreetMap features in a square around the station (1 km, plus a 15% margin so nothing is clipped at the edge), then draws them with Pillow:

1. **Land use** — parks, grass, woods, cemeteries, industrial and retail areas.
2. **Water** — polygons first, then rivers and canals as lines.
3. **Buildings.**
4. **Roads**, in two passes: a darker casing under every road, then the fill on top, ordered so motorways sit above minor streets.
5. **Railways** — surface lines in solid grey, tunnels faint, so the Tube is hinted at without being a giveaway.

Everything is drawn at 2x and downscaled with Lanczos, because Pillow has no antialiasing of its own. Coordinates are projected with a simple equirectangular projection corrected by cos(latitude), which is accurate to well under a pixel over 1 km.

Two details worth knowing:

- **Multipolygon rings.** A large water body such as the Thames arrives as dozens of separate ways, clipped by the query bounding box, so none of them is a closed ring. `stitch()` chains the open segments end to end (reversing where that joins them more closely), which walks one bank, crosses, and comes back along the other; the implicit close runs along the box edge, giving exactly the polygon to fill.
- **Caching.** Every Overpass response is written to `data/raw/osm_<slug>.json` (git-ignored). Re-running touches the network only for stations it hasn't got, so colours and blur radii can be re-tuned offline in a few minutes. Failed stations are skipped and listed at the end rather than killing the run.

## Blur levels

Six images per station. Level 1 is shown for guess 1 (most blurred), level 6 for guess 6 (sharpest). Radii are `[36, 20, 10, 5, 2, 0]` — a curve, not a straight line, so that level 3 is the "I nearly have it" moment. Each level is stored at `[160, 160, 320, 640, 640, 640]` px, since a heavily blurred image holds no detail worth full resolution. See ADR-009.

## Hint ladder

One hint per wrong guess, always in this order: zone → line(s) → borough → first letter → number of letters. All five come straight from the station record, so hints need no extra data.

## Share grid

Per guess: 🟩 correct, 🟨 same line as the answer **or** an adjacent station on any line, ⬛ otherwise. Adjacency comes from the `adjacent` list in each station record (see above), so both halves of the rule are cheap to evaluate client-side.

## State stored in the browser

`localStorage` only: stats (played, wins, current streak, max streak, guess distribution), today's in-progress guesses keyed by puzzle number, whether the how-to-play modal has been seen, and the theme choice. Nothing leaves the device.

## Future hooks (not built)

- **Archive mode:** everything is keyed by puzzle number, so playing puzzle N is a matter of passing N instead of computing it from the date.
- **Hard mode:** a flag that skips the hint ladder.
- **Distance and direction:** `lat`/`lon` are already in `stations.json`, so a bearing and distance can be computed client-side.


## The front end (`public/index.html`)

One file, no framework, no build step (ADR-002). Markup, CSS and JS in three
clearly banded sections, about 700 lines in total.

**State** is a single `state` object: the station list, the answer, the guesses
made, and a status of `playing` / `won` / `lost`. Every render function reads
from it and rewrites its own piece of the DOM; there is no partial-update logic
to get wrong at this size.

**Blur level** is `min(guesses.length + 1, 6)` while playing, and 6 once the
game ends — so guess 1 sees level 1, and the answer is always revealed sharp.
The swap fades out, waits for the new file to decode, then fades in; without
that wait the sharper level appears half-loaded and reads as a glitch. Level 2
is preloaded at start-up so the first wrong guess feels instant.

**Hints** come from `HINT_LADDER`, an ordered array of `{label, render}`. Hint
*n* is revealed after wrong guess *n*, so the five hints cover guesses 1-5.
Adding or reordering hints means editing that one array.

**Autocomplete** matches on a normalised form of each name — case, accents and
punctuation folded — so `st johns` finds `St. John's Wood`. Names starting with
the query rank above names merely containing it, stations already guessed are
filtered out, and Enter only ever commits a *highlighted suggestion*: raw text
can never be submitted, which is what keeps spelling out of the game.

**Guess verdicts** use the share-grid rule from the brief — correct, or shares
a line / is one stop away, or neither — computed from `lines` and `adjacent` in
the station record. Phase 5's emoji grid reuses this function unchanged.

**Line colours** are the official TfL palette. Chip text colour is derived from
each background's relative luminance rather than hardcoded, because several
lines (Circle, Hammersmith & City, Jubilee, Waterloo & City) are too pale for
white text.

**Layout** is mobile-first and deliberately capped: the map is square but never
taller than `52vh`, and only the guesses actually made are drawn. An early
version rendered all six guess rows up front, which pushed the search box below
the fold on a 375 px phone — the one thing that must never happen. The
suggestion list opens upward on phones (the keyboard covers everything below
the input) and downward on wider screens (where opening upward would cover the
map).