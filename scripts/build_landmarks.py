#!/usr/bin/env python3
"""Build data/landmarks.json — one "nearby landmark" hint per station.

Round-1 playtesting said the game was too hard, and the hint ladder was part of
why: zone, line and borough all assume you already carry the tube map in your
head, and none of them help you *locate* yourself on the picture in front of
you. This script supplies the missing rung — the most recognisable thing
nearby, with a rough distance and direction, so a player can reason from the
map rather than from memory.

Two phases, like fetch_osm_local.py:

1. **extract** (``--extract``) reads the Geofabrik .osm.pbf extracts once and
   writes every named feature that could make a landmark to
   ``data/raw/_landmark_candidates.jsonl.gz``. This is separate from the map
   cache on purpose: the map cache only holds what the renderer draws, so
   museums, attractions, towers and bridges were never on the shortlist, and the
   first version could only ever pick pocket parks.
2. **pick** (the default) scores the candidates around each station and writes
   the hint text.

"Recognisable" is judged by what OSM records, not by hand: a feature with a
Wikipedia or Wikidata link is worth far more than one without, and a park's
size counts for more than its mere existence. See ADR-024.

The hard part is not finding landmarks, it is not giving the game away. A
landmark whose name overlaps the station's ("Hyde Park" at Hyde Park Corner)
is a free answer, so those are rejected outright — see ``leaks_answer``.

Usage
-----
    python scripts/build_landmarks.py --extract data/pbf/*.osm.pbf   # once, ~3 min
    python scripts/build_landmarks.py --show                         # review the picks
    python scripts/build_landmarks.py                                # write the data
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FILE = ROOT / "data" / "stations.json"
RAW_DIR = ROOT / "data" / "raw"
CANDIDATES_FILE = RAW_DIR / "_landmark_candidates.jsonl.gz"
OUT_FILE = ROOT / "data" / "landmarks.json"
PUBLIC_FILE = ROOT / "public" / "data" / "landmarks.json"

AREA_M = 2500       # must match render_maps.AREA_M
MAX_DISTANCE_M = 1200   # the map reaches 1,250 m from the centre; stay inside it

# (tag key, tag value, kind shown to the player, base weight).
#
# The weight encodes how useful a *category* is as a clue. It is then adjusted
# by notability (a Wikipedia link), size (for areas) and distance — see score().
CATEGORIES: list[tuple[str, str, str, float]] = [
    ("aeroway", "aerodrome", "airport", 140),
    ("leisure", "stadium", "stadium", 130),
    ("tourism", "zoo", "zoo", 120),
    ("historic", "castle", "castle", 120),
    ("tourism", "museum", "museum", 110),
    ("tourism", "theme_park", "theme park", 110),
    ("building", "cathedral", "cathedral", 110),
    ("tourism", "gallery", "gallery", 100),
    ("tourism", "attraction", "landmark", 100),
    ("historic", "monument", "monument", 100),
    ("man_made", "bridge", "bridge", 100),
    ("leisure", "park", "park", 100),
    ("leisure", "common", "common", 100),
    ("natural", "heath", "heath", 100),
    ("amenity", "marketplace", "market", 95),
    ("landuse", "reservoir", "reservoir", 95),
    ("leisure", "nature_reserve", "nature reserve", 90),
    ("amenity", "university", "university", 90),
    ("shop", "mall", "shopping centre", 90),
    ("amenity", "theatre", "theatre", 85),
    ("natural", "wood", "woods", 85),
    ("landuse", "forest", "woods", 85),
    ("amenity", "hospital", "hospital", 75),
    ("leisure", "golf_course", "golf course", 70),
    ("landuse", "cemetery", "cemetery", 60),
]
# Towers and churches are everywhere; only the linked ones are worth a hint.
NOTABLE_ONLY: list[tuple[str, str, str, float]] = [
    ("man_made", "tower", "tower", 100),
    ("amenity", "place_of_worship", "church", 70),
]
WATERWAYS = {"river": ("river", 110), "canal": ("canal", 110)}

NOTABLE_BONUS = 60          # has a wikipedia / wikidata tag
# Size only says something about open spaces. A 1,000 m² footprint is a pocket
# park, but it is also the London Eye — so buildings and attractions are never
# marked down for being small.
SIZE_KINDS = {"park", "common", "heath", "woods", "nature reserve", "reservoir", "cemetery", "golf course"}
MIN_PLAIN_AREA_M2 = 20_000  # an unlinked park smaller than 2 ha is not a landmark

# Names that are never a useful landmark on their own, or are OSM housekeeping.
JUNK = re.compile(
    r"\b(station|underground|tube|railway|depot|sidings|car park|median strip|play ?area|"
    r"playground|allotments?|verge|roundabout|amenity|communal|land (at|adj\w*|off))\b"
    r"|^(the )?(meadow|green|garden|gardens|park|wood|woods|pond|lake|ravine|glade)$"
    r"|^\d|\d'",      # lock and bridge numbers: "2 Hawley lock 8'"
    re.I,
)

# Places OSM links to Wikipedia that almost nobody would recognise, or that sit
# inside a bigger answer (the Crown Jewels at Tower Hill). Skipping them lets the
# next pick through, with its distance and direction still computed — which is
# why this list exists rather than more OVERRIDES. Reviewed 2026-09-27.
SKIP: set[str] = {
    "ARTE DELUX", "Anaesthesia Heritage Centre", "Boston Music Room", "British Optical Association Museum",
    "Canal Cafe Theatre", "Chiswick Flyover", "Crown Jewels", "Cyberdog", "Eagle Squadron Monument",
    "Escape Studios", "Fake houses", "First World War Memorial", "For the Child",
    "Former North Circular Road Bridge", "Fusiliers London Volunteer Museum", "Fusiliers Museum",
    "General Roy's Baseline (Northwest End) Cannon Monument", "Gordon Museum", "Handel & Hendrix",
    "Hendon Police College", "Joseph Lister Monument", "Little Ben", "Little Dorrit Park",
    "London Sewing Machine Museum", "M4 Elevated Section", "Maddox Arts", "Pentameter's theatre",
    "Quentin Blake Centre for Illustration", "RIBA Library", "Ravensbourne University London",
    "Restored K6 phone booth", "Richard Cobden Statue", "Richmond American University London",
    "Royal College of Physicians Museum", "Sarm West Studios", "Studio Voltaire", "The Garden at 120",
    "The Lighthouse", "Topolski Century", "Traitor's Gate", "Twist Museum", "Unit London",
    "Victoria Road", "Waterloo Block", "Wimbourne House",
    "Kirkaldy Testing Museum", "Moco Museum", "Queen Anne", "Roman Baths",
    "Royal Pharmaceutical Society Museum", "The Museum of Philatelic History",
    "Tower and Portal of Church of St Mary", "Lillie Bridge", "Sambourne House",
    "British Red Cross Museum", "Gwendwr Gardens", "Museum of Methodism", "Spencer House",
    # UCL is dozens of buildings across Bloomsbury and beyond, so "UCL — just
    # east" is true from half of central London and tells the player nothing.
    "University College London",
}

# Sponsor names and OSM spellings that read badly in a hint.
RENAME: dict[str, str] = {
    "MATRADE Loftus Road Stadium": "Loftus Road Stadium",
    "Gtech Community Stadium": "Brentford Community Stadium",
    "Kia Oval": "The Oval cricket ground",
    "Elizabeth Tower": "Big Ben",
}

# Hand overrides, for the cases the heuristic still gets wrong.
# Slug → the exact hint text to show, or None to show no landmark hint at all.
OVERRIDES: dict[str, str | None] = {
    # Every nearby landmark is called "Clapham Common", which is the answer.
    "clapham-common": "A large open common — right beside the station",
    # The airport is the only landmark, and its name is the answer.
    "heathrow-terminals-2-and-3": "Airport runways — to the north and to the south",
}

COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


# ---------------------------------------------------------------------------
# Phase 1 — extract candidate features from the .pbf files
# ---------------------------------------------------------------------------


def classify(tags) -> tuple[str, float] | None:
    """(kind, base weight) if these tags describe a possible landmark, else None."""
    notable = "wikidata" in tags or "wikipedia" in tags
    for key, value, kind, weight in CATEGORIES:
        if tags.get(key) == value:
            return kind, weight
    if notable:
        for key, value, kind, weight in NOTABLE_ONLY:
            if tags.get(key) == value:
                if kind == "church" and not re.search(r"cathedral|abbey|minster", tags.get("name", ""), re.I):
                    return None
                return ("cathedral" if kind == "church" else kind), weight
    return None


def ring_area_m2(ring: list[tuple[float, float]]) -> float:
    """Planar area of a closed (lat, lon) ring in square metres (shoelace)."""
    if len(ring) < 3:
        return 0.0
    lat0 = ring[0][0]
    kx = 111_320 * math.cos(math.radians(lat0))
    pts = [((lon - ring[0][1]) * kx, (lat - lat0) * 110_540) for lat, lon in ring]
    s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    return abs(s) / 2


def thin(points: list[tuple[float, float]], cap: int = 160) -> list[list[float]]:
    """Every n-th point, so a big polygon stays small on disk, rounded to ~1 m."""
    step = max(1, len(points) // cap)
    return [[round(lat, 5), round(lon, 5)] for lat, lon in points[::step]]


def extract(pbf_paths: list[Path]) -> None:
    """Write every candidate landmark in the extracts to one JSONL file.

    Points (nodes), lines (rivers, canals) and areas (closed ways and
    multipolygons, assembled by osmium) each become one record holding a thinned
    outline, so the pick phase can measure to the nearest edge rather than to a
    centre that may be half a mile inside a park.
    """
    try:
        import osmium
    except ImportError:
        sys.exit("osmium is not installed — run: pip install -r requirements.txt")

    out = gzip.open(CANDIDATES_FILE, "wt")
    counts = {"node": 0, "line": 0, "area": 0}

    def write(kind_of: str, tags, points, area: float = 0.0) -> None:
        name = tags.get("name", "").strip()
        rec = classify(tags)
        if rec is None or not name or not points:
            return
        kind, weight = rec
        out.write(json.dumps({
            "name": name, "kind": kind, "weight": weight,
            "notable": "wikidata" in tags or "wikipedia" in tags,
            "area_m2": round(area), "shape": kind_of, "points": thin(points),
        }, ensure_ascii=False) + "\n")
        counts[kind_of] += 1

    class Handler(osmium.SimpleHandler):
        def node(self, n):
            if len(n.tags) < 2 or "name" not in n.tags:
                return
            write("node", n.tags, [(n.location.lat, n.location.lon)])

        def way(self, w):
            tags = w.tags
            waterway = tags.get("waterway")
            if waterway not in WATERWAYS or "name" not in tags:
                return
            # A river in a pipe is not on the map, so it cannot be a clue.
            if tags.get("tunnel") in ("culvert", "yes") or tags.get("covered") == "yes" \
                    or tags.get("location") == "underground":
                return
            try:
                pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
            except osmium.InvalidLocationError:
                return
            if len(pts) < 2:
                return
            kind, weight = WATERWAYS[waterway]
            out.write(json.dumps({
                "name": tags["name"].strip(), "kind": kind, "weight": weight,
                "notable": "wikidata" in tags or "wikipedia" in tags or "name:wikidata" in tags,
                "area_m2": 0, "shape": "line", "points": thin(pts),
            }, ensure_ascii=False) + "\n")
            counts["line"] += 1

        def area(self, a):
            if "name" not in a.tags or classify(a.tags) is None:
                return
            pts, total = [], 0.0
            try:
                for ring in a.outer_rings():
                    r = [(nd.lat, nd.lon) for nd in ring if nd.location.valid()]
                    total += ring_area_m2(r)
                    pts.extend(r)
            except osmium.InvalidLocationError:
                return
            write("area", a.tags, pts, total)

    for path in pbf_paths:
        started = time.time()
        print(f"{path.name} ...", flush=True)
        Handler().apply_file(str(path), locations=True, idx="flex_mem")
        print(f"  done in {time.time() - started:.0f}s", flush=True)

    out.close()
    print(f"\nwrote {CANDIDATES_FILE.relative_to(ROOT)} — "
          f"{counts['node']:,} points, {counts['line']:,} river/canal segments, {counts['area']:,} areas")


# ---------------------------------------------------------------------------
# Phase 2 — pick one landmark per station
# ---------------------------------------------------------------------------


def tokens(name: str) -> set[str]:
    """Lowercase word set, ignoring the noise words that join place names."""
    stop = {"the", "of", "and", "park", "road", "street", "lane", "hill", "green", "cross"}
    # Two characters is enough for a word to count: "The O2" is otherwise empty.
    words = {w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 2}
    return words - stop


def leaks_answer(landmark: str, station: str) -> bool:
    """True if naming this landmark would hand the player the station.

    Two ways that happens: the landmark's distinctive words are a subset of the
    station's ("Hyde Park" at Hyde Park Corner), or they share any distinctive
    word at all ("Wembley Stadium" at Wembley Park). Both are too generous a
    clue, so the test is deliberately strict — a station with no landmark is a
    better outcome than a station with a free one.
    """
    lm, st = tokens(landmark), tokens(station)
    return bool(lm & st) or not lm


def offset_m(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Metres east and north of (lat0, lon0). Flat-earth, fine over a few km."""
    east = (lon - lon0) * 111_320 * math.cos(math.radians(lat0))
    north = (lat - lat0) * 110_540
    return east, north


