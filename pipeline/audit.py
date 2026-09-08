#!/usr/bin/env python3
"""Audit candidate probes and keep the survivors.

    python pipeline/audit.py --show "Breaking Bad" --season 4 --dry-run     # print the three prompts for the first candidate
    python pipeline/audit.py --show "Breaking Bad" --season 4 --episode 1
    python pipeline/audit.py --show "Breaking Bad" --season 4

Reads data/probes/<slug>/s<NN>.candidates.json (from generate.py) and data/raw.
Writes s<NN>.audit.json (every candidate, every check, every reason) and
s<NN>.probes.json: per episode, "probes" (safe when shown by the coarse pass, i.e. to a
viewer who has seen only e - stride) and "fine_only" (safe only given e - 1; the fine
pass may use them, the coarse pass must not).

Checks per candidate, in this order — first failure rejects:
  form         mechanical: 10-30 words, no "you"
  names        mechanical: every name in characters_named appears in a prior episode's summary,
               this season's main cast, or any of the previous season's cast (from the Wikipedia Cast section)
  reverse      LLM: shown the season's summaries unlabelled and shuffled, must pick the right one
  faithful     LLM: the probe adds no event, outcome, motive or character the summary doesn't support (elaboration is fine)
  consequence  LLM: shown only what a viewer has seen when the coarse pass can show this episode
               (episodes <= e - stride, NOT e - 1), does the probe reveal an outcome/turning point.
               Asked --votes times (default 2); any "reveals" rejects. Borderline cases were
               observed to flip between runs, and the safe direction is to reject.
"""
import argparse
import json
import random
import re
import sys
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
KEEP = 3


class ReverseLookup(BaseModel):
    letter: str = Field(description="The single letter of the episode this moment belongs to")
    confidence: int = Field(ge=1, le=5, description="5 = only one episode fits, 1 = several fit about equally")


class Faithful(BaseModel):
    faithful: bool = Field(description="False only if the probe adds an event, outcome, motive, character or contradiction the summary does not support")
    unsupported: list[str] = Field(default_factory=list, description="Only the details that change what happened; not sensory or manner elaboration")


class Consequence(BaseModel):
    reveals: bool = Field(description="True if the probe reveals an outcome, turning point, or the answer to an open question")
    reason: str = Field(default="", description="One sentence: what it reveals, or why it is safe")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


# --- mechanical checks -----------------------------------------------------

def check_form(text: str, title: str) -> str | None:
    n = len(text.split())
    if not 10 <= n <= 30:
        return f"form: {n} words"
    if re.search(r"\byou\b", text, re.I):
        return "form: second person"
    return None


def prior_text(cur: dict, prev: dict | None, episode: int) -> str:
    parts = [e["summary"] for e in (prev or {}).get("episodes", [])]
    parts += [e["summary"] for e in cur["episodes"] if e["episode"] < episode]
    return " ".join(parts)


def season_stride(cur: dict) -> int:
    return 2 if len(cur["episodes"]) <= 16 else 3


def consequence_blocks(cur: dict, prev: dict | None, episode: int) -> list[dict]:
    """System blocks for the consequence check: what a viewer is assumed to have seen when this
    episode's probe is shown. The coarse pass can show episode e to a viewer who has only seen
    e - stride, so that is the context — NOT e - 1. One block per episode so prompt caching
    reuses the shared prefix across the season's checks."""
    known_upto = episode - season_stride(cur)
    blocks = [{"type": "text", "text": CONSEQUENCE_SYSTEM}]
    if prev:
        blocks.append({"type": "text", "text": "Previous season:\n" + "\n\n".join(e["summary"] for e in prev["episodes"])})
    for e in cur["episodes"]:
        if e["episode"] <= known_upto:
            blocks.append({"type": "text", "text": f"Episode {e['episode']}:\n{e['summary']}"})
    if len(blocks) == 1:
        blocks.append({"type": "text", "text": "(The viewer has not seen any episode of this series yet.)"})
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def norm(s: str) -> str:
    """Loose text normalisation for substring checks: quotes, dashes, ellipses, whitespace, case."""
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


