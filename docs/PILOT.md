# Pilot plan

Purpose: answer the one question the design cannot — after the inconsequential
rule, does Wikipedia yield enough distinctive probes per episode, and does a
forward Walk on them land the Frontier? Everything here is pre-registered.
Numbers are decided before running, not after.

## Seasons (5)

Fill in from your own viewing history. Criteria only:

| Slot | Requirement | Measures | Probes read? |
|---|---|---|---|
| F1 | A season you **finished**, serialized drama | False negatives (walk stops early on watched eps) | No |
| F2 | A season you **finished**, sitcom | Same, on the genre most likely to blur | No |
| N1 | Season 1 of a show you **never watched** but have heavy cultural exposure to | False positives from osmosis | No |
| R1 | A season you **stopped in**, high yield | Probe quality, by reading | Yes |
| R2 | A season you **stopped in**, borderline yield (~60–80 words/ep) | Where the floor is | Yes |

F1, F2, N1 are the blind set. R1, R2 are the review set.

## Order of operations (strict)

1. Fetch + parse all five. Report pre-filter word counts.
2. Generate + audit R1 and R2. Read everything. Iterate the prompt.
3. **Freeze the prompt.** Commit it.
4. Generate + audit F1, F2, N1. Do not read the output.
5. Walk F1, F2, N1 with the CLI at Stride 2. Record every answer.
6. Score. Then, and only then, read the blind-set probes.

## Generation

One call per episode. Context: all summaries for the season, target episode
marked. Output: up to 5 candidate probes as JSON, each with the moment text
(15–25 words, present tense, no second person, no episode title), a specificity
rank, and the character names used.

Hard rules in the prompt (Tier A):
- Texture, not plot. No deaths, reveals, betrayals, endings, resolutions,
  relationship changes, or anything the season treats as a turning point.
- Only name characters who appeared in an earlier episode.
- Must be a concrete sensory or situational detail, not a summary of events.
- Must be present in the source summary; never from general knowledge.

Include 3 hand-written examples of good and bad probes from one episode you
know well. This matters more than any other prompt detail.

## Audit (per candidate probe)

1. **Reverse lookup.** Probe + all season summaries with labels stripped and
   order shuffled. "Which of these does this moment belong to?" Reject unless
   it picks the right one. Catches non-distinctive and hallucinated probes.
2. **Consequence.** Probe + summaries of prior episodes only. "Does this
   reveal the outcome of a conflict, a character's fate, or the answer to an
   open question?" Reject on yes.
3. **New character.** Names used ⊂ characters seen in prior summaries.
   Mechanical, no model.

Keep the top 3 survivors by specificity rank.

## Walk harness

CLI. Loads a season file, implements the Walk exactly as ADR-0002: starts at
the prior season's finale (or E1 for season 1), Stride as given, three answers,
up to 3 retries per episode, Firm/Soft verdicts, prints the Resume Window.
Logs every probe shown and every answer to a file.

## Gates

| Metric | Where | Pass | Kill |
|---|---|---|---|
| Survivors per episode after audit (median) | all 5 | ≥ 2 | < 2 on the best-yielding season |
| Reverse-lookup accuracy on survivors | all 5 | ≥ 95% | — (diagnostic) |
| False stops (walk ends before finale) | F1, F2 | 0 | ≥ 1 |
| Retries per Watched episode | F1, F2 | ≤ 1 mean | — (diagnostic) |
| Walk advances past first probe | N1 | No | Yes |
| Spoilery survivors, by your reading | R1, R2 | 0 | > 0 → fix audit, rerun R only |
| Wrongly rejected probes, by your reading | R1, R2 | — | diagnostic; if the audit is rejecting the only distinctive moments, say so in writing |

Partial pass (drama passes, sitcom fails) is a catalog constraint, not a kill.
The kill is the best-yielding season failing.

## Pre-registered fallback

If Tier A fails the yield gate, run Tier B on R1 and R2 only: probes may be any
moment the summary places before its final third, other rules unchanged.
Tier B is accepted now as a valid product, so the decision is not made under
the influence of disappointing numbers. If Tier B also fails, stop.

## Model comparison (after the pilot passes, R1 only)

Same frozen prompt, run on a cheap candidate model (first candidate: Meta Muse
Spark 1.3 contributor tier — the training-data trade costs nothing here, since
inputs are public CC BY-SA text and outputs are already CC BY-SA by ADR-0001).
Cheap model is used for the full build iff, on R1 by your reading, its spoilery
survivors = 0 and its post-audit yield is within 20% of Opus 5. Also try the
split: strong model generates, cheap model audits, and the reverse. If nothing
passes, the catalog shrinks; the model does not get more expensive.

