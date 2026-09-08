#!/usr/bin/env python3
"""Generate candidate probes for one season from data/raw, into data/probes/<slug>/s<NN>.candidates.json.

    python pipeline/generate.py --show "Breaking Bad" --season 4 --dry-run          # print the prompt for E1, no API call
    python pipeline/generate.py --show "Breaking Bad" --season 4 --episode 1        # one episode
    python pipeline/generate.py --show "Breaking Bad" --season 4                    # whole season

Reads the previous season from data/raw if present, so "prior characters" and
"previously" context are correct for episode 1. Prompt text lives in
pipeline/prompts/generate.md — edit that, not this file. Freeze it before
generating the blind set (see docs/PILOT.md).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Read KEY=VALUE lines from .env at the repo root into the environment (no override)."""
    import os
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
PROMPT = (ROOT / "pipeline/prompts/generate.md").read_text()


class Probe(BaseModel):
    text: str = Field(description="The probe: 12-25 words, present tense, third person")
    specificity: int = Field(ge=1, le=5, description="1 = could be several episodes, 5 = unmistakably this one")
    characters_named: list[str] = Field(description="Every character name that appears in the probe text")
    grounded_in: str = Field(description="Verbatim phrase from the target episode's summary this probe comes from")


class Candidates(BaseModel):
    probes: list[Probe] = Field(description="Up to 5, best first. May be empty.")
    note: str = Field(default="", description="Only if something about this episode made probes hard or impossible")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_season(slug: str, season: int) -> dict | None:
    p = ROOT / f"data/raw/{slug}/s{season:02d}.json"
    return json.loads(p.read_text()) if p.exists() else None


def season_block(d: dict, tag: str) -> str:
    lines = [f"<{tag} season=\"{d['season']}\">"]
    for e in d["episodes"]:
        lines.append(f"Episode {e['episode']} — {e['title']}\n{e['summary']}\n")
    lines.append(f"</{tag}>")
    return "\n".join(lines)


def build_system(cur: dict, prev: dict | None) -> list[dict]:
    """Stable per-season context, cached across the season's episode calls."""
    context = season_block(cur, "season")
    if prev:
        context = season_block(prev, "previous_season") + "\n\n" + context
    return [
        {"type": "text", "text": PROMPT},
        {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
    ]


def build_user(cur: dict, ep: dict) -> str:
    return (f"Target: season {cur['season']}, episode {ep['episode']} — \"{ep['title']}\".\n"
            f"Write up to 5 probes for this episode only.")


def norm(s: str) -> str:
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2014", "-"), ("\u2013", "-"), ("\u2026", "...")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s.lower()).strip()


def grounded(quote: str, summary: str, threshold: float = 0.75) -> bool:
    """Cheap hallucination guard: enough of the quote's words appear in the summary.
    The model may compress a quote by a word or two; exact substring is too brittle.
    The faithfulness LLM check judges the probe itself against the summary."""
    q = [w for w in re.findall(r"[a-z0-9']+", norm(quote)) if len(w) > 2]
    if not q:
        return False
    s = set(re.findall(r"[a-z0-9']+", norm(summary)))
    return sum(w in s for w in q) / len(q) >= threshold


def grounded_ok(probe: Probe, summary: str) -> bool:
    return grounded(probe.grounded_in, summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--episode", type=int, help="Only this episode")
    ap.add_argument("--dry-run", action="store_true", help="Print the prompt for the first target and exit")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--force", action="store_true", help="Regenerate episodes that already have candidates")
    a = ap.parse_args()

    slug = slugify(a.show)
    cur = load_season(slug, a.season)
    if not cur:
        sys.exit(f"No data/raw/{slug}/s{a.season:02d}.json — run pipeline/fetch.py first")
    prev = load_season(slug, a.season - 1) if a.season > 1 else None
    if a.season > 1 and not prev:
        print(f"warning: no previous season file; 'prior characters' for E1 will only see this season", file=sys.stderr)

    targets = [e for e in cur["episodes"] if not a.episode or e["episode"] == a.episode]
    system = build_system(cur, prev)

    if a.dry_run:
        print("=== SYSTEM ===")
        for block in system:
            print(block["text"], "\n")
        print("=== USER ===")
        print(build_user(cur, targets[0]))
        return

    load_env()
    client = anthropic.Anthropic()
    out_path = ROOT / f"data/probes/{slug}/s{a.season:02d}.candidates.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_path.read_text()) if out_path.exists() else {"show": a.show, "slug": slug,
                                                                          "season": a.season, "model": a.model,
                                                                          "source": cur["source"], "episodes": {}}
    for ep in targets:
        if str(ep["episode"]) in results["episodes"] and not a.force:
            print(f"E{ep['episode']:>2} {ep['title']:<28} skipped (exists; --force to redo)")
            continue
        t0 = time.time()
        resp = client.messages.parse(
            model=a.model,
            max_tokens=16000,
            output_config={"effort": a.effort},
            system=system,
            messages=[{"role": "user", "content": build_user(cur, ep)}],
            output_format=Candidates,
        )
        if resp.stop_reason == "refusal":
            print(f"E{ep['episode']}: refused ({resp.stop_details and resp.stop_details.category})", file=sys.stderr)
            continue
        cands: Candidates = resp.parsed_output
        results["episodes"][str(ep["episode"])] = {
            "title": ep["title"],
            "candidates": [{**p.model_dump(), "grounded_ok": grounded_ok(p, ep["summary"])} for p in cands.probes],
            "note": cands.note,
            "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                      "cache_read": resp.usage.cache_read_input_tokens,
                      "cache_write": resp.usage.cache_creation_input_tokens},
        }
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        ungrounded = sum(not c["grounded_ok"] for c in results["episodes"][str(ep["episode"])]["candidates"])
        print(f"E{ep['episode']:>2} {ep['title']:<28} {len(cands.probes)} candidates"
              f"{f', {ungrounded} ungrounded' if ungrounded else ''}"
              f"  [{time.time()-t0:.0f}s, cache_read={resp.usage.cache_read_input_tokens}]"
              f"{'  note: ' + cands.note if cands.note else ''}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
