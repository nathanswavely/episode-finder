# User flow

Terms as in CONTEXT.md. Decisions as in ADR-0002.

## Screens

1. **Show.** Search over the catalog index. Not in catalog → "We don't have this
   one yet" + prefilled request issue. Failed the yield gate → "This show's
   episode summaries are too thin for this to work" — honest, not "coming soon".
2. **Season.** Season buttons and "Not sure". Not sure → a season-finder:
   for each season in order, up to four coarse-safe probes from its first
   Stride episodes (safe for someone who has not started it). Clear → watched;
   all "not sure" → Unresolved (ask once whether to keep going); any "no" →
   stop. The season walked is the first Unresolved one if any, else the last
   watched. Probes shown by the finder are not repeated in the walk. Honest cost of this path:
   the first unrecognised premiere is probed with up to k moments, and if the
   viewer stopped early in the previous season that premiere is many episodes
   ahead of their Frontier. Still bounded to one episode's inconsequential
   texture, but it is the one place the "next-to-watch" framing does not hold.
3. **Walk.** One card at a time. Probe text and three buttons:
   **I clearly remember this** · **Not sure** · **No**.
   No episode number on the card (numbers invite reasoning instead of recall,
   and reasoning produces false yeses). Progress as dots. The first card carries
   one line: "I'll skip ahead as we go, so the most I'll ever mention is one
   episode past where you stopped."
4. **Result.** "Start at episode N — if it feels familiar, skip to N+1." Two
   escape hatches: "I think I got further than that" continues the walk from N
   (consent implied); a finished season offers "keep going into season S+1".
   Episode
   titles shown here. Soft Frontier: "Your memory got hazy around here" and the
   fallback moves back one more. Finished the season: "Looks like you finished
   season S — start season S+1." Below: "Was this right?" and "Request a show"
   as prefilled issues; CC BY-SA attribution with a link per episode.

## Walk semantics

    stride = 2 if episodes_in_season <= 16 else 3
    k = 3                                  # probes per episode, max

    verdict(ep):
        if ep has no unshown probes: return UNKNOWN
        show up to k probes; stop at the first "clearly remember" → WATCHED
        every answer "not sure" → UNRESOLVED
        otherwise FRONTIER, Firm if every answer was "no", else Soft
        (a probe is never shown twice in one walk; 25 questions per walk, hard cap)

    if season > 1:
        verdict(previous season's finale)
        FRONTIER → offer to back up a season; stop

    # Coarse Pass
    next_target(e): aim for e + stride; if that episode has no probes, step BACK
                    toward e to the nearest probed one — never forward past it,
                    so a probeless episode cannot extend the reach. If nothing
                    in (e, e+stride] has probes, stop: the Fine Pass will land
                    on the first probeless episode and report it, conservatively,
                    as the resume point. (Breaking Bad S5E13–14 are both
                    probeless; a viewer who finished the season is told to
                    restart at 13. Undershoot is the cheap direction, and the
                    promise on the first card holds.)
    last_watched = 0; e = 1                    # always open on the premiere
    hazy = []
    while e <= n:
        v = verdict(e)
        WATCHED    → last_watched = e; hazy = []; e = next_target(e)
        UNRESOLVED → hazy += [e]; stop if 4 in a row, or if the viewer (asked once
                     per walk) declines to keep going; else e = next_target(e)
        FRONTIER   → frontier = e; break
    no frontier → frontier = n + 1             # the tail still needs the Fine Pass

    # Fine Pass — cannot Leak: every probe is watched or next-to-watch
    for e in last_watched+1 .. frontier-1:
        v = verdict(e)
        WATCHED  → last_watched = e
        UNKNOWN  → break                        # can't check it; resume here, conservatively
        FRONTIER → frontier = e; break

    last_watched == n → finished season; stop
    resume   = last_watched + 1
    hazy_from = first hazy episode ≥ resume, if any → reported: "you weren't
                sure from here on; if it's all familiar keep skipping ahead"
    fallback = last_watched, minus one more if the verdict was Soft

Verified by simulation on Breaking Bad S4 (13 episodes, E11 probeless): every
frontier 0..13 resolves to the correct resume episode (E11 conservatively, since
it cannot be checked), 4–9 questions each, and no probe ever reaches more than
Stride − 1 past the resume episode.

## Probe tiers

Each episode ships two lists. `probes` are safe when shown by the Coarse Pass,
i.e. to a viewer who has seen only e − Stride. `fine` are safe only given e − 1;
the Fine Pass may use them (it only ever probes e after e − 1 is Watched), the
Coarse Pass must not. An episode with no coarse-safe probes is stepped over by
the Coarse Pass but can still be verdicted in the Fine Pass if it has fine-only
probes. Serialized drama produces many fine-only probes (Breaking Bad: 98
coarse-safe, 39 fine-only); sitcoms almost none (The Office: 73 and 1).

## Leak accounting

The only probe that can reach past the resume episode is the Coarse Pass's
Frontier probe set, and it reaches at most Stride − 1 past it. The Fine Pass
never does. Probes for the resume episode itself are shown (up to k of them);
that is the episode the viewer is about to watch, so they are trailer-grade,
not Leaks. False "clearly remember" answers extend the reach by one episode
each, which is why that answer is worded as a high bar.

## Pilot harness

`pipeline/walk.py` implements exactly this in a terminal, logs every probe and
answer, and has a `--simulate` mode that plays a viewer with a known Frontier
so the algorithm can be checked without a human.
