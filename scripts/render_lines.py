#!/usr/bin/env python3
"""Render one whole-route map per tube line — the pictures for v3's line game.

v3 asks "which line is this?" rather than "which station?". Each puzzle shows
one line's full route, drawn in its real TfL colour over a plain map of London,
with the other ten lines faint underneath for context. Three blur levels, one
per guess (ADR-025).

Inputs are all local, so this needs no network:

- ``data/raw/route_<line>_<direction>.json`` — TfL route sequences saved by
  build_stations.py. Their ``lineStrings`` are the route geometry.
- ``data/stations.json`` — station positions, drawn as dots on the route.
- ``data/raw/_features.jsonl.gz`` — the OSM extract from fetch_osm_local.py,
  thinned here to a base map (water, big green spaces, main roads) and cached
  as ``data/raw/_basemap.json.gz``.

Usage
-----
    python scripts/render_lines.py               # all 11 lines
    python scripts/render_lines.py --only victoria,circle
    python scripts/render_lines.py --sheet       # also write data/raw/lines_sheet.png
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
STATIONS_FILE = ROOT / "data" / "stations.json"
FEATURES_FILE = RAW_DIR / "_features.jsonl.gz"
BASEMAP_FILE = RAW_DIR / "_basemap.json.gz"
OUT_DIR = ROOT / "public" / "lines"
DATA_OUT = ROOT / "public" / "data" / "lines.json"

SIZE_PX = 1024
SUPERSAMPLE = 2
MIN_SPAN_M = 6000        # the Waterloo & City is 2.4 km end to end; don't zoom in to street level
MARGIN = 1.14            # breathing room around the route
# One level per guess; the last is sharp. The map and the route blur separately:
# the map hides where in London you are, the route stays readable throughout —
# its colour is meant to be seen (ADR-025), its exact path sharpens with guesses.
BLUR_RADII = [16, 7, 0]
ROUTE_BLUR_RADII = [4, 2, 0]
WEBP_QUALITY = 82

# Official TfL colours, kept identical to LINE_COLOURS in public/index.html.
LINES = {
    "bakerloo": ("Bakerloo", "#B36305"),
    "central": ("Central", "#E32017"),
    "circle": ("Circle", "#FFD300"),
    "district": ("District", "#00782A"),
    "hammersmith-city": ("Hammersmith & City", "#F3A9BB"),
    "jubilee": ("Jubilee", "#A0A5A9"),
    "metropolitan": ("Metropolitan", "#9B0056"),
    "northern": ("Northern", "#000000"),
    "piccadilly": ("Piccadilly", "#003688"),
    "victoria": ("Victoria", "#0098D4"),
    "waterloo-city": ("Waterloo & City", "#95CDBA"),
}

# Base-map palette, the same family as render_maps.py so the two games match.
BG = "#e6e1d8"
C = {"green": "#cde6bf", "wood": "#b9d6a6", "field": "#e0ead2", "water": "#a9cbe9",
     "motorway": "#f2b46a", "primary": "#f6d48d"}

GREEN = {("leisure", "park"): "green", ("leisure", "common"): "green", ("leisure", "nature_reserve"): "wood",
         ("natural", "heath"): "green", ("natural", "wood"): "wood", ("landuse", "forest"): "wood",
         ("leisure", "golf_course"): "field", ("landuse", "farmland"): "field", ("landuse", "meadow"): "field",
         ("landuse", "grass"): "field"}
MIN_GREEN_M2 = 60_000    # at this scale anything smaller than 6 ha is a speck


# --------------------------------------------------------------- geometry ---

def ring_area_m2(pts: list[tuple[float, float]]) -> float:
    """Planar area of a (lat, lon) ring in square metres."""
    if len(pts) < 3:
        return 0.0
    lat0 = pts[0][0]
    kx = 111_320 * math.cos(math.radians(lat0))
    xy = [((lon - pts[0][1]) * kx, (lat - lat0) * 110_540) for lat, lon in pts]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2


def thin(pts, step_m: float = 25.0):
    """Drop points closer than ``step_m`` to the last kept one — plenty at 30 km scale."""
    out = [pts[0]]
    for lat, lon in pts[1:]:
        if abs(lat - out[-1][0]) * 110_540 + abs(lon - out[-1][1]) * 69_000 >= step_m:
            out.append((lat, lon))
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return [[round(a, 5), round(b, 5)] for a, b in out]


def assemble_rings(chains: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Join a multipolygon's member ways into closed rings by shared endpoints.

    The Thames arrives as dozens of open ways. render_maps.stitch() greedily
    chains them into one ring, which is right for a small clipped crop; across
    all of London a relation can hold several rings, and one greedy ring would
    draw chords between them. Here ways join only where their ends actually
    meet, and anything that never closes is dropped rather than guessed at.
    """
    closed = [c for c in chains if len(c) >= 4 and c[0] == c[-1]]
    open_ = [list(c) for c in chains if len(c) >= 2 and c[0] != c[-1]]
    while open_:
        ring = open_.pop()
        grown = True
        while grown and ring[0] != ring[-1]:
            grown = False
            for i, c in enumerate(open_):
                if c[0] == ring[-1]:
                    ring += c[1:]
                elif c[-1] == ring[-1]:
                    ring += c[-2::-1]
                elif c[-1] == ring[0]:
                    ring = c[:-1] + ring
                elif c[0] == ring[0]:
                    ring = c[:0:-1] + ring
                else:
                    continue
                open_.pop(i)
                grown = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            closed.append(ring)
    return closed


