#!/usr/bin/env python3
"""Build public/data/line_hints.json — landmark hints for the v3 line game.

Each line gets three landmarks near its stations, shown as the two hints a
player earns with wrong guesses: one after the first miss, two more after the
second. The landmarks come from the same scored candidates as the station
game's Nearby hint (build_landmarks.py, ADR-024), so "famous" means the same
thing in both modes.

Two rules make a landmark a good *line* clue rather than just a famous place:

- **It should point at one line.** Big Ben is next to Westminster, which the
  Jubilee, District and Circle all serve, so it barely narrows anything down.
  Each extra line near a landmark costs it points (``SHARED_PENALTY``).
- **Its name must not contain a line's name.** "Victoria and Albert Museum"
  would send a player towards the Victoria line whichever line it is really on.

The three picks are also spread across different stations, so a hint says
something about the line's reach rather than one busy interchange.

Usage
-----
    python scripts/build_line_hints.py --show   # review
    python scripts/build_line_hints.py          # write the data
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_landmarks import CANDIDATES_FILE, candidates, load_candidates, nearest  # noqa: E402
from render_lines import LINES  # noqa: E402

STATIONS_FILE = ROOT / "data" / "stations.json"
OUT_FILE = ROOT / "public" / "data" / "line_hints.json"

NEAR_M = 700            # a landmark counts as "on" a line within this of one of its stations
SHARED_PENALTY = 25     # per extra line near the same landmark
PICKS = 3

# Words from line names. "city" only counts against the Waterloo & City —
# elsewhere it is too common ("City Hall") to mean a line.
LINE_WORDS = {"bakerloo", "central", "circle", "district", "hammersmith", "jubilee",
              "metropolitan", "northern", "piccadilly", "victoria", "waterloo"}

# Hand review, 2026-09-29: things that are famous but a poor clue for a line.
SKIP: set[str] = set()

# Line id → the three landmark names to use (exact OSM names), best clue first.
#
# The automatic ranking, run first, favoured places near only one line — which
# on the tube means outer-suburban parks, so the Bakerloo got "Paddington
# Recreation Ground". The players v3 is for need the landmarks a visitor has
# heard of, and with only 11 lines, choosing those by hand beats any weighting.
# The script still checks every name exists and sits within ``MAX_OVERRIDE_M``
# of a station on that line, so a hand pick cannot quietly be wrong.
OVERRIDES: dict[str, list[str]] = {
    "bakerloo": ["Imperial War Museum London", "Trafalgar Square", "The Regent's Park"],
    "central": ["St Paul's Cathedral", "Marble Arch", "Westfield"],
    "circle": ["Tower of London", "Madame Tussauds", "Natural History Museum"],
    # No landmark appears for two lines (Zack, 2026-09-29): the Tower of London
    # stays with the Circle, Madame Tussauds with the Circle too.
    "district": ["Stamford Bridge", "Centre Court", "Big Ben"],
    "hammersmith-city": ["Portobello Market", "Whitechapel Gallery", "Shepherd's Bush Market"],
    "jubilee": ["The O2", "Lord's Cricket Ground", "Queen Elizabeth Olympic Park"],
    "metropolitan": ["Wembley Stadium", "Cassiobury Park", "Sherlock Holmes Museum"],
    "northern": ["Camden Market", "Hampstead Heath", "Battersea Power Station"],
    "piccadilly": ["London Heathrow Airport", "Emirates Stadium", "Harrods"],
    "victoria": ["Tate Britain", "Buckingham Palace", "Brixton Market"],
    "waterloo-city": ["Bank of England", "London Eye", "Royal Exchange"],
}
MAX_OVERRIDE_M = 1000   # Southfields to Centre Court is 926 m, and it is *the* station for Wimbledon

# How a landmark reads in a sentence, where the OSM name reads awkwardly.
DISPLAY = {
    "Imperial War Museum London": "the Imperial War Museum",
    "The Regent's Park": "Regent's Park",
    "Westfield": "Westfield shopping centre",
    "Centre Court": "Wimbledon's Centre Court",
    "Queen Elizabeth Olympic Park": "the Olympic Park",
    "London Heathrow Airport": "Heathrow Airport",
    "Natural History Museum": "the Natural History Museum",
    "Tower of London": "the Tower of London",
    "Bank of England": "the Bank of England",
    "London Eye": "the London Eye",
    "Royal Exchange": "the Royal Exchange",
    # Club names are what a visitor recognises, more than the ground's.
    "Stamford Bridge": "Chelsea's Stamford Bridge stadium",
    "Emirates Stadium": "Arsenal's Emirates Stadium",
    "Cassiobury Park": "Cassiobury Park in Watford",
    "Portobello Market": "Portobello Road Market",
    "Sherlock Holmes Museum": "the Sherlock Holmes Museum",
}


def leaks_line(name: str, line_id: str) -> bool:
    """True if the landmark's name contains a line's name."""
    words = set(re.findall(r"[a-z]+", name.lower()))
    if words & LINE_WORDS:
        return True
    return line_id == "waterloo-city" and "city" in words


def load_raw() -> list[dict]:
    """Every candidate, unfiltered. load_candidates() drops names containing
    "station" as junk, which is right for automatic picks and wrong for a hand
    pick like Battersea Power Station."""
    with gzip.open(CANDIDATES_FILE, "rt") as fh:
        return [json.loads(line) for line in fh]


def check_override(name: str, line_id: str, pool: list[dict], stations: list[dict]) -> dict:
    """Find a hand-picked landmark and prove it is near a station on the line."""
    records = [c for c in pool if c["name"] == name]
    if not records:
        sys.exit(f"{line_id}: no landmark called {name!r} in the candidate data")
    if leaks_line(name, line_id):
        sys.exit(f"{line_id}: {name!r} contains a line name")
    best = None
    for s in stations:
        if line_id not in s["lines"]:
            continue
        for c in records:
            d, _, _ = nearest(s, c["points"])
            if best is None or d < best[0]:
                best = (d, s, c)
    d, s, c = best
    if d > MAX_OVERRIDE_M:
        sys.exit(f"{line_id}: {name!r} is {d:.0f} m from the nearest {line_id} station ({s['name']})")
    lines = {l for st in stations for l in st["lines"]
             if any(nearest(st, r["points"])[0] <= NEAR_M for r in records)}
    return {"name": name, "kind": c["kind"], "station": f"{s['name']} ({d:.0f} m)",
            "lines": len(lines), "score": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true", help="print the picks and runners-up; write nothing")
    parser.add_argument("--runners-up", type=int, default=6)
    args = parser.parse_args()

    stations = json.loads(STATIONS_FILE.read_text())["stations"]
    pool = load_candidates()
    raw = load_raw()

    # Every good candidate near every station, remembering which lines it is near.
    near: dict[str, dict] = {}
    for s in stations:
        for c in candidates(pool, s):
            if c["distance_m"] > NEAR_M or c["name"] in SKIP:
                continue
            entry = near.setdefault(c["name"], {"name": c["name"], "kind": c["kind"], "lines": set(), "by_line": {}})
            entry["lines"].update(s["lines"])
            for line_id in s["lines"]:
                best = entry["by_line"].get(line_id)
                if best is None or c["score"] > best["score"]:
                    entry["by_line"][line_id] = {"score": c["score"], "station": s["name"]}

    hints = {}
    for line_id, (line_name, _) in LINES.items():
        ranked = []
        for e in near.values():
            if line_id not in e["lines"] or leaks_line(e["name"], line_id):
                continue
            hit = e["by_line"][line_id]
            score = hit["score"] - SHARED_PENALTY * (len(e["lines"]) - 1)
            ranked.append({"name": e["name"], "kind": e["kind"], "station": hit["station"],
                           "lines": len(e["lines"]), "score": score})
        ranked.sort(key=lambda r: -r["score"])

        if line_id in OVERRIDES:
            chosen = [check_override(n, line_id, raw, stations) for n in OVERRIDES[line_id]]
        else:
            chosen, used = [], set()
            for r in ranked:
                if r["station"] in used:
                    continue
                chosen.append(r)
                used.add(r["station"])
                if len(chosen) == PICKS:
                    break

        names = [c["name"] for c in chosen]
        shown = [DISPLAY.get(n, n) for n in names]
        hints[line_id] = {
            "first": f"Stops near {shown[0]}",
            "second": f"Also stops near {shown[1]} and {shown[2]}",
            "landmarks": names,
        }
        if args.show:
            print(f"\n{line_name}")
            for c in chosen:
                print(f"  * {c['name']:<42} {c['kind']:<16} {c['station']:<28} lines={c['lines']} {c['score']:.0f}")
            for r in [r for r in ranked if r not in chosen][:args.runners_up]:
                print(f"    {r['name']:<42} {r['kind']:<16} {r['station']:<28} lines={r['lines']} {r['score']:.0f}")

    # Each landmark belongs to one line, so a hint never points at two answers.
    seen: dict[str, str] = {}
    for line_id, h in hints.items():
        for name in h["landmarks"]:
            if name in seen:
                sys.exit(f"{name!r} is a hint for both {seen[name]} and {line_id}")
            seen[name] = line_id

    if args.show:
        return
    OUT_FILE.write_text(json.dumps({"hints": hints}, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