def bearing_name(east: float, north: float) -> str:
    """Compass direction, to the nearest eighth."""
    angle = (math.degrees(math.atan2(east, north)) + 360) % 360
    return COMPASS[round(angle / 45) % 8]


def describe(distance_m: float, direction: str) -> str:
    """'about 400 m north-west' — rounded, because precision here is false.

    The space between the number and the unit is non-breaking: without it the
    line wraps as "600 / m north-west", which looks like a typo.
    """
    if distance_m < 250:
        return f"just {direction}"
    if distance_m < 1000:
        return f"about {round(distance_m / 100) * 100} m {direction}"
    return f"about {distance_m / 1000:.1f} km {direction}"


def nearest(station: dict, points: list[list[float]]) -> tuple[float, float, float]:
    """(distance, east, north) to the closest point of a feature's outline."""
    best = None
    for lat, lon in points:
        e, n = offset_m(station["lat"], station["lon"], lat, lon)
        d = math.hypot(e, n)
        if best is None or d < best[0]:
            best = (d, e, n)
    return best


def score(c: dict, distance: float) -> float | None:
    """How good a clue this candidate is from this station, or None to drop it.

    Category weight, plus a large bonus for a Wikipedia/Wikidata link (the
    single best proxy for "people have heard of it"), plus a size bonus for
    areas — a 100-hectare park is a better clue than a 1-hectare one — minus
    distance, because a clue half a mile away is harder to use.
    """
    if not c["notable"] and c["shape"] == "area" and c["area_m2"] < MIN_PLAIN_AREA_M2:
        return None
    if not c["notable"] and c["shape"] == "node":
        return None     # an unlinked point is almost always something tiny
    s = c["weight"] - distance / 12
    if c["notable"]:
        s += NOTABLE_BONUS
    if c["shape"] == "area" and c["area_m2"] > 0:
        size = max(-30.0, min(45.0, 15 * math.log10(c["area_m2"] / 10_000)))
        # Open spaces go up and down with size; buildings only ever go up, so
        # Tate Modern gains on a small museum but the London Eye loses nothing.
        s += size if c["kind"] in SIZE_KINDS else max(0.0, size)
    return s


