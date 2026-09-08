#!/usr/bin/env python3
"""One-off: rebuild the fine_only tier for seasons rechecked before recheck learned to keep dropped probes.

A probe that passed the full audit (rejected == None in audit.json) but is absent from probes.json
was dropped by a stride-aware recheck: safe at e-1, unsafe at e-stride → fine_only.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for probes_path in sorted((ROOT / "data/probes").glob("*/s*.probes.json")):
    audit = json.loads(probes_path.with_name(probes_path.name.replace(".probes.", ".audit.")).read_text())
    probes = json.loads(probes_path.read_text())
    moved = 0
    for ep, entry in probes["episodes"].items():
        have = {p["text"] for p in entry["probes"]} | {p["text"] for p in entry.get("fine_only", [])}
        survivors = [c for c in audit["episodes"].get(ep, {}).get("candidates", []) if not c["rejected"]]
        for c in survivors[:3]:  # KEEP=3, generator order — same rule the audit used
            if c["text"] not in have:
                entry.setdefault("fine_only", []).append({"text": c["text"], "specificity": None,
                                                          "reverse_confidence": c["checks"].get("reverse", {}).get("confidence")})
                moved += 1
        entry.setdefault("fine_only", [])
    probes_path.write_text(json.dumps(probes, indent=2, ensure_ascii=False))
    print(f"{probes['show']} S{probes['season']}: {moved} probes restored as fine-only")
