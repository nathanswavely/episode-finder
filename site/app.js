/* Where did I stop? — static client. Implements docs/FLOW.md; walk semantics mirror pipeline/walk.py. */
"use strict";

const REPO = "https://github.com/nathanswavely/episode-finder";
const K = 3; // probes per episode, max

const $app = document.getElementById("app");
document.getElementById("source-link").href = REPO;
document.getElementById("request-link").href =
  `${REPO}/issues/new?title=${encodeURIComponent("Show request: ")}&body=${encodeURIComponent("Show:\nWhy it's a good fit (serialized, popular, on streaming):\n")}`;

const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { $app.innerHTML = html; window.scrollTo(0, 0); };

// ---------- data ----------
let index = null;
async function loadIndex() {
  if (!index) index = await (await fetch("data/index.json")).json();
  return index;
}
async function loadShow(slug) {
  return (await fetch(`data/shows/${slug}.json`)).json();
}

// ---------- screens ----------
async function screenHome() {
  const intro = `
    <h1>Where did I stop?</h1>
    <p class="lede">Forgot where you stopped watching? Answer a few questions and we'll suggest where to pick it back up.</p>`;
  let shows;
  try {
    if (!index) h(`${intro}<div class="skeleton" aria-hidden="true"></div>`);
    shows = await loadIndex();
  } catch (e) {
    h(`${intro}<div class="error">The list of shows didn't load. Check your connection and <a href="">try again</a>.</div>`);
    return;
  }
  const chips = shows.slice(0, 12).map((s) => `<li><button data-slug="${s.slug}">${esc(s.title)}</button></li>`).join("");
  h(`
    ${intro}
    <div class="search">
      <label for="q" class="muted small" style="display:none">Show</label>
      <input id="q" type="search" placeholder="Which show?" autocomplete="off" autofocus aria-label="Which show?">
      <ul class="results" id="results"></ul>
    </div>
    <div class="catalog" id="catalog">Shows so far:
      <ul>${chips}${shows.length > 12 ? `<li class="muted">and ${shows.length - 12} more</li>` : ""}</ul>
    </div>
  `);
  const $q = document.getElementById("q"), $r = document.getElementById("results"), $c = document.getElementById("catalog");
  const render = () => {
    const q = $q.value.trim().toLowerCase();
    $c.hidden = !!q;
    if (!q) { $r.innerHTML = ""; return; }
    const hits = shows.filter((s) => s.title.toLowerCase().includes(q)).slice(0, 8);
    $r.innerHTML = hits.length
      ? hits.map((s) => `<li><button data-slug="${s.slug}"><span>${esc(s.title)}</span><span class="muted small">${s.seasons.length} season${s.seasons.length > 1 ? "s" : ""}</span></button></li>`).join("")
      : `<li class="none">Not here yet. <a href="${document.getElementById("request-link").href}" rel="noopener">Request it</a>.</li>`;
  };
  $q.addEventListener("input", render);
  const pick = async (e) => {
    const b = e.target.closest("button[data-slug]");
    if (!b) return;
    try { screenSeason(await loadShow(b.dataset.slug)); }
    catch { h(`${intro}<div class="error">That show didn't load. <a href="">Try again</a>.</div>`); }
  };
  $r.addEventListener("click", pick);
  $c.addEventListener("click", pick);
}

function screenSeason(show) {
  h(`
    <h1>${esc(show.title)}</h1>
    <p class="lede">Which season were you in when you stopped?</p>
    <div class="grid">
      ${show.seasons.map((s) => `<button class="btn" data-season="${s.season}">Season ${s.season}</button>`).join("")}
    </div>
    <div class="stack">
      <button class="btn" data-unsure><span>Not sure</span></button>
      <button class="btn quiet" data-home>Pick a different show</button>
    </div>
  `);
  $app.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.season) runWalk(show, Number(b.dataset.season));
    else if ("unsure" in b.dataset) runFindSeason(show);
    else if ("home" in b.dataset) { $app.onclick = null; screenHome(); }
  };
}

// ---------- walk engine (mirrors pipeline/walk.py — change both) ----------
const K_FINE = 5;          // fine pass may also draw on fine-only probes
const MAX_HAZY_RUN = 4;    // consecutive unresolved episodes before we stop and report softly
const MAX_QUESTIONS = 25;  // hard cap per walk

