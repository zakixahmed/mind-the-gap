#!/usr/bin/env python3
"""Build the OSM cache from local .osm.pbf extracts instead of the Overpass API.

Why this exists
---------------
Widening the crop to 2.5 km (ADR-018) multiplied the area of every Overpass
query by 6.25, and the free public instances stopped keeping up: the first full
run managed eight stations in 48 minutes — about 27 hours for all 272 — with
most of that time spent waiting on requests that then returned 504. Public
Overpass rate-limits per IP by queue slot, so 272 heavy queries is simply not
something it is willing to serve, and it is donated infrastructure besides.

A regional extract solves it properly. One download, no rate limit, no network
during the run, and the whole set takes minutes. It is also reproducible: the
same .pbf always yields the same maps, which the API could never promise.

The trick that makes it cheap: the 272 station boxes overlap heavily, so rather
than materialising 272 duplicated downloads we extract the *union* of the
features we draw once, then slice it per station locally.

This writes exactly the cache files render_maps.py already reads, so nothing
downstream changes — afterwards, `render_maps.py --offline` does the rest.

Getting the extracts
--------------------
Download from Geofabrik (https://download.geofabrik.de/europe/united-kingdom/
england/). Greater London covers most of the network; the Metropolitan and
Central line outliers need their counties too:

    greater-london-latest.osm.pbf     most stations
    buckinghamshire-latest.osm.pbf    Amersham, Chesham, Chalfont & Latimer
    hertfordshire-latest.osm.pbf      Watford, Rickmansworth, Moor Park, ...
    essex-latest.osm.pbf              Epping, Theydon Bois, Debden, Loughton

Usage
-----
    pip install osmium
    python scripts/fetch_osm_local.py data/pbf/*.osm.pbf        # both phases
    python scripts/fetch_osm_local.py --slice-only              # re-slice only
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

STATIONS_FILE = ROOT / "data" / "stations.json"
RAW_DIR = ROOT / "data" / "raw"
FEATURES_FILE = RAW_DIR / "_features.jsonl.gz"

# Kept identical to render_maps so the two cannot drift apart.
from render_maps import AREA_M, bbox_around  # noqa: E402

FETCH_MARGIN = 1.08

# The same selection the Overpass query makes, expressed as plain Python.
HIGHWAYS = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "unclassified", "living_street", "pedestrian",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}
RAILWAYS = {"rail", "light_rail", "subway", "tram", "narrow_gauge"}
NATURALS = {"water", "heath", "wood", "scrub"}


def wants_way(tags: dict) -> bool:
    """True if the renderer draws ways with these tags."""
    return (
        tags.get("highway") in HIGHWAYS
        or tags.get("railway") in RAILWAYS
        or "waterway" in tags
        or tags.get("natural") in NATURALS
        or "landuse" in tags
        or "leisure" in tags
    )


def wants_relation(tags: dict) -> bool:
    """True if the renderer fills this multipolygon relation."""
    return (
        tags.get("natural") == "water"
        or tags.get("waterway") == "riverbank"
        or tags.get("leisure") in {"park", "garden", "nature_reserve"}
        or tags.get("landuse") in {"forest", "grass", "cemetery"}
    )


def station_boxes() -> list[tuple[str, tuple[float, float, float, float]]]:
    """(slug, bbox) for every station, using render_maps' own box maths."""
    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    return [(s["slug"], bbox_around(s["lat"], s["lon"], AREA_M * FETCH_MARGIN)) for s in stations]


# ---------------------------------------------------------------------------
# Phase 1 — extract the union of everything we draw, once
# ---------------------------------------------------------------------------


def extract(pbf_paths: list[Path]) -> None:
    """Write every drawable feature from the extracts to one JSONL file.

    Two passes per file, because a .pbf stores nodes, then ways, then
    relations: by the time a relation names its member ways they have already
    gone past, so the first pass only notes which way ids the relations will
    need and the second pass collects geometry.
    """
    try:
        import osmium
    except ImportError:
        sys.exit("osmium is not installed — run: pip install osmium")

    out = gzip.open(FEATURES_FILE, "wt")
    written = 0

    for path in pbf_paths:
        print(f"\n{path.name}")
        started = time.time()

        # --- pass 1: which relations do we want, and which ways do they need?
        class Relations(osmium.SimpleHandler):
            def __init__(self):
                super().__init__()
                self.rels: dict[int, dict] = {}
                self.needed: set[int] = set()

            def relation(self, r):
                tags = dict(r.tags)
                if not wants_relation(tags):
                    return
                members = [(m.ref, m.role) for m in r.members if m.type == "w" and m.role in ("outer", "")]
                if not members:
                    return
                self.rels[r.id] = {"tags": tags, "members": members}
                self.needed.update(ref for ref, _ in members)

        rel_pass = Relations()
        rel_pass.apply_file(str(path))
        print(f"  {len(rel_pass.rels)} relations wanted, needing {len(rel_pass.needed)} member ways")

        # --- pass 2: geometry for the ways we draw, plus those member ways
        member_geom: dict[int, list[dict]] = {}

        class Ways(osmium.SimpleHandler):
            def __init__(self):
                super().__init__()
                self.count = 0

            def way(self, w):
                nonlocal written
                tags = dict(w.tags)
                is_member = w.id in rel_pass.needed
                if not is_member and not wants_way(tags):
                    return
                try:
                    geom = [{"lat": n.lat, "lon": n.lon} for n in w.nodes if n.location.valid()]
                except osmium.InvalidLocationError:
                    return
                if len(geom) < 2:
                    return
                if is_member:
                    member_geom[w.id] = geom
                if wants_way(tags):
                    out.write(json.dumps({"type": "way", "tags": tags, "geometry": geom}) + "\n")
                    written += 1
                    self.count += 1
                    if self.count % 100_000 == 0:
                        print(f"  {self.count:,} ways...", flush=True)

        way_pass = Ways()
        # flex_mem keeps node locations in RAM with an on-demand fallback; it is
        # the right index for regional extracts (a whole-planet run would need a
        # file-backed one).
        way_pass.apply_file(str(path), locations=True, idx="flex_mem")

        # --- assemble the relations now that their members have geometry
        kept = 0
        for rel in rel_pass.rels.values():
            members = [{"type": "way", "role": role or "outer", "geometry": member_geom[ref]}
                       for ref, role in rel["members"] if ref in member_geom]
            if not members:
                continue
            out.write(json.dumps({"type": "relation", "tags": rel["tags"], "members": members}) + "\n")
            written += 1
            kept += 1

        print(f"  {way_pass.count:,} ways + {kept:,} relations in {time.time() - started:.0f}s")

    out.close()
    size = FEATURES_FILE.stat().st_size / 1024 / 1024
    print(f"\nwrote {FEATURES_FILE.relative_to(ROOT)} — {written:,} features, {size:.0f} MB")


