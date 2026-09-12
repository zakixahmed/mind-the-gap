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
  │   tiles ──► public/maps/<slug>/1..6.png ──────►│   shows maps/<slug>/<n>.png      │
  └──────────────────────────────────┘             └──────────────────────────────────┘
```

The deployed site is `public/` and nothing else. No server, no API calls, no build step.

## File layout

```
.
├── public/               everything that gets deployed (GitHub Pages root)
│   ├── index.html        the whole game: markup, CSS and JS inline
│   └── maps/<slug>/      1.png … 6.png, most blurred to sharpest
├── data/
│   ├── stations.json     one record per station: name, slug, lat, lon, zones, lines, borough
│   └── schedule.json     ordered list of slugs — puzzle N shows schedule[N]
├── scripts/
│   ├── build_stations.py fetches and normalises station data
│   └── render_maps.py    fetches tiles, crops around each station, writes blur levels
├── docs/                 this file, the decision log and the devlog
└── requirements.txt      pipeline dependencies only
```

Note: `public/` needs read access to `data/*.json`. How that is done (copy at build time vs. symlink vs. keeping data inside `public/`) is decided in phase 4 and recorded here.

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

## Blur levels _(pending — phase 3)_

Six PNGs per station. Level 1 is shown for guess 1 (most blurred), level 6 for guess 6 (sharpest). The blur radius follows a curve, not a straight line, so that level 3 feels like "I nearly have it". The exact radii are tuned by eye on five sample stations before the full set is rendered, and recorded here once agreed.

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
