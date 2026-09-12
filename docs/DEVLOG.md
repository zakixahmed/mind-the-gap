# Devlog

One entry per working session, newest at the top. Each entry covers what was built, what broke, and what is next.

---

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
