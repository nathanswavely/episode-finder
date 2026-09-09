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
PROMPT = (ROOT / "pipeline/prompts/generate-v2.md").read_text()   # generous by default (2026-09-08); --prompt overrides


class Probe(BaseModel):
    text: str = Field(description="The probe: 12-25 words, present tense, third person")
    specificity: int = Field(ge=1, le=5, description="1 = could be several episodes, 5 = unmistakably this one")
    characters_named: list[str] = Field(description="Every character name that appears in the probe text")
    grounded_in: str = Field(description="Verbatim phrase from the target episode's summary this probe comes from")


class Candidates(BaseModel):
    probes: list[Probe] = Field(description="Up to 5, best first. May be empty.")
    note: str = Field(default="", description="Only if something about this episode made probes hard or impossible")


def make_client(provider: str):
    """Anthropic (default) or Meta Model API, which serves Muse Spark through an Anthropic-compatible
    Messages endpoint. META_API_KEY comes from .env; the contributor tier is the cheap one."""
    load_env()
    import os
    if provider == "meta":
        key = os.environ.get("META_API_KEY")
        if not key:
            sys.exit("META_API_KEY not set (put it in .env). Keys: https://dev.meta.ai/api-keys/")
        # Meta authenticates with "Authorization: Bearer", which the SDK sends for auth_token (not api_key)
        return anthropic.Anthropic(base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai"), auth_token=key)
    return anthropic.Anthropic()


def parse_json_text(text: str, schema):
    """Structured output without relying on output_format: find the JSON object in the reply and validate."""
    import json as _json, re as _re
    m = _re.search(r"\{.*\}", text, flags=_re.S)
    if not m:
        raise ValueError("no JSON object in reply")
    return schema.model_validate(_json.loads(m.group()))


def ask_structured(client, *, provider, model, effort, system, user, schema, max_tokens=4000):
    """One structured call. Anthropic: messages.parse with output_format, effort, cache_control.
    Meta: plain messages.create, schema described in the prompt, JSON parsed from the text."""
    if provider != "meta":
        r = client.messages.parse(model=model, max_tokens=max_tokens, output_config={"effort": effort},
                                  system=system, messages=[{"role": "user", "content": user}], output_format=schema)
        return r, r.parsed_output
    # Meta's Messages endpoint documents output_config.format and effort; try the same call without
    # cache_control (unknown there) and fall back to schema-in-prompt if it rejects the shape.
    plain_system = [{"type": "text", "text": b["text"]} for b in system] if isinstance(system, list) else system
    try:
        r = client.messages.parse(model=model, max_tokens=max_tokens, output_config={"effort": effort if effort != "max" else "xhigh"},
                                  system=plain_system, messages=[{"role": "user", "content": user}], output_format=schema)
        return r, r.parsed_output
    except anthropic.BadRequestError:
        pass
    sys_text = "\n\n".join(b["text"] for b in system) if isinstance(system, list) else system
    sys_text += ("\n\nRespond with a single JSON object and nothing else, matching this JSON schema exactly:\n"
                 + _json_dumps(schema.model_json_schema()))
    r = client.messages.create(model=model, max_tokens=max_tokens, system=sys_text,
                               messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return r, parse_json_text(text, schema)


def _json_dumps(o):
    import json as _json
    return _json.dumps(o, ensure_ascii=False)


def with_retry(fn, *, tries=7, base=5.0):
    """Anthropic 529/429 and transient network errors: exponential backoff, up to ~5 minutes total.
    The SDK's own 2 retries are not enough when the API is overloaded for a while."""
    import time
    for attempt in range(tries):
        try:
            return fn()
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError, anthropic.OverloadedError) as e:
            if attempt == tries - 1:
                raise
            wait = min(base * (2 ** attempt), 90)
            print(f"      ({type(e).__name__}; retrying in {wait:.0f}s)", file=sys.stderr)
            time.sleep(wait)


def pathlib_read(p):
    return (ROOT / p).read_text() if not p.startswith("/") else Path(p).read_text()


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
    ap.add_argument("--model", default=None, help="default: claude-opus-5, or muse-spark-1.3-contributor with --provider meta")
    ap.add_argument("--provider", default="anthropic", choices=["anthropic", "meta"])
    ap.add_argument("--prompt", help="alternative prompt file (default pipeline/prompts/generate.md)")
    ap.add_argument("--tag", help="output file tag (default: provider name for meta, none for anthropic)")
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

    a.model = a.model or ("muse-spark-1.3-contributor" if a.provider == "meta" else "claude-opus-5")
    global PROMPT
    if a.prompt:
        PROMPT = pathlib_read(a.prompt)
    client = make_client(a.provider)
    tag = f".{a.tag}" if a.tag else ("" if a.provider == "anthropic" else f".{a.provider}")
    out_path = ROOT / f"data/probes/{slug}/s{a.season:02d}{tag}.candidates.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_path.read_text()) if out_path.exists() else {"show": a.show, "slug": slug,
                                                                          "season": a.season, "model": a.model,
                                                                          "source": cur["source"], "episodes": {}}
    for ep in targets:
        if str(ep["episode"]) in results["episodes"] and not a.force:
            print(f"E{ep['episode']:>2} {ep['title']:<28} skipped (exists; --force to redo)")
            continue
        t0 = time.time()
        try:
            resp, cands = with_retry(lambda: ask_structured(client, provider=a.provider, model=a.model, effort=a.effort,
                                     system=system, user=build_user(cur, ep), schema=Candidates, max_tokens=16000))
        except anthropic.BadRequestError as e:
            if "content management policy" in str(e) or "filtered" in str(e):
                print(f"E{ep['episode']:>2} {ep['title']:<28} provider content filter refused this episode; skipped", file=sys.stderr)
                continue
            raise
        if getattr(resp, "stop_reason", "") == "refusal":
            print(f"E{ep['episode']}: refused", file=sys.stderr)
            continue
        results["episodes"][str(ep["episode"])] = {
            "title": ep["title"],
            "candidates": [{**p.model_dump(), "grounded_ok": grounded_ok(p, ep["summary"])} for p in cands.probes],
            "note": cands.note,
            "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                      "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                      "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0},
        }
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        ungrounded = sum(not c["grounded_ok"] for c in results["episodes"][str(ep["episode"])]["candidates"])
        print(f"E{ep['episode']:>2} {ep['title']:<28} {len(cands.probes)} candidates"
              f"{f', {ungrounded} ungrounded' if ungrounded else ''}"
              f"  [{time.time()-t0:.0f}s, cache_read={getattr(resp.usage, 'cache_read_input_tokens', 0) or 0}]"
              f"{'  note: ' + cands.note if cands.note else ''}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
