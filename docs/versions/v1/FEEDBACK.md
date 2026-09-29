# Feedback on v1 (`v0.1.0`)

_Round 1 of playtesting, September 2026._

**How it was tested.** The live site was shared with a handful of friends, who
played unprompted on their own phones. No script, no questions asked in
advance, and no observation: just a link and whatever they chose to say back.

**What they said.** Near-unanimously, that it was *too hard to guess the tube
station*. One added the suggestion that led to most of this round's changes:

> it would be nicer if there was a landmark as well with the map

Nobody reported a bug. Nobody complained about the look, the share grid, the
autocomplete, or the phone layout. The single complaint was difficulty — which
is a good failure to have, in that everything mechanical worked and the problem
was in the design.

## Diagnosis

Taking "too hard" at face value and simply reducing the blur would have been
the wrong fix. Watching where the difficulty actually comes from, there were
four separate causes, and blur was only one of them.

**1. The crop was too tight — the main cause.** Each map covered a 1 km square,
about 500 m in every direction. In most of London that is terraced streets and
nothing else, and terraced streets in Zone 3 look the same in every direction of
the compass. The features that actually let a person place themselves — a bend
in the Thames, the outline of a common, a park boundary, the fan of tracks
leaving a terminus — mostly live at the 2–3 km scale, and the crop was cutting
all of them off. The map was not too blurred to read so much as too small to
contain an answer.

**2. The late guesses revealed nothing.** The blur curve was `[5, 3.2, 2, 1,
0.4, 0]`, already softened twice after earlier feedback. The problem with it was
the tail: levels 4, 5 and 6 are close enough to be indistinguishable in play, so
a player who was stuck at guess 3 was still stuck at guess 5, having spent two
guesses and been given nothing back. This was a known trade-off, noted in
`BRIEF.md` when the curve was set, and it turned out to matter.

**3. There was nothing to calibrate against.** No scale, no north. A player
could not tell whether they were looking at 200 m or 2 km of city, which makes
every shape on the map ambiguous — a curve that would be recognisable as the
Thames at one scale is an anonymous A-road at another.

**4. The hint ladder was weak where it mattered.** Zone, line, borough, first
letter, letter count. The last two are close to giving the answer away, and the
first three are nearly useless to anyone who does not already carry the tube map
in their head. There was no rung that helped a player *locate* themselves, which
is the thing the map was failing to do.

## Also worth recording

Some testers do not know London well. That is a real limit on what this feedback
proves: a London-knowledge game is supposed to reward London knowledge, and no
amount of design will let someone identify Perivale if they have never heard of
it. The changes below are aimed at players who could plausibly get there — at
making the map readable enough to be worth reasoning about — not at removing the
need to know the city.

## Changes made in response

These became [v2](../v2/). See `CHANGELOG.md` 0.2.0 and ADR-018 onward in `docs/DECISIONS.md` for the detail.

- Crop widened from 1 km to 2.5 km, at a higher output resolution so the extra
  ground does not cost street detail. Addresses cause 1.
- Blur curve re-spread so every guess visibly sharpens the image. Addresses
  cause 2.
- Scale bar and north cue drawn over the map frame. Addresses cause 3.
- Hint ladder rebuilt around a new "nearby landmark" rung, with the two
  name-shaped hints merged into one to make room. Addresses cause 4.
- Hints now unlock face-down and are revealed by tapping, so a player chooses
  when to spend one rather than having it handed to them.
