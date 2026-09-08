#!/usr/bin/env python3
"""Fetch one season's episode summaries from Wikipedia into data/raw/<slug>/s<NN>.json.

    python pipeline/fetch.py --show "Breaking Bad" --season 4
    python pipeline/fetch.py --show "The Office" --season 5 --page "The Office (American TV series) season 5"

No LLM involved. Records the page revision for attribution and reproducibility.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
UA = "episode-finder-pipeline/0.1 (research; contact via GitHub issues)"
WORD_FLOOR = 40  # pre-filter line from ADR-0003; 60 rejected 50-word sitcom episodes that yielded 3 probes


def api(params: dict) -> dict:
    import time
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))   # Wikipedia asks for politeness; back off and retry


def fetch_wikitext(title: str) -> tuple[str, str, int]:
    """Return (resolved_title, wikitext, revid), following redirects."""
    data = api({"action": "parse", "page": title, "prop": "wikitext|revid", "redirects": 1})
    if "error" in data:
        raise SystemExit(f"Wikipedia: {data['error'].get('info')} (page: {title!r})")
    p = data["parse"]
    return p["title"], p["wikitext"]["*"], p["revid"]


# --- wikitext parsing ------------------------------------------------------

def find_templates(text: str, name_re: str):
    """Yield the full text of every top-level {{...}} whose name matches name_re.
    Brace-balanced, so nested {{cite}} / {{nowrap}} inside a field don't break it."""
    pat = re.compile(r"\{\{\s*(" + name_re + r")\s*(?=\||\}\})", re.I)
    for m in pat.finditer(text):
        depth, i = 0, m.start()
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    yield text[m.start():i]
                    break
            else:
                i += 1


def split_fields(template: str) -> dict:
    """Split a template body into {field: value}, respecting nested braces/brackets."""
    body = template[2:-2]
    parts, depth_b, depth_s, cur = [], 0, 0, []
    i = 0
    while i < len(body):
        two = body[i:i + 2]
        if two == "{{":
            depth_b += 1; cur.append(two); i += 2; continue
        if two == "}}":
            depth_b -= 1; cur.append(two); i += 2; continue
        if two == "[[":
            depth_s += 1; cur.append(two); i += 2; continue
        if two == "]]":
            depth_s -= 1; cur.append(two); i += 2; continue
        c = body[i]
        if c == "|" and depth_b == 0 and depth_s == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    fields = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            fields[k.strip()] = v.strip()
    return fields


def strip_markup(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>/]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    # templates: keep the last positional arg of a few inline ones, drop the rest
    def tmpl(m):
        inner = m.group(1)
        name, _, rest = inner.partition("|")
        name = name.strip().lower()
        if name in ("nowrap", "lang", "small", "em", "transl", "'"):
            return rest.split("|")[-1] if rest else ""
        if name == "start date":
            nums = [x for x in rest.split("|") if x.strip().isdigit()]
            return "-".join(f"{int(n):02d}" if i else n for i, n in enumerate(nums[:3]))
        return ""
    for _ in range(4):  # nested templates, innermost first
        s = re.sub(r"\{\{([^{}]*)\}\}", tmpl, s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)  # [[a|b]] -> b, [[a]] -> a
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)     # [url text] -> text
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def season_chunk(wikitext: str, season: int) -> str:
    """A page that lists several seasons has one {{Episode table ...}} per season (or one
    == Season N == heading). Return the chunk for the requested season; the whole text if the
    page has a single table."""
    parts = re.split(r"(?=\{\{\s*Episode table)", wikitext, flags=re.I)
    tables = [c for c in parts if re.match(r"\{\{\s*Episode table", c, re.I)]
    if len(tables) <= 1:
        return wikitext
    # a table's rows may carry NumParts etc.; assume tables appear in season order
    return tables[season - 1] if season - 1 < len(tables) else ""