def cast_tokens(cur: dict, prev: dict | None) -> set[str]:
    """Names a probe may use regardless of summaries: this season's main cast (on the poster) and
    every character listed for the previous season. Recurring characters introduced this season are
    not included — they must appear in an earlier summary first."""
    names = list((cur.get("cast") or {}).get("main", []))
    if prev:
        c = prev.get("cast") or {}
        names += c.get("main", []) + c.get("recurring", [])
    toks = set()
    for n in names:
        toks.update(re.findall(r"[A-Za-z][A-Za-z'\-]+", n))
    return toks


def check_names(names: list[str], prior: str, allowed: set[str] = frozenset()) -> str | None:
    if not prior.strip():
        return None   # series premiere: nothing precedes it, so nobody is "new" in a way that leaks
    words = set(re.findall(r"[A-Za-z][A-Za-z'\-]+", prior)) | set(allowed)
    missing = [n for n in names if not any(tok in words for tok in n.split())]
    return f"names: not in prior episodes: {', '.join(missing)}" if missing else None


# --- prompts ---------------------------------------------------------------

def reverse_context(cur: dict, seed: int) -> tuple[str, dict]:
    """Season summaries, unlabelled, shuffled once per season. Returns (text, letter->episode)."""
    eps = list(cur["episodes"])
    random.Random(seed).shuffle(eps)
    letters = {chr(ord("A") + i): e["episode"] for i, e in enumerate(eps)}
    text = "\n\n".join(f"[{chr(ord('A') + i)}]\n{e['summary']}" for i, e in enumerate(eps))
    return text, letters


REVERSE_SYSTEM = (
    "Below are the plot summaries of every episode in one season of a TV series, in random order, "
    "labelled with letters. You will be given a short description of a moment. Decide which single "
    "episode it belongs to. If it could plausibly belong to more than one, say so with a low confidence.\n\n"
)

FAITHFUL_SYSTEM = (
    "You will be given an episode's plot summary and a one-sentence description of a moment that claims "
    "to come from it. The sentence is allowed to describe the moment the way a viewer would see it — where "
    "it happens, what it looks like, how someone behaves, how long it takes — even when the summary does "
    "not spell those details out. Reject it only if it adds something the summary does not support that "
    "would change what a viewer thinks HAPPENED: a new action or event, an outcome, a motive or intention, "
    "a character the summary does not place in this moment, or a claim that contradicts the summary. "
    "Sensory, spatial and manner elaboration is fine. List only the details that fail this test."
)

