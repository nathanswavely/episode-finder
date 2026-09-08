#!/usr/bin/env python3
"""Walk a show — the reference implementation of docs/FLOW.md and the pilot harness.

    python pipeline/walk.py --show "Breaking Bad" --season 4                    # interactive: y / u / n
    python pipeline/walk.py --show "Breaking Bad" --season unsure               # season-finder first
    python pipeline/walk.py --show "Breaking Bad" --season 4 --simulate 7       # perfect-memory viewer, stopped after E7
    python pipeline/walk.py --show "Breaking Bad" --season 4 --simulate 7 --hazy 3-7   # ...but "not sure" on E3–E7
    python pipeline/walk.py --show "Breaking Bad" --season 4 --simulate all     # every frontier, as a table
    python pipeline/walk.py --show "Breaking Bad" --season unsure --simulate 3:7  # finder, viewer stopped at S3E7

Reads every data/probes/<slug>/s*.probes.json for the show. Interactive walks are logged to data/walks/.
site/app.js mirrors this file; change both.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

K = 3               # coarse-pass probes per episode (coarse-safe tier only)
K_FINE = 5          # fine pass may also draw on fine-only probes
MAX_HAZY_RUN = 4    # consecutive "unresolved" episodes before we stop and report softly
MAX_QUESTIONS = 25  # hard cap per walk

WATCHED, FRONTIER, UNKNOWN, UNRESOLVED = "watched", "frontier", "unknown", "unresolved"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_show(slug: str) -> dict:
    """{season_number: {episode_number: {title, probes, fine_only}}}"""
    seasons = {}
    for p in sorted((ROOT / f"data/probes/{slug}").glob("s*.probes.json")):
        if not re.fullmatch(r"s\d{2}\.probes\.json", p.name):
            continue   # tagged files are experiments
        d = json.loads(p.read_text())
        seasons[d["season"]] = {int(k): v for k, v in d["episodes"].items()}
    return seasons


class Walk:
    """answer(season, episode, probe_text) -> "clear" | "unsure" | "no"
       consent(season, episode) -> bool   (asked when an episode is unresolved: keep going?)"""

    def __init__(self, seasons: dict, answer, consent):
        self.seasons = seasons
        self.answer, self._consent = answer, consent
        self.log, self.shown = [], set()
        self.consented = None            # asked once per walk, then remembered

    def consent(self, season, ep) -> bool:
        if self.consented is None:
            self.consented = self._consent(season, ep)
        return self.consented

    # --- primitives --------------------------------------------------------

    def stride(self, season: int) -> int:
        return 2 if len(self.seasons[season]) <= 16 else 3

    def budget_left(self) -> bool:
        return len(self.log) < MAX_QUESTIONS

    def verdict(self, season: int, ep: int, probes: list, k: int) -> tuple[str, bool]:
        fresh = [p for p in probes if p["text"] not in self.shown][:k]
        if not fresh:
            return UNKNOWN, False
        answers = []
        for p in fresh:
            if not self.budget_left():
                break
            a = self.answer(season, ep, p["text"])
            self.shown.add(p["text"])
            self.log.append({"season": season, "episode": ep, "probe": p["text"], "answer": a})
            answers.append(a)
            if a == "clear":
                return WATCHED, False
        if not answers:
            return UNKNOWN, False
        if all(a == "unsure" for a in answers):
            return UNRESOLVED, True
        return FRONTIER, any(a == "unsure" for a in answers)

    def coarse_probes(self, season, ep):
        return self.seasons[season].get(ep, {}).get("probes", [])

    def fine_probes(self, season, ep):
        e = self.seasons[season].get(ep, {})
        return e.get("probes", []) + e.get("fine_only", [])

    def next_probed(self, season: int, e: int):
        """Aim for e+stride; step back toward e if that episode has no coarse-safe probes; never reach beyond."""
        n, st = max(self.seasons[season]), self.stride(season)
        for c in range(min(e + st, n), e, -1):
            if self.coarse_probes(season, c):
                return c
        return None

    # --- season finder -----------------------------------------------------

    def find_season(self) -> dict:
        """Stride-1 walk over the first `stride` episodes of each season (all coarse-safe, hence safe for
        someone who has not started the season). Returns the season to walk, or None if never started."""
        watched, hazy = None, []
        for s in sorted(self.seasons):
            st = self.stride(s)
            probes = [p for e in range(1, st + 1) if e in self.seasons[s] for p in self.coarse_probes(s, e)][:K + 1]
            v, _ = self.verdict(s, 1, probes, K + 1)
            if v == WATCHED:
                watched, hazy = s, []
            elif v == UNRESOLVED:
                hazy.append(s)
                if len(hazy) >= MAX_HAZY_RUN or not self.consent(s, 1):
                    break
            elif v == FRONTIER:
                break
            # UNKNOWN (no probes at all for the season's opening): skip it
        # a hazy season is the one to walk — the viewer may well have seen it
        return {"season": hazy[0] if hazy else watched, "hazy": bool(hazy), "log": self.log}

    # --- one season --------------------------------------------------------

    def run(self, season: int, *, prior_check=True, assume_watched_through=0) -> dict:
        eps = self.seasons[season]
        n = max(eps)
        result = {"season": season, "stride": self.stride(season)}

        prev = season - 1 if season - 1 in self.seasons else None
        if prev and prior_check and not assume_watched_through:
            fin = max(self.seasons[prev])
            v, _ = self.verdict(prev, fin, self.coarse_probes(prev, fin), K)
            if v == FRONTIER:
                return self.finish(result, outcome="back_up", prev_season=prev,
                                   message=f"Doesn't look like you finished season {prev}. Try that one.")

        # coarse pass — always opens on the premiere unless we've been told it was watched
        last, frontier, soft, hazy = assume_watched_through, None, False, []
        if last:
            e = self.next_probed(season, last)
        else:
            e = 1 if self.coarse_probes(season, 1) else self.next_probed(season, 0)
        while e is not None and e <= n and self.budget_left():
            v, s = self.verdict(season, e, self.coarse_probes(season, e), K)
            if v == WATCHED:
                last, hazy = e, []
                e = self.next_probed(season, e)
            elif v == UNRESOLVED:
                hazy.append(e)
                if len(hazy) >= MAX_HAZY_RUN or not self.consent(season, e):
                    break
                e = self.next_probed(season, e)
            elif v == UNKNOWN:
                e = self.next_probed(season, e)
            else:
                frontier, soft = e, s
                break
        if frontier is None:
            frontier = n + 1

        # fine pass — e is only probed once e-1 is settled, so fine-only probes are safe here.
        # Hazy episodes get re-probed with whatever wasn't shown yet.
        unchecked = None
        for f in range(last + 1, frontier):
            if not self.budget_left():
                break
            v, s = self.verdict(season, f, self.fine_probes(season, f), K_FINE)
            if v == WATCHED:
                last = f
                hazy = [h for h in hazy if h > f]
            elif v == UNKNOWN:
                if f in hazy:
                    break                    # unsure and nothing left to ask: stop here, softly
                unchecked = f
                break
            else:                            # frontier, or unresolved even with fine probes
                frontier, soft = f, True if v == UNRESOLVED else s
                break

        if last == n:
            nxt = season + 1 if season + 1 in self.seasons else None
            return self.finish(result, outcome="finished", next_season=nxt,
                               message=f"Looks like you finished season {season}."
                                       + (f" Start season {nxt}." if nxt else " That's the last season we have."))
        resume = last + 1
        hazy_from = min([h for h in hazy if h >= resume], default=None)
        soft = soft or hazy_from is not None or not self.budget_left()
        fallback = max(1, last - (1 if soft else 0)) if last else 1
        return self.finish(result, outcome="resume", resume=resume, fallback=fallback, soft=soft,
                           hazy_from=hazy_from, unchecked=unchecked, n=n,
                           message=self.message(season, resume, fallback, soft, hazy_from, unchecked, n))

    def message(self, season, resume, fallback, soft, hazy_from, unchecked, n):
        t = lambda e: f"E{self.seasons[season].get(e, {}).get('number', e)} “{self.seasons[season].get(e, {}).get('title', '?')}”"
        m = f"Start at {t(resume)}."
        if hazy_from:
            m += " You weren't sure from around here on, so if it's all familiar keep skipping ahead — you'll know."
        elif resume < n:
            m += f" If it's all familiar, skip to {t(resume + 1)}."
        if fallback < resume:
            m += f" If you might have stopped partway through {t(fallback)}, start there instead."
        if not self.budget_left():
            m += " (I stopped asking at the question limit.)"
        if unchecked:
            m += f" (I had nothing to check {t(unchecked)} with, so I'm assuming you didn't see it.)"
        return m

    def finish(self, result, **kw):
        result.update(kw)
        result["questions"] = len(self.log)
        result["log"] = self.log
        return result


# --- answer sources ----------------------------------------------------------

def interactive_answer(season, ep, text):
    print(f"\n  {text}\n")
    while True:
        a = input("  [y] I clearly remember this   [u] not sure   [n] no   > ").strip().lower()
        if a in ("y", "u", "n"):
            return {"y": "clear", "u": "unsure", "n": "no"}[a]
        if a == "q":
            sys.exit("quit")


def interactive_consent(season, ep):
    a = input("\n  You're not sure about that one. Keep going? I might mention something from a bit further ahead. [y/n] > ")
    return a.strip().lower().startswith("y")


def simulated(season_stop: int, ep_stop: int, hazy: set = frozenset(), keep_going=True):
    """A viewer who watched everything through S<season_stop>E<ep_stop>, answering "not sure" on the
    (season, episode) pairs in `hazy` even though they watched them."""
    def answer(season, ep, text):
        seen = (season, ep) <= (season_stop, ep_stop)
        if seen and (season, ep) in hazy:
            return "unsure"
        return "clear" if seen else "no"
    return answer, (lambda season, ep: keep_going)


# --- main --------------------------------------------------------------------

def parse_hazy(spec, season: int) -> set:
    if not spec:
        return set()
    a, b = spec.split("-")
    return {(season, e) for e in range(int(a), int(b) + 1)}


def simulate_all(seasons, season, hazy_spec):
    eps = seasons[season]; n = max(eps)
    stride = 2 if n <= 16 else 3
    probeless = [e for e in range(1, n + 1) if not eps.get(e, {}).get("probes")]
    print(f"S{season}: {n} episodes, stride {stride}, coarse-probeless {probeless or 'none'}"
          f"{', hazy ' + hazy_spec if hazy_spec else ''}\n")
    print(f"{'stopped after':>14} {'resume':>7} {'fallback':>9} {'q':>3} {'reach':>6}  ok")
    worst = 0
    for T in range(0, n + 1):
        ans, con = simulated(season, T, parse_hazy(hazy_spec, season))
        r = Walk(seasons, ans, con).run(season)
        shown = sorted({l["episode"] for l in r["log"] if l["season"] == season})
        reach = max([e - (T + 1) for e in shown if e > T + 1], default=0)
        worst = max(worst, reach)
        if r["outcome"] == "finished":
            ok = T == n
            print(f"{T:>14} {'done':>7} {'':>9} {r['questions']:>3} {reach:>6}  {'✓' if ok else '✗'}")
        else:
            exact = r["resume"] == T + 1
            conservative = r["resume"] <= T + 1 and (r.get("unchecked") or r.get("hazy_from"))
            print(f"{T:>14} {r['resume']:>7} {r['fallback']:>9} {r['questions']:>3} {reach:>6}  "
                  f"{'✓' if exact else ('~ (conservative)' if conservative else '✗ expected ' + str(T + 1))}")
    bound = stride - 1 + (stride if hazy_spec else 0)
    print(f"\nworst reach past the resume episode: {worst} (bound {bound}: stride-1{', +stride per consented continuation' if hazy_spec else ''})")
    assert worst <= bound, "leak bound violated"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", required=True, help="number, or 'unsure' to run the season-finder first")
    ap.add_argument("--simulate", help="'all', or E (stopped after episode E), or S:E with --season unsure")
    ap.add_argument("--hazy", help="episode range the simulated viewer is 'not sure' about, e.g. 3-7")
    a = ap.parse_args()

    seasons = load_show(slugify(a.show))
    if not seasons:
        sys.exit(f"no probes for {a.show}")

    if a.simulate == "all":
        simulate_all(seasons, int(a.season), a.hazy)
        return

    if a.simulate is not None:
        if a.season == "unsure":
            s, e = (int(x) for x in a.simulate.split(":"))
            ans, con = simulated(s, e, parse_hazy(a.hazy, s))
            w = Walk(seasons, ans, con)
            f = w.find_season()
            print(f"finder → season {f['season']}{' (hazy)' if f['hazy'] else ''} after {len(w.log)} questions")
            r = w.run(f["season"], prior_check=False) if f["season"] else {"message": "never started", "log": w.log}
        else:
            s = int(a.season)
            ans, con = simulated(s, int(a.simulate), parse_hazy(a.hazy, s))
            r = Walk(seasons, ans, con).run(s)
        for l in r["log"]:
            print(f"  S{l['season']}E{l['episode']:<3} {l['answer']:<7} {l['probe'][:80]}")
        print(f"\n{r['message']}  [{len(r['log'])} questions]")
        return

    w = Walk(seasons, interactive_answer, interactive_consent)
    if a.season == "unsure":
        print(f"\n{a.show}. Let's find the season first.\n")
        f = w.find_season()
        if not f["season"]:
            print("\n→ Looks like you haven't started this one."); return
        print(f"\n→ Season {f['season']}. I'll skip ahead as we go, so the most I'll ever mention is one episode past where you stopped.\n")
        r = w.run(f["season"], prior_check=False)
    else:
        print(f"\n{a.show}, season {a.season}. I'll skip ahead as we go, so the most I'll ever mention is one episode past where you stopped.\n")
        r = w.run(int(a.season))
    print(f"\n→ {r['message']}  [{r['questions']} questions]")
    out = ROOT / "data/walks" / f"{slugify(a.show)}-{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"logged → {out}")


if __name__ == "__main__":
    main()
