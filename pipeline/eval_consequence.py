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


V3_SYSTEM = (
    "You will be given a season's episode summaries (the viewer has seen the earlier ones), the summary of "
    "one later episode the viewer has NOT seen, and a one-sentence moment from that episode. Answer three "
    "separate questions, each on its own:\n"
    "1. summary_sentence: copy the sentence (or clause) of the unseen episode's summary that this moment comes from.\n"
    "2. is_outcome: is that sentence an event with consequences (a death, injury, arrest, discovery, reveal, "
    "betrayal, confession, breakup, alliance, a plan carried out, a conflict resolved, a character's situation "
    "changing), or is it texture (a setting, an errand, a habit, a mood, a routine)? Ordinary activity is texture "
    "even when it is dramatic to watch.\n"
    "3. already_known: does that same event, or the fact it implies, already appear in the summaries the viewer "
    "HAS seen? Only answer yes if the earlier summaries state it; the viewer knowing the setup is not the same as "
    "knowing the outcome.\n\n"
)


class V3(A.BaseModel):
    summary_sentence: str
    is_outcome: bool
    already_known: bool
    reason: str = ""


def fewshot_block(train):
    lines = ["Worked examples from another audit of this show, with the correct verdicts:\n"]
    for ep, text, label, why in train:
        lines.append(f'- Moment (episode {ep}): "{text}"\n  Verdict: {"REVEALS" if label == "leak" else "safe"}. {why}')
    return "\n".join(lines) + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--provider", default="meta", choices=["anthropic", "meta"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--variant", default="v1", choices=["v1", "v2", "v3", "v4"])
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--votes", type=int, default=1, help="majority of N samples")
    ap.add_argument("--split", default="all", choices=["all", "test"], help="'test' scores only the held-out half")
    a = ap.parse_args()
    a.model = a.model or ("muse-spark-1.3-contributor" if a.provider == "meta" else "claude-opus-5")

    slug = A.slugify(a.show)
    cur = A.load(A.ROOT / f"data/raw/{slug}/s{a.season:02d}.json")
    prev = A.load(A.ROOT / f"data/raw/{slug}/s{a.season-1:02d}.json") if a.season > 1 else None
    aud = A.load(A.ROOT / f"data/probes/{slug}/s{a.season:02d}.audit.json")
    probes = A.load(A.ROOT / f"data/probes/{slug}/s{a.season:02d}.probes.json")

    items = []
    fine_texts = {p["text"] for v in probes["episodes"].values() for p in v.get("fine_only", [])}
    recheck_reason = {r["text"]: r["reason"] for r in aud.get("recheck", [])}
    for ep, e in aud["episodes"].items():
        for c in e["candidates"]:
            r = c["rejected"] or ""
            why = (r.split(": ", 1)[1] if ": " in r else recheck_reason.get(c["text"], "")) or c["checks"].get("consequence", {}).get("reason", "")
            if r.startswith("consequence") or c["text"] in fine_texts:
                items.append((int(ep), c["text"], "leak", why[:160]))
            elif not r and c["text"] not in fine_texts:
                items.append((int(ep), c["text"], "safe", why[:160]))
    import hashlib
    half = lambda text: int(hashlib.md5(text.encode()).hexdigest(), 16) % 2
    train = [i for i in items if half(i[1]) == 0]
    test = [i for i in items if half(i[1]) == 1]
    scored = test if a.split == "test" else items
    print(f"{len(items)} labelled items ({sum(l=='leak' for _,_,l,_ in items)} leak); scoring {len(scored)} "
          f"({sum(l=='leak' for _,_,l,_ in scored)} leak); few-shot pool {len(train)}")
    by_ep = {e["episode"]: e for e in cur["episodes"]}

    client = A.make_client(a.provider)
    tp = fp = fn = tn = 0
    misses = []
    for ep, text, label, _why in sorted(scored):
        blocks = A.consequence_blocks(cur, prev, ep)
        user = f"Moment: {text}"
        if a.variant == "v2":
            blocks = [{"type": "text", "text": V2_SYSTEM}] + blocks[1:]; schema = V2
        elif a.variant == "v3":
            blocks = [{"type": "text", "text": V3_SYSTEM}] + blocks[1:] + [{"type": "text", "text": f"Unseen episode's summary:\n{by_ep[ep]['summary']}"}]
            schema = V3
        elif a.variant == "v4":
            ex = [i for i in train if i[1] != text]
            blocks = [{"type": "text", "text": A.CONSEQUENCE_SYSTEM + fewshot_block(ex)}] + blocks[1:]; schema = A.Consequence
        else:
            schema = A.Consequence
        votes = []
        errors = 0
        for _ in range(a.votes):
            try:
                _, out = A.ask_structured(client, provider=a.provider, model=a.model, effort=a.effort,
                                          system=blocks, user=user, schema=schema)
            except Exception as e:   # filtered / malformed reply: count as "reveals" (unverifiable = reject)
                errors += 1
                votes.append(True)
                out = type("O", (), {"reveals": True, "reason": f"provider error: {type(e).__name__}"})()
                continue
            if a.variant == "v3":
                votes.append(out.is_outcome and not out.already_known)
                out.reason = f"outcome={out.is_outcome} known={out.already_known} | {out.summary_sentence[:60]}"
            else:
                votes.append(bool(out.reveals))
        reveals = sum(votes) * 2 > len(votes) if a.votes > 1 else votes[0]
        if a.votes > 1 and sum(votes) * 2 == len(votes):
            reveals = True   # ties go to safety
        pred = "leak" if reveals else "safe"
        if label == "leak" and pred == "leak": tp += 1
        elif label == "leak": fn += 1; misses.append((ep, text, out.reason))
        elif pred == "leak": fp += 1
        else: tn += 1
    rec = tp / max(1, tp + fn); prec = tp / max(1, tp + fp)
    print(f"(provider errors counted as reveals: {sum(1 for _ in [])})") if False else None
    print(f"\n{a.provider} {a.model} {a.variant}: leak recall {rec:.0%} ({tp}/{tp+fn}), precision {prec:.0%}, false alarms {fp}/{fp+tn} of safe")
    for ep, text, reason in misses:
        print(f"  MISSED E{ep}: {text[:80]}…\n      model said: {reason[:110]}")


if __name__ == "__main__":
    main()
