# Feedback on v3 (`v0.3.0`)

_Round 3 of playtesting, from 29 September 2026. Shared as an Instagram story
("I made a puzzle game — give it a go and let me know your thoughts") with a
link sticker. Responses are added here as they come in._

## What was said

**Tester 1 — lives in London.** The eleven answer buttons make it too easy:

> Don't keep the options like that, make it like a text box where I can type
> the line name. Having the options wide open makes it easier.

Worth weighing against who v3 is for: a Londoner already knows all eleven
names, so the buttons give them little beyond convenience — but a player who
doesn't know London may not know the names at all, and the buttons are what
lets them play. One reply so far; see what the non-Londoners say before
deciding.

**Tester 2 — a friend.** Likes it, but wants more to go on from the start:

> The game is good, but a little more information on the map would make the
> guesses easier. Hints such as notable places or stops along the route would
> be helpful. That said, I did notice that you get additional clues as you
> make more attempts, such as total number of stops.

Two things in this are worth noting. The landmark hints already exist but only
unlock after a wrong guess, so a player who gets the first guess wrong has
already paid for them. And the station count is not a clue during play: it is
shown on the result card after the answer, so it reads as information that
arrived too late.

## Early read

The two replies pull in opposite directions: a Londoner finds it too easy, the
other tester wants more help. That is the gap between the two audiences
showing, not a contradiction — and it points at letting each player choose how
much help to take rather than picking one difficulty for everyone.

## What changed going into this round

Round 2 said the station game only works if you already know London. v3 changes
the question to "which line is this?": eleven answers instead of 272, each
line's whole route drawn in its real colour, three guesses, three puzzles a
day, landmark hints and a fun fact after every answer. The station game is
kept as hard mode. The reasoning, and the trade-offs accepted, are in ADR-025
in `docs/DECISIONS.md`.

## Worth asking testers

- Could you solve them without knowing London? (The point of v3.)
- Was it too easy? The colour is visible from the first guess.
- Did the landmark hints help, and did you read the fun facts?
- Did the yellow squares mean anything to you? Most lines share a station with
  most others, so 🟨 is common.
- Did anyone find hard mode, and did they play it?
