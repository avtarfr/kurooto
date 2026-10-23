// NOTES, the map (shared by the dashboard and the phone app's Notes map view; see common.js). The dashboard's own
// parts (pointing, the card with a note's first lines, search, R) are home.js's Notes, which extends Mind; the
// phone's (touch: drag, pinch, tap) are views/phone.js's.
"use strict";
// -------------------------------------------------------------------------------------------------- NOTES
// Neighborhoods come from your own notes: each course or subject folder (sources/<name>/, or <name>/ beside its
// course.md) is one, each research project (projects/<name>/ or research/<name>/) is one, the other maps and hubs are
// the hub, and any other note joins the neighborhood most of its links go to.
// Names on the map (0.5.19): at the usual zoom the map names its regions, like a map names places: each
// neighbourhood's name (its course page's title, or its project's) at the middle of its notes. A note's own name shows
// when you point at it, find it, light the recent ones (R) or zoom in; zoomed in, course pages, hubs and projects come
// first, then notes that link across neighbourhoods. A book's index note comes last and is drawn small: its hundreds
// of links come from reading the book ("Seen in" lines), not from how your notes connect.
// -- the pure part (no page, no canvas): tests/unit/test_notes_labels.py runs it in node
const HOOD_COLORS = ["peach", "lav", "rose", "pink", "sand"], MAX_HOODS = 8; // research projects are the accent
const HUB = { label: "Maps & hubs", get color() { return PAL.fg; }, anchor: { x: 0, y: -40 } };
const OTHER = { label: "Other Notes", get color() { return PAL.dim; }, anchor: { x: 0, y: 380 } };
const prettyHood = (s) => s.replace(/^project:/, "").replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// the folders research projects live in: projects/ and research/, and the layout's own (g.layout.project, e.g.
// "work/{project}/index")
function projectDirs(lay = {}) {
  const dirs = new Set(["projects/", "research/"]), m = /^([^{}]+\/)\{project\}/.exec(lay.project || "");
  if (m) dirs.add(m[1]);
  return [...dirs];
}
// a note's role: "course" (a course page), "hub" (a map, the home or research hub, a project's index), "book" (a
// book's index note, <subject>/books/<book>) or "note"
function noteRole(id, lay = {}) {
  if (/(^|\/)books\//.test(id)) return "book";
  if (/^maps\/courses\/[^/]+$/.test(id) || /^[^/]+\/course$/.test(id) || /^sources\/[^/]+\/course$/.test(id)) return "course";
  if (/^maps\//.test(id) || /^(index|research\/index|projects\/[^/]+\/index|research\/[^/]+\/index|projects\/[^/]+)$/.test(id) || id === lay.research) return "hub";
  return "note";
}
// subjects: the folder names that are courses (sources/<s>/…, or <s>/course in the kurooto layout); dirs: projectDirs()
function hoodOf(id, subjects = new Set(), dirs = projectDirs()) {
  let m = /^sources\/([^/]+)\//.exec(id || ""); if (m) return m[1];
  for (const d of dirs) { m = new RegExp(`^${escRe(d)}([^/]+)/.`).exec(id || ""); if (m && `${d}${m[1]}` !== "research/index") return `project:${m[1]}`; }
  m = /^maps\/courses\/([^/]+)$/.exec(id || ""); if (m && subjects.has(m[1])) return m[1]; // a course page joins its course
  if (/^(maps|projects|research)\//.test(id || "") || id === "index") return "hub";
  m = /^([^/]+)\//.exec(id || ""); if (m && subjects.has(m[1])) return m[1];
  return null;
}
// n.neighborhood, n.role, n.sdeg (links that aren't a book's) and n.bridge (how many other neighbourhoods its links
// reach) for every node (n.nb holds its links, n.out the ones it makes); returns {key: {label, color, anchor, project}}.
// info: the graph's layout ({research, project}) and research ({<project>: {name, topics}}: each project's
// entry in the research hub, read by web/live.py). Once per graph update, never per frame.
// A research project's region is its folder's notes, the notes its index links to and the topics its hub entry links
// to; it's always named, however small. Any other note (a concept note in zettel/, say) joins the region most of its
// links come from (a tie goes to the course), else "other".
function assignHoods(nodes, info = {}) {
  const lay = info.layout || {}, research = info.research || {}, dirs = projectDirs(lay);
  const subjects = new Set();
  for (const n of nodes.values()) { const m = /^sources\/([^/]+)\//.exec(n.id) || /^([^/]+)\/course$/.exec(n.id); if (m) subjects.add(m[1]); }
  const base = new Map(), size = new Map(), projects = new Set(Object.keys(research).map((p) => `project:${p}`));
  for (const n of nodes.values()) {
    n.role = noteRole(n.id, lay);
    const k = hoodOf(n.id, subjects, dirs); base.set(n.id, k);
    if (k && k.startsWith("project:")) projects.add(k); else if (k && k !== "hub") size.set(k, (size.get(k) || 0) + 1);
  }
  const courses = [...size].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, MAX_HOODS).map(([k]) => k);
  const keys = [...courses, ...[...projects].sort()];
  const known = new Set(keys), hoods = new Map([["hub", HUB], ["other", OTHER]]);
  const titleOf = (...ids) => { for (const id of ids) { const n = nodes.get(id); if (n && n.title && n.title !== id.split("/").pop()) return n.title; } return null; };
  const indexOf = (p) => [...dirs.map((d) => `${d}${p}/index`), ...dirs.map((d) => `${d}${p}`)].find((id) => nodes.has(id));
  let ci = 0;
  keys.forEach((k, i) => {
    const ang = (i / keys.length) * 2 * Math.PI - Math.PI / 2, p = k.replace(/^project:/, ""), project = k.startsWith("project:");
    const label = (project ? titleOf(...dirs.map((d) => `${d}${p}/index`), ...dirs.map((d) => `${d}${p}`)) || (research[p] && research[p].name)
      : titleOf(`maps/courses/${k}`, `${k}/course`, `sources/${k}/course`)) || prettyHood(k);
    const col = project ? "accent" : HOOD_COLORS[ci++ % HOOD_COLORS.length];
    hoods.set(k, { label, project, get color() { return PAL[col]; }, anchor: { x: Math.cos(ang) * 420, y: Math.sin(ang) * 300 } });
  });
  // a project's reach: what its index links to (one hop) and its hub entry's topics; a note in a folder stays there
  const seed = new Map();
  for (const k of keys) {
    if (!k.startsWith("project:")) continue;
    const p = k.slice(8), idx = nodes.get(indexOf(p));
    for (const id of [...(idx ? idx.out || idx.nb || [] : []), ...((research[p] && research[p].topics) || [])]) if (!seed.has(id)) seed.set(id, k);
  }
  const region = (id) => { const b = base.get(id); return known.has(b) ? b : b === "hub" ? null : seed.get(id) || null; };
  for (const n of nodes.values()) {
    let k = base.get(n.id);
    if (k !== "hub" && !known.has(k)) {
      k = seed.get(n.id);
      if (!k) {
        const votes = new Map();
        for (const id of n.nb || []) { const r = region(id); if (r) votes.set(r, (votes.get(r) || 0) + 1); }
        const proj = (key) => (key.startsWith("project:") ? 1 : 0);
        const top = [...votes].sort((a, b) => b[1] - a[1] || proj(a[0]) - proj(b[0]) || a[0].localeCompare(b[0]))[0];
        k = (top && top[0]) || "other";
      }
    }
    n.neighborhood = k;
  }
  for (const n of nodes.values()) {
    const other = [...(n.nb || [])].map((id) => nodes.get(id)).filter((q) => q && q.role !== "book");
    n.sdeg = n.role === "book" ? Math.min(n.nb ? n.nb.size : 0, 4) : other.length;
    n.bridge = new Set(other.map((q) => q.neighborhood).filter((h) => h !== n.neighborhood && h !== "other")).size;
  }
  return hoods;
}
// which notes get their names when zoomed in, best first: course pages, hubs and projects, then notes that link
// across neighbourhoods, then the best-linked; a book's index note last
function rankLabels(nodes) {
  const score = (n) => (n.role === "course" || n.role === "hub" ? 3e6 : n.role === "book" ? -1e6 : n.bridge * 1e3) + (n.sdeg || 0);
  return [...nodes].sort((a, b) => score(b) - score(a) || a.id.localeCompare(b.id));
}
// each region's name and where it goes: the middle of its notes (better-linked notes count more; books barely), for
// neighbourhoods of three notes or more, and every research project however small (placed first, so a bigger
// region's name never crowds it out); in the map's own coordinates
function regionSpots(nodes, hoods) {
  const acc = new Map();
  for (const n of nodes) {
    if (n.neighborhood === "other" || !hoods.has(n.neighborhood)) continue;
    const w = n.role === "book" ? 0.2 : Math.sqrt((n.sdeg || 0) + 1), a = acc.get(n.neighborhood) || { x: 0, y: 0, w: 0, n: 0 };
    a.x += n.x * w; a.y += n.y * w; a.w += w; a.n++; acc.set(n.neighborhood, a);
  }
  const proj = (key) => (hoods.get(key).project ? 1 : 0); // research first: its name always gets a place
  return [...acc].filter(([key, a]) => a.n >= 3 || proj(key)).sort((p, q) => proj(q[0]) - proj(p[0]) || q[1].n - p[1].n)
    .map(([key, a]) => ({ key, label: hoods.get(key).label, project: !!hoods.get(key).project, x: a.x / a.w, y: a.y / a.w, n: a.n }));
}
// -- end of the pure part
const ZOOM_NAMES = 1.35; // zoomed in this far, notes get their names and the regions' names step back

const HUB_LINKS = 12, MAX_STEP = 40; // the notes graph: springs per hub, the furthest a note moves a frame
class Mind {
  constructor(cv) { this.cv = cv; this.nodes = new Map(); this.links = []; this.alpha = 1; this.view = { x: 0, y: 0, k: 1 }; this.autofit = true;
    this.flares = []; this.groupIdx = new Map(); this.hover = null; this.selected = null; this.query = ""; this.showRecent = false; this.version = -1;
    this.only = null; // Study mode: the subject's notes (their ids), lit and fitted to the pane
    this.wire(); }
  colorOf(n) {
    const key = typeof n === "object" && n ? n.neighborhood : n;
    const hood = this.hoods && this.hoods.get(key);
    return (hood && hood.color) || PAL.dim;
  }
  update(g) {
    const first = this.version < 0; this.version = g.version; const seen = new Set();
    for (const n of g.nodes) { seen.add(n.id); let node = this.nodes.get(n.id);
      if (!node) { node = Object.assign({}, n, { x: (Math.random() - 0.5) * 300, y: (Math.random() - 0.5) * 300, vx: 0, vy: 0, deg: 0 }); this.nodes.set(n.id, node); } else Object.assign(node, n); }
    for (const id of [...this.nodes.keys()]) if (!seen.has(id)) this.nodes.delete(id);
    this.links = g.links.map(([a, b]) => [this.nodes.get(a), this.nodes.get(b)]).filter(([a, b]) => a && b);
    for (const n of this.nodes.values()) { n.deg = 0; n.nb = new Set(); n.out = new Set(); }
    for (const [a, b] of this.links) { a.deg++; b.deg++; a.nb.add(b.id); b.nb.add(a.id); a.out.add(b.id); }
    this.hoods = assignHoods(this.nodes, { layout: g.layout, research: g.research });
    this.anchor = new Map([...this.hoods].map(([k, v]) => [k, v.anchor]));
    if (first) for (const n of this.nodes.values()) { const a = this.anchor.get(n.neighborhood) || { x: 0, y: 0 }; n.x = a.x + (Math.random() - 0.5) * 140; n.y = a.y + (Math.random() - 0.5) * 140; }
    else for (const id of g.changed || []) { const n = this.nodes.get(id); if (n) this.flares.push({ n, t0: performance.now() / 1000 }); this.alpha = Math.max(this.alpha, 0.45); }
    this.meta();
  }
  meta() { } // the summary line: notes, links, neighbourhoods (home.js, phone.js)
  toggleRecent() {
    this.showRecent = !this.showRecent;
    this.meta();
  }
  step() {
    const nodes = [...this.nodes.values()]; if (!nodes.length) return; const a = this.alpha;
    for (let i = 0; i < nodes.length; i++) {
      const p = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const q = nodes[j];
        let dx = q.x - p.x, dy = q.y - p.y;
        let d2 = dx * dx + dy * dy;
        if (d2 > 360000) continue;
        const d = Math.sqrt(Math.max(1, d2));
        const minDist = 26;
        let rep = (42 * a) / (d + 18);
        if (d < minDist) rep += ((minDist - d) / minDist) * 2.0 * a;
        const fx = (dx / d) * rep, fy = (dy / d) * rep;
        p.vx -= fx; p.vy -= fy; q.vx += fx; q.vy += fy;
      }
    }
    for (const [p, q] of this.links) {
      const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1;
      const sameHood = p.neighborhood === q.neighborhood;
      const targetL = sameHood ? (70 + Math.min(50, (p.deg + q.deg) * 0.7)) : (120 + Math.min(60, (p.deg + q.deg) * 0.8));
      const f = ((d - targetL) / d) * 0.022 * a;
      // a hub's springs are shared out over its links: a map note with hundreds of them would otherwise overshoot
      // further each step until the whole graph flies off the screen
      const fp = f * Math.min(1, HUB_LINKS / p.deg), fq = f * Math.min(1, HUB_LINKS / q.deg);
      p.vx += dx * fp; p.vy += dy * fp;
      q.vx -= dx * fq; q.vy -= dy * fq;
    }
    for (const n of nodes) {
      const an = this.anchor.get(n.neighborhood) || { x: 0, y: 0 };
      const pull = n.deg ? 0.0007 : 0.0025;
      n.vx += (an.x - n.x) * pull * a - n.x * 0.0001 * a;
      n.vy += (an.y - n.y) * pull * a - n.y * 0.0001 * a;
      if (n === this.dragging) { n.vx = n.vy = 0; continue; }
      n.vx *= 0.80; n.vy *= 0.80;
      const sp = Math.hypot(n.vx, n.vy); if (sp > MAX_STEP) { n.vx *= MAX_STEP / sp; n.vy *= MAX_STEP / sp; }
      n.x += n.vx; n.y += n.vy;
      if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) { n.x = an.x; n.y = an.y; n.vx = n.vy = 0; }
    }
    this.alpha = Math.max(0.04, this.alpha * 0.988);
  }
  fit(w, h) {
    let nodes = [...this.nodes.values()]; if (!nodes.length) return;
    if (this.only) { const o = nodes.filter((n) => this.only.has(n.id)); if (o.length) nodes = o; }
    const xs = nodes.map((n) => n.x).sort((a, b) => a - b), ys = nodes.map((n) => n.y).sort((a, b) => a - b);
    const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.round(f * (arr.length - 1))))];
    const x0 = q(xs, 0.02), x1 = q(xs, 0.98), y0 = q(ys, 0.02), y1 = q(ys, 0.98);
    const pad = this.fitPad != null ? this.fitPad : DENSE ? 120 : 160; // room left for the names (the phone's is narrow)
    const k = Math.min((w - pad) / Math.max(50, x1 - x0), (h - 90) / Math.max(50, y1 - y0)), tk = clamp(k, 0.08, 2.5);
    this.view.k += (tk - this.view.k) * 0.05; this.view.x += (-(x0 + x1) / 2 - this.view.x) * 0.05; this.view.y += (-(y0 + y1) / 2 - this.view.y) * 0.05;
  }
  // a note's dot: bigger the more links it has (a book's reading links don't count)
  radius(n) { return (2.0 + Math.sqrt(n.sdeg != null ? n.sdeg : n.deg) * 0.95) * Math.sqrt(this.view.k); }
  toScreen(n, w, h) { return { x: w / 2 + (n.x + this.view.x) * this.view.k, y: h / 2 + 8 + (n.y + this.view.y) * this.view.k }; }
  toWorld(x, y, w, h) { return { x: (x - w / 2) / this.view.k - this.view.x, y: (y - h / 2 - 8) / this.view.k - this.view.y }; }
  draw() {
    const { ctx, w, h } = fitCanvas(this.cv); this.w = w; this.h = h; ctx.clearRect(0, 0, w, h);
    if (!this.nodes.size) { ctx.fillStyle = PAL.dim; ctx.font = cf(12); ctx.textAlign = "center"; ctx.fillText("Your notes folder is empty so far.", w / 2, h / 2); return; }
    if (this.autofit) this.fit(w, h);
    const nowS = Date.now() / 1000, focus = this.hover || this.selected;
    const match = this.query ? new Set([...this.nodes.values()].filter((n) => (n.title + " " + n.id).toLowerCase().includes(this.query)).map((n) => n.id)) : this.only && this.only.size ? this.only : null;
    const isRecent = (n) => (nowS - (n.mtime || 0) < 86400);
    const lit = (n) => (match ? match.has(n.id) : focus ? n === focus || focus.nb.has(n.id) : this.showRecent ? isRecent(n) : true);
    
    // Links with neighborhood color
    for (const [p, q] of this.links) {
      const A = this.toScreen(p, w, h), B = this.toScreen(q, w, h), on = focus && (p === focus || q === focus);
      const col = this.colorOf(p);
      const linkLit = (!focus && !match && !this.showRecent) || (focus && on) || (match && match.has(p.id) && match.has(q.id)) || (this.showRecent && isRecent(p) && isRecent(q));
      ctx.strokeStyle = rgba(col, on ? 0.85 : linkLit ? 0.08 : 0.015);
      ctx.lineWidth = on ? 1.4 : 0.7;
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
    }

    // Nodes
    for (const n of this.nodes.values()) {
      const S = this.toScreen(n, w, h); if (S.x < -20 || S.y < -20 || S.x > w + 20 || S.y > h + 20) continue;
      const isFocused = (n === focus), isNeighbor = focus && focus.nb.has(n.id);
      const isNodeRecent = isRecent(n);
      const isHourRecent = (nowS - (n.mtime || 0) < 3600);
      const isLit = lit(n);
      const r = this.radius(n), col = this.colorOf(n);
      ctx.fillStyle = rgba(col, isLit ? (isFocused || isNeighbor ? 1.0 : 0.88) : 0.08);
      ctx.beginPath(); ctx.arc(S.x, S.y, r, 0, TAU); ctx.fill();
      if (isFocused) { ctx.strokeStyle = PAL.fg; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(S.x, S.y, r + 4.5, 0, TAU); ctx.stroke(); }
      if (this.showRecent && isNodeRecent) {
        ctx.strokeStyle = isHourRecent ? PAL.peach : rgba(col, 0.70);
        ctx.lineWidth = isHourRecent ? 1.4 : 0.9;
        ctx.beginPath(); ctx.arc(S.x, S.y, r + (isHourRecent ? 4 : 3), 0, TAU); ctx.stroke();
      }
    }

    const now = performance.now() / 1000; this.flares = this.flares.filter((f) => now - f.t0 < 4);
    for (const f of this.flares) { const k = (now - f.t0) / 4, S = this.toScreen(f.n, w, h); ctx.strokeStyle = rgba(PAL.sand, 0.8 * (1 - k)); ctx.lineWidth = 2 * (1 - k); ctx.beginPath(); ctx.arc(S.x, S.y, 4 + 46 * Math.sqrt(k), 0, TAU); ctx.stroke(); }
    
    // Names, with collision avoidance: the regions' names at the usual zoom; the notes' own when pointed at, found,
    // recent (R) or zoomed in (then the best by rankLabels)
    const zoomed = this.view.k >= ZOOM_NAMES;
    const onScreen = (n) => { const S = this.toScreen(n, w, h); return S.x > 0 && S.y > 0 && S.x < w && S.y < h; };
    const hubs = zoomed ? rankLabels([...this.nodes.values()].filter(onScreen)).filter((n) => n.role !== "book").slice(0, Math.round(6 + 4 * this.view.k)) : [];
    const recentTop = this.showRecent ? [...this.nodes.values()].filter(isRecent).sort((a, b) => (b.mtime || 0) - (a.mtime || 0)).slice(0, 8) : [];

    const candidates = [];
    if (focus) candidates.push({ node: focus, isFocused: true, priority: 1 });
    if (match && match.size < 25) {
      for (const id of match) {
        const n = this.nodes.get(id);
        if (n && n !== focus) candidates.push({ node: n, isMatched: true, priority: 2 });
      }
    }
    if (!focus && !match) {
      const list = this.showRecent ? recentTop : hubs;
      for (const n of list) candidates.push({ node: n, isHub: true, priority: 3 });
    }

    const placed = [];
    const collides = (b) => {
      if (b.x < 6 || b.y < 22 || b.x + b.w > w - 6 || b.y + b.h > h - 6) return true;
      for (const p of placed) {
        if (!(b.x + b.w + 4 < p.x || b.x > p.x + p.w + 4 || b.y + b.h + 3 < p.y || b.y > p.y + p.h + 3)) return true;
      }
      return false;
    };
    // the regions' names: large and quiet, in their colour; they step back while a note is pointed at or found, and
    // fade out as you zoom in
    const quiet = focus || match || this.showRecent, fade = clamp((ZOOM_NAMES + 0.25 - this.view.k) / 0.5, 0, 1);
    if (fade > 0 && !this.only) {
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      for (const g of regionSpots(this.nodes.values(), this.hoods || new Map())) {
        ctx.font = cf(13, g.project ? 750 : 650); // a research project's name: a little stronger, in the accent
        const S = this.toScreen(g, w, h), txt = g.label.length > 30 ? g.label.slice(0, 29) + "…" : g.label;
        const tw = ctx.measureText(txt).width, bh = 18 * FSC;
        let box = null;
        for (const dy of [0, -bh - 2, bh + 2, -2 * bh - 4, 2 * bh + 4]) {
          const b = { x: clamp(S.x - tw / 2 - 4, 8, w - tw - 16), y: clamp(S.y + dy - bh / 2, 24, h - bh - 8), w: tw + 8, h: bh };
          if (!collides(b)) { box = b; break; }
        }
        if (!box) continue;
        if (!quiet) placed.push(box);
        const a = fade * (quiet ? 0.35 : 0.95), x = box.x + box.w / 2, y = box.y + bh / 2;
        ctx.strokeStyle = rgba(PAL.bg, 0.85 * a); ctx.lineWidth = 4; ctx.strokeText(txt, x, y);
        ctx.fillStyle = rgba(g.project ? PAL.accent : mix(this.hoods.get(g.key).color, PAL.fg, 0.35), a); ctx.fillText(txt, x, y);
      }
    }
    ctx.font = cf(10.5, 600);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (const item of candidates) {
      const n = item.node;
      const S = this.toScreen(n, w, h);
      if (S.x < -20 || S.y < -20 || S.x > w + 20 || S.y > h + 20) continue;
      const r = this.radius(n);
      const txt = n.title.length > 28 ? n.title.slice(0, 27) + "…" : n.title;
      const tw = ctx.measureText(txt).width;
      const pillW = tw + 18, pillH = 18;

      const slots = [
        { x: S.x - pillW / 2, y: S.y - r - pillH - 4 },
        { x: S.x - pillW / 2, y: S.y + r + 4 },
        { x: S.x + r + 6, y: S.y - pillH / 2 },
        { x: S.x - r - pillW - 6, y: S.y - pillH / 2 }
      ];

      let chosen = null;
      for (const s of slots) {
        const box = { x: s.x, y: s.y, w: pillW, h: pillH };
        if (!collides(box)) { chosen = box; break; }
      }

      if (!chosen && item.isFocused) {
        chosen = { x: S.x - pillW / 2, y: S.y - r - pillH - 4, w: pillW, h: pillH };
      }
      if (!chosen) continue;

      placed.push(chosen);
      const col = this.colorOf(n);

      ctx.fillStyle = rgba(PAL.bg, item.isFocused ? 0.95 : 0.88);
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(chosen.x, chosen.y, pillW, pillH, 4);
      else ctx.rect(chosen.x, chosen.y, pillW, pillH);
      ctx.fill();

      ctx.strokeStyle = item.isFocused ? PAL.fg : rgba(col, item.isHub ? 0.6 : 0.35);
      ctx.lineWidth = item.isFocused ? 1.2 : 0.8;
      ctx.stroke();

      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(chosen.x + 8, chosen.y + pillH / 2, 2.5, 0, TAU); ctx.fill();

      ctx.fillStyle = item.isFocused ? PAL.fg : rgba(PAL.fg, 0.92);
      ctx.fillText(txt, chosen.x + pillW / 2 + 4, chosen.y + pillH / 2);
    }
    if (DENSE) this.hud(ctx, w, h, nowS);
  }
  // dense: semantic neighborhoods and their counts
  hud(ctx, w, h, nowS) {
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic"; ctx.font = cf(11);
    const counts = new Map();
    for (const n of this.nodes.values()) counts.set(n.neighborhood, (counts.get(n.neighborhood) || 0) + 1);
    const legend = [...(this.hoods || [])]
      .map(([k, v]) => [v.label, counts.get(k) || 0, v.color])
      .filter(([_, count]) => count > 0);
    const legOpen = LEGENDS || inside(this.mouse, this.legendRect);
    if (legOpen && legend.length) {
      const lw = Math.max(...legend.map(([l, c]) => ctx.measureText(`${l} ${c}`).width)) + 26;
      ctx.fillStyle = rgba(PAL.bg, 0.75); ctx.fillRect(w - lw - 10, 14, lw, legend.length * 15 + 6);
      let y = 26;
      for (const [label, count, col] of legend) {
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(w - lw - 1, y - 4, 3.5, 0, TAU); ctx.fill();
        ctx.fillStyle = rgba(PAL.fg, 0.75); ctx.fillText(`${label} ${count}`, w - lw + 8, y); y += 15;
      }
      this.legendRect = { x0: w - lw - 10, y0: 14, x1: w - 10, y1: 14 + legend.length * 15 + 6 };
    } else if (legend.length) { // folded: a row of the neighbourhoods' colours and one word
      const dots = legend.length * 9, tw = ctx.measureText("legend ▸").width, x1 = w - 12, x0 = x1 - dots - tw - 8;
      legend.forEach(([, , col], i) => { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x0 + 4 + i * 9, 22, 3, 0, TAU); ctx.fill(); });
      ctx.fillStyle = rgba(PAL.fg, 0.5); ctx.fillText("legend ▸", x0 + dots + 6, 26);
      this.legendRect = { x0: x0 - 2, y0: 14, x1: x1 + 2, y1: 32 };
    }
    if (this.showRecent) { // only while it's on: R (or a click on this line) turns it off
      const hotHour = [...this.nodes.values()].filter((n) => nowS - (n.mtime || 0) < 3600).length;
      const hotDay = [...this.nodes.values()].filter((n) => nowS - (n.mtime || 0) < 86400).length;
      say(ctx, `Recent: ${hotHour} in the last hour, ${hotDay} today · R: off`, 14, 26, PAL.peach, "left", cf(11));
    }
    const recent = [...this.nodes.values()].sort((a, b) => (b.mtime || 0) - (a.mtime || 0)).slice(0, 5);
    const recOpen = LEGENDS || inside(this.mouse, this.recentRect);
    const shown = recOpen ? recent : recent.slice(0, 1);
    shown.forEach((n, i) => say(ctx, `~ ${n.id.slice(-40)} · ${ago(nowS - (n.mtime || 0))} ago${!recOpen && recent.length > 1 ? `  ▸ ${recent.length - 1}` : ""}`, 14, h - 14 - i * 15,
      rgba(i === 0 ? PAL.sand : PAL.fg, 0.72 - i * 0.11), "left", NEW ? `11px ${MONO}` : cf(11))); // paths
    this.recentRect = { x0: 10, y0: h - 14 - (shown.length - 1) * 15 - 12, x1: 340, y1: h - 8 };
  }
  wire() { } // pointer, touch and keys: the page's own (home.js's Notes, phone.js)
  pick(x, y) { let best = null, bd = 14; for (const n of this.nodes.values()) { const S = this.toScreen(n, this.w, this.h), d = Math.hypot(S.x - x, S.y - y); if (d < bd) { bd = d; best = n; } } return best; }
}
