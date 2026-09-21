#!/usr/bin/env python3
"""Render six progressively-blurred map crops for every station in data/stations.json.

Why we draw the maps ourselves
------------------------------
Free tile servers (OpenStreetMap, CARTO, Stadia…) forbid bulk downloading,
server-side caching and derivative images, and their tiles carry station names.
So instead this script fetches raw OpenStreetMap data for a 1 km square around
each station from the Overpass API and draws a simple, label-free map with
Pillow. The data is ODbL — attribution "© OpenStreetMap contributors" is all
that is required. See docs/DECISIONS.md, ADR-008.

Output
------
    public/maps/<slug>/1.webp … 6.webp   1 = most blurred (guess 1), 6 = sharp (guess 6)

WebP rather than PNG: the full set is ~25 MB as WebP (quality 80) against
~95 MB as palette PNG, and every current browser decodes it. ADR-010.

Usage
-----
    python scripts/render_maps.py                       # everything (~272 Overpass queries, cached)
    python scripts/render_maps.py --only bank,amersham  # a few stations
    python scripts/render_maps.py --offline             # re-render from data/raw/ without network
    python scripts/render_maps.py --only bank --contact-sheet   # also write a 6-up review image

Overpass responses are cached in data/raw/osm_<slug>.json (git-ignored), so
tweaking colours or blur radii and re-running never hits the network again.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Configuration — the knobs worth tuning live here, not scattered in the code
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FILE = ROOT / "data" / "stations.json"
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "public" / "maps"

# Public Overpass instances, tried in order. The main one returns 504 when busy.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
WEBP_QUALITY = 80
USER_AGENT = "mind-the-gap-render-maps/0.1 (zzakiahmedd@gmail.com)"
OVERPASS_PAUSE = 1.0  # seconds between queries; polite, and well under the public instance's limits

AREA_M = 1000          # side of the square drawn around the station, in metres
SIZE_PX = 640          # side of the output image, in pixels
SUPERSAMPLE = 2        # draw at 2x then downscale: Pillow has no antialiasing of its own

# Gaussian blur radius (in SIZE_PX pixels) for guesses 1..6. Not linear on
# purpose: the big drop between levels 2 and 3 is what makes guess 3 feel like
# "I nearly have it", while 4-6 are refinement. Tuned by eye on five stations.
BLUR_RADII = [36, 20, 10, 5, 2, 0]

# Pixel size each level is stored at. A heavily blurred image carries no
# detail finer than its blur radius, so storing it at a quarter of the size
# and letting the browser upscale it is visually identical and ~10x smaller.
LEVEL_SIZES = [160, 160, 320, 640, 640, 640]

# Colours. Light map so it reads inside the dark UI; muted so the blur levels
# stay legible rather than turning into mud.
BG = "#ebe7df"
COLOURS = {
    "park": "#cde6bf",
    "grass": "#dbebcf",
    "wood": "#b9d6a6",
    "cemetery": "#cad9bf",
    "pitch": "#c4dfd4",
    "industrial": "#e8e2e0",
    "retail": "#f0e5dc",
    "water": "#a9cbe9",
    "building": "#ddd8d0",
    "building_edge": "#cfc9c0",
    "road_casing": "#c8c2b8",
    "motorway": "#f2b46a",
    "primary": "#f6d48d",
    "secondary": "#fbeeb6",
    "minor": "#ffffff",
    "path": "#e4dfd6",
    "rail": "#7d7d7d",
    "rail_tunnel": "#bdbdbd",
}

# Road class → (colour key, width in metres). Anything not listed is skipped.
ROADS = {
    "motorway": ("motorway", 16), "motorway_link": ("motorway", 10),
    "trunk": ("motorway", 14), "trunk_link": ("motorway", 9),
    "primary": ("primary", 12), "primary_link": ("primary", 8),
    "secondary": ("secondary", 10), "secondary_link": ("secondary", 7),
    "tertiary": ("minor", 8), "tertiary_link": ("minor", 6),
    "residential": ("minor", 6), "unclassified": ("minor", 6), "living_street": ("minor", 5),
    "service": ("minor", 4), "pedestrian": ("minor", 5),
    "footway": ("path", 2), "path": ("path", 2), "cycleway": ("path", 2), "steps": ("path", 2),
}

# Land polygons: (tag key, tag value) → colour key. Drawn first, so order matters little.
LAND = {
    ("leisure", "park"): "park", ("leisure", "garden"): "park", ("leisure", "nature_reserve"): "wood",
    ("leisure", "pitch"): "pitch", ("leisure", "golf_course"): "grass", ("leisure", "playground"): "grass",
    ("leisure", "sports_centre"): "pitch", ("leisure", "recreation_ground"): "grass",
    ("landuse", "grass"): "grass", ("landuse", "meadow"): "grass", ("landuse", "farmland"): "grass",
    ("landuse", "recreation_ground"): "grass", ("landuse", "village_green"): "grass", ("landuse", "allotments"): "grass",
    ("landuse", "forest"): "wood", ("natural", "wood"): "wood", ("natural", "scrub"): "wood",
    ("landuse", "cemetery"): "cemetery",
    ("landuse", "industrial"): "industrial", ("landuse", "railway"): "industrial",
    ("landuse", "retail"): "retail", ("landuse", "commercial"): "retail",
}


# ---------------------------------------------------------------------------
# Geometry helpers (pure, unit-testable)
# ---------------------------------------------------------------------------


def bbox_around(lat: float, lon: float, size_m: float) -> tuple[float, float, float, float]:
    """South, west, north, east bounds of a ``size_m`` square centred on (lat, lon).

    One degree of latitude is ~111.32 km everywhere; a degree of longitude
    shrinks by cos(latitude), which matters even over London's 0.5° span.
    """
    half = size_m / 2
    dlat = half / 111_320
    dlon = half / (111_320 * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


class Projector:
    """Map lat/lon to pixel coordinates for one station's square.

    An equirectangular projection with a cos(lat) correction is accurate to
    well under a pixel over 1 km, so full Web Mercator maths is unnecessary.
    """

    def __init__(self, lat: float, lon: float, size_m: float, size_px: int):
        self.lat, self.lon = lat, lon
        self.px_per_m = size_px / size_m
        self.centre = size_px / 2
        self.m_per_deg_lat = 111_320
        self.m_per_deg_lon = 111_320 * math.cos(math.radians(lat))

    def __call__(self, pt: dict) -> tuple[float, float]:
        """Overpass ``{"lat": …, "lon": …}`` → (x, y) pixels, y growing downwards."""
        dx = (pt["lon"] - self.lon) * self.m_per_deg_lon * self.px_per_m
        dy = (pt["lat"] - self.lat) * self.m_per_deg_lat * self.px_per_m
        return self.centre + dx, self.centre - dy


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """The Overpass QL for everything we draw inside ``bbox``, with geometry inlined."""
    b = ",".join(f"{v:.6f}" for v in bbox)
    return f"""[out:json][timeout:90];
