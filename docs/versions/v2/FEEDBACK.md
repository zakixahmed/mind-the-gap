# Feedback on v2 (`v0.2.0`)

_Round 2 of playtesting, from 29 September 2026. Friends' responses will be
added here as they come in._

## How it was tested

The first test was the developer's own: playing the live site on a phone the
morning after release, as someone who does not live in London. The same friends
who tested v1 have the link.

## What was said

Still hard to work out which station it is:

> I am still struggling to figure out what station it is. Maybe it's just me
> 'cause I don't live there.

## Diagnosis

v2 fixed what round 1 diagnosed — the map is wider, every guess visibly
sharpens it, and there is a scale to read it by. But every clue in the game
still assumes the player already knows London:

- **The map** is only a clue if its shapes mean something to you. A bend in
  the Thames or the outline of a park is recognisable to a Londoner and
  anonymous to everyone else.
- **The Nearby hint** names a landmark, which helps only if you know where
  that landmark is. "Southbank Centre — just north-west" is a strong clue for
  some players and no clue at all for others.
- **Zone and borough** are London vocabulary.
- **The guess list** is all 272 stations every time, however many hints have
  been revealed.

Round 1 noticed this ("some testers do not know London well") and deliberately
set it aside, on the grounds that a London game should reward London knowledge.
Round 2 says it cannot be set aside: the people the game is shared with are
exactly the people who don't know the city. v3 is aimed at them.

## Options considered for v3

- Distance and direction after each wrong guess (the Worldle mechanic), turning
  recall into deduction.
- Narrowing the guess list to the stations that still fit the revealed hints.
- A small "where in London" locator on the map.
- Drawing the tube lines on the map in their real colours.
- An easier mode for visitors, using well-known stations only.
- Guessing the line rather than the station.

**Decision:** guess the line rather than the station — see [v3](../v3/) and ADR-025 in `docs/DECISIONS.md`.
