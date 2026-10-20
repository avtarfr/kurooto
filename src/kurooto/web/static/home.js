// The dashboard: STATUS (this computer), SYSTEMS (Kurooto's features as living cells round a beating core; what
// happens runs along the nerves), NOTES (your notes and their links) and tabs for activity, AI jobs, the
// schedule, features and settings. Everything comes from /api/stream; nothing loads from the internet.
//
// Two layouts (Settings → look.layout). "dense", the default on screens 1280 px wide or more, is one full-screen
// board: thin borders with each pane's name in its top line, STATUS down the left as a btop-like monitor (processor,
// memory, graphics card, network, disks, processes, study today, projects), SYSTEMS with today, what's due, the AI's
// corner and recent events round the cells, NOTES with its folders and latest edits, and a terminal below whose
// border also holds the other tabs (Alt+1… switches terminals, Alt+/ finds a note). "roomy" is the earlier
// layout with bigger type, used by itself on narrower screens.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const TAU = Math.PI * 2;
const FONT = '"JetBrains Mono", "Cascadia Mono", "SF Mono", Consolas, monospace';
// the canvases' colours are the page's palette (style.css: "kuro" by default, "rose" with look.palette = rose)
const css = (name, fallback) => { const v = getComputedStyle(document.body).getPropertyValue(name).trim(); return /^#[0-9a-f]{6}$/i.test(v) ? v : fallback; };
const PAL = { bg: css("--bg", "#0b0f0a"), fg: css("--fg", "#dad3c8"), accent: css("--accent-text", "#a6c07a"), lav: css("--lav", "#8dbdb3"),
  pink: css("--pink", "#d6967a"), peach: css("--peach", "#ddb866"), sand: css("--sand", "#e4d8b4"), rose: css("--rose", "#b9a6cc"),
  bad: css("--bad", "#e8735a"), panel: css("--panel", "#151b12") };
const hexRgb = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const mix = (a, b, t) => "#" + hexRgb(a).map((v, i) => Math.round(v + (hexRgb(b)[i] - v) * t).toString(16).padStart(2, "0")).join("");
const rgba = (h, a) => { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; };
PAL.dim = mix(PAL.fg, PAL.bg, 0.5); PAL.line = mix(PAL.lav, PAL.bg, 0.62);
// the palette can change while the page is open (look.palette = system follows the desktop): read it again
function readPalette() {
  Object.assign(PAL, { bg: css("--bg", PAL.bg), fg: css("--fg", PAL.fg), accent: css("--accent-text", PAL.accent), lav: css("--lav", PAL.lav),
    pink: css("--pink", PAL.pink), peach: css("--peach", PAL.peach), sand: css("--sand", PAL.sand), rose: css("--rose", PAL.rose),
    bad: css("--bad", PAL.bad), panel: css("--panel", PAL.panel) });
  PAL.dim = mix(PAL.fg, PAL.bg, 0.5); PAL.line = mix(PAL.lav, PAL.bg, 0.62);
  if (typeof SPRITES !== "undefined") SPRITES.clear();
  if (typeof TERM !== "undefined") for (const x of Object.values(TERM.xs)) x.term.options.theme = { background: PAL.panel, foreground: PAL.fg, cursor: PAL.accent, selectionBackground: rgba(PAL.lav, 0.35) };
  if (typeof last !== "undefined" && last) renderStatus(last);
}
window.addEventListener("kurooto:palette", () => requestAnimationFrame(readPalette));
// cool to warm, for meters and graphs: the palette's lav, peach and pink
const grad = (v) => (v = clamp(v || 0, 0, 1)) < 0.5 ? mix(PAL.lav, PAL.peach, v * 2) : mix(PAL.peach, PAL.pink, (v - 0.5) * 2);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ago = (sec) => { if (sec == null || !isFinite(sec)) return "—"; sec = Math.max(0, sec); if (sec < 60) return `${Math.round(sec)}s`; if (sec < 3600) return `${Math.round(sec / 60)}m`; if (sec < 86400) return `${Math.floor(sec / 3600)}h${String(Math.floor((sec % 3600) / 60)).padStart(2, "0")}`; return `${Math.floor(sec / 86400)}d`; };
const bytes = (n) => { if (!n) return "0"; const u = ["B", "K", "M", "G", "T"]; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return `${n.toFixed(i > 1 ? 1 : 0)}${u[i]}`; };
const hm = (ts) => new Date(ts * 1000).toTimeString().slice(0, 5);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();
let LIGHT = false; // lighter drawing on modest computers (hardware profile "light") or with reduced motion

// ------------------------------------------------------------------------------------------------ layout
const WANT = () => (document.body.dataset.layout === "roomy" ? "roomy" : "dense");
let DENSE = false;
const denseFits = () => WANT() === "dense" && window.innerWidth >= 1280 && window.innerHeight >= 600;

const SPRITES = new Map();
function glow(color) {
  if (SPRITES.has(color)) return SPRITES.get(color);
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d"), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, rgba(color, 0.85)); gr.addColorStop(0.25, rgba(color, 0.35)); gr.addColorStop(1, rgba(color, 0));
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128); SPRITES.set(color, c); return c;
}
function fitCanvas(cv) {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); return { ctx, w, h };
}
// text on a plate of background, so it stays readable over whatever moves behind it
function say(ctx, s, x, y, col, align = "left", font = `9px ${FONT}`) {
  ctx.font = font; ctx.textAlign = align; ctx.textBaseline = "alphabetic";
  const wd = ctx.measureText(s).width, x0 = align === "right" ? x - wd : align === "center" ? x - wd / 2 : x;
  ctx.fillStyle = rgba(PAL.bg, 0.72); ctx.fillRect(x0 - 2, y - 9, wd + 4, 12); ctx.fillStyle = col; ctx.fillText(s, x, y);
  return wd;
}

// ------------------------------------------------------------------------------------------------ SYSTEMS
const COLORS = { telegram: "lav", chat: "peach", reminders: "pink", checkins: "rose", deadlines: "accent", gbrain: "lav",
  local_models: "sand", subjects: "sand", quiz: "pink", weekly: "rose", files: "peach", skills: "lav", library: "sand",
  remember: "rose", retro: "pink", capture: "peach", calls: "accent", alarm: "peach", voice_notes: "lav", calendar: "rose",
  notes_sync: "lav", backups: "sand", google: "peach", study: "accent", research: "lav", terminals: "sand" };
const SHORT = { telegram: "telegram", chat: "chat", reminders: "reminders", checkins: "check-ins", deadlines: "deadlines",
  gbrain: "notes brain", local_models: "local models", subjects: "subjects", quiz: "quiz", weekly: "weekly", files: "files",
  library: "quick notes", retro: "look back", capture: "after class", voice_notes: "voice notes", notes_sync: "notes sync",
  classroom_notes: "classroom", mail_digest: "mail", reply_drafts: "drafts", agent_plan: "agent plan", awake: "awake",
  handwritten: "handwritten", study: "study", research: "research", calendar: "calendar", alarm: "alarm", calls: "calls",
  skills: "skills", remember: "remember", terminals: "terminals", backups: "backups", google: "google" };
const OUTBOUND = /fired|asked|told|notified|done|reply/;
const BRAIN = { agy: "agy", codex: "codex", claude: "claude", gemini: "gemini", ollama: "local AI" };
const brainName = (b) => (b && BRAIN[b.id]) || "AI"; // agy, codex…; any other brain is "your AI"

