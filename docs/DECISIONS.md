# Decision log

Lightweight ADRs. One entry per meaningful decision, newest at the bottom. Status is one of **Proposed**, **Accepted**, **Superseded by ADR-nnn**.

Template:

```
## ADR-nnn: Title
- Date: YYYY-MM-DD
- Status: Accepted
- Context: what question needed answering
- Decision: what was chosen
- Consequences: what that makes easier or harder
```

---

## ADR-001: Repository root is the game folder, not the parent portfolio folder
- Date: 2026-09-12
- Status: Accepted
- Context: The project lives inside a wider "Portfolio Website" folder. The game needs its own GitHub repository and GitHub Pages deployment.
- Decision: `git init` in `Mind the Gap - web game/` itself. The parent folder is untouched.
- Consequences: One repo per project, clean history, Pages can serve straight from `public/`. If the portfolio site later wants to embed the game, it links to the Pages URL rather than sharing a repo.

## ADR-002: Single-file front end with no framework and no build step
- Date: 2026-09-12
- Status: Accepted
- Context: The brief requires `public/index.html` with inline CSS and JS. Worth recording why that is a good fit rather than a constraint to work around.
- Decision: All markup, styles and logic live in one file. No bundler, no package.json for the front end.
- Consequences: The whole game is readable top to bottom, deploys anywhere that serves static files, and there is nothing to break in CI. The cost is that the file will grow to roughly a thousand lines; sections are separated with clear comment banners to keep it navigable. If it ever needs splitting, `<script src>` to sibling files is still build-free.

## ADR-003: Rendered map images are committed, size permitting
- Date: 2026-09-12 (resolved 2026-09-22)
- Status: Accepted — the full set is 15.9 MB, comfortably under the threshold, so `public/maps/` is committed
- Context: GitHub Pages serves files from the repository, so the PNGs must be in git or fetched at deploy time. The brief sets a 50 MB threshold.
- Decision: Commit `public/maps/` by default. After the full render in phase 3, measure the total. Over 50 MB → ignore the folder, document regeneration in README, and consider a GitHub Action that renders on deploy.
- Consequences: Simplest possible deploy while the set is small. The `.gitignore` already contains the commented-out rule so the switch is one line.

## ADR-004: Commit identity and authorship
- Date: 2026-09-12
- Status: Accepted
- Context: Commits are created from an AI-assisted session but the repository is Zack's portfolio.
- Decision: Commits are authored as Zack Ahmed (local git config in this repo only). Each commit body ends with a Co-Authored-By trailer naming the assistant, which is the standard GitHub convention for pair-authored commits.
- Consequences: Authorship is honest on both sides; GitHub attributes the work to Zack's account and the trailer records the collaboration without hiding it.

## ADR-005: Station data from the TfL Unified API, boroughs from Nominatim
- Date: 2026-09-12
- Status: Accepted
- Context: The brief allowed either the TfL Unified API or an OpenStreetMap extract. The game needs, per station: coordinates, fare zone(s), lines served, borough, and which stations are adjacent (for the 🟨 share-grid rule).
- Decision: TfL for everything TfL has (`/Line/Mode/tube`, `/Line/{id}/StopPoints`, `/Line/{id}/Route/Sequence/{direction}`), because it is the authoritative source for zones, lines and route order, and it defines "London Underground" for us (11 lines, 272 stations) with no heuristics. OSM has none of the fare data and would need filtering to separate Tube from Overground, DLR and the Elizabeth line. TfL does not publish boroughs, so each station is reverse-geocoded once with OSM Nominatim (1 request/second, cached, identifying User-Agent as its policy requires).
- Consequences: 34 TfL requests and 272 Nominatim requests per full build, about five minutes. Two attributions to carry (TfL open data, OSM ODbL). Raw responses are cached under `data/raw/` and git-ignored, so the dataset is reproducible and inspectable but the repo stays small. Rejected alternative: point-in-polygon against London Datastore borough boundaries — deterministic, but needs a shapefile parser or GeoJSON download and would still need a second source for the 16 stations outside Greater London.