def load_candidates() -> list[dict]:
    """Read the phase-1 file, with a bounding box per record for quick rejection."""
    if not CANDIDATES_FILE.exists():
        sys.exit(f"{CANDIDATES_FILE.relative_to(ROOT)} not found — run with --extract first")
    out = []
    with gzip.open(CANDIDATES_FILE, "rt") as fh:
        for line in fh:
            c = json.loads(line)
            if JUNK.search(c["name"]) or c["name"] in SKIP:
                continue
            c["name"] = RENAME.get(c["name"], c["name"])
            lats = [p[0] for p in c["points"]]
            lons = [p[1] for p in c["points"]]
            c["bbox"] = (min(lats), min(lons), max(lats), max(lons))
            out.append(c)
    return out


def candidates(pool: list[dict], station: dict) -> list[dict]:
    """Every usable feature near the station, scored and sorted, best first."""
    dlat = MAX_DISTANCE_M / 110_540
    dlon = MAX_DISTANCE_M / (111_320 * math.cos(math.radians(station["lat"])))
    s_, w_, n_, e_ = station["lat"] - dlat, station["lon"] - dlon, station["lat"] + dlat, station["lon"] + dlon

    best: dict[str, dict] = {}
    for c in pool:
        b = c["bbox"]
        if b[2] < s_ or b[0] > n_ or b[3] < w_ or b[1] > e_:
            continue
        if leaks_answer(c["name"], station["name"]):
            continue
        distance, east, north = nearest(station, c["points"])
        if distance > MAX_DISTANCE_M:
            continue
        sc = score(c, distance)
        if sc is None:
            continue
        # One place can arrive as many records (a river in segments, a park as
        # both a node and an area). Keep the best-scoring one per name.
        if c["name"] not in best or sc > best[c["name"]]["score"]:
            best[c["name"]] = {
                "name": c["name"], "kind": c["kind"], "score": sc,
                "distance_m": round(distance),
                "where": describe(distance, bearing_name(east, north)),
            }
    return sorted(best.values(), key=lambda c: -c["score"])