class Body {
  constructor(cv) {
    this.cv = cv; this.state = null; this.o = new Map(); this.pulses = []; this.ripples = []; this.widths = new Map();
    this.beats = []; this.systoles = []; this.nextBeat = 0; this.beat = 0;
    cv.addEventListener("mousemove", (e) => { const r = cv.getBoundingClientRect(); this.mouse = { x: e.clientX - r.left, y: e.clientY - r.top }; });
    cv.addEventListener("mouseleave", () => { this.mouse = null; });
  }
  update(m) {
    this.state = m;
    const on = m.cells.filter((c) => c.on);
    const ids = on.map((c) => c.id);
    for (const id of [...this.o.keys()]) if (!ids.includes(id)) this.o.delete(id);
    const fx = Object.fromEntries((m.features || []).map((f) => [f.id, f]));
    on.forEach((c, i) => {
      let o = this.o.get(c.id);
      if (!o) { o = { id: c.id, label: SHORT[c.id] || c.title, color: COLORS[c.id] || "fg", seed: Math.random() * 10, act: 0, flash: 0, hist: [] }; this.o.set(c.id, o); }
      o.i = i; o.target = c.act; o.data = c; o.hist.push(c.act); if (o.hist.length > 60) o.hist.shift();
      const f = fx[c.id] || {};
      o.proc = f.proc || null; o.last = f.last; o.next = f.next; o.down = !!f.down; o.idle = !!f.idle; o.often = !!f.intermittent;
    });
    let meta = `${on.length} feature${on.length === 1 ? "" : "s"} on`;
    const down = (m.features || []).filter((f) => f.down).length;
    if (down) meta += ` · ${down} not running`;
    if (DENSE && m.core && m.core.mem) meta += ` · kurooto ${(m.core.cpu * 100).toFixed(1)}% · ${bytes(m.core.mem)}`;
    if (m.link) meta += ` · call line ${m.link.connected ? "linked" : "offline"}`;
    $("#sys-meta").textContent = meta;
  }
  event(e) {
    const o = this.o.get(e.cell);
    const col = o ? PAL[o.color] : PAL.accent;
    if (o) { (OUTBOUND.test(e.kind) ? this.pulse("core", e.cell, col) : this.pulse(e.cell, "core", col)); o.flash = 1; }
    else this.ripples.push({ t0: performance.now() / 1000, col });
    this.extraBeat(1.3, col);
  }
  extraBeat(amp, col) {
    const now = performance.now() / 1000, last = this.beats[this.beats.length - 1];
    const t = last && now - last.t < 0.35 ? last.t + 0.35 : now;
    this.beats.push({ t, amp, col }); this.systoles.push({ t: t + 0.15, amp, col }); this.nextBeat = Math.max(this.nextBeat, t + 0.5);
  }
  pulse(from, to, color, dur = 1.3) { this.pulses.push({ from, to, color, t0: performance.now() / 1000, dur }); }
  tickBeats(now, cpu) {
    const bpm = clamp(58 + cpu * 140, 55, 130);
    if (now >= this.nextBeat) {
      const last = this.beats[this.beats.length - 1];
      if (!last || now - last.t > 0.3) { this.beats.push({ t: now, amp: 1, col: null }); this.systoles.push({ t: now + 0.15, amp: 1, col: null }); }
      this.nextBeat = now + (60 / bpm) * (0.94 + Math.random() * 0.12);
    }
    this.beats = this.beats.filter((b) => now - b.t < 3); this.systoles = this.systoles.filter((p) => now - p.t < 1.2);
  }
  blob(ctx, x, y, r, t, seed, wob, spin = 0) {
    const N = LIGHT ? 24 : 48, pts = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * TAU, b = a - spin;
      const k = 1 + wob * (0.5 * Math.sin(2 * b + t * 0.55 + seed) + 0.38 * Math.sin(3 * b - t * 0.9 + seed * 1.7) + 0.22 * Math.sin(5 * b + t * 1.4 + seed * 2.3));
      pts.push([x + Math.cos(a) * r * k, y + Math.sin(a) * r * k]);
    }
    ctx.beginPath();
    const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    let m = mid(pts[N - 1], pts[0]); ctx.moveTo(m[0], m[1]);
    for (let i = 0; i < N; i++) { const p = pts[i], q = pts[(i + 1) % N]; m = mid(p, q); ctx.quadraticCurveTo(p[0], p[1], m[0], m[1]); }
    ctx.closePath();
  }
  say(ctx, s, x, y, col, align = "left", font = `9px ${FONT}`) { return say(ctx, s, x, y, col, align, font); }
  ecg(ctx, w, now, base, amp) {
    const g = (d, mu, sd) => Math.exp(-((d - mu) ** 2) / (2 * sd * sd));
    const at = (tt) => { let v = 0.004 * Math.sin(tt * 47), col = null, best = 0;
      for (const b of this.beats) { const d = tt - b.t; if (d < -0.05 || d > 0.62) continue;
        const k = b.amp * (0.1 * g(d, 0.05, 0.02) - 0.12 * g(d, 0.125, 0.008) + g(d, 0.15, 0.0085) - 0.32 * g(d, 0.172, 0.009) + 0.27 * g(d, 0.36, 0.05));
        v += k; if (b.col && Math.abs(k) > best) { best = Math.abs(k); col = b.col; } }
      return [v, best > 0.08 ? col : null]; };
    const span = 6, step = 2, cols = Math.max(10, Math.floor(w / step)), c = this.trace || (this.trace = {});
    const head = Math.floor(((((now % span) + span) % span) / span) * cols);
    if (!c.v || c.v.length !== cols) { c.v = new Float32Array(cols); c.c = new Array(cols).fill(null);
      for (let i = 0; i < cols; i++) { const [v, col] = at(now - ((head - i + cols) % cols) * (span / cols)); c.v[i] = v; c.c[i] = col; } c.head = head; }
    let k = c.head, guard = 0;
    while (k !== head && guard++ < cols) { k = (k + 1) % cols; const [v, col] = at(now - ((head - k + cols) % cols) * (span / cols)); c.v[k] = v; c.c[k] = col; }
    c.head = head;
    ctx.globalCompositeOperation = "lighter";
    let run = null;
    const flush = () => { if (run) { ctx.strokeStyle = rgba(run.col, run.a); ctx.lineWidth = 1.1; ctx.stroke(); run = null; } };
    for (let i = 1; i < cols; i++) {
      const age = ((head - i + cols) % cols) / cols;
      if (age > 0.965 || i - 1 === head) { flush(); continue; }
      const col = c.c[i] || PAL.accent, a = 0.24 * (1 - Math.min(5, Math.floor(age * 6)) / 6.5);
      if (!run || run.col !== col || run.a !== a) { flush(); run = { col, a }; ctx.beginPath(); ctx.moveTo((i - 1) * step, base - c.v[i - 1] * amp); }
      ctx.lineTo(i * step, base - c.v[i] * amp);
    }
    flush(); ctx.globalCompositeOperation = "source-over";
  }
  // dense: the day's hour lines carried out past the clock, the hours on the outer ring, and the cells' orbit
  grid(ctx, cx, cy, r0, ringR, wide = 1) {
    ctx.lineWidth = 1;
    const r1 = ringR * 1.2;
    for (let k = 0; k < 24; k++) {
      const a = -Math.PI / 2 + (k / 24) * TAU, c = Math.cos(a), s = Math.sin(a);
      ctx.strokeStyle = rgba(PAL.fg, k % 6 ? 0.03 : 0.07);
      ctx.beginPath(); ctx.moveTo(cx + c * r0, cy + s * r0 * 0.86); ctx.lineTo(cx + c * r1 * wide, cy + s * r1 * 0.86); ctx.stroke();
      if (k % 3 === 0) {
        ctx.font = `8px ${FONT}`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = rgba(PAL.fg, 0.24);
        ctx.fillText(String(k).padStart(2, "0"), cx + c * (r1 * wide + 9), cy + s * (r1 + 9) * 0.86);
      }
    }
    ctx.strokeStyle = rgba(PAL.fg, 0.06); ctx.setLineDash([2, 4]);
    ctx.beginPath(); ctx.ellipse(cx, cy, ringR * wide, ringR * 0.86, 0, 0, TAU); ctx.stroke();
    ctx.setLineDash([]); ctx.strokeStyle = rgba(PAL.fg, 0.05);
    ctx.beginPath(); ctx.ellipse(cx, cy, r1 * wide, r1 * 0.86, 0, 0, TAU); ctx.stroke();
  }
  clock(ctx, cx, cy, r, t) {
    ctx.strokeStyle = rgba(PAL.line, 0.9); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.stroke();
    for (let h = 0; h < 24; h++) { const a = -Math.PI / 2 + (h / 24) * TAU, L = h % 6 === 0 ? 6 : 3;
      ctx.strokeStyle = rgba(PAL.fg, h % 6 === 0 ? 0.45 : 0.18);
      ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * (r - L), cy + Math.sin(a) * (r - L)); ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); ctx.stroke(); }
    const angHM = (s) => { const [H, M] = String(s).split(":").map(Number); return -Math.PI / 2 + ((H + (M || 0) / 60) / 24) * TAU; };
    const ang = (d) => -Math.PI / 2 + ((d.getHours() + d.getMinutes() / 60) / 24) * TAU;
    const today = (this.state && this.state.today) || {};
    for (const c of (today.items || []).filter((x) => x.end)) { // classes and calendar events: arcs on the day's ring
      ctx.strokeStyle = rgba(c.state === "now" ? PAL.accent : c.kind === "event" ? PAL.rose : PAL.lav, c.state === "skipped" ? 0.25 : c.state === "done" ? 0.4 : 0.85);
      ctx.lineWidth = 4; ctx.setLineDash(c.state === "skipped" ? [2, 3] : []);
      ctx.beginPath(); ctx.arc(cx, cy, r + 4, angHM(c.at), angHM(c.end)); ctx.stroke();
    }
    ctx.setLineDash([]); ctx.lineWidth = 1;
    for (const j of (today.items || []).filter((x) => !x.end)) { const a = angHM(j.at); ctx.fillStyle = PAL.pink; ctx.beginPath(); ctx.arc(cx + Math.cos(a) * (r + 4), cy + Math.sin(a) * (r + 4), 2.4, 0, TAU); ctx.fill(); }
    if (!today.items) for (const j of (this.state && this.state.schedule) || []) {
      if (j.kind !== "once") continue;
      const when = new Date(j.when * 1000); if (when - Date.now() > 86400000) continue;
      const a = ang(when); ctx.fillStyle = PAL.pink; ctx.beginPath(); ctx.arc(cx + Math.cos(a) * (r + 4), cy + Math.sin(a) * (r + 4), 2.3, 0, TAU); ctx.fill();
    }
    const a = ang(new Date());
    ctx.strokeStyle = rgba(PAL.sand, 0.9); ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * (r - 7), cy + Math.sin(a) * (r - 7)); ctx.lineTo(cx + Math.cos(a) * (r + 8), cy + Math.sin(a) * (r + 8)); ctx.stroke();
    ctx.lineWidth = 1; ctx.fillStyle = PAL.sand; ctx.beginPath(); ctx.arc(cx + Math.cos(a) * (r + 4), cy + Math.sin(a) * (r + 4), 2.2 + 0.6 * Math.sin(t * 3), 0, TAU); ctx.fill();
  }
  draw(t) {
    const { ctx, w, h } = fitCanvas(this.cv);
    ctx.clearRect(0, 0, w, h);
    if (!this.state) return;
    const now = performance.now() / 1000, cpu = this.state.sys.cpu || 0;
    let ringR, cx = w / 2, cy = h / 2 + 4;
    if (DENSE) { // room for the four corners: events, the AI, today, what's due
      const lh = 12, top = 24 + 6 * lh, bottom = h - 18 - 6 * lh;
      ringR = clamp(Math.min(w * 0.35, (bottom - top - 88) / 1.72), 56, 420);
      cy = top + 0.86 * ringR + 28 + Math.max(0, (bottom - top - 88 - 1.72 * ringR) / 2);
    } else ringR = clamp(Math.min(w * 0.36, (h - 70) / 1.9), 60, 420);
    const coreR = ringR * 0.18, rc = coreR * 2.2;
    this.tickBeats(now, cpu);
    if (!LIGHT) this.ecg(ctx, w, now, cy, ringR * 0.55);
    const cells = [...this.o.values()], n = Math.max(1, cells.length), orbit = LIGHT ? 0 : (t * TAU) / 180;
    // dense, with many features: the orbit widens sideways, where the pane has room
    const wide = DENSE ? Math.min(w * 0.42 / ringR, clamp(1 + (n - 10) * 0.035, 1, 1.3)) : 1;
    // a crowded ring becomes two: every other cell rides a little closer in, so neighbours and their words have room
    const twoRings = n >= 12 && (TAU * ringR * (1 + wide) / 2) / n < 80;
    for (const o of cells) {
      const a = -Math.PI / 2 + (o.i / n) * TAU + orbit + 0.05 * Math.sin(t * 0.13 + o.seed);
      const rr = ringR * (1 + 0.04 * Math.sin(t * 0.21 + o.seed * 2)) * (twoRings && o.i % 2 ? 0.86 : 1);
      o.x = cx + Math.cos(a) * rr * wide; o.y = cy + Math.sin(a) * rr * 0.86;
      o.act += ((o.target || 0) - o.act) * 0.05; o.flash *= 0.94; o.pump = (o.pump || 0) * 0.88;
    }
    if (DENSE) this.grid(ctx, cx, cy, rc + 14, ringR, wide);
    const ctrl = (a, b, seed) => { const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, k = 0.12 * d * Math.sin(t * 0.37 + seed); return { x: mx - (dy / d) * k, y: my + (dx / d) * k }; };
    const core = { x: cx, y: cy };
    for (const o of cells) {
      const c = ctrl(core, o, o.seed), fill = o.pump || 0, g = ctx.createLinearGradient(cx, cy, o.x, o.y);
      g.addColorStop(0, rgba(PAL.accent, 0.18 + 0.12 * fill)); g.addColorStop(1, rgba(PAL[o.color], 0.28 + 0.4 * o.act + 0.12 * fill));
      ctx.strokeStyle = g; ctx.lineWidth = 0.8 + 2 * o.act + o.flash * 1.5 + 0.5 * fill;
      ctx.setLineDash(o.down ? [3, 6] : []);
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(c.x, c.y, o.x, o.y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.globalCompositeOperation = "lighter";
    for (const p of this.systoles) {
      const d = now - p.t; if (d < 0 || d > 1.0) continue;
      const k = clamp(d / 0.7, 0, 1), ease = 1 - (1 - k) ** 3;
      ctx.strokeStyle = rgba(p.col || PAL.accent, 0.12 * (1 - d) * p.amp); ctx.lineWidth = 1.2 * (1 - d);
      ctx.beginPath(); ctx.arc(cx, cy, coreR * (1.1 + 4 * ease), 0, TAU); ctx.stroke();
      if (k >= 1 || LIGHT) continue;
      for (const o of cells) {
        const c = ctrl(core, o, o.seed), x = (1 - ease) ** 2 * cx + 2 * (1 - ease) * ease * c.x + ease ** 2 * o.x, y = (1 - ease) ** 2 * cy + 2 * (1 - ease) * ease * c.y + ease ** 2 * o.y;
        const sz = 10 * p.amp; ctx.globalAlpha = 0.55 * (1 - k * 0.5); ctx.drawImage(glow(p.col || PAL[o.color]), x - sz / 2, y - sz / 2, sz, sz);
        if (k > 0.86) o.pump = Math.max(o.pump || 0, p.amp);
      }
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    this.clock(ctx, cx, cy, rc, t);
    ctx.globalCompositeOperation = "lighter";
    this.pulses = this.pulses.filter((p) => now - p.t0 < p.dur + 0.4);
    for (const p of this.pulses) {
      const o = this.o.get(p.from === "core" ? p.to : p.from); if (!o) continue;
      const c = ctrl(core, o, o.seed), sp = clamp((now - p.t0) / p.dur, 0, 1), ease = sp < 0.5 ? 2 * sp * sp : 1 - Math.pow(-2 * sp + 2, 2) / 2;
      for (let k = 0; k < 10; k++) {
        let s = ease - k * 0.025; if (s < 0) break; if (p.to === "core") s = 1 - s;
        const x = (1 - s) ** 2 * cx + 2 * (1 - s) * s * c.x + s * s * o.x, y = (1 - s) ** 2 * cy + 2 * (1 - s) * s * c.y + s * s * o.y;
        const sz = k === 0 ? 22 : 15 - k; ctx.globalAlpha = (1 - k / 10) * (1 - Math.max(0, (now - p.t0 - p.dur) / 0.4));
        ctx.drawImage(glow(p.color), x - sz / 2, y - sz / 2, sz, sz);
      }
      if (sp >= 1 && !p.done) { p.done = true; if (p.to === "core") { this.ripples.push({ t0: now, col: p.color }); this.beat = Math.max(this.beat, 0.6); } else o.flash = 1; }
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    for (const o of cells) this.cell(ctx, o, t, ringR);
    this.labels(ctx, cells, cx, cy, coreR, w, h);
    this.beat *= 0.9;
    const breath = 0.5 + 0.5 * Math.sin((TAU * t) / (6.5 - 3.5 * clamp(cpu * 2.5, 0, 1)));
    let lubdub = 0;
    for (const p of this.systoles) { const d = now - p.t; lubdub += p.amp * (0.12 * Math.exp(-((d - 0.02) ** 2) / 0.0018) + 0.05 * Math.exp(-((d - 0.33) ** 2) / 0.0018)); }
    const cr = coreR * (1 + 0.04 * breath + 0.08 * this.beat + lubdub);
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.22 + 0.12 * breath + 0.25 * this.beat + lubdub;
    ctx.drawImage(glow(PAL.accent), cx - cr * 2.6, cy - cr * 2.6, cr * 5.2, cr * 5.2);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    this.blob(ctx, cx, cy, cr, t * 0.7, 1.7, 0.05, t * 0.04);
    const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr); cg.addColorStop(0, mix(PAL.accent, PAL.pink, 0.35)); cg.addColorStop(1, PAL.accent);
    ctx.fillStyle = cg; ctx.fill();
    ctx.fillStyle = PAL.bg; ctx.font = `700 ${Math.max(9, cr * 0.32)}px ${FONT}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText((this.state.name || "Kurooto").toUpperCase().slice(0, 10), cx, cy);
    this.ripples = this.ripples.filter((r) => now - r.t0 < 1.8);
    for (const r of this.ripples) { const k = (now - r.t0) / 1.8; ctx.strokeStyle = rgba(r.col, 0.45 * (1 - k)); ctx.lineWidth = 1.5 * (1 - k); ctx.beginPath(); ctx.arc(cx, cy, coreR * (1.1 + k * 3.2), 0, TAU); ctx.stroke(); }
    if (DENSE) this.panels(ctx, w, h, 12);
    if (!cells.length) this.say(ctx, `No features on yet: turn some on in the ${DENSE ? "features tab (terminal's border)" : "Features tab below"}.`, cx, h - 16 - (DENSE ? 84 : 0), PAL.dim, "center", `11px ${FONT}`);
    this.hoverCard();
  }
  cell(ctx, o, t, ringR) {
    const base = ringR * 0.075, col = o.down ? PAL.dim : PAL[o.color], breath = 0.5 + 0.5 * Math.sin((TAU * t) / (5.5 - 4.2 * o.act) + o.seed);
    const r = base * (1 + (0.05 + 0.1 * o.act) * breath + 0.2 * o.flash + 0.08 * (o.pump || 0)); o.r = r;
    const hr = base * 1.32; ctx.lineWidth = 1;
    o.hist.forEach((v, k) => { const a = -Math.PI / 2 + (k / 60) * TAU, L = 1.2 + base * 0.55 * v;
      ctx.strokeStyle = rgba(col, 0.18 + 0.5 * (k / Math.max(1, o.hist.length - 1)));
      ctx.beginPath(); ctx.moveTo(o.x + Math.cos(a) * hr, o.y + Math.sin(a) * hr); ctx.lineTo(o.x + Math.cos(a) * (hr + L), o.y + Math.sin(a) * (hr + L)); ctx.stroke(); });
    const spin = (o.i % 2 ? -1 : 1) * t * (0.2 + o.act) + o.seed;
    if (o.act > 0.05 || o.flash > 0.05) { ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.1 + 0.2 * breath * o.act + 0.45 * o.flash;
      const gs = r * (3.5 + 2 * o.act); ctx.drawImage(glow(col), o.x - gs / 2, o.y - gs / 2, gs, gs); ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over"; }
    this.blob(ctx, o.x, o.y, r, t * (0.6 + o.act), o.seed, 0.05 + 0.05 * o.act + 0.05 * o.flash, spin);
    ctx.fillStyle = PAL.bg; ctx.fill(); ctx.fillStyle = rgba(col, 0.2 + 0.35 * o.act + 0.3 * o.flash); ctx.fill();
    ctx.strokeStyle = rgba(col, o.down ? 0.5 : 0.85); ctx.lineWidth = 1.1; ctx.setLineDash(o.down ? [2, 3] : []); ctx.stroke(); ctx.setLineDash([]);
    o.reach = hr + base * 0.55 + 1; // the cell with its halo: what words mustn't cover
  }
  // Each cell's words sit outside it, along the line from the core (never on its own nerve). A label that would touch
  // another cell, another label, the core or a corner panel tries a little further out, then turned a little either
  // way, then with fewer words (no detail, then the name alone, then a shortened name). A label that had to give way
  // needs a few pixels to spare before it grows back, so the words don't flicker as the cells orbit.
  labels(ctx, cells, cx, cy, coreR, w, h) {
    const LH = 11, placed = [], panels = DENSE ? this.panelRects || [] : [];
    const width = (text, font) => { const k = font + "|" + text; let v = this.widths.get(k);
      if (v === undefined) { ctx.font = font; v = ctx.measureText(text).width; if (this.widths.size > 4000) this.widths.clear(); this.widths.set(k, v); } return v; };
    // how badly a box would cover what's there: 0 when it fits (pad: the room it must leave)
    const cost = (b, o, pad) => {
      let c = Math.max(0, 2 - b.x0) + Math.max(0, 2 - b.y0) + Math.max(0, b.x1 - w + 2) + Math.max(0, b.y1 - h + 2);
      const into = (x, y, r) => Math.max(0, r - Math.hypot(clamp(x, b.x0 - pad, b.x1 + pad) - x, clamp(y, b.y0 - pad, b.y1 + pad) - y));
      c += into(cx, cy, coreR * 1.25) * 4;
      for (const q of cells) c += into(q.x, q.y, q === o ? q.reach - 1 : q.reach) * 3;
      for (const r of [...placed, ...panels]) {
        const ox = Math.min(b.x1 + pad, r.x1) - Math.max(b.x0 - pad, r.x0), oy = Math.min(b.y1 + pad, r.y1) - Math.max(b.y0 - pad, r.y0);
        if (ox > 0 && oy > 0) c += Math.sqrt(ox * oy) * 2;
      }
      return c;
    };
    const order = [...cells].sort((a, b) => (b.data.events || 0) - (a.data.events || 0) || (b.proc ? 1 : 0) - (a.proc ? 1 : 0) || a.i - b.i);
    for (const o of order) {
      const col = o.down ? PAL.dim : PAL[o.color], vital = this.vital(o), more = DENSE ? this.detail(o) : "";
      const name = [o.label, `600 10px ${FONT}`, rgba(o.down ? PAL.dim : PAL.fg, 0.95)];
      const full = [name, [vital, `9px ${FONT}`, o.down ? rgba(PAL.bad, 0.85) : rgba(col, 0.85)], ...(more ? [[more, `8px ${FONT}`, rgba(PAL.fg, 0.42)]] : [])];
      const short = o.label.length > 8 ? [[o.label.slice(0, 7) + "…", name[1], name[2]]] : [name];
      const variants = [full, full.slice(0, 2), [name], short].filter((v, i, all) => i === 0 || v.length < all[i - 1].length || v[0][0] !== all[i - 1][0][0]);
      const dx = o.x - cx, dy = o.y - cy, d = Math.hypot(dx, dy) || 1, a0 = Math.atan2(dy / d, dx / d);
      // close to the cell first (straight out, then turned a little), trading words for closeness before distance;
      // when nothing fits, a small short name; when even that won't, no words at all (hovering still shows the card)
      const near = [[0, 0], [0.35, 0], [-0.35, 0]], mid = [[0, 1], [0.35, 1], [-0.35, 1], [0.7, 0], [-0.7, 0]];
      const far = [[0, 2], [0.7, 1], [-0.7, 1], [1.15, 0], [-1.15, 0], [1.15, 1], [-1.15, 1], [0, 3], [0.35, 3], [-0.35, 3], [1.15, 2], [-1.15, 2]];
      const tries = [];
      for (const spots of [near, mid]) for (const lines of variants.slice(0, 3)) for (const sp of spots) tries.push([lines, sp]);
      for (const lines of variants.slice(2)) for (const sp of [...near, ...mid, ...far]) tries.push([lines, sp]);
      const tiny = [[o.label.length > 8 ? o.label.slice(0, 7) + "…" : o.label, `600 8px ${FONT}`, name[2]]];
      for (const sp of [...near, ...mid, ...far]) tries.push([tiny, sp]);
      let best = null, rank = 0;
      for (const [lines, [turn, step]] of tries) {
        const bw = Math.max(...lines.map(([s, f]) => width(s, f))) + 4, bh = lines.length * LH;
        const ux = Math.cos(a0 + turn), uy = Math.sin(a0 + turn), dist = o.reach + 3 + step * 10, ax = o.x + ux * dist, ay = o.y + uy * dist;
        const x0 = ax - bw / 2 + (bw / 2) * clamp(ux / 0.55, -1, 1), y0 = ay - bh / 2 + (bh / 2) * clamp(uy / 0.55, -1, 1);
        const b = { x0, y0, x1: x0 + bw, y1: y0 + bh, ux }, moved = turn !== 0 || step > 0;
        if (cost(b, o, rank < (o.labRank ?? 1e9) ? 5 : 1) === 0) { best = { b, lines, rank, moved }; break; }
        rank++;
      }
      o.labRank = best ? best.rank : 1e6;
      if (!best) continue;
      placed.push(best.b);
      if (best.moved) { // a hairline from the cell to words that had to move, so it's clear whose they are
        const bx = clamp(o.x, best.b.x0, best.b.x1), by = clamp(o.y, best.b.y0, best.b.y1), dd = Math.hypot(bx - o.x, by - o.y) || 1;
        ctx.strokeStyle = rgba(o.down ? PAL.dim : PAL[o.color], 0.35); ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(o.x + ((bx - o.x) / dd) * o.reach, o.y + ((by - o.y) / dd) * o.reach); ctx.lineTo(bx, by); ctx.stroke();
      }
      const { b, lines } = best, align = b.ux > 0.5 ? "left" : b.ux < -0.5 ? "right" : "center";
      const x = align === "left" ? b.x0 + 2 : align === "right" ? b.x1 - 2 : (b.x0 + b.x1) / 2;
      lines.forEach(([s, f, c], k) => this.say(ctx, s, x, b.y0 + (k + 1) * LH - 2, c, align, f));
      b.id = o.id;
    }
    this.placed = placed; // (what a check of the layout reads)
  }
  // a cell's figures: a feature with its own processes shows their cpu and memory, the others what they did
  vital(o) {
    const ev = o.data.events;
    if (o.down) return "not running";
    if (o.idle) return "idle"; // its programs run now and then (Module.processes_intermittent)
    if (!DENSE) return o.often && o.proc ? "running" : ev ? `${ev} in 2 min` : "quiet";
    if (o.proc) return `${o.often ? "running · " : ""}${(o.proc.cpu * 100).toFixed(1)}% · ${bytes(o.proc.mem)}`;
    if (ev) return `${ev} in 2 min`;
    return o.last != null ? `last ${ago(o.last)} ago` : "quiet";
  }
  detail(o) {
    if (o.proc) return [`up ${ago(o.proc.up)}`, o.proc.threads ? `${o.proc.threads} threads` : ""].filter(Boolean).join(" · ");
    if (o.next) { const d = o.next - Date.now() / 1000; return d < 86400 ? `next ${d < 3600 ? "in " + ago(d) : hm(o.next)}` : ""; }
    return "";
  }
  // the four corners: recent events, the AI's corner, today, what's due
  panels(ctx, w, h, lh) {
    const st = this.state || {}, nowS = Date.now() / 1000;
    const dim = rgba(PAL.fg, 0.42), mid = rgba(PAL.fg, 0.64);
    const cut = Math.max(16, Math.floor((w * 0.5 - 24) / 5.4));
    // a row is [text, colour] or [[title, tail], colour]: the title gives way so the tail (a time, a status) survives
    const fitRow = (s) => (Array.isArray(s) ? (s[0].length + s[1].length > cut ? s[0].slice(0, Math.max(4, cut - s[1].length - 1)) + "…" : s[0]) + s[1] : s.slice(0, cut));
    const rects = (this.panelRects = []); // where the corners' words are: the cells' labels keep clear of them
    const block = (rows, x, align, fromTop) => {
      const r = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
      rows.slice(0, 6).forEach(([s, col], i, arr) => {
        const y = fromTop ? 24 + i * lh : h - 20 - (arr.length - 1 - i) * lh, wd = say(ctx, fitRow(s), x, y, col, align), x0 = align === "right" ? x - wd : x;
        Object.assign(r, { x0: Math.min(r.x0, x0 - 2), x1: Math.max(r.x1, x0 + wd + 2), y0: Math.min(r.y0, y - 9), y1: Math.max(r.y1, y + 3) });
      });
      rects.push(r);
    };
    // recent events, newest first
    const ev = [[feed.length ? "events" : "no events yet", dim]];
    feed.slice(0, 5).forEach((e, i) => {
      const fresh = SEEN.has(e) && performance.now() / 1000 - SEEN.get(e) < 6;
      const o = this.o.get(e.cell);
      ev.push([`${(e.ts || "").slice(11, 16)} ${String(e.kind).replace(/_/g, " ")}${detailOf(e) ? " · " + detailOf(e) : ""}`,
        fresh ? (o ? PAL[o.color] : PAL.accent) : rgba(PAL.fg, 0.62 - i * 0.08)]);
    });
    block(ev, 12, "left", true);
    // the AI: what it ran lately, the local models, what's scheduled
    const ag = st.agent || {}, jobs = st.jobs || [];
    const rows = [[brainName(ag.brain) === "AI" ? "your AI" : brainName(ag.brain), dim]];
    const run = jobs.filter((j) => j.status === "running" || j.status === "queued");
    for (const j of run.slice(0, 2)) rows.push([[j.title || "a request", `  ${j.effort || ""} ${ago(nowS - j.created)}  ${j.status}`], PAL.peach]);
    for (const j of jobs.filter((x) => !run.includes(x)).slice(0, 3 - Math.min(2, run.length)))
      rows.push([[j.title || "a request", `  ${j.seconds ? ago(j.seconds) : ""}  ${j.status}`], j.status === "ok" ? mid : PAL.bad]);
    if (!jobs.length) rows.push(["no AI requests yet", mid]);
    if (ag.models) rows.push([`local models: ${ag.models.length ? ag.models.map((m) => `${m.name} ${bytes(m.vram)}`).join(", ") : "nothing loaded"}`, mid]);
    if (ag.next) rows.push([[`${ag.scheduled} scheduled · next ${ag.next.what}`, ` in ${ago(ag.next.when - nowS)}`], mid]);
    block(rows, w - 12, "right", true);
    // today
    const td = st.today || {}, items = td.items || [];
    const day = [["today", dim]];
    const live = items.filter((x) => x.state !== "done" && x.state !== "skipped");
    for (const x of live.slice(0, 4)) day.push([`${x.at}${x.end ? "–" + x.end : ""} ${x.what}${x.state === "now" ? "  now" : ""}`, x.state === "now" ? PAL.accent : mid]);
    if (td.focus) day.push([`focus until ${td.focus}`, PAL.peach]);
    if (td.quiet) day.push([`no calls until ${td.quiet}`, PAL.peach]);
    if (day.length === 1) day.push([items.length ? "nothing more today" : "nothing scheduled", mid]);
    block(day, 12, "left", false);
    // what's due
    const dl = st.deadlines || [];
    const when = (hr) => (hr < 0 ? `overdue ${ago(-hr * 3600)}` : `in ${ago(hr * 3600)}`);
    const due = [[`due · ${st.deadlines_open != null ? st.deadlines_open : dl.length} open`, dim]];
    for (const d of dl.slice(0, 5)) due.push([[d.title, `  ${when(d.hours)}`], d.hours < 0 ? PAL.bad : d.hours < 24 ? PAL.peach : mid]);
    if (!dl.length) due.push([this.o.has("deadlines") ? "nothing due" : "deadlines are off", mid]);
    block(due, w - 12, "right", false);
  }
  hoverCard() {
    const card = $("#body-card");
    if (!this.mouse) { card.classList.add("hidden"); return; }
    let best = null, bd = 1e9;
    for (const o of this.o.values()) { const d = Math.hypot(o.x - this.mouse.x, o.y - this.mouse.y); if (d < (o.r || 10) * 2.2 && d < bd) { bd = d; best = o; } }
    if (!best) { card.classList.add("hidden"); return; }
    const p = best.proc;
    card.innerHTML = `<div class="h">${esc(best.data.title)}</div><div>${best.data.events} event${best.data.events === 1 ? "" : "s"} in the last 2 minutes</div>` +
      (best.down ? '<div class="bad2">its program isn\'t running</div>' : "") +
      (best.idle ? '<div class="d">idle: its program runs now and then</div>' : "") +
      (p ? `<div class="d">${p.n > 1 ? `its ${p.n} processes` : "its process"}: cpu ${(p.cpu * 100).toFixed(1)}% · ${bytes(p.mem)} · ${p.threads} threads · up ${ago(p.up)}</div>` : "") +
      (best.last != null ? `<div class="d">last event ${ago(best.last)} ago</div>` : "") +
      (best.next ? `<div class="d">next scheduled ${hm(best.next)}</div>` : "");
    card.classList.remove("hidden");
  }
}
// an event's details in a few words (never message text: the events hold names, counts and times)
const detailOf = (e) => Object.entries(e).filter(([k]) => !["ts", "kind", "t", "cell"].includes(k))
  .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 60);

// -------------------------------------------------------------------------------------------------- NOTES
const GROUP_COL = { inbox: "fg", journal: "sand", root: "fg" };
const EXTRA = ["lav", "pink", "peach", "rose", "sand", "accent"];
class Mind {
  constructor(cv) { this.cv = cv; this.nodes = new Map(); this.links = []; this.alpha = 1; this.view = { x: 0, y: 0, k: 1 }; this.autofit = true;
    this.flares = []; this.groupIdx = new Map(); this.hover = null; this.selected = null; this.query = ""; this.version = -1; this.wire(); }
  colorOf(g) { if (GROUP_COL[g]) return PAL[GROUP_COL[g]]; if (!this.groupIdx.has(g)) this.groupIdx.set(g, this.groupIdx.size); return PAL[EXTRA[this.groupIdx.get(g) % EXTRA.length]]; }
  update(g) {
    const first = this.version < 0; this.version = g.version; const seen = new Set();
    for (const n of g.nodes) { seen.add(n.id); let node = this.nodes.get(n.id);
      if (!node) { node = { ...n, x: (Math.random() - 0.5) * 300, y: (Math.random() - 0.5) * 300, vx: 0, vy: 0, deg: 0 }; this.nodes.set(n.id, node); } else Object.assign(node, n); }
    for (const id of [...this.nodes.keys()]) if (!seen.has(id)) this.nodes.delete(id);
    this.links = g.links.map(([a, b]) => [this.nodes.get(a), this.nodes.get(b)]).filter(([a, b]) => a && b);
    for (const n of this.nodes.values()) { n.deg = 0; n.nb = new Set(); }
    for (const [a, b] of this.links) { a.deg++; b.deg++; a.nb.add(b.id); b.nb.add(a.id); }
    const groups = [...new Set([...this.nodes.values()].map((n) => n.group))].sort();
    this.groups = groups.length;
    this.anchor = new Map(groups.map((gname, i) => [gname, { x: Math.cos((i / groups.length) * TAU) * 210, y: Math.sin((i / groups.length) * TAU) * 190 }]));
    if (first) for (const n of this.nodes.values()) { const a = this.anchor.get(n.group); n.x = a.x + (Math.random() - 0.5) * 120; n.y = a.y + (Math.random() - 0.5) * 120; }
    else for (const id of g.changed || []) { const n = this.nodes.get(id); if (n) this.flares.push({ n, t0: performance.now() / 1000 }); this.alpha = Math.max(this.alpha, 0.35); }
    this.meta();
  }
  meta() { $("#mind-meta").textContent = `${this.nodes.size} notes · ${this.links.length} links` + (DENSE ? ` · ${this.groups || 0} folders` : ""); }
  step() {
    const nodes = [...this.nodes.values()]; if (!nodes.length) return; const a = this.alpha;
    for (let i = 0; i < nodes.length; i++) { const p = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) { const q = nodes[j]; let dx = q.x - p.x, dy = q.y - p.y, d2 = dx * dx + dy * dy;
        if (d2 > 90000) continue; if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        const f = (380 * a) / d2; p.vx -= dx * f; p.vy -= dy * f; q.vx += dx * f; q.vy += dy * f; } }
    for (const [p, q] of this.links) { const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, L = 40 + Math.min(44, (p.deg + q.deg) * 0.8), f = ((d - L) / d) * 0.035 * a;
      p.vx += dx * f; p.vy += dy * f; q.vx -= dx * f; q.vy -= dy * f; }
    for (const n of nodes) { const an = this.anchor.get(n.group) || { x: 0, y: 0 }, pull = n.deg ? 0.0022 : 0.012;
      n.vx += (an.x - n.x) * pull * a - n.x * 0.0006 * a; n.vy += (an.y - n.y) * pull * a - n.y * 0.0006 * a;
      if (n === this.dragging) { n.vx = n.vy = 0; continue; } n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy; }
    this.alpha = Math.max(0.05, this.alpha * 0.985);
  }
  fit(w, h) {
    const nodes = [...this.nodes.values()]; if (!nodes.length) return;
    const xs = nodes.map((n) => n.x).sort((a, b) => a - b), ys = nodes.map((n) => n.y).sort((a, b) => a - b);
    const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.round(f * (arr.length - 1))))];
    const x0 = q(xs, 0.02), x1 = q(xs, 0.98), y0 = q(ys, 0.02), y1 = q(ys, 0.98);
    const k = Math.min((w - (DENSE ? 120 : 160)) / Math.max(50, x1 - x0), (h - 90) / Math.max(50, y1 - y0)), tk = clamp(k, 0.25, 2.5);
    this.view.k += (tk - this.view.k) * 0.05; this.view.x += (-(x0 + x1) / 2 - this.view.x) * 0.05; this.view.y += (-(y0 + y1) / 2 - this.view.y) * 0.05;
  }
  toScreen(n, w, h) { return { x: w / 2 + (n.x + this.view.x) * this.view.k, y: h / 2 + 8 + (n.y + this.view.y) * this.view.k }; }
  toWorld(x, y, w, h) { return { x: (x - w / 2) / this.view.k - this.view.x, y: (y - h / 2 - 8) / this.view.k - this.view.y }; }
  draw() {
    const { ctx, w, h } = fitCanvas(this.cv); this.w = w; this.h = h; ctx.clearRect(0, 0, w, h);
    if (!this.nodes.size) { ctx.fillStyle = PAL.dim; ctx.font = `12px ${FONT}`; ctx.textAlign = "center"; ctx.fillText("Your notes folder is empty so far.", w / 2, h / 2); return; }
    if (this.autofit) this.fit(w, h);
    const nowS = Date.now() / 1000, focus = this.hover || this.selected;
    const match = this.query ? new Set([...this.nodes.values()].filter((n) => (n.title + " " + n.id).toLowerCase().includes(this.query)).map((n) => n.id)) : null;
    const lit = (n) => (match ? match.has(n.id) : focus ? n === focus || focus.nb.has(n.id) : true);
    ctx.lineWidth = 0.8;
    for (const [p, q] of this.links) { const A = this.toScreen(p, w, h), B = this.toScreen(q, w, h), on = focus && (p === focus || q === focus);
      ctx.strokeStyle = rgba(this.colorOf(p.group), on ? 0.75 : (match || focus) ? 0.04 : 0.16); ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke(); }
    for (const n of this.nodes.values()) { const S = this.toScreen(n, w, h); if (S.x < -20 || S.y < -20 || S.x > w + 20 || S.y > h + 20) continue;
      const r = (1.6 + Math.sqrt(n.deg) * 0.9) * Math.sqrt(this.view.k), col = this.colorOf(n.group);
      ctx.fillStyle = rgba(col, lit(n) ? 0.92 : 0.18); ctx.beginPath(); ctx.arc(S.x, S.y, r, 0, TAU); ctx.fill();
      if (nowS - (n.mtime || 0) < 3600 && lit(n)) { ctx.strokeStyle = rgba(col, 0.9); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(S.x, S.y, r + 3.5, 0, TAU); ctx.stroke(); }
      if (n === focus) { ctx.strokeStyle = PAL.fg; ctx.beginPath(); ctx.arc(S.x, S.y, r + 8, 0, TAU); ctx.stroke(); } }
    const now = performance.now() / 1000; this.flares = this.flares.filter((f) => now - f.t0 < 4);
    for (const f of this.flares) { const k = (now - f.t0) / 4, S = this.toScreen(f.n, w, h); ctx.strokeStyle = rgba(PAL.sand, 0.8 * (1 - k)); ctx.lineWidth = 2 * (1 - k); ctx.beginPath(); ctx.arc(S.x, S.y, 4 + 46 * Math.sqrt(k), 0, TAU); ctx.stroke(); }
    ctx.font = `10.5px ${FONT}`; ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    const hubs = new Set([...this.nodes.values()].sort((a, b) => b.deg - a.deg).slice(0, 7).map((n) => n.id));
    for (const n of this.nodes.values()) { const show = n === focus || (match && match.has(n.id) && match.size < 25) || (!focus && !match && hubs.has(n.id)); if (!show) continue;
      const S = this.toScreen(n, w, h), txt = n.title.length > 30 ? n.title.slice(0, 29) + "…" : n.title, tw = ctx.measureText(txt).width;
      ctx.fillStyle = rgba(PAL.bg, 0.75); ctx.fillRect(S.x - tw / 2 - 3, S.y - 21, tw + 6, 13); ctx.fillStyle = rgba(n === focus ? PAL.fg : this.colorOf(n.group), 0.9); ctx.fillText(txt, S.x, S.y - 8); }
    if (DENSE) this.hud(ctx, w, h, nowS);
  }
  // dense: the folders and their counts, whether anything was touched this hour, and the notes edited last
  hud(ctx, w, h, nowS) {
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic"; ctx.font = `11px ${FONT}`;
    const counts = new Map();
    for (const n of this.nodes.values()) counts.set(n.group, (counts.get(n.group) || 0) + 1);
    const legend = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    const lw = Math.max(...legend.map(([g, c]) => ctx.measureText(`${g.slice(0, 14)} ${c}`).width)) + 26;
    ctx.fillStyle = rgba(PAL.bg, 0.72); ctx.fillRect(w - lw - 10, 14, lw, legend.length * 14 + 6);
    let y = 26;
    for (const [gname, c] of legend) {
      ctx.fillStyle = this.colorOf(gname); ctx.beginPath(); ctx.arc(w - lw - 1, y - 4, 3, 0, TAU); ctx.fill();
      ctx.fillStyle = rgba(PAL.fg, 0.58); ctx.fillText(`${gname.slice(0, 14)} ${c}`, w - lw + 8, y); y += 14;
    }
    const hot = [...this.nodes.values()].filter((n) => nowS - (n.mtime || 0) < 3600).length;
    say(ctx, hot ? `${hot} note${hot > 1 ? "s" : ""} touched this hour` : "quiet: nothing touched this hour", 14, 26, rgba(PAL.fg, 0.5), "left", `11px ${FONT}`);
    const recent = [...this.nodes.values()].sort((a, b) => (b.mtime || 0) - (a.mtime || 0)).slice(0, 5);
    recent.forEach((n, i) => say(ctx, `~ ${n.id.slice(-40)} · ${ago(nowS - (n.mtime || 0))} ago`, 14, h - 14 - i * 15,
      rgba(i === 0 ? PAL.sand : PAL.fg, 0.72 - i * 0.11), "left", `11px ${FONT}`));
  }
  pick(x, y) { let best = null, bd = 14; for (const n of this.nodes.values()) { const S = this.toScreen(n, this.w, this.h), d = Math.hypot(S.x - x, S.y - y); if (d < bd) { bd = d; best = n; } } return best; }
  async showCard(n, pinned) {
    const card = $("#mind-card"); if (!n) { card.classList.add("hidden"); return; }
    card.innerHTML = `<div class="h">${esc(n.title)}</div><div class="d">${esc(n.id)}</div><div>${n.deg} links · ${n.words} words · edited ${ago(Date.now() / 1000 - (n.mtime || 0))} ago</div>` + (pinned ? '<pre>…</pre><div class="d">double-click: open it</div>' : "");
    card.classList.remove("hidden");
    if (pinned) { try { const r = await api(`note?id=${encodeURIComponent(n.id)}`); if (this.selected === n) card.querySelector("pre").textContent = (r.text || "").trim().split("\n").slice(0, 14).join("\n"); } catch { /* leave it */ } }
  }
  openSearch() { const s = $("#mind-search"); s.classList.remove("hidden"); s.value = this.query; s.focus(); }
  wire() {
    const cv = this.cv; let down = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); this.autofit = false; const r = cv.getBoundingClientRect(), before = this.toWorld(e.clientX - r.left, e.clientY - r.top, this.w, this.h);
      this.view.k = clamp(this.view.k * Math.exp(-e.deltaY * 0.0015), 0.15, 6); const after = this.toWorld(e.clientX - r.left, e.clientY - r.top, this.w, this.h);
      this.view.x += after.x - before.x; this.view.y += after.y - before.y; }, { passive: false });
    cv.addEventListener("mousedown", (e) => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, n = this.pick(x, y);
      down = { x, y, n, vx: this.view.x, vy: this.view.y, moved: false }; if (n) this.dragging = n; });
    window.addEventListener("mousemove", (e) => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      if (down) { if (Math.hypot(x - down.x, y - down.y) > 3) down.moved = true;
        if (down.n) { const W = this.toWorld(x, y, this.w, this.h); down.n.x = W.x; down.n.y = W.y; this.alpha = Math.max(this.alpha, 0.2); }
        else if (down.moved) { this.autofit = false; this.view.x = down.vx + (x - down.x) / this.view.k; this.view.y = down.vy + (y - down.y) / this.view.k; } return; }
      if (x < 0 || y < 0 || x > r.width || y > r.height) return;
      const n = this.pick(x, y); if (n !== this.hover) { this.hover = n; if (!this.selected || n) this.showCard(n || this.selected, !n && !!this.selected); } });
    window.addEventListener("mouseup", () => { if (down && !down.moved) { this.selected = down.n || null; this.showCard(this.selected, !!this.selected); if (!down.n) this.autofit = true; } this.dragging = null; down = null; });
    cv.addEventListener("dblclick", async (e) => { const r = cv.getBoundingClientRect(), n = this.pick(e.clientX - r.left, e.clientY - r.top); if (n) await api("open-note", { id: n.id }); });
    const s = $("#mind-search");
    s.addEventListener("input", () => { this.query = s.value.trim().toLowerCase(); });
    s.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { this.query = ""; s.value = ""; s.classList.add("hidden"); }
      if (e.key === "Enter") { // go to the first match
        const hit = [...this.nodes.values()].find((n) => (n.title + " " + n.id).toLowerCase().includes(this.query));
        if (hit) { this.selected = hit; this.autofit = false; this.view.x = -hit.x; this.view.y = -hit.y; this.view.k = Math.max(this.view.k, 1.6); this.showCard(hit, true); }
      }
    });
    window.addEventListener("keydown", (e) => { if (e.key === "/" && !e.altKey && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName) && !document.activeElement.closest(".xterm")) { e.preventDefault(); this.openSearch(); } });
  }
}

// -------------------------------------------------------------------------------------- STATUS and tabs
let last = null;
function renderStatus(m) {
  if (DENSE) { renderBoard(m); return; }
  const s = m.sys, pct = (v) => `${Math.round((v || 0) * 100)}%`;
  const meter = (v, col) => `<div class="meter"><i style="width:${clamp(v * 100, 0, 100)}%;background:var(--${col})"></i></div>`;
  const gpu = (s.gpus || []).map((g) => esc(g.name) + (g.vram_gb ? ` (${g.vram_gb} GB)` : "")).join(", ") || "none in use";
  $("#status").className = "";
  $("#status-meta").textContent = "";
  $("#status").innerHTML = `
    <div class="row2"><span class="k">cpu</span><span>${pct(s.cpu)}${s.temps.cpu ? ` · ${s.temps.cpu}°C` : ""}</span></div>
    <div class="cores">${s.cores.map((c) => `<i style="height:${Math.max(4, c * 100)}%"></i>`).join("")}</div>
    <div class="row2"><span class="k">memory</span><span>${bytes(s.mem_used)} / ${bytes(s.mem_total)}</span></div>${meter(s.mem, "lav")}
    <div class="row2"><span class="k">network</span><span>↓ ${bytes(s.rx)}/s ↑ ${bytes(s.tx)}/s</span></div>
    <div class="row2"><span class="k">disk free</span><span>${bytes(s.disk_free)} of ${bytes(s.disk_total)}</span></div>${meter(1 - s.disk_free / s.disk_total, "peach")}
    ${s.battery ? `<div class="row2"><span class="k">battery</span><span>${Math.round(s.battery.percent)}% ${s.battery.ac === false ? "on battery" : "on charger"}</span></div>` : ""}
    <div class="row2"><span class="k">graphics</span><span>${gpu}</span></div>
    <div class="row2"><span class="k">profile</span><span>${esc(s.profile || "—")}</span></div>
    <div class="row2"><span class="k">up</span><span>${ago(s.uptime)}</span></div>
    <div class="row2"><span class="k">kurooto</span><span class="${m.power && m.power.mode !== "normal" ? "warn" : ""}">${
      !m.power || m.power.mode === "normal" ? "running" : m.power.mode === "saver" ? "saving battery: heavy work waits for the charger" : `paused ${esc(m.power.why)}`}</span></div>
    <div class="pw">${m.power && m.power.mode === "paused" ? '<button data-pw="resume">Resume</button>' : '<button data-pw="pause">Pause 1 h</button>'}<button data-pw="off">Turn off</button></div>`;
  $("#meta").textContent = `${m.cells.filter((c) => c.on).length} features on · ${m.jobs.filter((j) => j.status === "running").length} AI request running · cpu ${pct(s.cpu)}`;
  const u = m.updates || {};
  const badge = $("#update-badge");
  if (u.ready && u.ready.version) { badge.textContent = `update ${u.ready.version} ${u.ready.staged ? "ready tonight" : u.ready.waiting ? "waiting" : "available"}`; badge.title = u.ready.waiting ? `It waits: ${u.ready.waiting}` : ""; badge.classList.remove("hidden"); } else badge.classList.add("hidden");
  healthBadge($("#health-badge"), m.health);
  $("#ver").textContent = m.version;
}
// what isn't working (core/health.py): a badge that opens the Features tab, where each has its Fix button
function healthBadge(el, hp) {
  if (!el) return;
  hp = hp || [];
  el.textContent = hp.length ? `${hp.length} need${hp.length === 1 ? "s" : ""} a look` : "";
  el.title = hp.map((r) => `${r.title}: ${r.detail}`).join("\n");
  el.classList.toggle("hidden", !hp.length);
  el.style.cursor = "pointer";
  el.onclick = () => showTab("features");
}
function healthBlock(h) {
  const bad = (h.results || []).filter((r) => r.ok === false);
  if (!bad.length) return "";
  return `<div class="card2 health"><b>Needs a look</b>${bad.map((r) => `<p><span class="warn">${esc(r.title)}</span>: ${esc(r.detail)}${r.fix_label
    ? ` <button data-fix="${esc(r.id)}">${esc(r.fix_label)}</button>` : r.help ? ` <span class="d">${esc(r.help)}</span>` : ""}</p>`).join("")}</div>`;
}

// ---------------------------------------------------------------------------- STATUS, dense: a btop-like monitor
// Graphs are dots in character-sized cells (two columns and four rows of dots per character, like braille), coloured
// cool to warm by height; meters are the same gradient cut at the value.
const SB = { built: false, sort: "cpu", cw: 7.5, lh: 17 };
try { SB.sort = localStorage.getItem("kurooto.dash.procsort") === "mem" ? "mem" : "cpu"; } catch { /* fine */ }
function dotGraph(cv, vals, { max = 1, mirror = null, lines = null } = {}) {
  const { ctx, w, h } = fitCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const px = SB.cw / 2, py = SB.lh / 4, cols = Math.max(4, Math.floor(w / px)), r = Math.max(0.8, Math.min(px, py) * 0.3);
  const draw = (series, top, height, down, peak) => {
    const rows = Math.max(1, Math.floor(height / py)), colors = [...Array(rows)].map((_, i) => grad(rows > 1 ? i / (rows - 1) : 0.5));
    const v = series.slice(-cols), off = cols - v.length;
    v.forEach((x, i) => {
      const k = clamp((x || 0) / (peak || 1), 0, 1), n = k > 0 ? Math.max(1, Math.round(k * rows)) : 0;
      for (let j = 0; j < n; j++) {
        ctx.fillStyle = colors[j];
        const y = down ? top + (j + 0.5) * py : top + height - (j + 0.5) * py;
        ctx.beginPath(); ctx.arc((off + i + 0.5) * px, y, r, 0, TAU); ctx.fill();
      }
    });
  };
  if (mirror) { // two series about the middle: the first grows up, the second down (network: down and up)
    const half = h / 2;
    draw(vals, 0, half, false, max); draw(mirror, half, half, true, lines || max);
    ctx.fillStyle = rgba(PAL.fg, 0.08); ctx.fillRect(0, Math.round(half), w, 1);
  } else draw(vals, 0, h, false, max);
}
const meter = (v, cls = "") => `<span class="m grow ${cls}"><i style="clip-path:inset(0 ${(100 - clamp((v || 0) * 100, 0, 100)).toFixed(1)}% 0 0)"></i></span>`;
const pct = (v) => `${Math.round((v || 0) * 100)}%`;
const temp = (c) => (c == null ? "" : `<span class="${c >= 90 ? "hot" : c >= 80 ? "warm" : "v"}">${Math.round(c)}°</span>`);
function buildBoard() {
  const st = $("#status");
  st.className = "board";
  st.innerHTML = `
  <div class="hd"><span><b id="sb-name">KUROOTO</b> <span class="k" id="sb-ver"></span> <span id="sb-mode" class="warm"></span><span id="sb-badge" class="warm"></span> <span id="sb-health" class="hot"></span></span><span class="clock" id="sb-clock"></span></div>
  <div class="hd"><span id="sb-up"></span><span id="sb-act"></span></div>
  <div class="box" id="bx-cpu"><div class="lab"><span class="t">CPU</span><span class="meta" id="cpu-meta"></span></div>
    <div class="graph"><canvas class="cv" id="g-cpu"></canvas><span class="pct" id="cpu-pct"></span></div>
    <div class="cpus" id="cpu-cores"></div><div class="row" id="cpu-info"></div></div>
  <div class="duo" id="duo-mem">
    <div class="box" id="bx-mem"><div class="lab"><span class="t">MEM</span><span class="meta" id="mem-meta"></span></div><div id="mem-body"></div></div>
    <div class="box" id="bx-gpu"><div class="lab"><span class="t">GPU</span><span class="meta" id="gpu-meta"></span></div><div id="gpu-body"></div><div class="graph"><canvas class="cv" id="g-gpu"></canvas></div></div>
  </div>
  <div class="duo">
    <div class="box" id="bx-net"><div class="lab"><span class="t">NET</span><span class="meta" id="net-meta"></span></div>
      <div class="graph"><canvas class="cv" id="g-net"></canvas><span class="tag top" id="net-rx"></span><span class="tag top right k" id="net-peak"></span><span class="tag bot" id="net-tx"></span></div><div class="row" id="net-tot"></div></div>
    <div class="box" id="bx-disk"><div class="lab"><span class="t">DISKS</span><span class="meta" id="disk-meta"></span></div><div id="disk-body"></div></div>
  </div>
  <div class="box procs" id="bx-proc"><div class="lab"><span class="t">PROCESSES</span><span class="meta" id="proc-meta"></span></div><div id="proc-body"></div></div>
  <div class="box study" id="bx-study"><div class="lab"><span class="t">STUDY TODAY</span><span class="meta" id="study-meta"></span></div><div id="study-body"></div></div>
  <div class="box proj" id="bx-proj"><div class="lab"><span class="t">PROJECTS</span><span class="meta" id="proj-meta"></span></div><div id="proj-body"></div></div>`;
  const probe = document.createElement("canvas").getContext("2d");
  const fs = getComputedStyle(st);
  probe.font = `${fs.fontSize} ${FONT}`;
  SB.cw = probe.measureText("0000000000").width / 10 || 7.5;
  SB.lh = parseFloat(fs.lineHeight) || 17;
  $("#g-cpu").style.height = `${SB.lh * 4}px`;
  $("#g-gpu").style.height = `${SB.lh}px`;
  $("#g-net").style.height = `${SB.lh * 3}px`;
  $("#proc-meta").onclick = (e) => { const b = e.target.closest("[data-sort]"); if (b) setSort(b.dataset.sort); };
  $("#proc-body").onclick = (e) => { const b = e.target.closest("[data-sort]"); if (b) setSort(b.dataset.sort); };
  SB.built = true; SB.cores = -1;
  clockTick();
}
function setSort(k) { SB.sort = k; try { localStorage.setItem("kurooto.dash.procsort", k); } catch { /* fine */ } if (last) renderBoard(last); }
function clockTick() {
  const c = $("#sb-clock"); if (!c) return;
  const d = new Date();
  c.innerHTML = `${d.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" }).toUpperCase().replace(",", "")} <b>${d.toTimeString().slice(0, 8)}</b>`;
}
function renderBoard(m) {
  if (!SB.built || !$("#bx-cpu")) buildBoard();
  $("#status-meta").textContent = "kurooto top";
  const s = m.sys, H = s.hist || {}, nowS = Date.now() / 1000;
  // header: name, version, mode; up, events today, power; pause / off / setup
  $("#sb-name").textContent = (m.name || "Kurooto").toUpperCase();
  $("#sb-ver").textContent = m.version;
  const mode = m.power && m.power.mode !== "normal" ? (m.power.mode === "saver" ? " saving battery" : ` paused ${m.power.why}`) : "";
  $("#sb-mode").textContent = mode;
  const u = m.updates || {};
  $("#sb-badge").textContent = u.ready && u.ready.version ? ` update ${u.ready.version} ${u.ready.staged ? "tonight" : "available"}` : "";
  healthBadge($("#sb-health"), m.health);
  const p = s.power;
  const pw = !p ? "" : p.ac === false
    ? ` · <span class="k">battery</span> <span class="${p.pct < 20 ? "hot" : "v"}">${Math.round(p.pct)}%</span>${p.secs ? ` <span class="k">${ago(p.secs)} left</span>` : ""}${p.watts ? ` <span class="k">${p.watts.toFixed(1)}W</span>` : ""}`
    : ` · <span class="k">${p.ac ? "ac" : "power"}</span> <span class="v">${Math.round(p.pct)}%</span>`;
  $("#sb-up").innerHTML = `<span><span class="k">UP</span> <span class="v">${ago(s.uptime)}</span></span><span><span class="k">EVENTS TODAY</span> <span class="v">${m.events_today || 0}</span></span>${pw ? `<span>${pw.replace(/^ · /, "")}</span>` : ""}`;
  $("#sb-act").innerHTML = `${m.power && m.power.mode === "paused" ? '<button data-pw="resume">resume</button>' : '<button data-pw="pause">pause 1h</button>'} · <button data-pw="off">off</button> · <a href="/setup">setup</a>`;
  // CPU: the history, every core with its own short history, speed, load, temperatures, fans
  $("#cpu-meta").textContent = [s.cpu_name, s.phys && s.phys !== s.threads ? `${s.phys} cores` : "", `${s.threads} threads`].filter(Boolean).join(" · ");
  $("#cpu-pct").innerHTML = `<span style="color:${grad(s.cpu)}">${pct(s.cpu)}</span>`;
  dotGraph($("#g-cpu"), H.cpu || []);
  const n = s.cores.length, cols = n <= 8 ? 1 : n <= 20 ? 2 : n <= 36 ? 3 : 4, rows = Math.ceil(n / cols);
  const grid = $("#cpu-cores");
  if (SB.cores !== n) {
    SB.cores = n;
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`; grid.style.gridAutoFlow = "column";
    grid.style.gridTemplateRows = `repeat(${rows}, auto)`;
    grid.classList.toggle("narrow", cols > 2);
    grid.innerHTML = s.cores.map((_, i) => `<div class="core"><span class="k">C${i}</span>${meter(0)}<span class="r v" id="c${i}"></span><canvas class="cv" id="gc${i}"></canvas></div>`).join("");
  }
  s.cores.forEach((v, i) => {
    const row = grid.children[i];
    row.querySelector("i").style.clipPath = `inset(0 ${(100 - clamp(v * 100, 0, 100)).toFixed(1)}% 0 0)`;
    row.querySelector(".r").textContent = pct(v);
    if (cols <= 2 && H.cores && H.cores[i]) dotGraph(row.querySelector("canvas"), H.cores[i]);
  });
  const t = s.temps || {}, info = [];
  if (s.freq) info.push(`<span class="v">${(s.freq.cur / 1000).toFixed(1)}</span><span class="k">GHz</span>`);
  if (s.load) info.push(`<span class="k">load</span> <span class="v">${s.load.map((x) => x.toFixed(2)).join(" ")}</span>`);
  if (t.cpu != null) info.push(`<span class="k">cpu</span> ${temp(t.cpu)}`);
  if (t.disk != null) info.push(`<span class="k">disk</span> ${temp(t.disk)}`);
  if (s.fans && s.fans.length) info.push(`<span class="k">fans</span> <span class="v">${s.fans.join("/")}</span><span class="k"> rpm</span>`);
  $("#cpu-info").innerHTML = info.join("  ");
  // memory: used, cached, available, swap
  const mx = s.memx || {}, sw = s.swapx;
  $("#mem-meta").textContent = bytes(mx.total);
  const mrow = (k, v, frac, extra = "") => `<div class="row"><span class="k" style="width:3.6em">${k}</span>${meter(frac)}<span class="v r" style="min-width:4.4em">${v}</span>${extra}</div>`;
  $("#mem-body").innerHTML = mrow("used", bytes(mx.used), mx.used / mx.total) + mrow("cache", bytes(mx.cached), mx.cached / mx.total) +
    mrow("avail", bytes(mx.available), mx.available / mx.total) + (sw ? mrow("swap", `${bytes(sw.used)}/${bytes(sw.total)}`, sw.pct) : "");
  // the graphics card: live figures where the computer gives them, else its name
  const g = s.gpu, known = (s.gpus || [])[0], gbox = $("#bx-gpu");
  gbox.classList.toggle("hidden", !g && !known);
  $("#duo-mem").classList.toggle("one", !g && !known);
  if (g && !g.asleep) {
    $("#gpu-meta").textContent = (g.name || "").replace(/^NVIDIA (GeForce )?/, "");
    $("#gpu-body").innerHTML = mrow("use", pct(g.util), g.util) + mrow("vram", `${bytes(g.mem_used)}/${bytes(g.mem_total)}`, g.mem_total ? g.mem_used / g.mem_total : 0) +
      `<div class="row">${g.temp != null ? temp(g.temp) : ""}${g.watts != null ? `<span><span class="v">${g.watts.toFixed(0)}W</span>${g.watts_max ? `<span class="k">/${g.watts_max.toFixed(0)}W</span>` : ""}</span>` : ""}</div>`;
    $("#g-gpu").parentElement.classList.remove("hidden");
    dotGraph($("#g-gpu"), H.gpu || []);
  } else if (g || known) {
    $("#gpu-meta").textContent = ((g && g.name) || (known && known.name) || "").replace(/^NVIDIA (GeForce )?/, "");
    $("#gpu-body").innerHTML = `<div class="row"><span class="k">${g && g.asleep ? "asleep (saving power)" : "no live figures"}</span></div>` +
      (known && known.vram_gb ? `<div class="row"><span class="k">vram</span> <span class="v">${known.vram_gb} GB</span></div>` : "");
    $("#g-gpu").parentElement.classList.add("hidden");
  }
  // network: down above the line, up below; totals since the computer started
  const net = s.net || {}, peak = Math.max(10240, ...(H.rx || []), ...(H.tx || []));
  $("#net-meta").textContent = net.dev || "";
  $("#net-rx").innerHTML = `<span style="color:var(--lav)">↓</span> <span class="v">${bytes(net.rx)}/s</span>`;
  $("#net-tx").innerHTML = `<span style="color:var(--pink)">↑</span> <span class="v">${bytes(net.tx)}/s</span>`;
  dotGraph($("#g-net"), H.rx || [], { max: peak, mirror: H.tx || [] });
  $("#net-peak").textContent = `${bytes(peak)}/s`;
  $("#net-tot").innerHTML = net.dev ? `<span class="k">total</span> <span class="v">↓${bytes(net.rx_total)} ↑${bytes(net.tx_total)}</span>` : '<span class="k">no connection</span>';
  // disks: how full; reads and writes per second
  const io = s.io;
  $("#disk-meta").textContent = io ? `r ${bytes(io.read)}/s w ${bytes(io.write)}/s` : "";
  const label = (mnt) => (mnt.length > 1 ? mnt.replace(/[\\/]+$/, "") : mnt).split(/[\\/]/).slice(-1)[0] || mnt;
  $("#disk-body").innerHTML = (s.disks || []).slice(0, 4).map((d) => `<div class="row" title="${esc(d.mount)}"><span class="k" style="width:5.5em;overflow:hidden;text-overflow:ellipsis">${esc(d.mount === "/" ? "/" : label(d.mount))}</span>${meter(d.pct)}<span class="v r" style="min-width:3em">${pct(d.pct)}</span></div>`).join("") ||
    '<div class="row"><span class="k">no disks to show</span></div>';
  // processes: sorted by cpu or memory; Kurooto's own marked ✦
  $("#proc-meta").innerHTML = `<button data-sort="cpu" class="${SB.sort === "cpu" ? "on" : ""}">cpu</button><button data-sort="mem" class="${SB.sort === "mem" ? "on" : ""}">mem</button> · <span class="mine" style="color:var(--pink)">✦</span> kurooto`;
  const procs = [...(m.procs || [])].sort((a, b) => (SB.sort === "mem" ? b.mem - a.mem : b.cpu - a.cpu || b.mem - a.mem));
  // study today and projects first, so the processes take what's left
  const study = m.study, sbox = $("#bx-study");
  sbox.classList.toggle("hidden", study == null);
  if (study != null) {
    const tot = study.reduce((a, r) => a + r.seconds, 0), top = Math.max(1, ...study.map((r) => r.seconds));
    $("#study-meta").textContent = `${(tot / 3600).toFixed(1)}h`;
    $("#study-body").innerHTML = study.slice(0, 4).map((r) => `<div class="row"><span class="v" style="width:9em;overflow:hidden;text-overflow:ellipsis">${esc(r.name)}</span>${meter(r.seconds / top)}<span class="v r" style="min-width:3.5em">${(r.seconds / 3600).toFixed(1)}h</span></div>`).join("") ||
      '<div class="row"><span class="k">no study time yet today</span></div>';
  }
  const pr = m.projects || [];
  $("#proj-meta").textContent = pr.length ? `${pr.length}` : "";
  $("#proj-body").innerHTML = pr.slice(0, 5).map((r) => {
    const bits = [r.last ? `<span class="k">commit</span> <span class="v">${ago(nowS - r.last)}</span>` : '<span class="k">no commits</span>'];
    if (r.ahead) bits.push(`<span class="warm">↑${r.ahead} to push</span>`); else if (r.ahead === 0) bits.push('<span class="k">pushed</span>');
    if (r.dirty) bits.push(`<span class="k">${r.dirty} changed</span>`);
    return `<div class="row"><span class="mark">⌥</span><span class="v" style="width:13em;overflow:hidden;text-overflow:ellipsis">${esc(r.name)}</span>${bits.join(" · ")}</div>`;
  }).join("") || '<div class="row"><span class="k">your git folders: Settings → look.projects</span></div>';
  const body = $("#proc-body"), box = $("#bx-proc");
  const avail = box.clientHeight - 12, fit = Math.max(1, Math.floor(avail / SB.lh) - 1);
  const head = `<tr><th class="id" style="width:5.6em">pid</th><th class="n">process</th><th style="width:3em">thr</th><th data-sort="cpu" class="${SB.sort === "cpu" ? "on" : ""}" style="width:4.4em">cpu</th><th data-sort="mem" class="${SB.sort === "mem" ? "on" : ""}" style="width:5em">mem</th></tr>`;
  body.innerHTML = `<table>${head}${procs.slice(0, fit).map((r) => `<tr><td class="id">${r.pid}</td><td class="n">${r.own ? `<span class="mine">✦ ${esc(r.own === "kurooto" ? "kurooto" : r.name)}</span>` : `<span class="v">${esc(r.name)}</span>`}</td><td class="k">${r.threads ?? ""}</td><td style="color:${grad(Math.min(1, r.cpu))}">${(r.cpu * 100).toFixed(1)}%</td><td class="v">${bytes(r.mem)}</td></tr>`).join("")}</table>`;
}

const feed = [];
const SEEN = new WeakMap(); // when each live event arrived (fresh ones are bright in SYSTEMS)
const TABS = { activity: "Activity", jobs: "AI jobs", schedule: "Schedule", features: "Features", phone: "Phone", research: "Research", about: "About you", settings: "Settings" };
const DLABEL = { activity: "activity", jobs: "jobs", schedule: "schedule", features: "features", phone: "phone", research: "research", about: "you", settings: "settings" };
let tab = "activity"; // roomy: the tab below the panes
let dtab = "kurooto"; // dense: the terminal pane shows "kurooto" (the chat), a terminal, or one of TABS
const current = () => (DENSE ? dtab : tab);
function showTab(name) {
  if (DENSE) { showDense(name === "terminals" ? (TERM.list[0] || {}).name || "kurooto" : name); return; }
  tab = name;
  renderNav();
  try { localStorage.setItem("kurooto.dash.tab", name); } catch { /* fine */ }
  // the settings-like tabs get room (the canvases above shrink and redraw by themselves)
  $(".grid").classList.toggle("tall", ["features", "phone", "research", "about", "settings", "terminals"].includes(name));
  renderTab();
}
function renderNav() {
  const nav = $("#tabs");
  if (!DENSE) {
    nav.onclick = null;
    nav.replaceChildren(...Object.entries(TABS).map(([k, v]) => { const b = document.createElement("button"); b.textContent = v; b.className = k === tab ? "on" : ""; b.onclick = () => showTab(k); return b; }));
    return;
  }
  // dense: TERMINAL and its tabs set into the pane's top border, then the other pages, then the keys
  const terms = denseTerms(), isTerm = TERM.list.some((t) => t.name === dtab);
  let html = '<span class="t">TERMINAL</span><span class="rule">─</span>';
  terms.forEach((t, i) => { html += `<button class="tab${dtab === t.name ? " on" : ""}" data-dt="${esc(t.name)}" title="Alt+${i + 1}"><span class="k">${i + 1}</span>${esc(t.label)}<span class="dot${t.live ? " live" : ""}"></span></button><span class="rule">─</span>`; });
  if (!TERM.on) html += `<button class="tab off${dtab === "termsoff" ? " on" : ""}" data-dt="termsoff" title="a shell, your AI's program and the log, right here">+ terminals</button><span class="rule">─</span>`;
  if (isTerm) html += '<button class="tab" data-restart="1" title="end the program in this terminal and start it again">restart</button><span class="rule">─</span>';
  html += `<span class="rule">┤</span><span class="pages">${Object.keys(DLABEL).map((k) => `<button class="tab${dtab === k ? " on" : ""}" data-dt="${k}">${DLABEL[k]}</button>`).join("")}</span><span class="rule">├</span>`;
  html += `<span class="meta">alt+1..${terms.length} tabs · alt+/ find note</span>`;
  nav.innerHTML = html;
  nav.onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.dt) showDense(b.dataset.dt);
    if (b.dataset.restart && TERM.shown) api(`term/${TERM.shown}/restart`, {}).then(() => termAttach(TERM.shown));
  };
}
function renderTab() {
  if (DENSE) { if (DLABEL[dtab]) renderPage(dtab, $("#page-host")); return; }
  renderPage(tab, $("#tab-body"));
}
function renderPage(name, body) {
  if (!body) return;
  if (name === "activity") body.innerHTML = feed.length ? `<table>${feed.slice(0, 80).map((e) => `<tr><td>${esc((e.ts || "").slice(11, 19))}</td><td>${esc(e.kind.replace(/_/g, " "))}</td><td class="d">${esc(Object.entries(e).filter(([k]) => !["ts", "kind", "t", "cell"].includes(k)).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 160))}</td></tr>`).join("")}</table>` : "Nothing yet. Things Kurooto does appear here as they happen.";
  else if (name === "jobs" && last) {
    // running and waiting requests get a Cancel button (a running agent program stops with what it started)
    body.innerHTML = last.jobs.length ? `<table><tr><th>when</th><th>request</th><th>effort</th><th>took</th><th>result</th><th></th></tr>${last.jobs.map((j) => `<tr><td>${ago(Date.now() / 1000 - j.created)} ago</td><td>${esc(j.title)}</td><td>${esc(j.effort || "")}</td><td>${j.seconds ? Math.round(j.seconds) + "s" : ""}</td><td class="${j.status === "ok" ? "ok2" : j.status === "failed" ? "bad2" : ""}">${esc(j.status)}${j.status === "running" && j.brain ? " · " + esc(j.brain) : ""}${j.verdict && j.verdict !== "ok" ? " · " + esc(j.verdict) : ""}</td><td>${j.status === "running" || j.status === "queued" ? `<button data-cancel="${esc(j.id)}">Cancel</button>` : ""}</td></tr>`).join("")}</table>` : "No AI requests yet.";
    body.onclick = async (e) => {
      const b = e.target.closest("[data-cancel]"); if (!b) return;
      b.disabled = true;
      const r = await api("jobs/cancel", { id: b.dataset.cancel });
      b.textContent = r.ok ? "cancelled" : "finished";
    };
  }
  else if (name === "schedule" && last) body.innerHTML = last.schedule.length ? `<table><tr><th>when</th><th>what</th></tr>${last.schedule.map((s) => `<tr><td>${new Date(s.when * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}</td><td>${esc(s.what)}</td></tr>`).join("")}</table>` : "Nothing scheduled.";
  else if (name === "features") renderFeatures(body);
  else if (name === "phone") renderPhone(body);
  else if (name === "research") renderResearch(body);
  else if (name === "about") renderAboutTab(body);
  else if (name === "settings") renderSettings(body);
  else if (name === "terminals") renderTerminals(body);
}
// dense: the terminal pane's three hosts (the chat, a terminal, a page) stay; switching shows one
function denseHosts() {
  const tb = $("#tab-body");
  if ($("#page-host")) return;
  tb.onclick = tb.onchange = tb.onsubmit = null;
  tb.innerHTML = '<div id="chat-host" class="chat hidden"></div><div id="term-host" class="term-host hidden"></div><div id="page-host" class="page hidden"></div>';
  chatInit($("#chat-host"));
}
function showDense(name) {
  const isTerm = TERM.list.some((t) => t.name === name);
  if (!(name === "kurooto" || name === "termsoff" || isTerm || DLABEL[name])) name = "kurooto";
  dtab = name;
  try { localStorage.setItem("kurooto.dash.dtab", name); } catch { /* fine */ }
  denseHosts(); renderNav();
  $("#chat-host").classList.toggle("hidden", name !== "kurooto");
  $("#term-host").classList.toggle("hidden", !isTerm);
  $("#page-host").classList.toggle("hidden", name === "kurooto" || isTerm);
  if (name === "kurooto") { chatDraw(); $("#chat-input").focus({ preventScroll: true }); }
  else if (isTerm) loadXterm().then(() => termShow(name)).catch(() => { $("#page-host").classList.remove("hidden"); $("#page-host").textContent = "The terminal display couldn't load."; });
  else if (name === "termsoff") {
    const p = $("#page-host"); p.onclick = p.onchange = p.onsubmit = null;
    p.innerHTML = '<p>Terminals is off. With it on, this pane also has your AI\'s own program (agy, Codex or Claude Code), a shell and Kurooto\'s log, each a real terminal. Turn it on in <a href="#" data-goto="features">features</a>, only on a computer that\'s yours alone: anyone who can open this page can type into them.</p>';
    p.onclick = (e) => { if (e.target.dataset.goto) { e.preventDefault(); showDense(e.target.dataset.goto); } };
  } else renderPage(name, $("#page-host"));
}
// the terminal tabs: your AI's program, a shell, the kurooto chat, the log (the chat works without Terminals)
function agentLabel(title) {
  const b = last && last.agent && last.agent.brain;
  if (b && BRAIN[b.id]) return BRAIN[b.id];
  const known = { "Antigravity (agy)": "agy", "ChatGPT / Codex": "codex", "Claude Code (Advanced)": "claude" };
  return known[title] || String(title || "agent").toLowerCase().split(/[ (/]/)[0];
}
function denseTerms() {
  const by = Object.fromEntries(TERM.list.map((t) => [t.name, t])), out = [];
  const add = (name, label) => { if (by[name]) out.push({ name, label, live: by[name].alive || TERM.live.has(name) }); };
  add("agent", by.agent ? agentLabel(by.agent.title) : "");
  add("shell", "shell");
  out.push({ name: "kurooto", label: ((last && last.name) || "Kurooto").toLowerCase(), live: true });
  add("logs", "logs");
  for (const t of TERM.list) if (!["agent", "shell", "ask", "logs"].includes(t.name)) add(t.name, String(t.title).toLowerCase());
  return out;
}
const said = {}; // a feature's last Set up result (✓ or ✗), shown on its card
async function renderFeatures(body) {
  const st = await api("state");
  let health = {};
  try { health = await api("health"); } catch { /* an older Kurooto */ }
  const form = (m) => !m.form || m.ready ? "" : `<form class="sf" data-form="${m.id}"><p class="d">${esc(m.form.intro)}</p>
    ${m.form.steps ? `<ol class="d form-steps">${m.form.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
    ${m.form.guide ? `<p><a href="${esc(m.form.guide[1])}" target="_blank" rel="noopener">${esc(m.form.guide[0])}</a></p>` : ""}
    ${(m.form.copy || []).map(([l, v]) => `<div class="copy-row"><span class="d">${esc(l)}:</span> <code>${esc(v)}</code> <button type="button" data-copy="${esc(v)}">Copy</button></div>`).join("")}
    <p class="d">${m.form.links.map(([l, h]) => `<a href="${esc(h)}" target="_blank" rel="noopener">${esc(l)}</a>`).join(" · ")}</p>
    ${m.form.fields.map((f) => `<label>${esc(f.label)}${f.type === "textarea" ? `<textarea name="${esc(f.name)}" rows="3" placeholder="${esc(f.placeholder || "")}"></textarea>`
      : `<input name="${esc(f.name)}" type="${f.type === "password" ? "password" : "text"}" placeholder="${esc(f.placeholder || "")}" autocomplete="off">`}${f.accept ? `<input type="file" accept="${esc(f.accept)}" data-fill="${esc(f.name)}">` : ""}</label>`).join("")}
    <button class="primary" type="submit">Save</button></form>`;
  // Phone calls: what it needs, in order; the Gemini key right here; Set up makes the call line on Cloudflare
  const calls = (m) => m.id !== "calls" || m.on ? "" : `<ol class="d"><li>a free Gemini API key (needed even if agy or another AI answers your messages: calls talk through Gemini Live)${st.keys.gemini ? " ✓" : ""}</li>
    <li>a free Cloudflare account: Set up makes your own call line on it${m.ready ? " ✓" : ""}</li><li>then pair your phone (Phone tab)</li></ol>
    ${st.keys.gemini ? "" : `<form class="sf" data-gemini><label>Gemini API key (<a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">Google AI Studio</a> → Create API key)<input name="key" autocomplete="off"></label><button class="primary" type="submit">Save key</button></form>`}`;
  // a feature's own card parts while it's on (Module.card(): lines and switches, e.g. Exam season's parts)
  const pieces = (m) => !m.on || !m.card ? "" : `<div class="pieces">${(m.card.lines || []).map((l) => `<p>${esc(l)}</p>`).join("")}${(m.card.toggles || []).map((x) => `<label><input type="checkbox" data-card="${esc(m.id)}" data-act="${esc(x.id)}"${x.on ? " checked" : ""}${x.disabled ? " disabled" : ""}> ${esc(x.label)}</label>`).join("")}</div>`;
  const card = (m) => `<div class="card2 ${m.on ? "on" : ""}" data-id="${m.id}"><b>${esc(m.title)}</b><p>${esc(m.description)}</p><p style="color:var(--lav)">${esc(m.privacy)}</p>${m.id === "mail_digest" && m.on ? `<p><a href="/confidential" target="_blank" rel="noopener">Confidential mail (summarised on this computer)</a></p>` : ""}
    ${m.on ? `<button data-off="${m.id}">Turn off</button>` : m.ready ? `<button class="primary" data-on="${m.id}">Turn on</button>` : m.setup ? `<button class="primary" data-setup="${m.id}">Set up</button> <span class="d">${esc(m.why)}</span>` : `<span class="d">${esc(m.why)}</span>`}${calls(m)}${form(m)}${pieces(m)}${said[m.id] ? `<p class="${said[m.id].startsWith("✓") ? "ok2" : "bad2"}" style="font-weight:600">${esc(said[m.id])}</p>` : ""}</div>`;
  const addons = st.modules.filter((m) => m.addon); // features from your own add-ons folder (core/overlay.py)
  const kept = $("#flog") ? $("#flog").innerHTML : ""; // what the last step said survives the re-render
  body.innerHTML = `${healthBlock(health)}<div class="feat">${st.modules.filter((m) => !m.addon).map(card).join("")}</div>${addons.length
    ? `<p class="d">Your add-ons: your own code, from your add-ons folder</p><div class="feat">${addons.map(card).join("")}</div>` : ""}<div class="log" id="flog">${kept}</div>`;
  body.onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target, flog = $("#flog");
    const values = Object.fromEntries([...f.querySelectorAll("input:not([type=file]), textarea")].map((i) => [i.name, i.value]));
    if (f.dataset.gemini !== undefined) { // the Gemini key, for Phone calls
      const r = await api("keys/gemini", { key: values.key });
      flog.textContent = r.ok ? "Gemini key saved. Now Set up Phone calls." : r.error;
      if (r.ok) renderFeatures(body);
      return;
    }
    const r = await api("modules/configure", { id: f.dataset.form, values });
    flog.textContent = r.message || "";
    if (r.open) { // popup blockers stop a tab opened after waiting for Kurooto: the link always works
      try { window.open(r.open, "_blank", "noopener"); } catch { /* the link below */ }
      flog.innerHTML = `<p><a class="button primary" href="${esc(r.open)}" target="_blank" rel="noopener">Open Google sign-in</a></p>
        <p class="d">After you approve, Google brings you back to this computer (a 127.0.0.1 page) that says 'Signed in with Google'. This card then turns on by itself.</p>`;
      const id = f.dataset.form, run = (renderFeatures.wait = (renderFeatures.wait || 0) + 1);
      for (let i = 0; i < 300 && run === renderFeatures.wait && tab === "features"; i++) {
        await new Promise((ok) => setTimeout(ok, 3000));
        const m = (await api("state")).modules.find((x) => x.id === id);
        if (m && m.ready) { renderFeatures(body); return; }
      }
    }
    if (r.ok && !r.open) renderFeatures(body);
  };
  body.onchange = async (e) => { // a file chosen for a box (Google's client JSON): its text goes into the box
    const t = e.target;
    if (t.dataset.fill && t.files[0]) t.closest("form").querySelector(`[name="${t.dataset.fill}"]`).value = await t.files[0].text();
  };
  body.onclick = async (e) => {
    const t = e.target, flog = $("#flog");
    if (t.dataset.copy !== undefined) { // a value for Google's Branding page
      const done = () => { t.textContent = "Copied"; setTimeout(() => { t.textContent = "Copy"; }, 1600); };
      (navigator.clipboard ? navigator.clipboard.writeText(t.dataset.copy) : Promise.reject()).then(done).catch(() => { t.textContent = "Press Ctrl+C"; });
      return;
    }
    if (t.dataset.card) { const r = await api("modules/card", { id: t.dataset.card, act: t.dataset.act, value: t.checked }); flog.textContent = r.message || r.error || ""; renderFeatures(body); return; }
    if (t.dataset.fix) { t.disabled = true; const r = await api("health/fix", { id: t.dataset.fix }); flog.textContent = r.message || ""; renderFeatures(body); return; }
    if (t.dataset.on) { const r = await api("modules/enable", { ids: [t.dataset.on] }); flog.textContent = Object.values(r.results).map((x) => x.message).join("\n"); renderFeatures(body); }
    if (t.dataset.off) { const r = await api("modules/disable", { id: t.dataset.off }); flog.textContent = r.message; renderFeatures(body); }
    if (t.dataset.setup) {
      const id = t.dataset.setup;
      t.disabled = true;
      const r = await api("modules/setup", { id });
      if (r.started === false) { flog.textContent = r.message; t.disabled = false; return; } // something else is running
      let lines = [];
      for (;;) { const p = await api("progress"); lines = p.lines.map((l) => l.line); flog.innerHTML = linkify(lines.join("\n")); if (!p.installing) break; await new Promise((r) => setTimeout(r, 1000)); }
      said[id] = [...lines].reverse().find((l) => /^[✓✗]/.test(l)) || "";
      renderFeatures(body); // the log stays (kept), and the ✓/✗ line shows on the card
    }
  };
}
// escaped text with its web addresses as links (the Cloudflare sign-in page shows up in a setup log)
const linkify = (text) => text.split(/(https?:\/\/[^\s<>"]+)/g).map((part, i) => (i % 2
  ? `<a href="${esc(part)}" target="_blank" rel="noopener">${esc(part.length > 90 ? part.slice(0, 87) + "…" : part)}</a>` : esc(part))).join("");

async function renderPhone(body) {
  const ph = await api("phone");
  if (!ph.on) { body.innerHTML = "<p>Phone calls are off. Turn them on in the Features tab (you'll need a free Gemini key and a free Cloudflare account; setup does the rest).</p><p class=\"d\">The phone app comes from your own call line: set up Phone calls first.</p>"; return; }
  const devs = ph.devices;
  body.innerHTML = `<p>Your call line: <a href="${esc(ph.url)}" target="_blank" rel="noopener">${esc(ph.url)}</a> ·
    <span class="${ph.connected ? "ok2" : "bad2"}">${ph.connected ? "connected" : "not connected" + (ph.error ? " (" + esc(ph.error) + ")" : "")}</span></p>
    <p><button class="primary" data-pair>Pair a phone</button> <button data-ring ${ph.connected ? "" : "disabled"}>Ring my phone (test)</button></p>
    <div id="pairbox"></div>
    ${devs === null ? "<p class=\"d\">Paired phones show here when the line is connected.</p>" : devs.length
      ? `<table><tr><th>phone</th><th>kind</th><th>paired</th><th></th></tr>${devs.map((d) => `<tr><td>${esc(d.name)}</td><td>${esc(d.kind)}${d.push ? " · notifications on" : ""}</td><td>${esc(d.created.slice(0, 10))}</td><td><button data-revoke="${esc(d.id)}">Remove</button></td></tr>`).join("")}</table>`
      : "<p class=\"d\">No phones paired yet.</p>"}
    <p class="d" id="phone-msg"></p>`;
  body.onclick = async (e) => {
    const t = e.target, msg = $("#phone-msg");
    if (t.dataset.pair !== undefined) {
      t.disabled = true;
      const r = await api("phone/pair", {});
      t.disabled = false;
      $("#pairbox").innerHTML = r.ok
        ? `<div class="qr">${r.svg}</div><p>Scan this with your phone. The page that opens has 1) Download the app (Android) or Add to Home Screen (iPhone), then 2) pairing. Works for 15 minutes (or send /phone to your bot and tap the link on the phone). Code <code>${esc(r.code)}</code> · <a href="${esc(r.link)}" target="_blank" rel="noopener">link</a></p>`
        : `<p class="bad2">${esc(r.error)}</p>`;
    }
    if (t.dataset.ring !== undefined) { const r = await api("phone/test", {}); msg.textContent = r.ok ? "Ringing your paired phones…" : r.error; }
    if (t.dataset.revoke) { const r = await api("phone/revoke", { id: t.dataset.revoke }); msg.textContent = r.ok ? "Removed." : (r.error || "Not found."); renderPhone(body); }
  };
}

// Research: your sources (arXiv fields, bioRxiv, medRxiv, PubMed, any feed), what you work on, and the digest
const RS_KINDS = { arxiv: "arXiv", biorxiv: "bioRxiv", medrxiv: "medRxiv", pubmed: "PubMed", rss: "A journal's or blog's feed (RSS/Atom)" };
let rsKind = "arxiv";
async function renderResearch(body) {
  const r = await api("research"), cat = r.catalog;
  const [freq, day, time] = (() => { const m = /^(daily|weekly)(?: (\w{3}))? (\d{2}:\d{2})$/.exec(r.papers || "") || [];
    return [m[1] || "weekly", m[2] || "mon", m[3] || "08:00"]; })();
  const days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  const picker = rsKind === "arxiv"
    ? `<input id="rs-filter" placeholder="find a field: e.g. learning, number theory, galaxies">
       <div class="rs-list">${cat.arxiv.map(([g, cs]) => `<details><summary>${esc(g)} (${cs.length})</summary>${cs.map(([c, n]) =>
         `<label data-n="${esc((c + " " + n).toLowerCase())}"><input type="checkbox" value="${esc(c)}"> ${esc(n)} <span class="d">${esc(c)}</span></label>`).join("")}</details>`).join("")}</div>`
    : rsKind === "biorxiv" || rsKind === "medrxiv"
      ? `<div class="rs-list">${cat[rsKind].map((s) => `<label><input type="checkbox" value="${esc(s)}"> ${esc(s)}</label>`).join("")}</div>`
      : rsKind === "pubmed" ? '<input id="rs-query" placeholder="PubMed search, e.g. sleep AND adolescents">'
        : '<input id="rs-url" placeholder="https://… (the feed address; most journals have one)">';
  body.innerHTML = `<div class="rs">
    ${r.on ? "" : '<p class="warn">Research is off: add a source here, then turn it on in the Features tab.</p>'}
    <section><div><b>What I work on</b> <span class="d">(helps the AI pick${r.chat ? "" : "; needs Chat on"})</span></div>
      <textarea id="rs-about" rows="2" placeholder="e.g. graph neural networks for drug discovery">${esc(r.about)}</textarea></section>
    <section><b>Your sources</b>${r.feeds.length || r.topics.length ? `<ul class="rs-feeds">${r.feeds.map((f, i) =>
      `<li>${esc(f.label)} <button data-rs-del="${i}">remove</button></li>`).join("")}${r.topics.map((t) =>
      `<li>arXiv keyword: ${esc(t)} <button data-rs-topic="${esc(t)}">remove</button></li>`).join("")}</ul>` : '<p class="d">None yet: use a quick pick, or add one below.</p>'}</section>
    <section><b>Quick picks</b><div class="rs-picks">${cat.presets.map(([n], i) => `<button data-rs-preset="${i}">+ ${esc(n)}</button>`).join("")}</div></section>
    <section><b>Add a source</b>
      <div class="rs-kinds">${Object.entries(RS_KINDS).map(([k, v]) => `<button data-rs-kind="${k}" class="${k === rsKind ? "on" : ""}">${esc(v)}</button>`).join("")}</div>
      ${picker}
      ${rsKind === "pubmed" ? "" : '<input id="rs-kw" placeholder="keywords, comma-separated (optional: only papers mentioning any of them)">'}
      <div class="rs-row"><button data-rs-preview>Preview</button> <button class="primary" data-rs-add>Add</button></div>
      <div id="rs-preview" class="d"></div></section>
    <section><b>The digest</b>
      <div class="rs-row"><select id="rs-freq"><option value="weekly"${freq === "weekly" ? " selected" : ""}>weekly, on</option><option value="daily"${freq === "daily" ? " selected" : ""}>daily</option></select>
      <select id="rs-day"${freq === "daily" ? " disabled" : ""}>${days.map((d) => `<option${d === day ? " selected" : ""}>${d}</option>`).join("")}</select>
      at <input id="rs-time" type="time" value="${esc(time)}"> · up to <input id="rs-max" type="number" min="1" max="30" value="${r.max_papers}"> papers
      · <label><input id="rs-rank" type="checkbox"${r.rank ? " checked" : ""}> the AI picks and says why</label></div>
      <div class="rs-row"><button class="primary" data-rs-save>Save</button> <button data-rs-run>Send a digest now</button></div></section>
    <section><div><b>Projects</b> <span class="d">(each day's commits in these repositories go into the Log of research/&lt;project&gt;/index.md; on Telegram, /repos add &lt;folder&gt; as &lt;project&gt; names the project)</span></div>
      <ul class="rs-feeds">${r.repos.map((p, i) => `<li>${esc(p)} <span class="d">→ ${esc((r.projects || {})[p] || "")}</span> <button data-rs-repo-del="${i}">remove</button></li>`).join("")}</ul>
      <div class="rs-row"><input id="rs-repo" placeholder="a folder with a git repository, e.g. ~/code/my-project"> <button data-rs-repo-add>Add</button></div></section>
    <p class="d" id="rs-msg"></p></div>`;
  const msg = (t, bad) => { const m = $("#rs-msg"); m.textContent = t; m.className = bad ? "bad2" : "d"; };
  const save = async (b) => { const x = await api("research/save", b); if (!x.ok) { msg(x.error, true); return false; } renderResearch(body); return true; };
  const feedNow = () => {
    const kw = ($("#rs-kw") ? $("#rs-kw").value : "").split(",").map((s) => s.trim()).filter(Boolean);
    const ticked = [...body.querySelectorAll(".rs-list input:checked")].map((i) => i.value);
    if (rsKind === "arxiv") return { type: "arxiv", categories: ticked, keywords: kw };
    if (rsKind === "biorxiv" || rsKind === "medrxiv") return { type: rsKind, subjects: ticked, keywords: kw };
    if (rsKind === "pubmed") return { type: "pubmed", query: $("#rs-query").value };
    return { type: "rss", url: $("#rs-url").value, keywords: kw };
  };
  const plain = (f) => { const { label, ...rest } = f; return rest; };
  const filter = $("#rs-filter");
  if (filter) filter.oninput = () => { const q = filter.value.toLowerCase().trim();
    body.querySelectorAll(".rs-list label").forEach((l) => { l.hidden = !!q && !l.dataset.n.includes(q); });
    body.querySelectorAll(".rs-list details").forEach((d) => { d.open = !!q && [...d.querySelectorAll("label")].some((l) => !l.hidden); }); };
  $("#rs-freq").onchange = (e) => { $("#rs-day").disabled = e.target.value === "daily"; };
  body.onclick = async (e) => {
    const t = e.target, d = t.dataset;
    if (d.rsKind) { rsKind = d.rsKind; renderResearch(body); }
    else if (d.rsDel !== undefined) await save({ feeds: r.feeds.filter((_, i) => i !== Number(d.rsDel)).map(plain) });
    else if (d.rsTopic !== undefined) await save({ topics: r.topics.filter((x) => x !== d.rsTopic) });
    else if (d.rsPreset !== undefined) await save({ feeds: [...r.feeds.map(plain), ...cat.presets[Number(d.rsPreset)][1]] });
    else if (d.rsPreview !== undefined) {
      $("#rs-preview").textContent = "Looking…";
      const x = await api("research/preview", { feed: feedNow() });
      $("#rs-preview").innerHTML = !x.ok ? `<span class="bad2">${esc(x.error)}</span>` : x.count
        ? `${x.count} papers in the last week, for example:<ul>${x.papers.map((p) => `<li><a href="${esc(p.link)}" target="_blank" rel="noopener">${esc(p.title)}</a></li>`).join("")}</ul>`
        : "Nothing in the last week: try other fields or fewer keywords.";
    }
    else if (d.rsAdd !== undefined) await save({ feeds: [...r.feeds.map(plain), feedNow()] });
    else if (d.rsSave !== undefined) {
      const freqV = $("#rs-freq").value, spec = freqV === "daily" ? `daily ${$("#rs-time").value}` : `weekly ${$("#rs-day").value} ${$("#rs-time").value}`;
      if (await save({ about: $("#rs-about").value, papers: spec, max_papers: Number($("#rs-max").value), rank: $("#rs-rank").checked })) msg("Saved.");
    }
    else if (d.rsRun !== undefined) { const x = await api("research/run", {}); msg(x.message); }
    else if (d.rsRepoAdd !== undefined) await save({ repos: [...r.repos, $("#rs-repo").value] });
    else if (d.rsRepoDel !== undefined) await save({ repos: r.repos.filter((_, i) => i !== Number(d.rsRepoDel)) });
  };
}

// About you: your profile (about-me/profile.md), edited right here (aboutme.js); /aboutme on Telegram links here
async function renderAboutTab(body) {
  body.onclick = body.onchange = body.onsubmit = null; // another tab's handlers mustn't see the editor's clicks
  const a = await api("aboutyou/profile");
  if (!a.exists) { body.innerHTML = `<p class="d">No profile yet. Build one on the <a href="/setup">setup page</a> (its About you step): what your other AI accounts know about you, merged by your AI.</p>`; return; }
  body.innerHTML = `<p class="d">Your profile, ${esc(a.path)}. Edit it here or in your notes; building it again (on the <a href="/setup">setup page</a>) asks first if you've changed it.</p><div class="about-editor" id="about-host"></div>`;
  aboutEditor($("#about-host"), api);
}

async function renderSettings(body) {
  const { sections } = await api("settings");
  // a section may offer choices for a setting (a list) and a line of help under it; "fixed" shows a value that can't
  // change here, and "post" sends changes to the section's own request (Settings → Starting: /api/autostart)
  const LAYOUTS = [["dense", "dense: one full-screen board (screens 1280 px wide or more)"], ["roomy", "roomy: bigger panes and type"]];
  const NOTES = [["kurooto", "kurooto: journal/, about-me/, a folder per subject"], ["zettelkasten", "zettelkasten: dailies/, master/, sources/, zettel/"]];
  const field = (key, v, sec) => {
    const k = key.split(".").slice(1).join("."), help = ((sec && sec.help) || {})[k], fixed = ((sec && sec.fixed) || {})[k];
    const choices = ((sec && sec.choices) || {})[k] || (key === "look.layout" ? LAYOUTS : key === "notes.layout" ? NOTES : null);
    const post = sec && sec.post ? ` data-post="${esc(sec.post)}"` : "";
    const html = fixed ? `<label>${esc(key)}<span class="fixed">${esc(fixed)}</span></label>`
      : choices ? `<label>${esc(key)}<select data-key="${key}"${post}>${choices.map(([id, label]) => `<option value="${esc(id)}"${id === v ? " selected" : ""}>${esc(label)}</option>`).join("")}</select></label>` : plain(key, v);
    return help ? html.replace(/<\/label>$/, `</label><div class="help d">${esc(help)}</div>`) : html;
  };
  const plain = (key, v) => {
    if (typeof v === "boolean") return `<label>${esc(key)}<input type="checkbox" data-key="${key}" ${v ? "checked" : ""}></label>`;
    if (Array.isArray(v) || (v && typeof v === "object")) return `<label>${esc(key)}<input data-key="${key}" data-json value="${esc(JSON.stringify(v))}"></label>`;
    return `<label>${esc(key)}<input data-key="${key}" ${typeof v === "number" ? 'type="number" data-num' : ""} value="${esc(v ?? "")}"></label>`;
  };
  body.innerHTML = `<div class="form">${sections.map((s) => `<fieldset><legend>${esc(s.title)}</legend>${Object.entries(s.values).map(([k, v]) => field(`${s.section}.${k}`, v, s)).join("")}</fieldset>`).join("")}</div><p class="d" id="saved"></p>`;
  body.onchange = async (e) => {
    const t = e.target; if (!t.dataset.key) return;
    let value = t.type === "checkbox" ? t.checked : t.dataset.num !== undefined ? Number(t.value) : t.value;
    if (t.dataset.json !== undefined) { try { value = JSON.parse(t.value); } catch { $("#saved").textContent = "That isn't valid; it wasn't saved."; return; } }
    if (t.dataset.post) { // its own request, which says what it did (and what's in effect when it couldn't)
      $("#saved").textContent = "…";
      const r = await api(t.dataset.post, { [t.dataset.key.split(".").slice(1).join(".")]: value });
      const said = r.message || r.error || (r.ok ? `Saved ${t.dataset.key}.` : "That didn't work.");
      $("#saved").textContent = said;
      const fs = t.closest("fieldset"); // and right under it, where you're looking
      let line = fs.querySelector(".said");
      if (!line) { line = document.createElement("div"); line.className = "help said"; fs.append(line); }
      line.textContent = said;
      if (r.when && r.when !== value) t.value = r.when;
      return;
    }
    const r = await api("settings", { key: t.dataset.key, value });
    $("#saved").textContent = r.ok ? `Saved ${t.dataset.key}.` : r.error;
    if (r.ok) settingChanged(t.dataset.key, value);
  };
}

// ------------------------------------------------------------------------------------------- the kurooto tab
// Plain English, as on Telegram: quick things happen at once, a bigger request goes to your AI and its answer prints
// here (not on Telegram). help, check, jobs and clear are this tab's own words.
const CHAT = { log: [], hist: [], hi: -1 };
const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
const promptText = () => `${((last && last.name) || "Kurooto").toLowerCase()} ) `;
function chatInit(host) {
  host.innerHTML = '<div class="chat-log" id="chat-log"></div><label class="chat-in"><span class="p" id="chat-p"></span><input id="chat-input" spellcheck="false" autocomplete="off" aria-label="Ask in plain English"></label>';
  const inp = $("#chat-input");
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const v = inp.value.trim(); inp.value = ""; if (v) chatSend(v); }
    else if (e.key === "ArrowUp" && CHAT.hist.length) { e.preventDefault(); CHAT.hi = CHAT.hi < 0 ? CHAT.hist.length - 1 : Math.max(0, CHAT.hi - 1); inp.value = CHAT.hist[CHAT.hi]; }
    else if (e.key === "ArrowDown" && CHAT.hi >= 0) { e.preventDefault(); CHAT.hi++; if (CHAT.hi >= CHAT.hist.length) { CHAT.hi = -1; inp.value = ""; } else inp.value = CHAT.hist[CHAT.hi]; }
    else if (e.key === "l" && e.ctrlKey) { e.preventDefault(); CHAT.log = []; chatDraw(); }
  });
  host.addEventListener("mouseup", () => { if (!String(getSelection())) inp.focus({ preventScroll: true }); });
  chatDraw();
}
function chatBanner() {
  const name = ((last && last.name) || "Kurooto").toUpperCase().split("").join(" ");
  const brain = brainName(last && last.agent && last.agent.brain);
  return `<span class="banner">${esc(name)}</span>   <span class="d">plain English, right here</span>
<span class="d">quick:</span> <span class="ex">"push the evening check-in by 30 min"</span> <span class="d">·</span> <span class="ex">"what's due this week?"</span> <span class="d">·</span> <span class="ex">"no calls till 6"</span>
<span class="d">bigger:</span> anything else goes to ${esc(brain === "AI" ? "your AI" : brain)}; the answer prints here   <span class="d">(help · check · jobs · clear)</span>
`;
}
function chatDraw() {
  const el = $("#chat-log"); if (!el) return;
  el.innerHTML = chatBanner() + CHAT.log.map((l) => `\n<span class="${l.c}">${l.html}</span>`).join("");
  el.scrollTop = el.scrollHeight;
  $("#chat-p").textContent = promptText();
}
function chatAdd(text, c = "a", html = false) { CHAT.log.push({ c, html: html ? text : esc(text) }); if (CHAT.log.length > 400) CHAT.log.splice(0, 100); chatDraw(); }
const CHAT_HELP = `Type what you'd send Kurooto on Telegram: a reminder, "what's due this week?", a question for your AI.
  check   is every feature that's on working?
  jobs    your AI's latest requests
  clear   a clean screen (Ctrl+L)
  ↑ ↓     what you typed before
Alt+1… switches the terminal pane's tabs; Alt+/ finds a note.`;
async function chatSend(text) {
  CHAT.hist.push(text); CHAT.hi = -1;
  chatAdd(`<span class="p">${esc(promptText())}</span>${esc(text)}`, "q", true);
  const word = text.toLowerCase();
  if (word === "clear") { CHAT.log = []; chatDraw(); return; }
  if (word === "help") { chatAdd(CHAT_HELP, "d"); return; }
  if (word === "jobs") {
    const js = (last && last.jobs) || [];
    chatAdd(js.length ? js.map((j) => `${(j.status || "").padEnd(7)} ${ago(Date.now() / 1000 - j.created).padStart(5)} ago  ${j.title}${j.seconds ? `  (${Math.round(j.seconds)}s)` : ""}`).join("\n") : "No AI requests yet.", "a");
    return;
  }
  if (word === "check") {
    try {
      const st = await api("state"), on = st.modules.filter((m) => m.on);
      chatAdd(on.length ? on.map((m) => `${m.ready ? "✓" : "✗"} ${m.title}${m.ready ? "" : ": " + m.why}`).join("\n") : "No features are on yet (the features tab).", "a");
    } catch { chatAdd("Kurooto didn't answer (is it running?).", "x"); }
    return;
  }
  let r;
  try { r = await api("say", { text }); } catch { chatAdd("Kurooto didn't answer (is it running?).", "x"); return; }
  if (!r.ok) { chatAdd(r.error || "That didn't work.", "x"); return; }
  if (!r.job) { chatAdd((r.replies || []).join("\n") || "Done."); return; }
  chatAdd("working on it; the answer prints here", "w");
  for (let i = 0; i < 900; i++) {
    await sleep(2000);
    let j; try { j = await api(`job?id=${encodeURIComponent(r.job)}`); } catch { continue; }
    if (j.ok === false) { chatAdd(j.error || "That request is gone.", "x"); return; }
    if (j.status === "ok" || j.status === "failed") {
      chatAdd(`── ${text.slice(0, 60)}${j.status === "failed" ? " (failed)" : ""}`, "d");
      chatAdd(String(j.answer || "").trim() || "(no answer)", j.status === "ok" ? "a" : "x");
      return;
    }
  }
  chatAdd("No answer after 30 minutes; it may still be going (the jobs tab).", "d");
}

// ------------------------------------------------------------------------------------------------ wiring
let body, mind;
function connect() {
  const es = new EventSource(`/api/stream?t=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.t === "graph") mind.update(m);
    else if (m.t === "body") {
      const first = !last; last = m; LIGHT = m.sys.profile === "light" || matchMedia("(prefers-reduced-motion: reduce)").matches;
      body.update(m); renderStatus(m);
      if (current() === "jobs" || current() === "schedule") renderTab();
      if (first && DENSE) { renderNav(); if (dtab === "kurooto") chatDraw(); }
    }
    else if (m.t === "event") { SEEN.set(m, performance.now() / 1000); feed.unshift(m); feed.length = Math.min(feed.length, 200); body.event(m); if (current() === "activity") renderTab(); }
    else if (m.t === "hello") { TERM.cid = m.cid; if (TERM.shown) termAttach(TERM.shown); }
    else if (m.t === "pty") { termData(m); if (!TERM.live.has(m.n)) { TERM.live.add(m.n); if (DENSE) renderNav(); } }
  };
  es.onerror = () => { (DENSE ? $("#sys-meta") : $("#meta")).textContent = "reconnecting…"; };
}
// a setting changed on the Settings tab that changes this page
function settingChanged(key, value) {
  if (key === "look.layout") { document.body.dataset.layout = value; applyLayout(); }
  if (key === "look.palette") setTimeout(() => location.reload(), 300); // the canvases take their colours at load
}
function applyLayout(force = false) {
  const d = denseFits();
  if (d === DENSE && !force) return;
  DENSE = d;
  document.body.classList.toggle("dense", DENSE);
  $(".grid").classList.remove("tall");
  SB.built = false;
  const tb = $("#tab-body"); tb.onclick = tb.onchange = tb.onsubmit = null; tb.innerHTML = "";
  if (last) renderStatus(last);
  if (mind) mind.meta();
  if (DENSE) showDense(dtab); else showTab(tab === "terminals" && !TERM.on ? "activity" : tab);
}
// Pause, resume, or off completely (until Kurooto is opened again from the app menu or `kurooto on`)
document.addEventListener("click", async (e) => {
  const what = e.target.dataset && e.target.dataset.pw;
  if (!what) return;
  if (what === "off" && !confirm("Turn Kurooto off completely?\n\nIt stops now and won't start when you sign in, and your call line won't call you, until you open Kurooto from your app menu again (or run `kurooto on`).")) return;
  const r = await api(`power/${what}`, what === "pause" ? { when: "1h" } : {});
  $("#meta").textContent = r.message || "";
  if (DENSE && r.message) chatAdd(r.message, "d");
  if (what === "off") document.body.innerHTML = `<p style="padding:40px;font:16px var(--sans)">${esc(r.message || "Kurooto is off.")}</p>`;
});

// ------------------------------------------------------------------------------------------------ terminals
// Real terminals (modules/terminals.py): xterm.js (vendored, loaded the first time one opens) draws them; what you
// type goes to /api/term/<name>/input, their output comes back on the stream, only to this page.
const TERM = { cid: null, shown: null, list: [], xs: {}, loading: null, on: false, live: new Set() };
async function refreshTerms() {
  let r; try { r = await api("term"); } catch { return; }
  TERM.on = !!r.on; TERM.list = r.on ? r.terms : [];
  if (TERM.on) TABS.terminals = "Terminals"; else delete TABS.terminals;
  renderNav();
}
function loadXterm() {
  if (window.Terminal) return Promise.resolve();
  if (TERM.loading) return TERM.loading;
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/static/vendor/xterm/xterm.css"; document.head.appendChild(css);
  const add = (src) => new Promise((ok, bad) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = bad; document.head.appendChild(s); });
  TERM.loading = add("/static/vendor/xterm/xterm.js").then(() => add("/static/vendor/xterm/addon-fit.js"));
  return TERM.loading;
}
function termMake(name) {
  if (TERM.xs[name]) return TERM.xs[name];
  const el = document.createElement("div"); el.className = "term-one";
  const term = new window.Terminal({ fontFamily: FONT, fontSize: 13, cursorBlink: true, scrollback: 5000, allowProposedApi: false,
    theme: { background: PAL.panel, foreground: PAL.fg, cursor: PAL.accent, selectionBackground: rgba(PAL.lav, 0.35) } });
  const fit = new window.FitAddon.FitAddon(); term.loadAddon(fit);
  let pending = "", timer = null;
  term.onData((d) => { pending += d; if (!timer) timer = setTimeout(() => { const data = pending; pending = ""; timer = null; api(`term/${name}/input`, { data }).catch(() => {}); }, 12); });
  term.onResize(({ cols, rows }) => { if (TERM.cid != null) api(`term/${name}/resize`, { cid: TERM.cid, cols, rows }).catch(() => {}); });
  TERM.xs[name] = { term, fit, el, opened: false };
  return TERM.xs[name];
}
function termAttach(name) {
  const x = TERM.xs[name]; if (!x || TERM.cid == null) return;
  try { x.fit.fit(); } catch { /* not visible yet */ }
  api(`term/${name}/attach`, { cid: TERM.cid, cols: x.term.cols, rows: x.term.rows }).catch(() => {});
}
function termData(m) {
  const x = TERM.xs[m.n]; if (!x) return;
  const bin = atob(m.d), bytes8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes8[i] = bin.charCodeAt(i);
  if (m.replay) x.term.reset();
  x.term.write(bytes8);
}
function termShow(name) {
  const host = $("#term-host"); if (!host) return;
  if (TERM.shown && TERM.shown !== name && TERM.cid != null) api(`term/${TERM.shown}/leave`, { cid: TERM.cid }).catch(() => {});
  TERM.shown = name;
  for (const b of document.querySelectorAll("[data-term]")) b.classList.toggle("on", b.dataset.term === name);
  const x = termMake(name);
  host.replaceChildren(x.el);
  if (!x.opened) { x.term.open(x.el); x.opened = true; }
  termAttach(name);
  x.term.focus();
}
async function renderTerminals(body) {
  const r = await api("term");
  if (!r.on) { body.innerHTML = "Terminals is off: turn it on in Features (only on a computer that's yours alone)."; return; }
  TERM.list = r.terms;
  body.innerHTML = `<div class="term-bar">${r.terms.map((t, i) => `<button data-term="${esc(t.name)}">${esc(t.title)} <span class="d">Alt+${i + 1}</span></button>`).join("")}
    <button data-term-restart="1" title="end the program in this terminal and start it again">restart</button></div><div class="term-host" id="term-host"></div>`;
  body.onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.term) termShow(b.dataset.term);
    if (b.dataset.termRestart && TERM.shown) api(`term/${TERM.shown}/restart`, {}).then(() => termAttach(TERM.shown));
  };
  try { await loadXterm(); } catch { body.innerHTML = "The terminal display couldn't load."; return; }
  const want = TERM.shown && r.terms.some((t) => t.name === TERM.shown) ? TERM.shown : (r.terms[0] || {}).name;
  TERM.shown = null;
  if (want) termShow(want);
}
// Alt+1… switches terminals (dense: the terminal pane's tabs), Alt+/ finds a note; caught before a terminal sees them
window.addEventListener("keydown", (e) => {
  if (!e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "/") { e.preventDefault(); e.stopPropagation(); mind.openSearch(); return; }
  if (!/^[1-9]$/.test(e.key)) return;
  const t = DENSE ? denseTerms()[Number(e.key) - 1] : tab === "terminals" ? TERM.list[Number(e.key) - 1] : null;
  if (!t) return;
  e.preventDefault(); e.stopPropagation();
  if (DENSE) showDense(t.name); else termShow(t.name);
}, true);
window.addEventListener("resize", () => {
  applyLayout();
  if (DENSE && last) renderStatus(last); // the processes box shows as many as fit
  const showing = DENSE ? TERM.list.some((t) => t.name === dtab) : tab === "terminals";
  if (showing && TERM.shown && TERM.xs[TERM.shown]) try { TERM.xs[TERM.shown].fit.fit(); } catch { /* hidden */ }
});

(function main() {
  body = new Body($("#body")); mind = new Mind($("#mind"));
  try { tab = localStorage.getItem("kurooto.dash.tab") || "activity"; dtab = localStorage.getItem("kurooto.dash.dtab") || "kurooto"; } catch { /* fine */ }
  if (!TABS[tab] && tab !== "terminals") tab = "activity";
  const asked = location.hash.slice(1); // e.g. /#about, the link /aboutme sends
  if (TABS[asked]) { tab = asked; dtab = asked; }
  api("events").then((r) => { for (const e of (r.events || []).reverse()) feed.push(e); if (current() === "activity") renderTab(); }).catch(() => {});
  applyLayout(true);
  refreshTerms().then(() => { if (DENSE && TERM.list.some((t) => t.name === dtab)) showDense(dtab); else if (!DENSE && tab === "terminals") showTab("terminals"); });
  setInterval(refreshTerms, 20000);
  setInterval(() => { if (DENSE) clockTick(); }, 1000);
  connect();
  let lastT = 0;
  const frame = (ts) => { requestAnimationFrame(frame); if (document.hidden || ts - lastT < (LIGHT ? 33 : 16)) return; lastT = ts;
    const t = ts / 1000; try { body.draw(t); } catch (e) { console.error(e); } try { mind.step(); mind.draw(); } catch (e) { console.error(e); } };
  requestAnimationFrame(frame);
})();
