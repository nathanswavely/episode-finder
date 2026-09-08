Status: superseded by ADR-0004

# Wikipedia for probe text, TMDB for structure

Probes must discriminate between neighbouring episodes of the same season, which
is the hardest discrimination in this product. TMDB episode overviews are network
promotional copy — deliberately vague, structurally unable to separate S4E5 from
S4E7, and prone to manufacturing false Recognition in viewers who watched nothing.
Wikipedia episode plot summaries are dense with the concrete moments people
actually retain, so they are the source for probe generation; TMDB is used only
for structure (episode counts, titles, air dates, season boundaries, artwork).

## Consequences

- Probe text derives from CC BY-SA content. Share-alike propagates to the generated
  probe corpus, and attribution is required. This is accepted deliberately in
  exchange for probes that discriminate.
- TMDB's terms now constrain only structural metadata, not redistributed prose,
  which materially shrinks that risk.
- Coverage is bounded by Wikipedia episode-summary quality, which is strong for
  popular series and degrades sharply below them. This constrains catalog
  selection — see the catalog decision when it is made.
