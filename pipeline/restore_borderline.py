#!/usr/bin/env python3
"""Restore split-vote consequence rejections (1/2) into probes.json as borderline probes, appended
after the audited-safe ones. Product decision 2026-09-08: minor spoilers accepted. Unanimous
rejections (2/2) stay out. Idempotent."""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
total = 0
for audit_path in sorted(ROOT.glob("data/probes/*/s??.audit.json")):
    probes_path = audit_path.with_name(audit_path.name.replace(".audit.", ".probes."))
    if not probes_path.exists():
        continue
    a = json.loads(audit_path.read_text()); p = json.loads(probes_path.read_text())
    added = 0
    for ep, e in a["episodes"].items():
        entry = p["episodes"].setdefault(ep, {"title": e["title"], "probes": []})
        have = {x["text"] for x in entry["probes"]} | {x["text"] for x in entry.get("fine_only", [])}
        for c in e["candidates"]:
            r = c["rejected"] or ""
            if re.match(r"consequence \(1/2\)", r) and c["text"] not in have:
                entry.setdefault("fine_only", []).append({"text": c["text"], "specificity": 1,
                                                          "borderline": True, "reason": r.split(": ", 1)[-1][:160]})
                added += 1
    if added:
        probes_path.write_text(json.dumps(p, indent=2, ensure_ascii=False))
        print(f"{audit_path.parent.name} {audit_path.name[:3]}: +{added} borderline")
    total += added
print("restored", total)
