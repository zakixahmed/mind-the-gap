#!/usr/bin/env python3
"""Build data/stations.json — the station list Mind the Gap is played against.

Sources
-------
* TfL Unified API (https://api.tfl.gov.uk) for the list of London Underground
  lines, the stations on each line (name, coordinates, fare zone) and the
  ordered route sequences (used to work out which stations are adjacent).
* OpenStreetMap Nominatim (https://nominatim.openstreetmap.org) for the
  borough, via one reverse-geocode per station. TfL does not publish boroughs.

Usage
-----
    python scripts/build_stations.py              # full build (~5 minutes, mostly Nominatim's 1 req/s limit)
    python scripts/build_stations.py --no-borough # skip Nominatim; borough is null (quick iteration)
    python scripts/build_stations.py --offline    # rebuild from data/raw/ cache only, no network at all

Every HTTP response is cached under data/raw/ (git-ignored), so re-runs are
instant and the raw evidence for any record can be inspected.

Optional environment variable TFL_APP_KEY raises TfL's anonymous rate limit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_FILE = ROOT / "data" / "stations.json"

TFL_BASE = "https://api.tfl.gov.uk"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
# Nominatim's usage policy requires an identifying User-Agent with a contact.
USER_AGENT = "mind-the-gap-build-stations/0.1 (zzakiahmedd@gmail.com)"
NOMINATIM_MIN_INTERVAL = 1.1  # seconds; policy is "absolute maximum 1 request per second"

# Sanity bounds for the number of Underground stations. TfL lists 272 as of
# 2026; anything far outside this means the API changed or a fetch failed.
EXPECTED_COUNT_RANGE = (265, 280)

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


# ---------------------------------------------------------------------------
# HTTP with on-disk cache
# ---------------------------------------------------------------------------


def fetch_json(url: str, cache_name: str, params: dict | None = None, offline: bool = False) -> dict | list:
    """Return the JSON at ``url``, reading from / writing to ``data/raw/<cache_name>.json``.

    Retries on HTTP 429 (rate limited) with a growing back-off. In offline mode
    a cache miss is a hard error so a partial cache can never produce a
    silently incomplete dataset.
    """
    cache_path = RAW_DIR / f"{cache_name}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    if offline:
        sys.exit(f"offline mode but no cache for {cache_name} ({url})")

    params = dict(params or {})
    if url.startswith(TFL_BASE) and os.environ.get("TFL_APP_KEY"):
        params["app_key"] = os.environ["TFL_APP_KEY"]

    for attempt in range(5):
        resp = SESSION.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=1))
        return data
    sys.exit(f"gave up after repeated 429s: {url}")


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable, no I/O)
# ---------------------------------------------------------------------------

_NAME_SUFFIXES = (" Underground Station", "-Underground", " Station")

# TfL's disambiguators for same-named stations use internal abbreviations.
# Spell them out so the autocomplete list reads naturally to a player.
_NAME_OVERRIDES = {
    "Hammersmith (Dist&Picc Line)": "Hammersmith (District & Piccadilly)",
    "Hammersmith (H&C Line)": "Hammersmith (Hammersmith & City)",
    "Paddington (H&C Line)": "Paddington (Hammersmith & City)",
    "Edgware Road (Circle Line)": "Edgware Road (Circle)",
}


def clean_name(common_name: str) -> str:
    """Turn TfL's ``"Bank Underground Station"`` into ``"Bank"``.

    Disambiguators such as ``"Edgware Road (Bakerloo)"`` are kept, because
    TfL treats those as distinct stations and so does this game; a few are
    rewritten via ``_NAME_OVERRIDES`` to expand TfL's abbreviations.
    """
    name = common_name.strip()
    for suffix in _NAME_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = name.strip()
    return _NAME_OVERRIDES.get(name, name)


def slugify(name: str) -> str:
    """Filesystem- and URL-safe identifier: ``"King's Cross St. Pancras"`` → ``"kings-cross-st-pancras"``."""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"['’.]", "", s)  # King's → kings, St. → st
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def parse_zones(value: str | None) -> list[int]:
    """``"2+3"`` → ``[2, 3]``; ``"6"`` → ``[6]``; missing or unparseable → ``[]``.

    TfL writes boundary stations with a plus sign (``"2+3"``); the slash form
    is accepted too in case the API ever changes its mind.
    """
    if not value:
        return []
    zones = []
    for part in re.split(r"[+/]", value):
        part = part.strip()
        if part.isdigit():
            zones.append(int(part))
    return zones


_BOROUGH_PREFIXES = ("London Borough of ", "Royal Borough of ")


def normalise_borough(address: dict) -> str | None:
    """Pick the borough (or county, outside Greater London) from a Nominatim address.

    Inside London Nominatim reports ``city_district`` such as
    ``"London Borough of Lambeth"``; the prefix is dropped. Westminster and
    the City of London are cities rather than boroughs, so Nominatim puts
    them under ``city`` instead — they are kept as ``"City of Westminster"``
    and ``"City of London"`` because that is their name. Outside London the
    ``county`` (e.g. ``"Buckinghamshire"``) is the most useful hint a player
    could get.
    """
    city = address.get("city", "")
    if city.startswith("City of "):
        return city
    for key in ("city_district", "borough", "county", "state_district"):
        value = address.get(key)
        if value:
            for prefix in _BOROUGH_PREFIXES:
                if value.startswith(prefix):
                    value = value[len(prefix):]
            return value
    return None


def adjacent_pairs(ordered_routes: list[list[str]]) -> set[tuple[str, str]]:
    """Every consecutive pair of stop ids along each route, as unordered pairs."""
    pairs: set[tuple[str, str]] = set()
    for route in ordered_routes:
        for a, b in zip(route, route[1:]):
            pairs.add((min(a, b), max(a, b)))
    return pairs


# ---------------------------------------------------------------------------
# TfL fetches
# ---------------------------------------------------------------------------


def get_tube_lines(offline: bool) -> dict[str, str]:
    """Map of line id → display name for every London Underground line."""
    data = fetch_json(f"{TFL_BASE}/Line/Mode/tube", "tube_lines", offline=offline)
    return {line["id"]: line["name"] for line in data}


def get_line_stops(line_id: str, offline: bool) -> list[dict]:
    """Raw StopPoint records for one line (tube-mode stations only)."""
    data = fetch_json(f"{TFL_BASE}/Line/{line_id}/StopPoints", f"stops_{line_id}", offline=offline)
    return [s for s in data if "tube" in s.get("modes", [])]


def get_line_routes(line_id: str, offline: bool) -> list[list[str]]:
    """Ordered naptan-id lists for every route variant of a line, both directions."""
    routes = []
    for direction in ("inbound", "outbound"):
        data = fetch_json(
            f"{TFL_BASE}/Line/{line_id}/Route/Sequence/{direction}",
            f"route_{line_id}_{direction}",
            offline=offline,
        )
        routes.extend(r["naptanIds"] for r in data.get("orderedLineRoutes", []))
    return routes


# ---------------------------------------------------------------------------
# Nominatim
# ---------------------------------------------------------------------------


def lookup_borough(naptan_id: str, lat: float, lon: float, offline: bool) -> str | None:
    """Reverse-geocode one station, respecting Nominatim's one-request-per-second policy."""
    cache_path = RAW_DIR / f"borough_{naptan_id}.json"
    cached = cache_path.exists()
    data = fetch_json(
        NOMINATIM_URL,
        f"borough_{naptan_id}",
        params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10},
        offline=offline,
    )
    if not cached:
        time.sleep(NOMINATIM_MIN_INTERVAL)
    return normalise_borough(data.get("address", {}))


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------