# --------------------------------------------------------------- base map ---

def build_basemap() -> dict:
    """Thin the OSM extract to what reads at whole-line scale, and cache it."""
    if not FEATURES_FILE.exists():
        sys.exit(f"{FEATURES_FILE.relative_to(ROOT)} not found — run fetch_osm_local.py first")
    started = time.time()
    base = {"polys": [], "rivers": [], "roads": []}
    with gzip.open(FEATURES_FILE, "rt") as fh:
        for line in fh:
            f = json.loads(line)
            tags = f.get("tags") or {}
            hw = tags.get("highway")
            if f["type"] == "way":
                pts = [(p["lat"], p["lon"]) for p in f["geometry"]]
                if hw in ("motorway", "trunk", "primary"):
                    base["roads"].append({"k": "motorway" if hw != "primary" else "primary", "p": thin(pts, 60)})
                    continue
                if tags.get("waterway") == "river" and tags.get("tunnel") not in ("culvert", "yes"):
                    base["rivers"].append(thin(pts))
                    continue
                rings = [pts] if pts[0] == pts[-1] else []
            else:
                rings = assemble_rings([[(p["lat"], p["lon"]) for p in m["geometry"]]
                                        for m in f["members"] if m.get("role", "outer") == "outer"])
            colour = None
            if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
                colour = "water"
            else:
                for (k, v), c in GREEN.items():
                    if tags.get(k) == v:
                        colour = c
                        break
            if colour is None or not rings:
                continue
            area = sum(ring_area_m2(r) for r in rings)
            if area < (20_000 if colour == "water" else MIN_GREEN_M2):
                continue
            for r in rings:
                t = thin(r) if len(r) >= 3 else []
                if len(t) >= 3:   # thinning can collapse a sliver to a line
                    base["polys"].append({"c": colour, "p": t})
    with gzip.open(BASEMAP_FILE, "wt") as fh:
        json.dump(base, fh)
    print(f"base map: {len(base['polys']):,} areas, {len(base['rivers']):,} river ways, "
          f"{len(base['roads']):,} roads in {time.time() - started:.0f}s")
    return base


def load_basemap() -> dict:
    if BASEMAP_FILE.exists():
        with gzip.open(BASEMAP_FILE, "rt") as fh:
            return json.load(fh)
    return build_basemap()


# ------------------------------------------------------------------ lines ---

def line_paths(line_id: str) -> list[list[tuple[float, float]]]:
    """Every polyline of a line's route, both directions, as (lat, lon) lists."""
    paths, seen = [], set()
    for direction in ("inbound", "outbound"):
        path = RAW_DIR / f"route_{line_id}_{direction}.json"
        if not path.exists():
            continue
        for s in json.loads(path.read_text())["lineStrings"]:
            for poly in json.loads(s):
                key = tuple(map(tuple, poly))
                if key in seen or tuple(reversed(key)) in seen:
                    continue
                seen.add(key)
                paths.append([(lat, lon) for lon, lat in poly])
    if not paths:
        sys.exit(f"no route data for {line_id} in {RAW_DIR.relative_to(ROOT)}")
    return paths


def frame_for(paths) -> tuple[float, float, float]:
    """(centre lat, centre lon, span in metres) of a square that fits the route."""
    lats = [p[0] for path in paths for p in path]
    lons = [p[1] for path in paths for p in path]
    clat, clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
    h = (max(lats) - min(lats)) * 110_540
    w = (max(lons) - min(lons)) * 111_320 * math.cos(math.radians(clat))
    return clat, clon, max(MIN_SPAN_M, max(w, h) * MARGIN)