## Run 1 — Breaking Bad S4 (R1), Opus 5, 2026-09-07

Pre-registered gate: median survivors ≥ 2. **Measured: median 1, min 0**,
distribution [3,3,1,1,2,2,2,1,0,1,0,1,0], 18/44 survive.

Rejections by check: faithful 18, consequence 6, reverse 1, form 1.

- Consequence check: all 6 rejections correct on reading. Working as designed.
- Reverse lookup: 1 rejection, correct (Ted's tax beat spans E10–E11).
- Faithfulness check: all 18 rejections were sensory/spatial/manner elaboration
  ("hatch", "giggling", "hospital corridor", "for hours"). None added an event,
  outcome, motive or character. The generator prompt asks for viewer-eye
  description; the audit prompt forbade anything the synopsis did not state.
  The two contradicted and the audit won. **Recalibrated**: faithfulness now
  rejects only additions that change what happened. Elaboration is the part of
  a probe that recognition keys on; a wrong elaboration costs a false negative
  (cheap), a wrong event costs a Leak (expensive).
- Form: 12-word floor rejected an 11-word probe that was among the season's
  best (Marie at open houses). Floor lowered to 10, ceiling raised to 30.
- Re-scored with the recalibrated faithfulness check, by my reading:
  [3,3,2,3,3,2,3,3,2,3,0,3,2], median 3. **To be confirmed by rerun and by the
  reviewer's own reading of the 18.**
- E11 "Crawl Space" yields 0 under any reading. Recorded as a real property of
  some episodes, handled by the Walk (ADR-0002), not a gate failure.
- Generator emitted notes on 8/13 episodes explaining thin yield. The notes are
  accurate and useful; keep them in the output.

This is prompt iteration on the review set, permitted by the order of
operations. The prompt is not yet frozen.

## Run 2 — Breaking Bad S4 (R1), recalibrated faithfulness

**Median 3, min 0**, distribution [3,3,2,3,3,2,3,2,3,3,0,2,1], 30/44 survive.
**Gate: PASS.** Rejections: consequence 9, faithful 1, reverse 1, form 1.

- Faithfulness: 1 rejection, a cross-episode fact (car ownership established in
  E6, judged against E7's summary alone). Harmless; not worth widening the
  check's context for.
- Consequence: all 9 rejections correct on reading, including 5 candidates that
  died at faithfulness in run 1. But two candidates rejected in run 1 (E5 Jesse
  on money pickups with Mike; E9 Jesse clearing a warehouse) passed in run 2.
  Both are mild Leaks — each resolves the previous episode's cliffhanger. The
  check's judgement is sound; its consistency on borderline cases is not.
  **Changed**: consequence is now asked twice and any "reveals" rejects.
- Form: the episode-title substring check rejected "Marie … open houses" for
  the episode "Open House". Titles are not Leaks. **Removed.**
- Reviewer wince count on the 30 survivors: 1–2, both the flipped cases above.
  Everything else that reads alarmingly out of context is the aftermath of the
  previous episode's climax, which a viewer at that Frontier has seen.
- E11 = 0, E13 = 1. Consistent with run 1. Finale episodes and all-turning-point
  episodes are structurally thin. Handled by the Walk.

Voting confirmed on E5/E9: warehouse probe rejected 1/2; "Jesse rides with
Mike" passed 2/2 (4 safe votes vs 1 reveals across three runs). Accepted as the
season's one residual mild Leak. Final R1: median 3, 29/44 survive, E11 = 0.

Informal walk of R1 by the reviewer (contaminated: every probe read beforehand):
6 questions, result "start at E3", which matches the reviewer's own sense of
where they stopped. Notably, having read E3/E4's probes an hour earlier did not
produce "clearly remember" answers on them. Two E2/E3 probes describe the same
ongoing situation (Jesse's party); reverse lookup passed both at confidence 4.
Watch for cross-episode continuations in R2; the threshold may need to be 5.

Deviation, 2026-09-07: the R1 gate passed and the Walk is verified, so the
site is being built now with the full Breaking Bad corpus, ahead of R2 and the
blind walks. The order changed; the open questions did not. R2 (thin-summary
floor) and F1/F2/N1 (blind walks) are still owed, on other shows, and the site
itself becomes the harness. The generator prompt is still not frozen.

## Breaking Bad, all seasons — Opus 5, 2026-09-07

Generation ≈ $3 for 62 episodes; audits ≈ $1.20/season. Survivors per episode:

| Season | Median | Min | Total | Probeless |
|---|---|---|---|---|
| 1 | 2 (buggy audit; rerun pending) | 0 | 14 | E1 (bug) |
| 2 | 3 | 0 | 30 | E8 |
| 3 | 2 | 1 | 29 | — |
| 4 | 3 | 0 | 30 | E11 |
| 5 | 2 | 0 | 31 | E13, E14, E16 |

- Generator returned zero candidates for S5E14 "Ozymandias" by choice, with a
  note that every moment is a turning point and it would rather return nothing
  than stretch rule 1. Correct.
- S5E13–14 both probeless exposed a walk bug: the coarse pass "moved beyond"
  the stride window and reached two past the resume point. Fixed: the coarse
  pass never leaves (e, e+stride]; a probeless run becomes the conservative
  resume point. Viewers who finished S5 are told to restart at E13.
- Names check rejected every S1E1 probe (no prior context → every name is
  "new"). Fixed: series premiere exempt. Grounding check was exact-substring
  and rejected light paraphrases; now token overlap ≥ 75%.
- Reverse-lookup threshold raised to reject confidence ≤ 3 (one probe lost).
- Simulation: every frontier of every season resolves correctly with reach
  ≤ stride − 1. 4–11 questions.

## The Office S1–S2 — the thin-summary floor, 2026-09-07

S1 (84 words/ep): survivors [2,3,3,3,3,3], 17 probes, ~$0.75.
S2 (70 words/ep, four episodes under 60): **median 3, min 1**, 53 probes over
22 episodes, no probeless episodes, ~$1.9. Stride-3 walk holds on every
frontier. The four "too thin" episodes yielded 3, 2, 3, 1.

- The word-count pre-filter (60) was miscalibrated for sitcoms. Lowered to 40
  (ADR-0003).
- Rejections: names 5, consequence 2. The names check rejected Jan and Oscar
  (main cast) because S1's summaries never name them. Ensemble sitcoms will
  keep hitting this; fix is a per-season cast list from the Wikipedia
  infobox, if available.
- Probes read the way people describe sitcom episodes ("the one where…").
  Zero consequence rejections in S1; the genre has almost no turning points
  to leak.
- Sitcoms are in. The "procedurals blur" worry from the original plan is
  about summaries, not genre, and only NCIS-style stubs fail.

## Better Call Saul S1–S6 — second full show, 2026-09-07

All six seasons pass: medians 3,2,3,3,3,2; one probeless episode (S6E7). 142
probes over 63 episodes, ~$9.80. Consequence is the dominant rejection reason
(57 of 78), as expected for a show built on turning points.

**Audit gap found reading S6 as a viewer.** The consequence check assumed the
viewer had seen every episode before e. The coarse pass can show e to someone
who has only seen e − Stride. S6E8's probe ("Jimmy sits bound to a chair while
Lalo heads back out") is safe given E7 and a Leak of E7's climax without it —
and E7 is probeless, so the walk goes E6 → E8. Fixed: consequence context is
now episodes ≤ e − Stride; a `--recheck` mode re-runs only that check on
current survivors. All thirteen seasons rechecked (~$4).

Cast-aware names check added (Wikipedia season-page Cast section, main +
previous season's full cast). Recovered probes on ensemble shows; recurring
characters introduced mid-season are still gated by summaries.

## Autonomous pass — final state, 2026-09-07

Three shows, 13 seasons, 153 episodes shipped. Every season: every possible
frontier resolves correctly in simulation and no probe reaches more than
Stride − 1 past the resume episode.

| Show | Seasons | Coarse-safe | Fine-only | Coarse-probeless episodes |
|---|---|---|---|---|
| Breaking Bad | 5 | 98 | 39 | 16 of 62 |
| Better Call Saul | 6 | 112 | 30 | 10 of 63 |
| The Office | 2 | 73 | 1 | 0 of 28 |

- The stride-aware consequence recheck moved 70 probes to fine-only. They are
  not lost: the Fine Pass uses them. Serialized drama pays for its turning
  points in coarse coverage; sitcoms barely notice.
- Coarse-probeless episodes cost precision, not safety: the walk steps over
  them and the fine pass usually recovers them with fine-only probes. Where it
  cannot (BB S5E13–14), the resume point is reported conservatively.
- Spend: generation $6.69, audits ≈ $16, rechecks $5.01 — **≈ $28 total**
  against a $30 cap. Stopped here.

Still owed from the original pilot design: blind walks (F1/F2/N1) by a
reviewer who has not read the probes, and a viewer other than the author.
The site is the harness for both.

## First genuine test — Better Call Saul, reviewer, frontier unknown, 2026-09-07

The reviewer does not know where they stopped Better Call Saul. Chose "not
sure" for the season. The finder probed only each season's premiere; three
"not sure" answers on S4's premiere were treated as a Frontier, S3 was locked,
and the walk ended after ~6 questions with a result the reviewer believes is
seasons too early. No way to escape forward.

Diagnosis: (1) premieres are a poor test, (2) all-"not sure" was treated as
"no", (3) no continuation from a result. All three fixed — Unresolved verdict
with consented continuation, finder over the first Stride episodes, escape
hatches on the result screen. Verified by simulation (hazy viewers now reach
their clear memory; 13/13 seasons still pass without haze) and in the browser
on the reviewer's exact path. Reviewer retested from "not sure": reported
"much better" — a result they believe, reached with the keep-going path.

## Model comparison — Muse Spark 1.3 contributor vs Opus 5, Breaking Bad S4, 2026-09-08

Meta's Model API serves Muse Spark through an Anthropic-compatible Messages
endpoint (Bearer auth, base `https://api.meta.ai`), so the pipeline runs on it
with `--provider meta`. Output goes to `.meta.` files; nothing live touched.

- **Yield: pass.** 20 coarse-safe probes vs Opus's 20, median 2 vs 2. Same
  zeros on Crawl Space and Face Off, with the same reasoning in its notes.
  Cost ≈ $0.05 for the season (Opus ≈ $2).
- **Safety: fail.** Muse's audit rejected nothing on reverse, faithfulness or
  consequence (Opus rejected 9 on consequence). Read as a viewer, at least two
  survivors are Leaks Opus had caught: Ted's leased Mercedes (reveals the
  bailout) and Mike assuring Walt that Jesse is safe (resolves E4's
  cliffhanger). Five more were probes Opus had demoted to fine-only.
- Meta's content filter refused 1 of 84 audit calls on this crime-drama text;
  handled as "cannot verify → reject".
- Conclusion: Muse Spark can generate; it cannot be trusted to audit. The
  consequence check is the safety mechanism and must stay on Opus. Generation
  is the cheap stage anyway, so the saving from the split is modest.

## The Office S3–S9 — Muse generates, Opus audits, 2026-09-08

Seven seasons generated on Muse Spark for $0.21; Opus audits ≈ $1/season.
Opus rejected 60 Muse candidates on consequence across S4–S9: the split works
as the comparison predicted (Muse writes freely, Opus discriminates).

Two bugs surfaced by simulating the new seasons:

- **Double-length episodes were dropped by the fetcher.** Wikipedia lists them
  as one row with `NumParts=2` and `EpisodeNumber2_1/_2`; the parser only read
  `EpisodeNumber2`. On The Office that is most premieres and finales (15
  episodes across S3–S9). Fixed: episodes are now indexed by row position
  (1..N) for the walk's arithmetic, with Wikipedia's label ("1–2") carried for
  display. Existing files were re-keyed; the missing episodes generated.
- Anthropic 529 (overloaded) killed one audit and the credit balance ran out
  during the rechecks. Retry with backoff added for 429/529/5xx; `build_site`
  now refuses any season without a completed recheck, so a partial run can
  never ship an unverified coarse tier.

Final: all nine seasons shipped, 186 episodes, 324 coarse-safe + 14 fine-only
probes. Every season passes full-frontier simulation. The Office cost ≈ $11
total (Muse generation $0.21, Opus audits and rechecks ≈ $10.50).

S8 is the one season under the pre-registered gate: median 1, seven of 24
episodes probeless, because its Wikipedia summaries are stubs (median 59
words, several under 30). Shipped anyway, with this note: the miss is
precision, not safety (the walk undershoots on thin seasons), a hole in the
middle of a show is worse for the viewer than a conservative answer, and S8 is
where many people stopped watching. Regenerating S8 from a richer source is
the fix if it matters.

## The Gentlemen S1–S2 — first requested show, 2026-09-08

Requested by a friend of the reviewer, who typed it into the search and took
that for a request; the GitHub-issue link read as prose and needed a login.
Replaced with two Tally forms created through Tally's API (free plan), with
hidden fields carrying the typed title or the walk's result. Verified end to
end with a test submission.

Muse Spark was too sparing on this show: 9 candidates for 8 episodes in S1,
three episodes probeless. Opus regenerated both seasons for about $1: S1 15
coarse-safe (median 2, min 1), S2 19 (median 3, min 1), no probeless episodes.
For plot-dense serialized shows, Opus generation is worth the extra cents; the
Muse-generates split still holds for sitcoms. Also fixed: multi-season
Wikipedia pages (both seasons listed on one page) are now split by episode
table.

## Cost

~75 episodes × (1 generation + ~5 audit calls). Pennies to a few dollars.
No stored keys: key in the shell environment for the afternoon.

## Explicitly not in the pilot

Show search, season-unknown flow, Narrowing, window-width-by-softness, web UI,
any show outside the five, and scoring the stopped-in seasons by walking them.