def build(offline: bool, with_borough: bool) -> dict:
    """Assemble the full dataset and return it as a JSON-ready dict."""
    lines = get_tube_lines(offline)
    print(f"{len(lines)} Underground lines: {', '.join(sorted(lines))}")

    stations: dict[str, dict] = {}  # keyed by naptan id
    pairs: set[tuple[str, str]] = set()

    for line_id in sorted(lines):
        stops = get_line_stops(line_id, offline)
        print(f"  {lines[line_id]:<22} {len(stops):>3} stations")
        for stop in stops:
            record = stations.setdefault(
                stop["naptanId"],
                {
                    "name": clean_name(stop["commonName"]),
                    "slug": None,
                    "naptan": stop["naptanId"],
                    "lat": stop["lat"],
                    "lon": stop["lon"],
                    "zones": parse_zones(
                        next((p["value"] for p in stop.get("additionalProperties", []) if p["key"] == "Zone"), None)
                    ),
                    "lines": [],
                    "borough": None,
                    "adjacent": [],
                },
            )
            if line_id not in record["lines"]:
                record["lines"].append(line_id)
        pairs |= adjacent_pairs(get_line_routes(line_id, offline))

    # Slugs must be unique because they name the map folders.
    for record in stations.values():
        record["slug"] = slugify(record["name"])
        record["lines"].sort()
    slugs = [r["slug"] for r in stations.values()]
    duplicates = {s for s in slugs if slugs.count(s) > 1}
    if duplicates:
        sys.exit(f"duplicate slugs, disambiguate in clean_name(): {sorted(duplicates)}")

    # Adjacency, expressed as slugs so the front end never sees naptan ids.
    for a, b in pairs:
        if a in stations and b in stations:
            stations[a]["adjacent"].append(stations[b]["slug"])
            stations[b]["adjacent"].append(stations[a]["slug"])
    for record in stations.values():
        record["adjacent"] = sorted(set(record["adjacent"]))

    if with_borough:
        print(f"looking up boroughs for {len(stations)} stations via Nominatim (about 1 per second)")
        for i, record in enumerate(stations.values(), 1):
            record["borough"] = lookup_borough(record["naptan"], record["lat"], record["lon"], offline)
            if i % 25 == 0:
                print(f"  {i}/{len(stations)}")

    ordered = sorted(stations.values(), key=lambda r: r["name"])
    return {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(ordered),
            "lines": lines,
            "sources": {
                "stations": "TfL Unified API — Powered by TfL Open Data. Contains OS data © Crown copyright and database rights 2016 and Geomni UK Map data © and database rights 2019",
                "boroughs": "© OpenStreetMap contributors, ODbL 1.0 (via Nominatim reverse geocoding)",
            },
        },
        "stations": ordered,
    }