function seasonMap(S) {
  const eps = new Map(S.episodes.map((e) => [e.episode, e]));
  return { eps, n: Math.max(...eps.keys()),
           probes: (e) => (eps.get(e)?.probes) || [],                                   // coarse-safe
           fineProbes: (e) => [...((eps.get(e)?.probes) || []), ...((eps.get(e)?.fine) || [])] }; // + fine-only
}

class Walker {
  constructor(show) {
    this.show = show; this.log = []; this.shown = new Set(); this.consented = null; this.walkSeason = null;
    this.seasons = new Map(show.seasons.map((S) => [S.season, S]));
  }
  stride(seasonNum) { return seasonMap(this.seasons.get(seasonNum)).n <= 16 ? 2 : 3; }
  budgetLeft() { return this.log.length < MAX_QUESTIONS; }

  ask(probe, seasonNum) {
    return new Promise((resolve) => {
      const n = this.log.length + 1;
      const label = this.walkSeason ? `season ${this.walkSeason}` : "which season?";
      const est = Math.max(n, Math.ceil(seasonMap(this.seasons.get(this.walkSeason || seasonNum) || this.show.seasons[0]).n / 2) + 2);
      const dots = Array.from({ length: est }, (_, i) => `<i class="${i < n ? "on" : ""}"></i>`).join("");
      h(`
        <p class="note">${n === 1
          ? `${esc(this.show.title)}, ${label}. We'll only show you moments from episodes you've seen, or at most one past where you stopped.`
          : `${esc(this.show.title)}, ${label}`}</p>
        <div class="dots" aria-hidden="true">${dots}</div>
        <div class="card">${esc(probe)}</div>
        <div class="answers">
          <button class="btn primary" data-a="clear"><span>I clearly remember this</span><kbd>1</kbd></button>
          <button class="btn" data-a="unsure"><span>Not sure</span><kbd>2</kbd></button>
          <button class="btn" data-a="no"><span>I don't remember this</span><kbd>3</kbd></button>
        </div>
      `);
      const done = (a) => { $app.onclick = null; document.onkeydown = null; resolve(a); };
      $app.onclick = (e) => { const b = e.target.closest("button[data-a]"); if (b) done(b.dataset.a); };
      document.onkeydown = (e) => {
        const map = { "1": "clear", "y": "clear", "2": "unsure", "u": "unsure", "3": "no", "n": "no" };
        const a = map[e.key.toLowerCase()];
        if (a && !e.metaKey && !e.ctrlKey) { e.preventDefault(); done(a); }
      };
    });
  }

  consent() {
    if (this.consented !== null) return Promise.resolve(this.consented);
    return new Promise((resolve) => {
      h(`
        <p class="note">${esc(this.show.title)}</p>
        <div class="card consent">You weren't sure about that one. We can keep going, but then we might mention something from more than one episode past where you stopped.</div>
        <div class="answers">
          <button class="btn primary" data-c="1"><span>Keep going</span><kbd>1</kbd></button>
          <button class="btn" data-c="0"><span>Stop here</span><kbd>2</kbd></button>
        </div>
      `);
      const done = (v) => { $app.onclick = null; document.onkeydown = null; this.consented = v; resolve(v); };
      $app.onclick = (e) => { const b = e.target.closest("button[data-c]"); if (b) done(b.dataset.c === "1"); };
      document.onkeydown = (e) => { if (e.key === "1" || e.key.toLowerCase() === "y") done(true); if (e.key === "2" || e.key.toLowerCase() === "n") done(false); };
    });
  }

  async verdict(seasonNum, ep, probes, k) {
    const fresh = probes.filter((p) => !this.shown.has(p)).slice(0, k);
    if (!fresh.length) return ["unknown", false];
    const answers = [];
    for (const p of fresh) {
      if (!this.budgetLeft()) break;
      const a = await this.ask(p, seasonNum);
      this.shown.add(p);
      this.log.push({ season: seasonNum, episode: ep, probe: p, answer: a });
      answers.push(a);
      if (a === "clear") return ["watched", false];
    }
    if (!answers.length) return ["unknown", false];
    if (answers.every((a) => a === "unsure")) return ["unresolved", true];
    return ["frontier", answers.includes("unsure")];
  }

