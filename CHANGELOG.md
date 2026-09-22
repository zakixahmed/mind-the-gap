# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- The game itself: `public/index.html` — full core loop (progressive blur, station autocomplete, six guesses, hint ladder, win/lose screen) against one hardcoded puzzle. Dark theme, mobile-first, no framework or build step.
- `public/data/stations.json`: trimmed, minified station list written alongside the canonical one, so `public/` deploys standalone.
- `scripts/render_maps.py` and `public/maps/`: six progressively-blurred, label-free map crops for all 272 stations (1,632 WebP images, 15.9 MB), drawn from OpenStreetMap data via the Overpass API.
- `scripts/build_stations.py` and `data/stations.json`: all 272 London Underground stations with slug, coordinates, zones, lines, borough and adjacent stations, built from the TfL Unified API and Nominatim.
- Project scaffold: folder layout, `.gitignore`, MIT licence with third-party content note, pinned `requirements.txt`.
- Placeholder `public/index.html`.
- Documentation skeleton: README, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DEVLOG.md`.

[Unreleased]: https://github.com/USERNAME/mind-the-gap/compare/main...HEAD
