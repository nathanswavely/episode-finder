# Episode Finder

Helps someone who abandoned a TV series partway through, and no longer remembers
where, reconstruct how far they got — using their own recall, because no viewing
history of them exists anywhere.

## Language

**Probe**:
A single concrete, inconsequential moment drawn from one episode, shown to the
viewer to test Recognition. A moment, never a plot summary, and never a turning
point — no deaths, reveals, betrayals, endings or resolutions. Texture, not plot.
_Avoid_: question, prompt, clue, hint, synopsis

**Recognition**:
What a viewer reports when a probe feels familiar. Evidence that they watched the
episode, never proof — trailers, recaps, clips and cultural osmosis all
manufacture it.
_Avoid_: recall, memory, "yes"

**Verdict**:
The decision about one episode after its probes. Watched on any clear
Recognition; Frontier if any probe was answered "no" without one; Unresolved if
every answer was "not sure". A Frontier is Firm if every answer was "no", Soft
otherwise. An Unresolved episode does not stop the Walk by itself.
_Avoid_: score, confidence, probability, result

**Resume Window**:
The output. The episode to resume with, plus the last Watched episode as a
fallback because viewers often stop mid-episode and rewatching one is cheap.
Widens backward only when the Verdicts at the Frontier were Soft.
_Avoid_: resume point, stopping point, answer, result

**Frontier**:
The boundary between the episodes a viewer has watched and the ones they have
not. What the whole product is trying to locate.
_Avoid_: stopping point, where they left off, position

**Walk**:
The sequence of probes, moving forward from the start of a season toward the
Frontier. Never moves backward and never probes ahead of the current position.
_Avoid_: search, quiz, session, flow

**Coarse Pass**:
The first half of a Walk: probing forward from the start of the season at the
Stride, until the first episode the viewer does not recognise.
_Avoid_: search, scan, first pass

**Fine Pass**:
The second half of a Walk: probing the episodes the Coarse Pass skipped, one at
a time, forward from the last Watched episode. Never reaches past the episode
the viewer resumes with, so it costs no Leak.
_Avoid_: narrowing, refinement, drilling down

**Stride**:
How many episodes the Coarse Pass advances after each Watched verdict. Set from
season length, not chosen by the viewer. Stride − 1 is the most episodes past
the Frontier a probe can reach.
_Avoid_: step size, granularity, carefulness level

**Leak**:
A probe shown for an episode past the Frontier — a moment the viewer had not
yet seen. The thing Stride bounds and false Recognition causes.
_Avoid_: spoiler (too broad — a Leak is specifically a probe past the Frontier)