  nextProbed(seasonNum, e) {
    const { n, probes } = seasonMap(this.seasons.get(seasonNum));
    const st = this.stride(seasonNum);
    for (let c = Math.min(e + st, n); c > e; c--) if (probes(c).length) return c;
    return null; // nothing probed within the stride window: stop rather than reach beyond it
  }

  // Stride-1 walk over the first `stride` episodes of each season — all coarse-safe, so safe for
  // someone who hasn't started that season. A hazy season is the one to walk.
  async findSeason() {
    this.walkSeason = null;
    let watched = null, hazy = [];
    for (const S of this.show.seasons) {
      const { probes } = seasonMap(S);
      const st = this.stride(S.season);
      const pool = [];
      for (let e = 1; e <= st; e++) pool.push(...probes(e));
      const [v] = await this.verdict(S.season, 1, pool.slice(0, K + 1), K + 1);
      if (v === "watched") { watched = S.season; hazy = []; }
      else if (v === "unresolved") { hazy.push(S.season); if (hazy.length >= MAX_HAZY_RUN || !(await this.consent())) break; }
      else if (v === "frontier") break;
    }
    return { season: hazy.length ? hazy[0] : watched, hazy: hazy.length > 0 };
  }

  async run(seasonNum, { priorCheck = true, assumeWatchedThrough = 0 } = {}) {
    this.walkSeason = seasonNum;
    const S = this.seasons.get(seasonNum);
    const { eps, n, probes, fineProbes } = seasonMap(S);
    const base = { show: this.show, seasonNum, S, eps, n, log: this.log };

    const prev = this.seasons.get(seasonNum - 1);
    if (prev && priorCheck && !assumeWatchedThrough) {
      const pm = seasonMap(prev);
      const [v] = await this.verdict(prev.season, pm.n, pm.probes(pm.n), K);
      if (v === "frontier") return { ...base, outcome: "back_up", prevSeason: prev.season };
    }

    // coarse pass — opens on the premiere unless we've been told it was watched
    let last = assumeWatchedThrough, frontier = null, soft = false, hazy = [];
    let e = last ? this.nextProbed(seasonNum, last) : (probes(1).length ? 1 : this.nextProbed(seasonNum, 0));
    while (e !== null && e <= n && this.budgetLeft()) {
      const [v, s] = await this.verdict(seasonNum, e, probes(e), K);
      if (v === "watched") { last = e; hazy = []; e = this.nextProbed(seasonNum, e); }
      else if (v === "unresolved") {
        hazy.push(e);
        if (hazy.length >= MAX_HAZY_RUN || !(await this.consent())) break;
        e = this.nextProbed(seasonNum, e);
      }
      else if (v === "unknown") e = this.nextProbed(seasonNum, e);
      else { frontier = e; soft = s; break; }
    }
    if (frontier === null) frontier = n + 1;

    // fine pass — f is only probed once f-1 is settled, so fine-only probes are safe here
    let unchecked = null;
    for (let f = last + 1; f < frontier; f++) {
      if (!this.budgetLeft()) break;
      const [v, s] = await this.verdict(seasonNum, f, fineProbes(f), K_FINE);
      if (v === "watched") { last = f; hazy = hazy.filter((x) => x > f); }
      else if (v === "unknown") { if (hazy.includes(f)) break; unchecked = f; break; }
      else { frontier = f; soft = v === "unresolved" ? true : s; break; }
    }

    if (last === n) return { ...base, outcome: "finished", nextSeason: this.seasons.has(seasonNum + 1) ? seasonNum + 1 : null };
    const resume = last + 1;
    const hazyFrom = hazy.filter((x) => x >= resume)[0] ?? null;
    soft = soft || hazyFrom !== null || !this.budgetLeft();
    const fallback = last ? Math.max(1, last - (soft ? 1 : 0)) : 1;
    return { ...base, outcome: "resume", resume, fallback, soft, hazyFrom, unchecked, budgetHit: !this.budgetLeft() };
  }
}

async function runWalk(show, seasonNum, opts, walker) {
  walker = walker || new Walker(show);
  screenResult(walker, await walker.run(seasonNum, opts));
}