## ADR-006: Scope is London Underground only
- Date: 2026-09-12
- Status: Accepted
- Context: TfL's network also includes the Elizabeth line, Overground, DLR and trams, all with map presence and zones.
- Decision: Only stations served by mode `tube` are included. Stations shared with other modes (e.g. Stratford) are included as Tube stations, with only their Tube lines listed.
- Consequences: Matches the game's name and the brief. Adding other modes later is a one-line change to `get_tube_lines()` plus a re-render, but would need thought about how many obscure stations the schedule can absorb.

## ADR-007: `stations.json` carries adjacency and uses slugs as the primary key
- Date: 2026-09-12
- Status: Accepted
- Context: The share grid needs "adjacent station" and the map renderer needs a safe folder name per station. Both could be computed at runtime or stored.
- Decision: Store both. `slug` is derived from the display name (`King's Cross St. Pancras` → `kings-cross-st-pancras`), asserted unique at build time, and is the key the front end and the map folders share. `adjacent` is a list of slugs derived from TfL's ordered route sequences in both directions. Four same-named stations have TfL's abbreviations expanded (`Dist&Picc Line` → `District & Piccadilly`) so the autocomplete reads naturally.
- Consequences: The front end never sees a naptan id and does no graph work. The file is 79 KB uncompressed, fine for a single fetch. If a station is renamed the slug changes and its map folder must be re-rendered — acceptable for a dataset that changes every few years.

## ADR-008: Draw the maps ourselves from raw OSM data rather than using map tiles
- Date: 2026-09-22
- Status: Accepted
- Context: The brief called for "a free static tile source whose licence permits this use". Two problems emerged. First, every standard tile style prints station names on the map, which would hand the player the answer at the sharpest level. Second, the licences forbid exactly what this game does. OpenStreetMap's tile usage policy lists under "You must not": "Bulk download ('scrape') tiles or offer prefetch features." CARTO's basemap terms prohibit "downloading or extracting map content in bulk" (9.c.i), "proxying or caching the content on the server side" (9.c.iii), and creating derivative works (15.d); their only static-image allowance is for "screenshots or other static images ... for illustrative, editorial or documentary purposes". Pre-rendering 1,632 cropped images and serving them from GitHub Pages does not fit inside that.
- Decision: Query the Overpass API for the raw OpenStreetMap *data* in a 1 km square around each station, and draw the map ourselves with Pillow — roads, rail, water, green space and buildings, no labels. The data is ODbL; the obligation is attribution ("© OpenStreetMap contributors") and nothing else. Overpass's usage policy allows a one-off job of this size comfortably: "less than 10,000 queries per day and download less than 1 GB data per day"; ours is 272 queries and about 400 MB, run once.
- Consequences: More code than pointing at a tile server, but we control the cartography, the maps are label-free by construction, and the licence position is clean and documented. The renderer is also reproducible offline from the cached responses. Cost: our maps are plainer than a professional basemap, which suits a blurred-image puzzle.

## ADR-009: Blur curve and per-level image sizes
- Date: 2026-09-22 (revised 2026-09-22 after playtesting)
- Status: Accepted — revised curve below supersedes the original
- Context: Six levels have to go from "almost nothing" to "fully legible" with guess 3 feeling like the turning point, and the whole set has to stay small.
- Decision: Gaussian radii `[36, 20, 10, 5, 2, 0]` — deliberately non-linear, with the big drop between levels 2 and 3. Reviewed on a five-station contact sheet (Amersham, Bank, Hainault, Turnham Green, Westminster) and signed off. Levels are stored at `[160, 160, 320, 640, 640, 640]` px: an image blurred at radius 36 carries no detail finer than that, so storing it small and letting the browser scale it up is visually identical and roughly ten times smaller.
- Consequences: The curve is a single constant to re-tune, and re-rendering from cache takes about a minute with no network.
- **Revision 2 (final):** the softened curve still read as too heavy in play, for a reason the first revision missed — the radii are defined against a 640 px image, but the map is displayed at whatever width the screen allows, so on a desktop showing it at ~780 px the blur is amplified by about a fifth. The curve is now `[5, 3.2, 2, 1, 0.4, 0]` and every level is stored at full 640 px: at radii this gentle, a reduced storage size would become what limits the image rather than the blur. The set is 31.3 MB, still inside ADR-003's threshold. Known trade-off, accepted deliberately: levels 4, 5 and 6 are now nearly indistinguishable, so the last two guesses gain little visually and lean on the hint ladder instead.
- **Revision 1:** playing the finished UI showed the original curve was far too aggressive. Levels 1 and 2 were near-featureless colour washes — striking to look at, but they gave a player nothing to reason about, so the first two of six guesses were effectively wasted. The curve is now `[13, 8, 4.5, 2.5, 1, 0]`: guess 1 shows major roads, water and green space clearly enough to place a district, and the ramp to legibility happens across the middle guesses instead of all at the end. Level sizes rose to `[320, 384, 512, 640, 640, 640]` to match — at radius 13 the old 160 px storage, not the blur, would have been what limited the image. The full set grew from 15.9 MB to 20.7 MB, still comfortably inside ADR-003's threshold.