def render_line(line_id: str, base: dict, all_paths: dict, stations: list[dict]) -> dict:
    """Draw one line's map at every blur level; return its metadata."""
    name, colour = LINES[line_id]
    clat, clon, span = frame_for(all_paths[line_id])
    px = SIZE_PX * SUPERSAMPLE
    k = px / span
    kx = 111_320 * math.cos(math.radians(clat))

    def xy(lat, lon):
        return ((lon - clon) * kx * k + px / 2, px / 2 - (lat - clat) * 110_540 * k)

    half = span / 2 * 1.05
    def visible(pts):
        return any(abs((lat - clat) * 110_540) < half and abs((lon - clon) * kx) < half for lat, lon in pts)

    img = Image.new("RGB", (px, px), BG)
    d = ImageDraw.Draw(img, "RGBA")
    s = SUPERSAMPLE * SIZE_PX / 1024   # widths below are in 1024-px units

    for poly in base["polys"]:
        if len(poly["p"]) >= 3 and poly["c"] != "water" and visible(poly["p"]):
            d.polygon([xy(*p) for p in poly["p"]], fill=C[poly["c"]])
    for poly in base["polys"]:
        if len(poly["p"]) >= 3 and poly["c"] == "water" and visible(poly["p"]):
            d.polygon([xy(*p) for p in poly["p"]], fill=C["water"])
    for river in base["rivers"]:
        if visible(river):
            d.line([xy(*p) for p in river], fill=C["water"], width=round(3 * s), joint="curve")
    # Primary roads are structure on a 12 km map and noise on a 40 km one.
    road_kinds = {"motorway", "primary"} if span < 20_000 else {"motorway"}
    for road in base["roads"]:
        if road["k"] in road_kinds and visible(road["p"]):
            d.line([xy(*p) for p in road["p"]], fill=C[road["k"]], width=round((2.2 if road["k"] == "motorway" else 1.5) * s))

    # The other ten lines, faint: enough to read the network, not enough to compete.
    for other, paths in all_paths.items():
        if other == line_id:
            continue
        r, g, b = (int(LINES[other][1][i:i + 2], 16) for i in (1, 3, 5))
        for path in paths:
            d.line([xy(*p) for p in path], fill=(r, g, b, 80), width=round(2.5 * s), joint="curve")

    # The mystery line, on its own layer: a dark hairline and a white casing
    # make pale colours (Circle yellow, Hammersmith & City pink) readable.
    route = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    rd = ImageDraw.Draw(route)
    for path in all_paths[line_id]:
        pts = [xy(*p) for p in path]
        rd.line(pts, fill="#3a3a3a", width=round(19 * s), joint="curve")
        rd.line(pts, fill="#ffffff", width=round(16 * s), joint="curve")
    for path in all_paths[line_id]:
        rd.line([xy(*p) for p in path], fill=colour, width=round(11 * s), joint="curve")
    rad = 6 * s
    for st in stations:
        if line_id in st["lines"]:
            x, y = xy(st["lat"], st["lon"])
            rd.ellipse([x - rad, y - rad, x + rad, y + rad], fill="#ffffff", outline="#3a3a3a", width=round(2 * s))

    base_img = img.resize((SIZE_PX, SIZE_PX), Image.LANCZOS)
    route = route.resize((SIZE_PX, SIZE_PX), Image.LANCZOS)
    out = OUT_DIR / line_id
    out.mkdir(parents=True, exist_ok=True)
    for level, (radius, rradius) in enumerate(zip(BLUR_RADII, ROUTE_BLUR_RADII), start=1):
        frame = base_img.filter(ImageFilter.GaussianBlur(radius)) if radius else base_img.copy()
        layer = route.filter(ImageFilter.GaussianBlur(rradius)) if rradius else route
        frame.paste(layer, (0, 0), layer)
        frame.save(out / f"{level}.webp", "WEBP", quality=WEBP_QUALITY, method=6)

    count = sum(1 for st in stations if line_id in st["lines"])
    return {"name": name, "colour": colour, "span_m": round(span), "stations": count}


def contact_sheet(ids: list[str]) -> None:
    """Every line at every level on one image, for review."""
    cell = 300
    sheet = Image.new("RGB", (cell * len(BLUR_RADII), cell * len(ids)), "white")
    for r, line_id in enumerate(ids):
        for c in range(len(BLUR_RADII)):
            im = Image.open(OUT_DIR / line_id / f"{c + 1}.webp").convert("RGB").resize((cell, cell))
            sheet.paste(im, (c * cell, r * cell))
    sheet.save(RAW_DIR / "lines_sheet.png")
    print(f"wrote {(RAW_DIR / 'lines_sheet.png').relative_to(ROOT)}")


def main() -> None:
    """Render the requested lines and write public/data/lines.json."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated line ids (default: all)")
    parser.add_argument("--sheet", action="store_true", help="also write a contact sheet for review")
    parser.add_argument("--rebuild-base", action="store_true", help="rebuild the cached base map")
    args = parser.parse_args()

    base = build_basemap() if args.rebuild_base else load_basemap()
    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    all_paths = {line_id: line_paths(line_id) for line_id in LINES}
    ids = args.only.split(",") if args.only else list(LINES)

    meta = json.loads(DATA_OUT.read_text())["lines"] if DATA_OUT.exists() else {}
    for line_id in ids:
        started = time.time()
        meta[line_id] = render_line(line_id, base, all_paths, stations)
        print(f"{LINES[line_id][0]:<20} {meta[line_id]['span_m'] / 1000:5.1f} km across, "
              f"{meta[line_id]['stations']} stations, {time.time() - started:.1f}s")

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps({"lines": meta}, separators=(",", ":"), ensure_ascii=False))
    if args.sheet:
        contact_sheet(ids)


if __name__ == "__main__":
    main()