def validate(dataset: dict) -> None:
    """Fail loudly on anything that would break the game rather than shipping bad data."""
    stations = dataset["stations"]
    lo, hi = EXPECTED_COUNT_RANGE
    problems = []
    if not lo <= len(stations) <= hi:
        problems.append(f"station count {len(stations)} outside expected range {lo}-{hi}")
    for s in stations:
        if not s["zones"]:
            problems.append(f"{s['name']}: no zone")
        if not s["borough"]:
            problems.append(f"{s['name']}: no borough")
        if not s["lines"]:
            problems.append(f"{s['name']}: no lines")
        if not s["adjacent"]:
            problems.append(f"{s['name']}: no adjacent stations")
        if not (51.2 < s["lat"] < 51.8 and -0.8 < s["lon"] < 0.4):
            problems.append(f"{s['name']}: coordinates look wrong ({s['lat']}, {s['lon']})")
    if problems:
        print("VALIDATION PROBLEMS:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Parse flags, build, validate, write, and print a spot-check sample."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="use data/raw/ cache only; never touch the network")
    parser.add_argument("--no-borough", action="store_true", help="skip Nominatim lookups (borough will be null)")
    args = parser.parse_args()

    dataset = build(offline=args.offline, with_borough=not args.no_borough)
    if not args.no_borough:
        validate(dataset)
    OUT_FILE.write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"\nwrote {OUT_FILE.relative_to(ROOT)} with {dataset['meta']['count']} stations")

    # Five fixed spot-checks spanning zones, line counts and the edge of the network.
    print("\nSpot-check against https://tfl.gov.uk/tube/stop/<naptan>/<slug>:")
    by_slug = {s["slug"]: s for s in dataset["stations"]}
    for slug in ("bank", "amersham", "turnham-green", "heathrow-terminal-4", "hainault"):
        s = by_slug.get(slug)
        if s:
            print(f"  {s['name']:<22} zones={s['zones']} lines={s['lines']} borough={s['borough']} "
                  f"adjacent={s['adjacent']}  https://tfl.gov.uk/tube/stop/{s['naptan']}/{s['slug']}")


if __name__ == "__main__":
    main()
