#!/usr/bin/env python3
"""Evaluate a consequence-check prompt on a provider against Opus's verdicts as labels.

    python pipeline/eval_consequence.py --show "Breaking Bad" --season 4 --provider meta [--variant v2]

Labels come from data/probes/<slug>/s<NN>.audit.json (an Opus audit of Opus candidates):
  leak = rejected on consequence, or moved to fine-only by the stride-aware recheck
  safe = a coarse-safe survivor
Each item is judged with the stride-aware context (episodes <= e - stride). Reports recall on
leaks (the number that matters: a missed leak ships a spoiler) and precision.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit as A  # noqa: E402  (reuse prompts, context builder, client, schema)

V2_SYSTEM = (
    "A viewer has watched every episode summarised below, and nothing after. They are about to be shown "
    "one sentence describing a moment from an episode they have NOT seen.\n\n"
    "Work in two steps. First, list every fact in the sentence that the viewer does not already know from "
    "the summaries below: events, outcomes, who is where, who is alive, who is working with whom, what a plan "
    "led to, what a character has learned. Second, decide whether any listed fact is one that matters: a death, "
    "injury, arrest, discovery, reveal, betrayal, confession, breakup, new alliance, the outcome of a conflict "
    "the viewer knows is pending, or the answer to a question the story has left open. Ordinary settings, "
    "activities and character texture do not matter, even if new. Be strict about outcomes.\n\n"
)


class V2(A.Consequence):
    new_facts: list[str] = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--provider", default="meta", choices=["anthropic", "meta"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--variant", default="v1", choices=["v1", "v2"])
    ap.add_argument("--effort", default="medium")
    a = ap.parse_args()
    a.model = a.model or ("muse-spark-1.3-contributor" if a.provider == "meta" else "claude-opus-5")

    slug = A.slugify(a.show)
    cur = A.load(A.ROOT / f"data/raw/{slug}/s{a.season:02d}.json")
    prev = A.load(A.ROOT / f"data/raw/{slug}/s{a.season-1:02d}.json") if a.season > 1 else None
    aud = A.load(A.ROOT / f"data/probes/{slug}/s{a.season:02d}.audit.json")
    probes = A.load(A.ROOT / f"data/probes/{slug}/s{a.season:02d}.probes.json")

    items = []
    fine_texts = {p["text"] for v in probes["episodes"].values() for p in v.get("fine_only", [])}
    for ep, e in aud["episodes"].items():
        for c in e["candidates"]:
            r = c["rejected"] or ""
            if r.startswith("consequence") or c["text"] in fine_texts:
                items.append((int(ep), c["text"], "leak"))
            elif not r and c["text"] not in fine_texts:
                items.append((int(ep), c["text"], "safe"))
    print(f"{len(items)} labelled items: {sum(l=='leak' for _,_,l in items)} leak, {sum(l=='safe' for _,_,l in items)} safe")

    client = A.make_client(a.provider)
    tp = fp = fn = tn = 0
    misses = []
    for ep, text, label in sorted(items):
        blocks = A.consequence_blocks(cur, prev, ep)
        if a.variant == "v2":
            blocks = [{"type": "text", "text": V2_SYSTEM}] + blocks[1:]
            schema = V2
        else:
            schema = A.Consequence
        _, out = A.ask_structured(client, provider=a.provider, model=a.model, effort=a.effort,
                                  system=blocks, user=f"Moment: {text}", schema=schema)
        pred = "leak" if out.reveals else "safe"
        if label == "leak" and pred == "leak": tp += 1
        elif label == "leak": fn += 1; misses.append((ep, text, out.reason))
        elif pred == "leak": fp += 1
        else: tn += 1
    rec = tp / max(1, tp + fn); prec = tp / max(1, tp + fp)
    print(f"\n{a.provider} {a.model} {a.variant}: leak recall {rec:.0%} ({tp}/{tp+fn}), precision {prec:.0%}, false alarms {fp}/{fp+tn} of safe")
    for ep, text, reason in misses:
        print(f"  MISSED E{ep}: {text[:80]}…\n      model said: {reason[:110]}")


if __name__ == "__main__":
    main()