## ADR-013: A shared daily puzzle *and* unlimited practice rounds
- Date: 2026-09-22
- Status: Accepted — amends the brief
- Context: The brief specified one puzzle per day, identical for everyone. In review the preference changed to letting a player play as many rounds as they like. Pure endless play was considered and rejected: it would leave the share grid pointless (nobody else played your puzzle) and streaks meaningless, losing the two things that make the format social.
- Decision: Keep the shared daily puzzle as the headline round — it is what the share grid and streaks are built on — and add unlimited practice rounds on top, reachable from the end screen. Practice rounds draw from the full 272 stations, are not shareable and do not touch stats; only the daily counts.
- Consequences: One extra mode rather than a different game, and the daily logic, share grid and stats from phase 5 are unaffected. Practice needs its own lightweight state so an in-progress practice round cannot overwrite the day's saved daily game. The curated schedule stays worth doing, because it now only has to be good for the daily.


## ADR-010: WebP rather than PNG for the map images
- Date: 2026-09-22
- Status: Accepted — supersedes the PNG output named in the brief
- Context: The brief specified `public/maps/<slug>/1.png … 6.png`. Measured on the densest station, a palette-quantised PNG at 640 px was about 150 KB, putting the full set near 95 MB — well past the 50 MB threshold in ADR-003, which would have forced the maps out of the repository and into a build step.
- Decision: WebP at quality 80. The same image is about 41 KB; the full set is 15.9 MB (60 KB per station).
- Consequences: The repo stays self-contained and GitHub Pages serves the images directly, with no CI render step. WebP is supported by every browser released in the last several years, which is an acceptable floor for a hobby puzzle game. Changing back is a one-line edit plus a re-render from cache.

## ADR-011: `public/` carries its own trimmed copy of the station data
- Date: 2026-09-22
- Status: Accepted
- Context: The deploy target is the `public/` folder alone, but the canonical station list lives in `data/`. Options were a build-time copy, a symlink (which GitHub Pages will not follow), or moving the data into `public/` entirely.
- Decision: `scripts/build_stations.py` writes both — `data/stations.json` (canonical, indented, every field including naptan ids and build metadata) and `public/data/stations.json` (minified, only the eight fields the browser uses, 50 KB).
- Consequences: `public/` can be deployed as-is with nothing else alongside it, and the file the player downloads carries no dead weight. The cost is two files that must not drift; they are written by the same function in the same run, so they cannot.

## ADR-012: Enter never submits free text
- Date: 2026-09-22
- Status: Accepted
- Context: The brief rules out free-text entry to avoid spelling disputes. The obvious implementation — match the typed string against the station list on submit — still lets a player type `Tottenham Court Rd` and be told they are wrong.
- Decision: The input is a combobox over the station list. Enter commits only the currently highlighted suggestion; with nothing highlighted it does nothing but prompt. Matching folds case, accents and punctuation, so `st johns wood`, `King's Cross` and `kings cross` all find their station.
- Consequences: There is no code path that can reject a guess for spelling, because there is no path that accepts a string. The cost is that a player must always pick from the list, which is also what makes the game feel fair.

