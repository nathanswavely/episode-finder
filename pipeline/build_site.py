#!/usr/bin/env python3
"""Assemble the shipped static data from data/probes into site/data/.

    python pipeline/build_site.py

site/data/index.json            — [{slug, title, seasons}]
site/data/shows/<slug>.json     — everything the walk needs for one show

Only seasons with an audited probes file are included. Episodes with zero
surviving probes are included with an empty list (the walk steps over them).
Every season carries its Wikipedia source and revision for CC BY-SA attribution.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site/data"


def main():
    watch = json.loads((ROOT / "data/watch.json").read_text()) if (ROOT / "data/watch.json").exists() else {}
    shows = {}
    for probes_path in sorted((ROOT / "data/probes").glob("*/s*.probes.json")):
        if ".meta." in probes_path.name:
            continue   # provider-comparison output, never shipped
        p = json.loads(probes_path.read_text())
        raw = json.loads((ROOT / f"data/raw/{p['slug']}/s{p['season']:02d}.json").read_text())
        titles = {e["episode"]: e["title"] for e in raw["episodes"]}
        labels = {e["episode"]: e.get("number", str(e["episode"])) for e in raw["episodes"]}
        missing = [e["episode"] for e in raw["episodes"] if str(e["episode"]) not in p["episodes"]]
        if missing:
            # audit.py writes incrementally; never ship a season that is still being audited
            print(f"skip {p['show']} S{p['season']}: not fully audited (missing episodes {missing})")
            continue
        audit = json.loads(probes_path.with_name(probes_path.name.replace(".probes.", ".audit.")).read_text())
        if "recheck_spend" not in audit:
            # the stride-aware recheck is what makes the coarse tier safe; never ship without it
            print(f"skip {p['show']} S{p['season']}: not rechecked (run audit.py --recheck)")
            continue
        show = shows.setdefault(p["slug"], {"slug": p["slug"], "title": p["show"],
                                            "license": "CC BY-SA 4.0", "seasons": [],
                                            **({"watch": watch[p["slug"]]} if p["slug"] in watch else {})})
        show["seasons"].append({
            "season": p["season"],
            "source": {"title": raw["source"]["title"], "url": raw["source"]["url"], "revid": raw["source"]["revid"]},
            "episodes": [
                {"episode": int(k), "title": titles.get(int(k), v["title"]), "number": labels.get(int(k), k),
                 "probes": [x["text"] for x in v["probes"]],
                 "fine": [x["text"] for x in v.get("fine_only", [])]}
                for k, v in sorted(p["episodes"].items(), key=lambda kv: int(kv[0]))
            ],
        })

    (OUT / "shows").mkdir(parents=True, exist_ok=True)
    index = []
    for slug, show in sorted(shows.items()):
        show["seasons"].sort(key=lambda s: s["season"])
        (OUT / "shows" / f"{slug}.json").write_text(json.dumps(show, ensure_ascii=False, separators=(",", ":")))
        index.append({"slug": slug, "title": show["title"], "seasons": [s["season"] for s in show["seasons"]]})
        eps = sum(len(s["episodes"]) for s in show["seasons"])
        probes = sum(len(e["probes"]) for s in show["seasons"] for e in s["episodes"])
        fine = sum(len(e["fine"]) for s in show["seasons"] for e in s["episodes"])
        print(f"{show['title']}: seasons {[s['season'] for s in show['seasons']]}, {eps} episodes, {probes} coarse-safe + {fine} fine-only probes")
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