(
  way["highway"]({b});
  way["railway"]({b});
  way["waterway"]({b});
  way["natural"="water"]({b});
  way["landuse"]({b});
  way["leisure"]({b});
  way["building"]({b});
  relation["natural"="water"]({b});
  relation["waterway"="riverbank"]({b});
  relation["leisure"~"park|garden|nature_reserve"]({b});
  relation["landuse"~"forest|grass|cemetery"]({b});
);
out geom;"""


def stitch(chains: list[list[dict]]) -> list[dict]:
    """Join open way segments into one ring by greedily chaining nearest endpoints.

    A multipolygon's outer boundary (the Thames, say) arrives as dozens of
    separate ways, and Overpass clips those to the query bbox, so the pieces
    inside our square are typically two long open chains — one per bank.
    Chaining each chain's end to the nearest remaining start (reversing a
    chain when that is closer) walks north bank → south bank → back, and the
    final implicit close runs along the bbox edge, which is exactly the
    polygon we want to fill.
    """
    chains = [c for c in chains if len(c) >= 2]
    if not chains:
        return []
    ring = list(chains.pop(0))

    def key(pt: dict) -> tuple[float, float]:
        return pt["lat"], pt["lon"]

    def dist(a: dict, b: dict) -> float:
        return (a["lat"] - b["lat"]) ** 2 + (a["lon"] - b["lon"]) ** 2

    while chains:
        end = ring[-1]
        best = min(range(len(chains)), key=lambda i: min(dist(end, chains[i][0]), dist(end, chains[i][-1])))
        nxt = chains.pop(best)
        if dist(end, nxt[-1]) < dist(end, nxt[0]):
            nxt = nxt[::-1]
        ring.extend(nxt[1:] if key(nxt[0]) == key(end) else nxt)
    return ring


def rings(element: dict) -> list[list[dict]]:
    """Coordinate rings to fill for a way or a multipolygon relation.

    Only outer members are used; inner rings (islands, courtyards) are rare at
    this scale and invisible under blur. Points Overpass returns without
    coordinates (outside the bbox) are dropped.
    """
    if element["type"] == "way":
        return [[p for p in element.get("geometry", []) if "lat" in p]]
    chains = [[p for p in m.get("geometry", []) if "lat" in p]
              for m in element.get("members", []) if m.get("role") == "outer"]
    closed = [c for c in chains if len(c) >= 3 and (c[0]["lat"], c[0]["lon"]) == (c[-1]["lat"], c[-1]["lon"])]
    open_chains = [c for c in chains if c not in closed]
    return closed + ([stitch(open_chains)] if open_chains else [])


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_osm(slug: str, lat: float, lon: float, offline: bool) -> list[dict] | None:
    """Overpass elements for the station's square, cached in data/raw/osm_<slug>.json.

    Returns None if every attempt failed, so the caller can skip the station
    and keep going; a re-run picks up the gaps from the cache.
    """
    cache = RAW_DIR / f"osm_{slug}.json"
    if cache.exists():
        return json.loads(cache.read_text())["elements"]
    if offline:
        print(f"  no cached OSM data for {slug} (offline)", file=sys.stderr)
        return None

    query = overpass_query(bbox_around(lat, lon, AREA_M * 1.15))  # 15% margin so edge features aren't clipped
    for attempt in range(9):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]  # rotate mirrors on each retry
        host = url.split("/")[2]
        try:
            resp = requests.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=120)
        except requests.RequestException as exc:
            # Connection errors on every mirror usually mean *our* network dropped; wait longer.
            wait = 10 * (attempt + 1)
            print(f"  {host}: {exc.__class__.__name__}, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (429, 502, 503, 504):
            wait = 5 * (attempt + 1)
            print(f"  {host} busy ({resp.status_code}), waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        time.sleep(OVERPASS_PAUSE)
        return data["elements"]
    print(f"  giving up on {slug} for now; re-run to retry", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------


def draw_map(elements: list[dict], lat: float, lon: float) -> Image.Image:
    """Draw the sharp map for one station and return it at SIZE_PX × SIZE_PX."""
    px = SIZE_PX * SUPERSAMPLE
    project = Projector(lat, lon, AREA_M, px)
    scale = px / AREA_M  # pixels per metre, for line widths
    img = Image.new("RGB", (px, px), BG)
    d = ImageDraw.Draw(img)

    def poly(elem: dict, colour: str, outline: str | None = None) -> None:
        for ring in rings(elem):
            if len(ring) >= 3:
                d.polygon([project(p) for p in ring], fill=colour, outline=outline)

    def line(elem: dict, colour: str, width_m: float) -> None:
        pts = [project(p) for p in elem.get("geometry", [])]
        if len(pts) >= 2:
            d.line(pts, fill=colour, width=max(1, round(width_m * scale)), joint="curve")

    tagged = [e for e in elements if e.get("tags")]

    # 1. Land use, then water on top of it.
    for e in tagged:
        for (k, v), colour in LAND.items():
            if e["tags"].get(k) == v:
                poly(e, COLOURS[colour])
                break
    for e in tagged:
        t = e["tags"]
        if t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("landuse") == "reservoir":
            poly(e, COLOURS["water"])
    for e in tagged:
        w = e["tags"].get("waterway")
        if e["type"] == "way" and w in ("river", "canal", "stream"):
            line(e, COLOURS["water"], {"river": 12, "canal": 8, "stream": 3}[w])

    # 2. Buildings.
    for e in tagged:
        if e["type"] == "way" and "building" in e["tags"]:
            poly(e, COLOURS["building"], COLOURS["building_edge"])

    # 3. Roads: casing pass, then fill pass, minor roads before major so major sit on top.
    roads = [(e, ROADS[e["tags"]["highway"]]) for e in tagged
             if e["type"] == "way" and e["tags"].get("highway") in ROADS and e["tags"].get("tunnel") != "yes"]
    order = {"path": 0, "minor": 1, "secondary": 2, "primary": 3, "motorway": 4}
    roads.sort(key=lambda r: order[r[1][0]])
    for e, (colour, width) in roads:
        if colour != "path":
            line(e, COLOURS["road_casing"], width + 2)
    for e, (colour, width) in roads:
        line(e, COLOURS[colour], width)

    # 4. Railways. Tunnels are drawn faintly: the Tube is mostly underground and
    #    a bold line would give the station away, but a hint of it is fair.
    for e in tagged:
        t = e["tags"]
        if e["type"] == "way" and t.get("railway") in ("rail", "light_rail", "subway", "tram", "narrow_gauge"):
            if t.get("tunnel") == "yes":
                line(e, COLOURS["rail_tunnel"], 3)
            else:
                line(e, COLOURS["rail"], 4)

    return img.resize((SIZE_PX, SIZE_PX), Image.LANCZOS)


def blur_levels(sharp: Image.Image) -> list[Image.Image]:
    """Six images, guess 1 (most blurred) to guess 6 (sharp).

    Each is blurred at full size, then downscaled to its LEVEL_SIZES entry.
    """
    out = []
    for radius, size in zip(BLUR_RADII, LEVEL_SIZES):
        img = sharp.filter(ImageFilter.GaussianBlur(radius)) if radius else sharp
        if size != SIZE_PX:
            img = img.resize((size, size), Image.LANCZOS)
        out.append(img)
    return out


def contact_sheet(sets: dict[str, list[Image.Image]], path: Path) -> None:
    """One row per station, six columns (guess 1 → 6), for reviewing the blur curve."""
    thumb = 220
    sheet = Image.new("RGB", (6 * thumb, len(sets) * thumb), "white")
    for row, levels in enumerate(sets.values()):
        for col, img in enumerate(levels):
            sheet.paste(img.resize((thumb, thumb), Image.LANCZOS), (col * thumb, row * thumb))
    sheet.save(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse flags, then fetch → draw → blur → save for each selected station."""
    # Progress lines must reach a log file as they happen, not in 8 KB chunks,
    # otherwise `tail -f render.log` shows only the (unbuffered) error lines.
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated slugs to render (default: all)")
    parser.add_argument("--offline", action="store_true", help="use cached Overpass data only")
    parser.add_argument("--contact-sheet", action="store_true", help="also write data/raw/contact_sheet.png")
    args = parser.parse_args()

    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    if args.only:
        wanted = set(args.only.split(","))
        stations = [s for s in stations if s["slug"] in wanted]
        missing = wanted - {s["slug"] for s in stations}
        if missing:
            sys.exit(f"unknown slugs: {sorted(missing)}")

    sets: dict[str, list[Image.Image]] = {}
    total_bytes = 0
    failed: list[str] = []
    for i, s in enumerate(stations, 1):
        print(f"[{i}/{len(stations)}] {s['name']}")
        elements = fetch_osm(s["slug"], s["lat"], s["lon"], args.offline)
        if elements is None:
            failed.append(s["slug"])
            continue
        levels = blur_levels(draw_map(elements, s["lat"], s["lon"]))
        folder = OUT_DIR / s["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        for n, img in enumerate(levels, 1):
            path = folder / f"{n}.webp"
            img.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
            total_bytes += path.stat().st_size
        if args.contact_sheet:
            sets[s["slug"]] = levels

    done = len(stations) - len(failed)
    print(f"\nwrote {done * 6} images for {done} stations, {total_bytes / 1_048_576:.1f} MB total "
          f"({total_bytes / max(done, 1) / 1024:.0f} KB per station)")
    if failed:
        print(f"FAILED ({len(failed)}), run again to retry: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)
    if args.contact_sheet:
        path = RAW_DIR / "contact_sheet.png"
        contact_sheet(sets, path)
        print(f"contact sheet: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