## ADR-014: Date seeding compares calendar dates, never elapsed time
- Date: 2026-09-22
- Status: Accepted
- Context: The puzzle number is "days since launch, in London". The tempting implementations — subtracting timestamps and dividing by 86,400,000, or adding 24 hours to find the next puzzle — are both wrong twice a year, when a London day is 23 or 25 hours long, and wrong all year for players outside the UK.
- Decision: Format "now" as a London calendar date with `Intl.DateTimeFormat("en-CA", {timeZone: "Europe/London"})`, which yields `YYYY-MM-DD`, then subtract two `Date.UTC(...)` values built from those date parts. That compares calendar days as calendar days and never meets a DST transition. The countdown to the next puzzle finds the exact instant the London date changes by bisecting over UTC milliseconds — about sixteen iterations, and correct on clock-change nights.
- Consequences: A player in Sydney gets the same puzzle as a player in Southwark on the same London day, which is the point. Verified in the browser across both 2026 DST transitions and a year boundary.

## ADR-015: Facts are optional, and the fallback is generated from the station record
- Date: 2026-09-22
- Status: Accepted
- Context: The win screen shows "one interesting fact". Writing 272 of them — or even 100 — is a large content job, and a half-remembered fact confidently displayed is worse than none.
- Decision: `public/data/facts.json` holds only facts we are confident of (20 at the time of writing). For every other station the game composes a sentence from the station's own record: zone, borough and lines. The file can grow over time and the game never shows an invented claim.
- Consequences: Every station has something to show from day one, and nothing in the game asserts anything the data does not support. Adding a fact is a one-line edit with no code change.

## ADR-016: The station list opens on tap, and Enter never fires on a browse list
- Date: 2026-09-22
- Status: Accepted
- Context: The autocomplete only appeared once the player typed, so tapping the box did nothing — a dead end for anyone who does not already know a station name, and no way to browse what is available.
- Decision: An empty query now returns the whole list rather than nothing, so focusing the input opens all 272 stations, scrollable, and typing filters from there. Crucially, the top entry is pre-highlighted **only** once something has been typed: with the full list open and nothing typed, a stray Enter would otherwise spend one of six guesses on whatever sorts first (Acton Town). Arrowing into the list highlights normally, and the highlight is scrolled into view.
- Consequences: The input works as both a search box and a browsable menu, with one code path. The full list is 272 DOM nodes, built once per open — measurably instant, and far simpler than virtualising a list this size.

## ADR-017: Deploy with a GitHub Actions workflow rather than renaming `public/`
- Date: 2026-09-22
- Status: Accepted
- Context: GitHub Pages serves a branch's root or its `/docs` folder — it cannot be pointed at `public/`, which is where the brief put the site. The options were to rename `public/` to `docs/`, to publish from a `gh-pages` branch, or to upload the folder as a Pages artifact from Actions.
- Decision: A GitHub Actions workflow uploads `public/` directly. The repository keeps the layout the project was designed around, and the site is published byte-for-byte with no build or transformation step, which matches ADR-002. The workflow first checks that the data files are present and that all 100 scheduled stations have six rendered map levels — the two failures that would otherwise produce a site that loads but does not work.
- Consequences: One more file to maintain, and a one-time repository setting (Pages source: GitHub Actions). In exchange the deploy is reproducible, visible in the Actions tab, and has a guard against shipping a broken schedule. Every asset path is relative, so the same files work under `/mind-the-gap/` or at a domain root with no base-path configuration.