async function runFindSeason(show) {
  const walker = new Walker(show);
  const f = await walker.findSeason();
  if (!f.season) return screenResult(walker, { show, outcome: "never_started", log: walker.log });
  screenResult(walker, await walker.run(f.season, { priorCheck: false }));
}

// ---------- result ----------
function screenResult(walker, r) {
  const { show } = r;
  const t = (e) => `episode ${e}${r.eps?.get(e) ? `, <span class="ep">${esc(r.eps.get(e).title)}</span>` : ""}`;
  let body = "", headline, actions = "";

  if (r.outcome === "resume") {
    headline = `Start at season ${r.seasonNum}, ${t(r.resume)}.`;
    const lines = [];
    if (r.hazyFrom) lines.push(`You weren't sure from here on. If it's all familiar, keep skipping ahead.`);
    else if (r.resume < r.n) lines.push(`If it's all familiar, skip to ${t(r.resume + 1)}.`);
    if (r.fallback < r.resume) lines.push(`If you think you stopped partway through ${t(r.fallback)}, start there.`);
    if (r.budgetHit) lines.push(`<span class="muted">That was the 25-question limit, so treat this as a best guess.</span>`);
    if (r.unchecked) lines.push(`<span class="muted">We have no questions for ${t(r.unchecked)}, so we're assuming you haven't seen it.</span>`);
    body = lines.map((l) => `<p>${l}</p>`).join("");
    if (r.resume < r.n) actions += `<button class="btn" data-further="${r.resume}"><span>I got further than that</span></button>`;
  } else if (r.outcome === "finished") {
    headline = `Looks like you finished season ${r.seasonNum}.`;
    body = r.nextSeason ? `<p>Start at season ${r.nextSeason}, episode 1.</p>` : `<p>That's the last season here.</p>`;
    if (r.nextSeason) actions += `<button class="btn" data-next="${r.nextSeason}"><span>Keep going into season ${r.nextSeason}</span></button>`;
  } else if (r.outcome === "back_up") {
    headline = `It doesn't look like you finished season ${r.prevSeason}.`;
    body = "";
    actions += `<button class="btn primary" data-season="${r.prevSeason}"><span>Try season ${r.prevSeason}</span></button>`;
  } else {
    headline = `Looks like you haven't started ${esc(show.title)}.`;
    body = `<p>Start at episode 1.</p>`;
  }

  const seasonsUsed = [...new Set(r.log.map((l) => l.season))].map((n) => show.seasons.find((s) => s.season === n)).filter(Boolean);
  const answers = r.log.map((l) => `S${l.season}E${l.episode}: ${l.answer}`).join("\n");
  const feedback = `${REPO}/issues/new?title=${encodeURIComponent(`Result check: ${show.title} S${r.seasonNum ?? "?"}`)}&body=${encodeURIComponent(
    `Result: ${headline.replace(/<[^>]+>/g, "")}\n\nWas it right? (what's the real answer, if you know)\n\n\nAnswers:\n${answers}\n`)}`;

  h(`
    <div class="result">
      <p class="big">${headline}</p>
      ${body}
    </div>
    <div class="stack">
      ${actions}
      <a class="btn" href="${feedback}" rel="noopener"><span>Tell us if this was right</span></a>
      <button class="btn quiet" data-again>Start over</button>
    </div>
    <div class="attr">
      Episode summaries from Wikipedia, CC BY-SA 4.0:
      <ul>${seasonsUsed.map((s) => `<li><a href="${esc(s.source.url)}" rel="noopener">${esc(s.source.title)}</a> (revision ${s.source.revid})</li>`).join("")}</ul>
      <p>${r.log.length} question${r.log.length === 1 ? "" : "s"} asked.</p>
    </div>
  `);
  $app.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    $app.onclick = null;
    if (b.dataset.season) runWalk(show, Number(b.dataset.season), {}, walker);
    else if (b.dataset.further) { walker.consented = true; runWalk(show, r.seasonNum, { priorCheck: false, assumeWatchedThrough: Number(b.dataset.further) }, walker); }
    else if (b.dataset.next) runWalk(show, Number(b.dataset.next), { priorCheck: false }, walker);
    else if ("again" in b.dataset) screenHome();
  };
}

screenHome();