def parse_episodes(wikitext: str) -> list[dict]:
    """One entry per Wikipedia row. `episode` is the row's position in the season (1..N), which is
    what the walk does arithmetic on; `number` is Wikipedia's label ("9", or "1–2" for a
    double-length episode listed as one row with NumParts=2), which is what viewers see."""
    rows = []
    for t in find_templates(wikitext, r"Episode list(?:/sublist)?"):
        f = split_fields(t)
        summary = strip_markup(f.get("ShortSummary", ""))
        if not summary:
            continue
        parts = int(re.search(r"\d+", f.get("NumParts", "1") or "1").group())
        if parts > 1:
            nums = [f.get(f"EpisodeNumber2_{i}") or f.get(f"EpisodeNumber_{i}") or "" for i in range(1, parts + 1)]
            nums = [re.search(r"\d+", n).group() for n in nums if re.search(r"\d+", n or "")]
            overall = f.get("EpisodeNumber_1", "0")
        else:
            n = f.get("EpisodeNumber2") or f.get("EpisodeNumber") or ""
            m = re.search(r"\d+", n)
            nums = [m.group()] if m else []
            overall = f.get("EpisodeNumber", "0")
        if not nums:
            continue
        rows.append({
            "sort": int(nums[0]),
            "number": "–".join(nums) if len(nums) > 1 else nums[0],
            "overall": int((re.search(r"\d+", overall) or re.search(r"\d", "0")).group()),
            "title": strip_markup(f.get("Title", "")),
            "air_date": strip_markup(f.get("OriginalAirDate", "")),
            "summary": summary,
            "words": len(summary.split()),
        })
    rows.sort(key=lambda e: e["sort"])
    eps = []
    for i, r in enumerate(rows, 1):
        r.pop("sort")
        eps.append({"episode": i, **r})
    return eps


def parse_cast(wikitext: str) -> dict:
    """Character names from the season page's Cast section, split into main and recurring.
    Entries look like '* [[Actor]] as [[Character]]' or '* [[Actor]] as Character, description'."""
    sec = re.search(r"==+\s*Cast(?: and characters)?\s*==+(.*?)(?=\n==[^=])", wikitext, flags=re.S)
    if not sec:
        return {"main": [], "recurring": []}
    out, bucket = {"main": [], "recurring": []}, "main"
    for line in sec.group(1).splitlines():
        h = re.match(r"\s*===+\s*([^=]+?)\s*===+", line)
        if h:
            bucket = "main" if re.search(r"main|starring|regular", h.group(1), re.I) else "recurring"
            continue
        m = re.match(r"\s*\*+\s*\[\[[^\]]+\]\]\s+as\s+(?:\[\[(?:[^\]|]*\|)?([^\]]+)\]\]|([A-Z][\w.'\-\" ]+?))(?=[,;:(\n]| \(|\.\s|$)", line)
        if m:
            out[bucket].append((m.group(1) or m.group(2)).strip())
    return out


# --- main ------------------------------------------------------------------

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--page", help="Wikipedia page title if not '<show> season <n>'")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--update-cast", action="store_true",
                    help="Only add the Cast section to an existing raw file; leave summaries untouched")
    a = ap.parse_args()

    page = a.page or f"{a.show} season {a.season}"
    title, wikitext, revid = fetch_wikitext(page)
    if a.page:
        chunk = season_chunk(wikitext, a.season)
        if chunk != wikitext:
            print(f"(multi-season page: using episode table {a.season})")
        wikitext_eps = chunk
    else:
        wikitext_eps = wikitext
    if a.update_cast:
        dest = Path(a.out) / slugify(a.show) / f"s{a.season:02d}.json"
        d = json.loads(dest.read_text())
        d["cast"] = parse_cast(wikitext)
        dest.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        print(f"{title}: cast main {len(d['cast']['main'])}, recurring {len(d['cast']['recurring'])} -> {dest}")
        return
    eps = parse_episodes(wikitext_eps)
    if not eps:
        sys.exit(f"No Episode list templates with summaries found on {title!r}. "
                 "Try --page with the exact title, or the show's 'List of ... episodes' page.")

    out = {
        "show": a.show,
        "slug": slugify(a.show),
        "season": a.season,
        "source": {
            "title": title,
            "revid": revid,
            "url": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&oldid={revid}",
            "license": "CC BY-SA 4.0",
        },
        "cast": parse_cast(wikitext),
        "episodes": eps,
    }
    dest = Path(a.out) / out["slug"] / f"s{a.season:02d}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    words = sorted(e["words"] for e in eps)
    below = sum(w < WORD_FLOOR for w in words)
    passes = (len(eps) - below) / len(eps) >= 0.9
    print(f"{title} (rev {revid}) -> {dest}")
    print(f"  {len(eps)} episodes | median {words[len(words)//2]} words | min {words[0]} | max {words[-1]}")
    print(f"  {below} below {WORD_FLOOR} words -> pre-filter {'PASS' if passes else 'FAIL'}")


if __name__ == "__main__":
    main()