## ADR-018: The map crop is 2.5 km across, not 1 km
- Date: 2026-09-25
- Status: Accepted
- Context: Round-1 playtesting said the game was too hard to guess (`docs/FEEDBACK.md`). The obvious reading was that the blur was too heavy, but it had already been softened twice, and softening it further would eventually just show an unblurred map. Looking at what players actually had to work with, the crop was the bigger problem: a 1 km square is about 500 m in every direction, which in most of London is terraced streets, and terraced streets in Zone 3 look identical in every direction of the compass. The features that let a person place themselves — a bend in the Thames, the outline of a common, a park boundary, the fan of tracks leaving a terminus — mostly live at the 2–3 km scale and were being cut off entirely. The map was less "too blurred to read" than "too small to contain an answer".
- Decision: `AREA_M` goes from 1000 to 2500, with `SIZE_PX` raised from 640 to 896 so the extra ground does not come out of street detail. The blur curve was rewritten against the new scale rather than carried over: at 2500 m across 896 px one pixel is about 2.8 m, so the radii are chosen in metres-on-the-ground and spread so that each of the six guesses is a visible step.
- Consequences: Every station has to be re-fetched from Overpass, because Overpass data is clipped to the bbox it was requested for. That is a slow, once-off job and the reason ADR-022 exists. Images roughly double in pixel count; per-level encoding quality (ADR-019's sibling change) keeps the total in the same range. The 1 km set stays on disk, so v0.1.0 remains reproducible.

## ADR-019: Roads are drawn with a minimum width in pixels, and the smallest classes are dropped
- Date: 2026-09-25
- Status: Accepted
- Context: Line widths are specified in metres and scaled to pixels, which is the honest way to draw a map and worked well at 1 km. At 2.5 km it falls apart in both directions: a 12 m primary road becomes about four pixels and reads as a scratch rather than a route, while footways and service roads fall below a pixel and turn into noise laid over everything beneath them. Real cartography does not draw every zoom level from the same rules; it generalises.
- Decision: Each road class gains a minimum drawn width in output pixels alongside its true metre width, and the renderer takes whichever is larger. The floor is generous for the classes that carry a place's structure (motorway, trunk, primary, and surface railway) and almost nothing for residential streets, which at this scale are texture rather than information. Footways, cycleways, steps and service roads are no longer drawn at all, and building outlines are dropped, leaving only the fill.
- Consequences: The maps are deliberately no longer to scale in their line work, which is a normal cartographic compromise but worth stating plainly. Arterial roads and railways now survive the blur at guess 1, which is the point — they are the features a player can actually reason from. Residential street patterns are still visible as texture, so the built-up-versus-open distinction is intact.

## ADR-020: The landmark hint is derived from OSM, not hand-written
- Date: 2026-09-25
- Status: Accepted
- Context: The strongest suggestion from round 1 was to show a landmark alongside the map. Drawing named landmarks onto the image was rejected immediately: labels are exactly what ADR-008 avoids, and a map captioned "British Museum" ends the puzzle. That leaves a landmark as a *hint* — but 272 hand-written hints is a content project, not a feature, and `public/data/facts.json` had already shown how slowly that kind of list fills up (20 of 100 scheduled stations after three sessions).
- Decision: `scripts/build_landmarks.py` derives one landmark per station from the Overpass data already cached for rendering, so it costs no extra network. Candidates are scored by category prominence minus distance — a stadium half a mile away beats a hospital next door, because you can see the stadium on the map — and any name whose distinctive words overlap the station's own is rejected outright. An `OVERRIDES` table exists for the cases the heuristic gets wrong, and stations with no acceptable candidate simply show a different line on that rung.
- Consequences: Coverage arrives all at once rather than accruing, and improves for free whenever OSM does. The rejection test is deliberately strict, so some stations lose a landmark they could arguably have had; that is the right side to err on, since a hint that names the answer is worse than no hint. The output is reviewable in bulk with `--show`, which is how the overrides get found.

## ADR-021: Hints unlock face-down and are revealed by tapping
- Date: 2026-09-25
- Status: Accepted
- Context: Hints appeared automatically after each wrong guess. That made a wrong guess feel doubly punitive — you lost a guess *and* had information pushed at you whether or not you wanted it — and it removed any decision from the middle of the round. It also meant a player who was one clue away from solving it unaided never got to find out.
- Decision: A wrong guess unlocks the next rung but leaves it face-down; the player taps to turn it over. Once the round ends every hint is shown, since there is nothing left to protect. Which hints were revealed is saved alongside the rest of the daily game, so reloading does not hand them all over.
- Consequences: One more piece of state to persist, and one more tap between a stuck player and help. In exchange the round has a small ongoing choice in it, the player keeps the satisfaction of solving it without assistance, and a future hard mode has an obvious shape — count revealed hints, or disable the ladder entirely.

## ADR-022: The OSM cache filename carries the crop size
- Date: 2026-09-25
- Status: Accepted
- Context: `fetch_osm` cached Overpass responses at `data/raw/osm_<slug>.json`, keyed on the station alone. Overpass returns only what falls inside the bbox it was asked for, so once `AREA_M` changed, every one of those files was wrong — and re-running the renderer would have reused them happily, producing 272 maps showing a small island of city in a large blank square. It would have looked like a rendering bug, not a caching one, which is the expensive kind of failure to debug.
- Decision: The cache path is `osm_<slug>_<AREA_M>m.json.gz`. A crop size that has not been fetched simply has no cache and is fetched; a crop size that has is reused. The v0.1.0 filename is still read when `AREA_M` is 1000, so the old release renders from the old cache untouched.
- Consequences: Stale-cache bugs of this shape are now impossible rather than merely unlikely, and a previous release stays reproducible. Changing the crop means paying for a full re-fetch, which is correct — the alternative was paying for it in silently wrong output. The files are gzipped in the same change, because 6.25× the area would otherwise have been roughly 3 GB of JSON on a laptop; Overpass responses compress by about 85%.

## ADR-023: Buildings are not drawn, and the Overpass query only asks for what is drawn
- Date: 2026-09-25
- Status: Accepted
- Context: The first real fetch at 2.5 km made the cost of ADR-018 obvious: every station needed retries, and one exhausted all nine attempts and failed. The public Overpass instances were answering 504 far more often than they were answering with data. This was predictable in hindsight — the box is 6.25× the area of the v0.1.0 one, and the query asked for every `highway` and every `building` inside it, which in central London is tens of thousands of ways with full geometry inlined (1.7 MB gzipped for one Canary Wharf response). Hammering free, donated infrastructure 272 times with a query that heavy is also simply rude.
- Decision: The query now asks only for the road classes the renderer still draws — ADR-019 dropped footways, cycleways, steps and service roads, but the query had gone on fetching them — and does not ask for buildings at all. Built-up areas are carried by a flat wash over `landuse=residential` instead. The fetch margin drops from 15% to 8%, since at 2.5 km the old fraction meant 375 m of extra city in every direction for nothing.
- Consequences: Buildings were 37–49% of the elements returned. The decision to drop them was made from a side-by-side render rather than from reasoning: at guess-1 blur the two versions are indistinguishable, and even sharp, a station's identity comes from water, railways, green space and arterial roads, not from building texture. This is also better cartography — real maps stop drawing individual buildings well before this zoom level and switch to landuse. The trade is that the final sharp reveal is a little plainer than it was. Caches fetched before this change contain the extra data harmlessly, since the renderer simply ignores it.

## ADR-024: Landmarks come from their own pass over the extracts, ranked by Wikipedia links
- Date: 2026-09-27
- Status: Accepted (supersedes the candidate source in ADR-020)
- Context: The first full `--show` review of ADR-020's output was poor. Every station had a hint and none leaked the answer, but most picks were things no player would recognise — "Tiny Urban Forest", "Floating Pocket Park", "Shire Lane median strip lower" — along with rivers that run underground (the Fleet, offered at four stations) and plain road names. The cause was structural, not a scoring problem: the candidates came from the render cache, and ADR-023 had trimmed that cache to exactly what the map draws. Museums, attractions, towers, bridges and palaces were never on the shortlist, so the picker could only ever choose between parks and water.
- Decision: `build_landmarks.py --extract` reads the Geofabrik extracts once and keeps every named feature in a landmark category (points, rivers and canals as lines, and areas assembled by osmium from closed ways and multipolygons). Notability is judged by whether OSM links the feature to Wikipedia or Wikidata, worth a flat +60. Open spaces also score by size, up or down; buildings only ever gain from size, so the London Eye is not marked down for its small footprint. Unlinked points and unlinked parks under 2 ha are dropped, as are culverted rivers and roads. Distance is measured to a feature's nearest edge rather than its centre. A reviewed `SKIP` list removes linked-but-obscure places and things inside a bigger answer (the Crown Jewels at Tower Hill), letting the next pick through with its distance still computed; `RENAME` fixes sponsor names; `OVERRIDES` is down to two stations.
- Consequences: The picks are now the ones a Londoner would give — Big Ben, Tate Modern's neighbours, The O2, Emirates, Platform 9¾, Buckingham Palace. The Wikipedia link is a proxy, and it over-rewards small institutions with keen editors, which is what `SKIP` is for; that list is judgement and will need topping up as more of the 272 are played. The extract takes under a minute and needs the same four .pbf files as the maps, so a landmark rebuild adds no new dependency. Chigwell is the one station with no hint.


## ADR-025: v3 asks "which line?", with the whole route in its real colour
- Date: 2026-09-29
- Status: Accepted
- Context: Round 2 (`docs/versions/v2/FEEDBACK.md`) showed that v2 still only works for players who already know London, and those are not the people it is being shared with. 272 possible answers is the heart of the problem: someone who doesn't know the city cannot even narrow the list. Three alternatives were weighed — keep stations and add distance-and-direction feedback plus a filtered guess list; keep stations and colour the lines on the map; or change the question to the line. The concern raised against lines was that a route drawn in its real colour largely answers itself for anyone who knows the tube map, that 11 answers with generous guesses can be solved by elimination, and that the puzzle images repeat.
- Decision (Zack's call): the main game becomes "which line is this?". Each puzzle shows the line's whole route, in its real TfL colour, over a plain map of London with the other ten lines faint for context. Three guesses instead of six, so elimination is not enough (at most 3 of 11). Three puzzles a day, the same for everyone, played back to back and reset at midnight London time, with one share grid covering all three. The station game stays as a hard mode. Hints are famous landmarks along the route.
- Rendering: `scripts/render_lines.py` draws 11 × 3 images from the TfL route geometry already saved by `build_stations.py` and a base map thinned from the OSM extract — no network. The map and the route blur separately (`BLUR_RADII` vs `ROUTE_BLUR_RADII`): the map hides where in London you are, while the route's colour stays readable at every level, since it is meant to be seen. Multipolygon water is assembled into rings by exact shared endpoints, not `render_maps.stitch()`'s greedy chaining, which draws chords across a whole-city relation.
- Consequences: The game becomes learnable by anyone with the tube map, which is the point — but it becomes easy for people who know the colours by heart, and with 11 pictures the same line comes up about every four days. Both are accepted trade-offs for now; round-3 feedback will say whether they matter. Possible later levers, not built: a stretch of the line instead of the whole route, or withholding the colour until a later guess.

## ADR-026: Two hint rungs are open before the first guess, and the station count is one of them
- Date: 2026-10-06
- Status: Accepted
- Context: Round-3 feedback (`docs/versions/v3/FEEDBACK.md`) from a tester who had lived in London a year: *"a little more information on the map would make the guesses easier. Hints such as notable places or stops along the route would be helpful."* The landmark hints they were asking for already existed — but every rung was locked until a wrong guess, and the line game only gives three. A player had to spend a third of their attempts before any help existed, which is a steep toll for the audience v3 was built for. The same tester also noticed the line's station count and read it as a clue that had arrived too late; it was, because it was only ever printed on the result card after the answer.
- Decision: The ladder becomes three rungs — station count, landmark, second landmark — with the first two open from the start and the third bought with a wrong guess. Rungs still sit face down and are turned over by tapping, so a confident player can ignore all of them. The station count leads because it is the one clue that needs no London knowledge at all: it narrows eleven lines without naming a single place.
- Consequences: The game is easier at the opening, deliberately, for the players v3 exists to serve. That cuts against round-3's other reply — a Londoner who found the eleven buttons too easy already — so the share grid now marks a line solved with help (`💡`). Once help is free for the asking it has to be visible, or solving it unaided looks identical to being handed the answer. That gives the too-easy camp something to play for without imposing a difficulty on anyone, which is the direction the feedback itself pointed: let each player choose how much help to take. The result card still recites the station count, which is now a repeat for anyone who opened that rung, and worth keeping for anyone who did not.