# ---------------------------------------------------------------------------
# Phase 2 — slice the union into the per-station caches render_maps reads
# ---------------------------------------------------------------------------


def feature_bbox(feature: dict) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a feature, over all its coordinates."""
    if feature["type"] == "way":
        pts = feature["geometry"]
    else:
        pts = [p for m in feature["members"] for p in m["geometry"]]
    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    return min(lats), min(lons), max(lats), max(lons)


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """True if two (south, west, north, east) boxes intersect at all."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


# Grid cell size in degrees. A station box is 2.7 km across, so at ~2.2 km per
# cell of latitude each station lands in a handful of cells and each feature
# only has to be tested against the stations that share one.
CELL = 0.02


def cells_for(bbox: tuple[float, float, float, float]) -> set[tuple[int, int]]:
    """Every grid cell a (south, west, north, east) box touches."""
    south, west, north, east = bbox
    return {(y, x)
            for y in range(int(south // CELL), int(north // CELL) + 1)
            for x in range(int(west // CELL), int(east // CELL) + 1)}


def slice_to_stations(overwrite: bool) -> None:
    """Read the feature file once, writing every station's cache as it goes.

    One pass, not one per station: each feature is looked up in a grid index to
    find the few stations whose box it could possibly touch, and appended to
    each of their open files. Holding all 272 stations' features in memory
    instead would be several gigabytes, because neighbouring stations
    legitimately share most of their map.
    """
    if not FEATURES_FILE.exists():
        sys.exit(f"{FEATURES_FILE.relative_to(ROOT)} not found — run the extract phase first")

    boxes = station_boxes()
    if not overwrite:
        boxes = [(slug, bb) for slug, bb in boxes
                 if not (RAW_DIR / f"osm_{slug}_{AREA_M}m.json.gz").exists()]
    print(f"{len(boxes)} stations to build")
    if not boxes:
        return

    # 272 open files at once is more than macOS allows by default.
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < len(boxes) + 64:
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(len(boxes) + 256, hard), hard))

    grid: dict[tuple[int, int], list[str]] = {}
    for slug, bb in boxes:
        for cell in cells_for(bb):
            grid.setdefault(cell, []).append(slug)
    lookup = dict(boxes)

    tmp_dir = RAW_DIR / "_slices"
    tmp_dir.mkdir(exist_ok=True)
    handles = {slug: gzip.open(tmp_dir / f"{slug}.jsonl.gz", "wt") for slug, _ in boxes}

    started, seen = time.time(), 0
    with gzip.open(FEATURES_FILE, "rt") as fh:
        for line in fh:
            feature = json.loads(line)
            fb = feature_bbox(feature)
            candidates = set()
            for cell in cells_for(fb):
                candidates.update(grid.get(cell, ()))
            for slug in candidates:
                if overlaps(fb, lookup[slug]):
                    handles[slug].write(line)
            seen += 1
            if seen % 200_000 == 0:
                print(f"  {seen:,} features, {time.time() - started:.0f}s", flush=True)

    for fh in handles.values():
        fh.close()
    print(f"  {seen:,} features placed in {time.time() - started:.0f}s")

    # Turn each station's line-per-feature file into the cache render_maps reads.
    for slug, _ in boxes:
        src = tmp_dir / f"{slug}.jsonl.gz"
        with gzip.open(src, "rt") as fh:
            elements = [json.loads(line) for line in fh]
        with gzip.open(RAW_DIR / f"osm_{slug}_{AREA_M}m.json.gz", "wt") as fh:
            json.dump({"elements": elements}, fh)
        src.unlink()
    tmp_dir.rmdir()

    print("\ndone — now run: python scripts/render_maps.py --offline")


def main() -> None:
    """Extract from .pbf files, then slice the result into per-station caches."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pbf", nargs="*", type=Path, help="one or more .osm.pbf extracts")
    parser.add_argument("--slice-only", action="store_true", help="skip the extract phase and re-slice")
    parser.add_argument("--overwrite", action="store_true", help="rewrite caches that already exist")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not args.slice_only:
        if not args.pbf:
            sys.exit("give at least one .osm.pbf file, or pass --slice-only")
        missing = [p for p in args.pbf if not p.exists()]
        if missing:
            sys.exit(f"not found: {missing}")
        extract(args.pbf)

    slice_to_stations(args.overwrite)


if __name__ == "__main__":
    main()
