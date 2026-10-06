# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Two hints are now available before the first guess instead of none: with only
  three guesses, locking all help behind a wrong one meant paying a third of
  your attempts to get any. Round-3 feedback; see ADR-026.
- The line's station count is now the first hint rather than a line on the
  result card. A tester spotted it there and read it as a clue that had arrived
  too late — it had. It is the one clue that needs no knowledge of London.

- A wrong guess is only "near" now if the two lines run alongside each other or
  cover the same part of London. It used to mean they shared any station at
  all, which was true of 87% of wrong guesses — the share grid was a column of
  yellow squares that recorded nothing. Now 32%. See ADR-027.

### Added
- The share grid marks a line solved with help (`💡`), so that solving one
  unaided still reads differently from being handed it.

## [0.3.0] — 2026-09-29

The line game, in response to round-2 feedback: v2 still only worked for
players who know London. See `docs/versions/v2/FEEDBACK.md` and ADR-025.

### Added
- A new main game: *which tube line is this?* Each puzzle shows one line's
  whole route in its real TfL colour over a blurred map of London, with the
  other ten lines faint for context. Three guesses, eleven answers.
- Three puzzles a day, the same for everyone, dealt from shuffled decks so
  every line comes up once per eleven puzzles and no day repeats a line. One
  share grid covers the day.
- Landmark hints for each line, unlocked by wrong guesses, and a fun fact about
  the line after every answer, each checked against a recorded source.
- `scripts/render_lines.py`, `scripts/build_line_hints.py`,
  `public/data/line_facts.json`.
- A version history in `docs/versions/`: each release's README, screenshots
  and the feedback it got.

### Changed
- The station game moved, unchanged, to `stations.html` as hard mode, linked
  both ways and keeping its own stats.
- The deploy check now also requires every line's maps and hints.

## [0.2.0] — 2026-09-27

The legibility pass, in response to the first round of player feedback
("too hard to guess"). See `docs/versions/v1/FEEDBACK.md`.

### Added
- A "nearby landmark" hint: the nearest notable place, with a rough distance and
  direction, derived from OpenStreetMap by `scripts/build_landmarks.py`.
  Landmarks are ranked by whether OpenStreetMap links them to Wikipedia, so the
  hint names places people recognise rather than the nearest pocket park.
- A scale bar and north cue on the map, so the crop can be read at a known size.
- A playtesting record, recording each round of feedback and what changed
  because of it.

### Changed
- Maps now cover 2.5 km rather than 1 km, at a higher resolution. This is the
  main response to "too hard to guess": the old crop was too tight to contain
  the features that let a player place themselves.
- The blur curve is re-spread so every guess visibly sharpens the map. The
  previous curve's last three levels were almost identical.
- Hints unlock face-down and are revealed by tapping, rather than appearing
  automatically — a wrong guess now offers help instead of forcing it.
- The hint ladder is Zone, Nearby, Line, Borough, Name; the separate
  first-letter and letter-count hints are merged into one rung.
- Roads are drawn with a minimum width so arterial routes stay legible at the
  wider crop; footways, cycleways, steps and service roads are no longer drawn.
- Individual buildings are no longer drawn; built-up areas are shown as a flat
  wash over residential land. At this scale the building layer was texture
  rather than information, and it was around 40% of the map data fetched.
- Cached OpenStreetMap responses are gzipped and their filenames carry the crop
  size, so map data can never be reused at the wrong scale.

## [0.1.0] — 2026-09-22

### Added
- GitHub Pages deployment via GitHub Actions, publishing `public/` with a pre-flight check that every scheduled station has all six map levels.
- Daily puzzle seeding from the London calendar date, with a curated 100-day schedule (`scripts/build_schedule.py` → `data/schedule.json`).
- Emoji share grid with the Web Share API on mobile and a clipboard fallback.
- Local stats: games played, win %, current and max streak, guess distribution — plus resume-on-reload for an in-progress daily game.
- Countdown to the next puzzle.
- Unlimited practice rounds, which don't affect stats.
- `public/data/facts.json` — one fact per station where we have a reliable one, with a fallback composed from the station's own record.

### Changed
- The station picker now opens the full browsable list on tap, instead of only appearing once you type.
- Softened the blur curve twice after playtesting, ending at `[5, 3.2, 2, 1, 0.4, 0]` with every level stored at full resolution. Full set re-rendered, 31.3 MB.

### Added
- The game itself: `public/index.html` — full core loop (progressive blur, station autocomplete, six guesses, hint ladder, win/lose screen) against one hardcoded puzzle. Dark theme, mobile-first, no framework or build step.
- `public/data/stations.json`: trimmed, minified station list written alongside the canonical one, so `public/` deploys standalone.
- `scripts/render_maps.py` and `public/maps/`: six progressively-blurred, label-free map crops for all 272 stations (1,632 WebP images, 15.9 MB), drawn from OpenStreetMap data via the Overpass API.
- `scripts/build_stations.py` and `data/stations.json`: all 272 London Underground stations with slug, coordinates, zones, lines, borough and adjacent stations, built from the TfL Unified API and Nominatim.
- Project scaffold: folder layout, `.gitignore`, MIT licence with third-party content note, pinned `requirements.txt`.
- Placeholder `public/index.html`.
- Documentation skeleton: README, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DEVLOG.md`.

[Unreleased]: https://github.com/zakixahmed/mind-the-gap/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/zakixahmed/mind-the-gap/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/zakixahmed/mind-the-gap/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zakixahmed/mind-the-gap/releases/tag/v0.1.0