def main() -> None:
    """Extract candidates, or pick a landmark for every station and write the data files."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extract", nargs="+", type=Path, metavar="PBF",
                        help="build the candidate file from these .osm.pbf extracts, then stop")
    parser.add_argument("--show", action="store_true", help="print every choice for review, and write nothing")
    parser.add_argument("--runners-up", type=int, default=0, help="also print N rejected alternatives per station")
    parser.add_argument("--only", help="comma-separated slugs to consider (with --show)")
    args = parser.parse_args()

    if args.extract:
        missing = [p for p in args.extract if not p.exists()]
        if missing:
            sys.exit(f"not found: {', '.join(map(str, missing))}")
        extract(args.extract)
        return

    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    if args.only:
        wanted = set(args.only.split(","))
        stations = [s for s in stations if s["slug"] in wanted]
    pool = load_candidates()
    landmarks: dict[str, dict] = {}
    empty = []

    for s in stations:
        picks = [] if s["slug"] in OVERRIDES else candidates(pool, s)
        if s["slug"] in OVERRIDES:
            text = OVERRIDES[s["slug"]]
            if text:
                landmarks[s["slug"]] = {"text": text, "kind": "manual"}
            chosen = text or "(no hint)"
            kind = "manual"
        elif picks:
            top = picks[0]
            landmarks[s["slug"]] = {"text": f"{top['name']} — {top['where']}", "kind": top["kind"]}
            chosen, kind = landmarks[s["slug"]]["text"], top["kind"]
        else:
            empty.append(s["slug"])
            chosen, kind = "(nothing found)", "-"

        if args.show:
            print(f"{s['name']:<38} {kind:<16} {chosen}")
            for alt in picks[1:1 + args.runners_up]:
                print(f"{'':<38} {'':<16}   ({alt['kind']}: {alt['name']}, {alt['distance_m']} m, {alt['score']:.0f})")

    if empty:
        print(f"\n{len(empty)} stations have no usable landmark; the game shows "
              f"'Nothing notable within a mile' for them: {empty}", file=sys.stderr)
    print(f"\n{len(landmarks)}/{len(stations)} stations have a landmark hint")
    if args.show or args.only:
        return

    OUT_FILE.write_text(json.dumps({"landmarks": landmarks}, indent=1, ensure_ascii=False) + "\n")
    PUBLIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_FILE.write_text(json.dumps({"landmarks": landmarks}, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {OUT_FILE.relative_to(ROOT)} and {PUBLIC_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
