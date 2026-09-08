Status: accepted (supersedes ADR-0001)

# No TMDB at all — Wikipedia is the only source

ADR-0001 kept TMDB for structural metadata after moving probe text to Wikipedia.
Reading the TMDB API terms killed that too: they prohibit derivatives of TMDB
Content, reserve any use "for training, a machine learning or artificial
intelligence based Application", cap caching at 6 months, and prohibit deriving
revenue without a written agreement. Structural data cached in static JSON would
go non-compliant twice a year, and the logo attribution would be required
regardless. Wikipedia episode-list pages already carry season structure, titles
and air dates, and Wikipedia pageviews supply a free popularity signal for the
candidate pool. The whole corpus is Wikipedia-derived and shipped under
CC BY-SA 4.0 with per-episode attribution.

## Consequences

- No poster art. The product is text-only.
- No rebuild cadence is forced by licensing. The corpus is rebuilt one show at
  a time, by hand, on request — never on a schedule.
- The original plan (LLM over TMDB overviews, static JSON, possibly ad-supported)
  would have breached four clauses at once. Recorded so nobody reintroduces
  TMDB "just for metadata".
