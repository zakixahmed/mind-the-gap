#!/usr/bin/env python3
"""Build data/schedule.json — the curated order the daily puzzle follows.

Puzzle N shows ``schedule[N % len(schedule)]``. The brief asks for 100 days
mixing famous and obscure stations, with no three obscure ones in a row.

"Famous" is a judgement call, so it is made here, in the open, as an editable
list rather than hidden inside a data file: a station a visitor to London might
plausibly have heard of — zone 1, a major interchange, an airport, a line
terminus, or a name that carries beyond the network (Abbey Road, Baker Street,
Wimbledon). Everything else counts as obscure, which is no insult: Chalfont &
Latimer is a fine puzzle, it just should not be three days running.

Usage
-----
    python scripts/build_schedule.py            # write the schedule
    python scripts/build_schedule.py --check    # validate the existing one only
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FILE = ROOT / "data" / "stations.json"
OUT_FILE = ROOT / "data" / "schedule.json"
PUBLIC_FILE = ROOT / "public" / "data" / "schedule.json"

LENGTH = 100
FAMOUS_RATIO = 0.45        # roughly how much of the schedule should be well-known
OPENING_FAMOUS = 3         # the first few days should be welcoming, not brutal

# Day one should be unmistakable. Drawing the opening from the whole famous
# pool gave a launch week of Pimlico and Morden — technically well-known, but
# a poor advertisement for the game.
MARQUEE = [
    "kings-cross-st-pancras", "oxford-circus", "piccadilly-circus", "westminster",
    "waterloo", "baker-street", "canary-wharf", "london-bridge", "victoria", "bank",
]
SEED = 20261001            # fixed, so the schedule is reproducible from source

# Day 1. The game reads this from schedule.json rather than keeping its own
# copy, so the date and the order it indexes can never drift apart.
LAUNCH_DATE = "2026-09-22"

# Stations a visitor might plausibly have heard of. Edit freely — the schedule
# is regenerated from this list, and --check will tell you if it drifts.
FAMOUS = {
    # Zone 1 core and the big interchanges
    "kings-cross-st-pancras", "oxford-circus", "piccadilly-circus", "leicester-square",
    "covent-garden", "westminster", "waterloo", "london-bridge", "bank", "monument",
    "liverpool-street", "paddington", "victoria", "euston", "euston-square", "baker-street",
    "tottenham-court-road", "holborn", "green-park", "bond-street", "marble-arch",
    "charing-cross", "embankment", "temple", "blackfriars", "st-pauls", "barbican",
    "farringdon", "moorgate", "aldgate", "aldgate-east", "tower-hill", "angel",
    "old-street", "russell-square", "warren-street", "goodge-street", "chancery-lane",
    "marylebone", "regents-park", "great-portland-street", "edgware-road-bakerloo",
    # Kensington, Chelsea and the museums
    "south-kensington", "knightsbridge", "hyde-park-corner", "sloane-square",
    "gloucester-road", "high-street-kensington", "earls-court", "notting-hill-gate",
    "kensington-olympia", "bayswater", "queensway", "lancaster-gate",
    # South of the river
    "elephant-and-castle", "borough", "brixton", "stockwell", "vauxhall", "pimlico",
    "kennington", "clapham-common", "london-bridge",
    # East and Docklands
    "canary-wharf", "stratford", "whitechapel", "bethnal-green", "mile-end",
    "canada-water", "canning-town", "north-greenwich", "bermondsey", "west-ham", "barking",
    # West
    "hammersmith-district-and-piccadilly", "shepherds-bush-central", "white-city",
    "ealing-broadway", "richmond", "kew-gardens", "putney-bridge", "fulham-broadway",
    "turnham-green", "wimbledon", "west-brompton",
    # North
    "camden-town", "finsbury-park", "seven-sisters", "highgate", "archway", "hampstead",
    "golders-green", "wembley-park", "harrow-on-the-hill", "walthamstow-central",
    # Airports and famous termini
    "heathrow-terminals-2-and-3", "heathrow-terminal-4", "heathrow-terminal-5",
    "cockfosters", "morden", "edgware", "high-barnet", "epping", "uxbridge", "amersham",
    "upminster", "watford", "stanmore", "brent-cross",
}


def build(stations: list[dict], rng: random.Random) -> list[str]:
    """Interleave famous and obscure stations, never three obscure in a row."""
    slugs = {s["slug"] for s in stations}
    famous = sorted(FAMOUS & slugs)
    obscure = sorted(slugs - FAMOUS)
    unknown = sorted(FAMOUS - slugs)
    if unknown:
        # A typo in FAMOUS would silently shrink the famous pool; say so loudly.
        print(f"warning: {len(unknown)} FAMOUS slugs are not in stations.json: {unknown}", file=sys.stderr)

    rng.shuffle(famous)
    rng.shuffle(obscure)

    # Put the opening days at the end of the famous pool, since it is pop()ed.
    marquee = [m for m in MARQUEE if m in slugs]
    rng.shuffle(marquee)
    famous = [f for f in famous if f not in marquee[:OPENING_FAMOUS]] + marquee[:OPENING_FAMOUS]

    schedule: list[str] = []
    run = 0  # how many obscure stations in a row we have just placed
    for i in range(LENGTH):
        want_famous = (
            i < OPENING_FAMOUS               # a gentle opening week
            or run >= 2                      # the brief's rule: never three in a row
            or rng.random() < FAMOUS_RATIO
        )
        if want_famous and famous:
            schedule.append(famous.pop())
            run = 0
        elif obscure:
            schedule.append(obscure.pop())
            run += 1
        else:
            schedule.append(famous.pop())
            run = 0
    return schedule


def check(schedule: list[str], stations: list[dict]) -> list[str]:
    """Return a list of problems with a schedule; empty means it is sound."""
    problems = []
    slugs = {s["slug"] for s in stations}
    if len(schedule) != LENGTH:
        problems.append(f"length {len(schedule)}, expected {LENGTH}")
    if len(set(schedule)) != len(schedule):
        dupes = {s for s in schedule if schedule.count(s) > 1}
        problems.append(f"duplicate entries: {sorted(dupes)}")
    missing = [s for s in schedule if s not in slugs]
    if missing:
        problems.append(f"not in stations.json: {missing}")
    run = 0
    for i, slug in enumerate(schedule):
        run = run + 1 if slug not in FAMOUS else 0
        if run >= 3:
            problems.append(f"three obscure stations in a row ending at day {i + 1}")
            run = 0
    return problems


def main() -> None:
    """Build (or validate) the schedule and report its shape."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate data/schedule.json without rewriting it")
    args = parser.parse_args()

    stations = json.loads(STATIONS_FILE.read_text())["stations"]

    if args.check:
        schedule = json.loads(OUT_FILE.read_text())["schedule"]
    else:
        schedule = build(stations, random.Random(SEED))

    problems = check(schedule, stations)
    if problems:
        print("SCHEDULE PROBLEMS:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    if not args.check:
        payload = {"launch": LAUNCH_DATE, "schedule": schedule}
        OUT_FILE.write_text(json.dumps(payload, indent=1) + "\n")
        PUBLIC_FILE.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_FILE.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"wrote {OUT_FILE.relative_to(ROOT)} and {PUBLIC_FILE.relative_to(ROOT)}")

    by_slug = {s["slug"]: s for s in stations}
    famous_count = sum(1 for s in schedule if s in FAMOUS)
    print(f"{len(schedule)} days — {famous_count} famous, {len(schedule) - famous_count} obscure")
    print("first ten days:")
    for i, slug in enumerate(schedule[:10], 1):
        tag = "famous " if slug in FAMOUS else "obscure"
        print(f"  {i:>3}. {tag}  {by_slug[slug]['name']}")


if __name__ == "__main__":
    main()
