# Catalog membership is decided by measured probe yield, not genre

The obvious catalog is "top N popular shows", and the obvious refinement is a
genre filter (serialized drama in, sitcoms and procedurals out). Measuring
Wikipedia summary density showed genre is the wrong axis: sitcoms (The Office,
Friends) yield as well as serialized drama, while procedurals (NCIS: median 37
words/episode, 19 of 22 episodes under 60) have nothing to build probes from.
A show is in the catalog if and only if enough of its episodes clear a yield
floor, measured at build time from the source summaries. Shows that fail are
excluded outright — the viewer is told there is no usable data — never shipped
with weak probes.

Reality television is excluded by product decision for now, even though its
summaries are dense. Consumption pattern and what counts as a spoiler differ
enough that it is a separate product question, deferred.

## Consequences

- Candidate pool can be far larger than 100 shows; batch cost is not the
  constraint, yield is.
- "Was the show consumed linearly" is not a criterion. The product's premise
  already selects for viewers who watched in order.
- Summary word count is only a pre-filter, used to avoid paying to generate
  probes for hopeless shows. The gate that decides membership is post-audit:
  a show is in iff ≥90% of its episodes have ≥2 surviving probes. Word count
  is a proxy and is never the final word.
- The pre-filter floor was first set at 60 words from the NCIS measurement.
  The Office S2 (median 70, four episodes at 50–54 words) yielded a median of
  3 probes and 2–3 on the "thin" episodes themselves: sitcom summaries are
  short because they are pure situation, which is what a probe is. Floor
  lowered to 40. The pre-filter exists to avoid paying for hopeless shows, and
  it should err toward paying.
