# Jump Back In

You watched a show years ago, got partway in, and can't remember where. This
asks you a few questions about moments from the show and tells you which
episode to resume from — without revealing anything you haven't seen.

Static site, no backend, no accounts. Probes are precomputed from Wikipedia
episode summaries (CC BY-SA 4.0) and shipped as JSON.

- Design: [docs/PROPOSAL.md](docs/PROPOSAL.md), [docs/FLOW.md](docs/FLOW.md), [docs/adr/](docs/adr/)
- Vocabulary: [CONTEXT.md](CONTEXT.md)
- Pilot record: [docs/PILOT.md](docs/PILOT.md)

## Pipeline

```bash
python3 -m venv .venv && .venv/bin/pip install anthropic
export ANTHROPIC_API_KEY=...

.venv/bin/python pipeline/fetch.py    --show "Breaking Bad" --season 4   # Wikipedia -> data/raw
.venv/bin/python pipeline/generate.py --show "Breaking Bad" --season 4   # candidates -> data/probes
.venv/bin/python pipeline/audit.py    --show "Breaking Bad" --season 4   # survivors  -> data/probes
.venv/bin/python pipeline/build_site.py                                  # -> site/data
```

Fetch a show's previous season too — the walk opens on its finale, and
"prior characters" for episode 1 come from it.

`pipeline/walk.py` runs the walk in a terminal (`--simulate all` checks every
possible stopping point against the shipped probes).

## Site

`site/` is plain HTML/JS. Serve it from anywhere static:

```bash
python3 -m http.server 8765 --directory site
```

Live at https://jumpbackin.show (Worker: episode-finder), deployed by Cloudflare
Workers Builds on every push to `main` (`wrangler.jsonc`: assets-only Worker
serving `site/`). The GitHub Pages workflow still runs in parallel until a
custom domain replaces the old URL.
