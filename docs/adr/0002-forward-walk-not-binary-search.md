# Probe forward from the start of the season, not by binary search

Binary search over a season opens at the midpoint, so the first probe leaks a
moment from several episodes past the viewer's stopping point roughly half the
time — before anything is known about them. A forward walk from episode 1 only
ever shows probes for episodes already watched, until the single probe that
crosses the Frontier, and that episode is the one the viewer resumes with anyway.
We accept more questions (O(n) rather than O(log n)) in exchange for a leak that
is structurally bounded rather than probabilistic.

## Consequences

- Leak past the Frontier is bounded by (Stride − 1) plus the number of consecutive
  false Recognitions. Probe quality — moments that do not trigger false
  familiarity — is what enforces the bound, not the walk itself.
- Stride is set automatically from season length (2 up to 16 episodes, 3
  above). It was originally a viewer choice; flow design showed nobody can
  price "careful vs quick" before seeing a card, and a settings screen before
  any value is delivered is where people leave. The first card states the
  bound in plain words instead.
- Memory gaps are handled by retrying with a different Probe from the same
  episode, never by probing ahead. Every episode therefore needs several
  independent probes, which multiplies corpus size and raises the bar on source
  summary quality.
- After the coarse pass stops, a stride-1 Fine Pass runs automatically over the
  episodes it skipped, forward from the last Watched one. Every probe in the
  Fine Pass is for an episode that is either already watched or the first
  unwatched one — the episode the viewer resumes with — so it can never Leak.
  It was originally an opt-in "Narrowing" step; the analysis showed there was
  nothing to opt into. The only Leak in the system is the coarse pass's
  Frontier probe, bounded at Stride − 1.
- Consequently the output is normally a single resume episode, with the last
  Watched episode as a fallback for mid-episode stops. A wider window appears
  only when Verdicts at the Frontier were Soft.
- No posterior is maintained. Inference is a per-episode Verdict plus a stop rule.
  A Bayesian model with information-gain probe selection was considered and
  rejected as over-engineering for this shape.
- "Not sure" is never given a numeric weight. Originally it also never steered
  the Walk — an episode answered all-"not sure" was a Frontier. The first
  genuine test (a viewer who did not know where they stopped Better Call Saul)
  showed that strands hazy viewers seasons early, and a three-season rewatch is
  not the cheap kind of wrong. Now an all-"not sure" episode is Unresolved: the
  Walk asks the viewer once whether to keep going, and continues at the Stride
  if they say yes. Each continuation can reach one Stride further than the
  standard bound; the viewer consented to that at the moment it mattered. Caps:
  four Unresolved episodes in a row, 25 questions per Walk. Undershoot is only
  cheap when it is small.
- The answer labels are part of the inference. "Clearly remember" is the only
  answer that advances the Walk, so it is worded as a high bar to push false
  familiarity into "not sure" rather than "yes".
- The Walk starts at the previous season's finale, not episode 1 of the stated
  season. Viewers are sometimes one season off, and starting inside the stated
  season would make the very first probe a Leak. A prior finale is spoiler-free
  if they are right, and if unrecognised the Walk backs into that season.
- The Resume Window's lower edge is the last Watched episode, not the Frontier.
  Viewers often stop mid-episode; a Watched verdict from first-half probes would
  otherwise skip the half they never saw. Undershooting by one is cheap.
- Probes are inconsequential by rule (see Probe in CONTEXT.md). The Walk bounds
  which episode leaks, not how much of it; without this rule the Frontier probe
  could be the season's biggest twist. This trades discriminating power for
  safety and is the largest open risk to yield — the pilot gate measures it.
- An episode with no surviving probes is walked over, not treated as a failure.
  Its neighbours are probed instead and the Resume Window widens by one. Some
  episodes genuinely have no inconsequential texture (Breaking Bad S4E11 in the
  pilot: every beat is a turning point), and at Stride 2–3 the Walk skips
  episodes anyway.
- The consequence audit must assume the viewer has seen only up to e − Stride,
  not e − 1. The coarse pass shows episode e to a viewer whose last Watched
  verdict was e − Stride; a probe that is safe given e − 1 can still reveal
  e − 1's climax. Found on Better Call Saul S6: E7 probeless, so the walk went
  E6 → E8, and E8's probe described the aftermath of E7's ending. Every shipped
  probe is now re-checked against the stride-aware context.
- The season-finder probes the first Stride episodes of each season, not just
  the premiere (premieres are often slow setup and a poor test), using
  coarse-safe probes, which are audited safe for a viewer who has not started
  that season. An Unresolved season is the one walked, not the one before it.
- The result screen offers "I think I got further" (continue the Walk from the
  result episode, consent implied) and, after a finished season, "keep going
  into the next season". Probes already shown are never repeated.
