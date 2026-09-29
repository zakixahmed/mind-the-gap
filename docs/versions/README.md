# How Mind the Gap evolved

Each version was shared with real players, and what they said shaped the next
one. Every folder here holds that version's README as it shipped, its
screenshots, and the feedback it received. The current version's README is the
one at the root of the repository.

## [v1 — `v0.1.0`](v1/) · 22 September 2026

**What it was.** A daily puzzle: guess the tube station from a blurred 1 km map
centred on it. Six guesses; each wrong one sharpened the map and revealed the
next hint — zone, line, borough, first letter, number of letters.

**What players said.** Near-unanimously, too hard to guess. One asked for a
landmark alongside the map. → [Feedback and diagnosis](v1/FEEDBACK.md)

## [v2 — `v0.2.0`](v2/) · 27 September 2026

**What changed.** The map went from 1 km to 2.5 km across, so it contains the
rivers, parks and railways that let you place yourself. The blur was re-spread
so every guess visibly helps, and a scale bar and north arrow were added. A new
"Nearby" hint names a recognisable landmark with its distance and direction,
and hints now unlock face down, to be revealed when the player chooses.

**What players said.** Still hard to work out the station for anyone who doesn't know
London. → [Feedback and diagnosis](v2/FEEDBACK.md)

## [v3 — `v0.3.0`](v3/) · 29 September 2026

**What changed.** The question changed. Instead of naming one of 272 stations,
you name one of the 11 lines, shown as its whole route in its real colour over
a blurred map of London. Three guesses, three lines a day, landmark hints along
the route, and a fun fact after every answer. The station game stays as hard
mode. Why this option was chosen over the others from round 2 — and what it
gives up — is in ADR-025.

**What players said.** Waiting for round 3. → [Feedback](v3/FEEDBACK.md)