CONSEQUENCE_SYSTEM = (
    "A viewer has watched every episode summarised below, and nothing after. They are about to be shown "
    "one sentence describing a moment from the NEXT episode, which they have not seen. Decide whether "
    "that sentence reveals anything that matters: a death, injury, arrest, discovery, reveal, betrayal, "
    "confession, breakup, new alliance, the outcome of a conflict the viewer knows is pending, or the "
    "answer to a question the story has left open. Ordinary situations, settings, activities and character "
    "texture are safe. Be strict about outcomes and lenient about texture.\n\n"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--episode", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--votes", type=int, default=2, help="Consequence check runs this many times; any 'reveals' rejects")
    ap.add_argument("--recheck", action="store_true",
                    help="Only re-run the consequence check on current survivors in probes.json (stride-aware context)")
    a = ap.parse_args()

    slug = slugify(a.show)
    cur = load(ROOT / f"data/raw/{slug}/s{a.season:02d}.json")
    prev = load(ROOT / f"data/raw/{slug}/s{a.season-1:02d}.json") if a.season > 1 else None
    cands = load(ROOT / f"data/probes/{slug}/s{a.season:02d}.candidates.json")
    if not (cur and cands):
        sys.exit("need data/raw season file and candidates file — run fetch.py and generate.py first")
    by_ep = {e["episode"]: e for e in cur["episodes"]}
    allowed_names = cast_tokens(cur, prev)

    rev_text, letters = reverse_context(cur, seed=a.season)
    ep_of_letter = letters
    letter_of_ep = {v: k for k, v in letters.items()}
    rev_system = [{"type": "text", "text": REVERSE_SYSTEM + rev_text, "cache_control": {"type": "ephemeral"}}]

    episodes = sorted(int(k) for k in cands["episodes"] if not a.episode or int(k) == a.episode)
    if not episodes:
        sys.exit("no candidates for that episode")

    if a.dry_run:
        ep = episodes[0]
        c = cands["episodes"][str(ep)]["candidates"][0]
        print("=== REVERSE (system, truncated) ===\n", rev_system[0]["text"][:600], "...\n")
        print("=== REVERSE (user) ===\nMoment: " + c["text"] + "\n")
        print("=== FAITHFUL (user) ===\nSummary:\n" + by_ep[ep]["summary"] + "\n\nMoment: " + c["text"] + "\n")
        print("=== CONSEQUENCE (system, truncated) ===\n", (CONSEQUENCE_SYSTEM + prior_text(cur, prev, ep))[:600], "...\n")
        print("=== CONSEQUENCE (user) ===\nMoment: " + c["text"])
        return

    load_env()
    client = anthropic.Anthropic()
    audit_path = ROOT / f"data/probes/{slug}/s{a.season:02d}.audit.json"
    probes_path = ROOT / f"data/probes/{slug}/s{a.season:02d}.probes.json"
    audit = load(audit_path) or {"show": a.show, "slug": slug, "season": a.season, "model": a.model, "episodes": {}}
    probes = load(probes_path) or {"show": a.show, "slug": slug, "season": a.season,
                                   "source": cands["source"], "episodes": {}}

    spend = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "calls": 0}

    def ask(system, user, schema, _retry=True):
        try:
            r = client.messages.parse(model=a.model, max_tokens=4000, output_config={"effort": a.effort},
                                      system=system, messages=[{"role": "user", "content": user}], output_format=schema)
        except Exception as e:  # seen once: a degenerate run of newlines hit max_tokens and truncated the JSON
            if _retry and "json" in str(e).lower():
                print(f"      (malformed structured output, retrying once)", file=sys.stderr)
                return ask(system, user, schema, _retry=False)
            raise
        u = r.usage
        spend["in"] += u.input_tokens; spend["out"] += u.output_tokens; spend["calls"] += 1
        spend["cache_read"] += u.cache_read_input_tokens or 0; spend["cache_write"] += u.cache_creation_input_tokens or 0
        if r.stop_reason == "refusal":
            raise RuntimeError(f"refusal: {r.stop_details and r.stop_details.category}")
        return r.parsed_output

    if a.recheck:
        if not probes["episodes"]:
            sys.exit("nothing to recheck")
        dropped = kept = 0
        for ep in sorted(int(k) for k in probes["episodes"] if not a.episode or int(k) == a.episode):
            entry = probes["episodes"][str(ep)]
            cons_system = consequence_blocks(cur, prev, ep)
            keep, fine_only = [], list(entry.get("fine_only", []))
            for pr in entry["probes"]:
                votes = [ask(cons_system, f"Moment: {pr['text']}", Consequence) for _ in range(a.votes)]
                if any(v.reveals for v in votes):
                    # safe at e-1 (it passed the full audit) but not at e-stride: usable in the fine pass only
                    dropped += 1
                    reason = next(v.reason for v in votes if v.reveals)
                    print(f"E{ep:>2} → fine-only: {pr['text'][:66]}…\n      {reason[:120]}")
                    audit.setdefault("recheck", []).append({"episode": ep, "text": pr["text"], "reason": reason})
                    fine_only.append(pr)
                else:
                    keep.append(pr); kept += 1
            entry["probes"] = keep
            entry["fine_only"] = fine_only
            probes_path.write_text(json.dumps(probes, indent=2, ensure_ascii=False))
        audit["recheck_spend"] = spend
        audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
        counts = sorted(len(v["probes"]) for v in probes["episodes"].values())
        est = (spend["in"] * 5 + spend["out"] * 25 + spend["cache_read"] * 0.5 + spend["cache_write"] * 6.25) / 1e6
        print(f"recheck: coarse-safe {kept}, fine-only {dropped}; median {counts[len(counts)//2]}, min {counts[0]}; {spend['calls']} calls, ~${est:.2f}")
        return

    for ep in episodes:
        entry = cands["episodes"][str(ep)]
        title = entry["title"]
        prior = prior_text(cur, prev, ep)
        cons_system = consequence_blocks(cur, prev, ep)
        results, survivors = [], []
        for c in entry["candidates"]:
            rec = {"text": c["text"], "checks": {}, "rejected": None}
            reason = check_form(c["text"], title) or check_names(c["characters_named"], prior, allowed_names)
            if not reason and not grounded(c.get("grounded_in", ""), by_ep[ep]["summary"]):
                reason = "grounding: quote not found in summary"
            if reason:
                rec["rejected"] = reason
            else:
                rl = ask(rev_system, f"Moment: {c['text']}", ReverseLookup)
                rec["checks"]["reverse"] = {"picked": ep_of_letter.get(rl.letter.strip().upper()),
                                            "confidence": rl.confidence}
                if rec["checks"]["reverse"]["picked"] != ep:
                    rec["rejected"] = f"reverse: picked E{rec['checks']['reverse']['picked']} (conf {rl.confidence})"
                elif rl.confidence <= 3:
                    rec["rejected"] = f"reverse: correct but not distinctive (conf {rl.confidence})"
            if not rec["rejected"]:
                f = ask(FAITHFUL_SYSTEM, f"Summary:\n{by_ep[ep]['summary']}\n\nMoment: {c['text']}", Faithful)
                rec["checks"]["faithful"] = f.model_dump()
                if not f.faithful:
                    rec["rejected"] = "faithful: " + "; ".join(f.unsupported)
            if not rec["rejected"]:
                votes = [ask(cons_system, f"Moment: {c['text']}", Consequence) for _ in range(a.votes)]
                rec["checks"]["consequence"] = {"votes": [v.model_dump() for v in votes],
                                                "reason": next((v.reason for v in votes if v.reveals), votes[0].reason)}
                if any(v.reveals for v in votes):
                    n = sum(v.reveals for v in votes)
                    rec["rejected"] = f"consequence ({n}/{len(votes)}): " + rec["checks"]["consequence"]["reason"]
            results.append(rec)
            if not rec["rejected"] and len(survivors) < KEEP:
                survivors.append({"text": c["text"], "specificity": c["specificity"],
                                  "reverse_confidence": rec["checks"]["reverse"]["confidence"]})
        audit["episodes"][str(ep)] = {"title": title, "candidates": results}
        probes["episodes"][str(ep)] = {"title": title, "probes": survivors}
        audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
        probes_path.write_text(json.dumps(probes, indent=2, ensure_ascii=False))
        print(f"E{ep:>2} {title:<28} {len(survivors)}/{len(results)} survive")
        for r in results:
            if r["rejected"]:
                print(f"      ✗ {r['text'][:70]}…\n        {r['rejected']}")

    counts = [len(v["probes"]) for v in probes["episodes"].values()]
    if counts:
        counts.sort()
        print(f"\nmedian survivors/episode: {counts[len(counts)//2]}  (min {counts[0]}, episodes audited {len(counts)})")
    audit["spend"] = spend
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    est = (spend["in"] * 5 + spend["out"] * 25 + spend["cache_read"] * 0.5 + spend["cache_write"] * 6.25) / 1e6
    print(f"{spend['calls']} calls, ~${est:.2f} at Opus 5 list prices")
    print(f"-> {audit_path}\n-> {probes_path}")


if __name__ == "__main__":
    main()
