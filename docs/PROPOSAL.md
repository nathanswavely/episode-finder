# Episode Finder — concrete proposal

Status: built. Pilot gate passed; three shows shipped. See PILOT.md for measured results.

## Build pipeline (offline, run by hand, one show at a time or all at once)

1. **Candidate pool.** Wikipedia "List of <show> episodes" pages, ranked by
   Wikipedia pageviews. Exclude reality, talk, news, soap, anthology by category.
   Start with top ~500.
2. **Fetch.** MediaWiki API, wikitext of every season page. Parse `Episode list`
   templates: number, title, air date, ShortSummary. No TMDB anywhere.
3. **Pre-filter.** Skip generation for shows where <90% of episodes have a
   summary ≥60 words. Cheap, no LLM.
4. **Probe generation.** Per episode, one LLM call with the full season's
   summaries as context. Output up to 5 candidate Probes, each a concrete
   inconsequential moment, ranked by specificity. Hard rules: no deaths,
   reveals, betrayals, endings, resolutions, relationship changes, or anything
   the season summary treats as a turning point.
5. **Audit.** Per probe: reverse lookup against the unlabelled season
   (distinctiveness + grounding), consequence check against prior episodes
   only, and a mechanical new-character check. Keep top 3 survivors.
   **Yield gate:** show is in iff ≥90% of episodes have ≥2 survivors.
   Failures are shown to the viewer as "no usable data."
6. **Ship.** `index.json` (show list for client-side search) plus
   `shows/<slug>.json` per show. Licensed CC BY-SA 4.0 with per-episode
   attribution links to the source article. Static host + domain.

Estimated cost: every call carries the season (~8k tokens, cached) and the audit
is ~5 calls per episode, so a full 500-show build is roughly $0.05/episode on
Claude Opus 5 (~$1,600; ~$800 via Batch API) versus ~$0.001/episode on a cheap
contributor-tier model such as Meta Muse Spark 1.3 (~$30). The pilot runs on Opus
5 regardless (~$4 for 75 episodes); the full-build model is chosen by a
pre-registered comparison on the review set (see PILOT.md). If no cheap model
passes, the catalog shrinks (~50 shows ≈ $150) rather than the budget growing.
Costs are one-time. There is no schedule: the unit of
work is "rebuild one show", triggered by a show request or by hand. Users are
asking about seasons that aired before they quit, so new seasons airing do not
make the corpus stale. The corpus is committed to the repo; no CI, no stored
API keys, no recurring spend.

## Runtime (static site, no inference, no backend)

1. Pick show (client-side fuzzy search over index).
2. Pick season, or "not sure" → a Stride-1 Walk over season premieres, then
   drop into the found season.
3. Walk (see FLOW.md). No settings. Starts at the previous season's finale.
   Coarse Pass at automatic Stride, then Fine Pass over the skipped episodes.
   Each probe: "I clearly remember this / Not sure / No." Up to 3 probes per
   episode. No episode numbers on cards.
4. Report Resume Window: the resume episode, with the last Watched as fallback.
   Soft Frontier → widened, and said so.
5. Footer: "Request a show" and "Was this right?" as prefilled GitHub issue
   links. CC BY-SA attribution.

## Gate before any UI is built

See PILOT.md. Pre-registered seasons, order of operations, audit design,
pass/kill thresholds and a fallback tier, decided before any numbers exist.

## Explicitly out

Backend, accounts, database, runtime LLM calls, analytics, ads, TMDB, reality
TV, poster art, any numeric weighting of answers, any calibration.
