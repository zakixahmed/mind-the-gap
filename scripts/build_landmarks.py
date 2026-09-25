#!/usr/bin/env python3
"""Build data/landmarks.json — one "nearby landmark" hint per station.

Round-1 playtesting said the game was too hard, and the hint ladder was part of
why: zone, line and borough all assume you already carry the tube map in your
head, and none of them help you *locate* yourself on the picture in front of
you. This script supplies the missing rung — the nearest notable thing, with a
rough distance and direction, so a player can reason from the map rather than
from memory.

Everything comes from the Overpass data already cached by render_maps.py, so
this script needs no network. Run it after the maps have been rendered.

The hard part is not finding landmarks, it is not giving the game away. A
landmark whose name overlaps the station's ("Hyde Park" at Hyde Park Corner)
is a free answer, so those are rejected outright — see ``leaks_answer``.

Usage
-----
    python scripts/build_landmarks.py           # write the data
    python scripts/build_landmarks.py --show    # print what it chose, for review
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FILE = ROOT / "data" / "stations.json"
RAW_DIR = ROOT / "data" / "raw"
OUT_FILE = ROOT / "data" / "landmarks.json"
PUBLIC_FILE = ROOT / "public" / "data" / "landmarks.json"

AREA_M = 2500       # must match render_maps.AREA_M: only pick things that are on the map
MAX_DISTANCE_M = 1400

# (tag key, tag value or None for "any") → (kind shown to the player, weight).
#
# Weight is how much a category is worth before distance is subtracted, and it
# encodes prominence: a stadium two-thirds of a mile away is a better clue than
# a hospital next door, because you can *see* the stadium on the map.
CATEGORIES: list[tuple[str, str | None, str, float]] = [
    ("waterway", "river", "river", 150),
    ("leisure", "stadium", "stadium", 130),
    ("leisure", "park", "park", 110),
    ("leisure", "common", "common", 110),
    ("leisure", "nature_reserve", "nature reserve", 95),
    ("natural", "heath", "heath", 105),
    ("natural", "wood", "woods", 85),
    ("landuse", "forest", "woods", 85),
    ("historic", "castle", "castle", 120),
    ("tourism", "museum", "museum", 110),
    ("tourism", "gallery", "gallery", 100),
    ("tourism", "attraction", "landmark", 95),
    ("amenity", "university", "university", 90),
    ("amenity", "hospital", "hospital", 75),
    ("landuse", "cemetery", "cemetery", 70),
    ("leisure", "golf_course", "golf course", 70),
    ("amenity", "prison", "prison", 90),
    ("aeroway", "aerodrome", "airport", 140),
]

# Roads are a weak clue but better than nothing in the outer suburbs, where a
# station can genuinely have no notable neighbour. Only named A-roads count.
ROAD_CLASSES = {"motorway", "trunk", "primary"}
ROAD_WEIGHT = 45

# Words that are never a useful landmark name on their own.
JUNK = re.compile(r"\b(station|underground|tube|railway|depot|sidings|car park)\b", re.I)

# Hand overrides, for the cases the heuristic gets wrong or finds nothing for.
# Slug → the exact hint text to show, or None to show no landmark hint at all.
OVERRIDES: dict[str, str | None] = {}

COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def tokens(name: str) -> set[str]:
    """Lowercase word set, ignoring the noise words that join place names."""
    stop = {"the", "of", "and", "park", "road", "street", "lane", "hill", "green", "cross"}
    words = {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 2}
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


def centroid(elem: dict) -> tuple[float, float] | None:
    """Mean position of a way's geometry, or a node's own position."""
    if elem.get("type") == "node" and "lat" in elem:
        return elem["lat"], elem["lon"]
    geom = elem.get("geometry") or []
    pts = [(p["lat"], p["lon"]) for p in geom if "lat" in p]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


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
        return f"about {round(distance_m / 100) * 100}\u00a0m {direction}"
    return f"about {distance_m / 1000:.1f}\u00a0km {direction}"


def candidates(elements: list[dict], station: dict) -> list[dict]:
    """Every nameable feature near the station, scored and sorted, best first."""
    found = []
    for elem in elements:
        tags = elem.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name or JUNK.search(name) or leaks_answer(name, station["name"]):
            continue

        kind = weight = None
        for key, value, label, w in CATEGORIES:
            if tags.get(key) == value or (value is None and key in tags):
                kind, weight = label, w
                break
        if kind is None and tags.get("highway") in ROAD_CLASSES:
            kind, weight = "road", ROAD_WEIGHT

        if kind is None:
            continue
        pos = centroid(elem)
        if pos is None:
            continue

        east, north = offset_m(station["lat"], station["lon"], *pos)
        distance = math.hypot(east, north)
        if distance > MAX_DISTANCE_M:
            continue

        found.append({
            "name": name,
            "kind": kind,
            "where": describe(distance, bearing_name(east, north)),
            "distance_m": round(distance),
            # Closer is better, but prominence outweighs a few hundred metres.
            "score": weight - distance / 12,
        })

    # Several OSM elements can describe one place (a park drawn as both a way
    # and a relation). Keep the best-scoring entry per name.
    best: dict[str, dict] = {}
    for c in found:
        if c["name"] not in best or c["score"] > best[c["name"]]["score"]:
            best[c["name"]] = c
    return sorted(best.values(), key=lambda c: -c["score"])


def load_cache(slug: str) -> list[dict] | None:
    """Read the Overpass cache render_maps.py wrote for this station."""
    path = RAW_DIR / f"osm_{slug}_{AREA_M}m.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt") as fh:
        return json.load(fh)["elements"]


def main() -> None:
    """Pick a landmark for every station and write the data files."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true", help="print every choice for review, and write nothing")
    parser.add_argument("--runners-up", type=int, default=0, help="also print N rejected alternatives per station")
    args = parser.parse_args()

    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    landmarks: dict[str, dict] = {}
    uncached, empty = [], []

    for s in stations:
        if s["slug"] in OVERRIDES:
            text = OVERRIDES[s["slug"]]
            if text:
                landmarks[s["slug"]] = {"text": text, "kind": "manual"}
            continue

        elements = load_cache(s["slug"])
        if elements is None:
            uncached.append(s["slug"])
            continue

        picks = candidates(elements, s)
        if not picks:
            empty.append(s["slug"])
            continue

        top = picks[0]
        landmarks[s["slug"]] = {"text": f"{top['name']} — {top['where']}", "kind": top["kind"]}

        if args.show:
            print(f"{s['name']:<38} {top['kind']:<14} {landmarks[s['slug']]['text']}")
            for alt in picks[1:1 + args.runners_up]:
                print(f"{'':<38} {'':<14}   ({alt['kind']}: {alt['name']}, {alt['distance_m']} m)")

    if uncached:
        print(f"\nno {AREA_M} m cache for {len(uncached)} stations — run render_maps.py first: "
              f"{uncached[:5]}{'...' if len(uncached) > 5 else ''}", file=sys.stderr)
    if empty:
        print(f"\n{len(empty)} stations have no usable landmark; the game will skip the rung for them: "
              f"{empty}", file=sys.stderr)

    print(f"\n{len(landmarks)}/{len(stations)} stations have a landmark hint")
    if args.show:
        return

    OUT_FILE.write_text(json.dumps({"landmarks": landmarks}, indent=1, ensure_ascii=False) + "\n")
    PUBLIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_FILE.write_text(json.dumps({"landmarks": landmarks}, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {OUT_FILE.relative_to(ROOT)} and {PUBLIC_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
