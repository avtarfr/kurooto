// SYSTEMS, the drawing (shared by the dashboard and the phone app's Systems view; see common.js). The dashboard's
// own parts (the cells' menu, the list for Tab and screen readers, the corner panels) are home.js's Board, which
// extends Body; the phone's (tap for a card, pinch) are views/phone.js's.
"use strict";
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

// The SYSTEMS view is the board's control centre. The new design draws it as living tissue: the core is a membrane
// (layered translucent rims round a brighter centre that carries the name; each heartbeat travels out through the
// rims), each feature is a small neuron (a wobbling body with short branches whose length is how busy it was over the
// last two minutes, oldest to newest clockwise), and each nerve is a tapered axon, thick at the core and fine at the
// cell, with a thinner second fibre and a twig; a pulse that arrives flashes where it touches (a synapse). Behind them
// a faint mesh, drawn once per size. Classic keeps its look (round cells with history ticks, plain curves).
// Interaction (both designs): point at a cell (its nerve lights, it swells, a card says what it is); click it for its
// menu (ping, sync now, quiet, its settings, its activity); click the core for Ctrl+K; drag to turn the ring a
// little and scroll to zoom (dense layout), both springing back; Tab walks the cells (a list for screen readers
// under the canvas), Enter opens a cell's menu, Esc closes it. With prefers-reduced-motion the tissue holds still.
const STILL = matchMedia("(prefers-reduced-motion: reduce)");
const CAN_HOVER = matchMedia("(hover: hover)");
const BLOB = new Float32Array(2 * 64); // a blob's rim points (no arrays made per frame)
const AX = new Float32Array(4 * 17); // an axon's two edges
const rubber = (x, lim) => lim * Math.tanh(x / lim); // dragged past its limit, the ring turns ever less
const wrapPi = (a) => Math.atan2(Math.sin(a), Math.cos(a));

class Body {
  // els: {meta, card, menu}: where it writes its summary line and the card for the cell pointed at (any may be missing)
  constructor(cv, els = {}) {
    this.cv = cv; this.els = els; this.state = null; this.o = new Map(); this.pulses = []; this.ripples = []; this.widths = new Map();
    this.beats = []; this.systoles = []; this.nextBeat = 0; this.beat = 0; this.bpm = 60;
    this.view = { rot: 0, vr: 0, zoom: 1, vz: 0, zt: 1, zAt: 0, drag: null }; // turned and zoomed by hand; springs back
    this.syn = []; this.focus = null; this.menu = null; this.cellIds = "";
    this.wire();
  }
  // ---------------------------------------------------------------------------------------------- input
  wire() {
    const cv = this.cv, at = (e) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    cv.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || this.view.drag) return; // one pointer at a time: a second finger is ignored
      const p = at(e);
      this.view.drag = { id: e.pointerId, x0: p.x, y0: p.y, rot0: this.view.rot, hit: this.hit(p), moved: false };
    });
    cv.addEventListener("pointermove", (e) => {
      const p = at(e), d = this.view.drag;
      if (e.pointerType === "mouse") this.mouse = p; // a pointer that hovers; a finger or pen taps instead
      if (d && e.pointerId === d.id) {
        if (!d.moved && Math.hypot(p.x - d.x0, p.y - d.y0) > 5) { d.moved = true; try { cv.setPointerCapture(e.pointerId); } catch (err) { /* gone */ } }
        if (d.moved) {
          const swept = wrapPi(Math.atan2(p.y - this.cy, p.x - this.cx) - Math.atan2(d.y0 - this.cy, d.x0 - this.cx));
          this.view.rot = rubber(d.rot0 + swept, 0.55); this.view.vr = 0;
        }
      }
      this.cursor();
    });
    const end = (e, cancel) => {
      const d = this.view.drag; if (!d || e.pointerId !== d.id) return;
      this.view.drag = null;
      if (cancel || d.moved) { this.cursor(); return; }
      this.tap(d.hit);
    };
    cv.addEventListener("pointerup", (e) => end(e, false));
    cv.addEventListener("pointercancel", (e) => end(e, true));
    cv.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") this.mouse = null; });
    cv.addEventListener("wheel", (e) => { // the dense board doesn't scroll, so the wheel zooms (gently; it springs back)
      if (!DENSE) return;
      e.preventDefault();
      this.view.zt = clamp(this.view.zt * Math.exp(-clamp(e.deltaY, -60, 60) * 0.004), 0.8, 1.3); this.view.zAt = performance.now();
    }, { passive: false });
  }
  tap(hit) { } // a click or tap that didn't drag: on the core, a cell (hit) or nothing (null)
  cursor() {
    const d = this.view.drag, h = d && d.moved ? "grabbing" : this.mouse && this.hit(this.mouse) ? "pointer" : "";
    if (this.cv.style.cursor !== h) this.cv.style.cursor = h;
  }
  // what's under a point: "core", a cell, or null
  hit(p) {
    if (!p || this.cx == null) return null;
    if (Math.hypot(p.x - this.cx, p.y - this.cy) < (this.cr || 20) * (NEW ? 1.2 : 1.1)) return "core";
    let best = null, bd = 1e9;
    for (const o of this.o.values()) { const d = Math.hypot(o.x - p.x, o.y - p.y); if (d < Math.max(14, (o.r || 10) * 2.2) && d < bd) { bd = d; best = o; } }
    return best;
  }
  // the cell that's lit: pointed at, focused, or with its menu open
  hot() {
    if (this.menu) return this.menu;
    if (this.focus) return this.focus;
    const h = CAN_HOVER.matches && !(this.view.drag && this.view.drag.moved) ? this.hit(this.mouse) : null;
    return h === "core" ? "core" : h ? h.id : null;
  }
  springs(now, dt, still) { // the hand's turn and zoom spring back (k 90, damping 13: a small overshoot)
    const v = this.view;
    if (!v.drag || !v.drag.moved) {
      if (still) { v.rot = 0; v.vr = 0; } else { v.vr += (-90 * v.rot - 13 * v.vr) * dt; v.rot += v.vr * dt; }
    }
    const zt = now * 1000 - v.zAt < 900 ? v.zt : (v.zt = 1);
    if (still) { v.zoom = zt; v.vz = 0; } else { v.vz += (-90 * (v.zoom - zt) - 13 * v.vz) * dt; v.zoom += v.vz * dt; }
  }
  // ---------------------------------------------------------------------------------------------- data
  update(m) {
    this.state = m;
    const on = m.cells.filter((c) => c.on);
    const ids = on.map((c) => c.id);
    for (const id of [...this.o.keys()]) if (!ids.includes(id)) this.o.delete(id);
    const fx = {};
    for (const f of m.features || []) fx[f.id] = f;
    on.forEach((c, i) => {
      let o = this.o.get(c.id);
      if (!o) {
        const seed = Math.random() * 10;
        o = { id: c.id, label: SHORT[c.id] || c.title, color: COLORS[c.id] || "fg", seed, act: 0, flash: 0, hist: [], hv: 0,
          side: seed % 2 < 1 ? 1 : -1, twig: 0.5 + (seed % 1) * 0.25, // which side its second fibre and twig take
          dend: [0, 1, 2, 3, 4].map((k) => ({ off: (k - 2) * 1.08 + (Math.random() - 0.5) * 0.4, bend: (Math.random() < 0.5 ? -1 : 1) * (0.25 + Math.random() * 0.35), len: 0.85 + Math.random() * 0.3 })) };
        this.o.set(c.id, o);
      }
      o.i = i; o.target = c.act; o.data = c; o.hist.push(c.act); if (o.hist.length > 60) o.hist.shift();
      const f = fx[c.id] || {};
      o.proc = f.proc || null; o.last = f.last; o.next = f.next; o.down = !!f.down; o.idle = !!f.idle; o.often = !!f.intermittent;
      o.health = f.health || null; // what needs a look (only the phone's copy carries it)
    });
    let meta = `${on.length} feature${on.length === 1 ? "" : "s"} on`;
    const down = (m.features || []).filter((f) => f.down).length;
    if (down) meta += ` · ${down} not running`;
    if (DENSE && m.core && m.core.mem) meta += ` · kurooto ${(m.core.cpu * 100).toFixed(1)}% · ${bytes(m.core.mem)}`;
    if (m.link) meta += ` · call line ${m.link.connected ? "linked" : "offline"}`;
    if (this.els.meta) this.els.meta.textContent = meta;
    this.updated(on);
  }
  updated(on) { } // after each update: the cells that are on
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
  pulse(from, to, color, dur = 1.3) { const p = { from, to, color, t0: performance.now() / 1000, dur }; this.pulses.push(p); return p; }
  tickBeats(now, cpu) {
    const bpm = (this.bpm = clamp(58 + cpu * 140, 55, 130));
    if (now >= this.nextBeat) {
      const last = this.beats[this.beats.length - 1];
      if (!last || now - last.t > 0.3) { this.beats.push({ t: now, amp: 1, col: null }); this.systoles.push({ t: now + 0.15, amp: 1, col: null }); }
      this.nextBeat = now + (60 / bpm) * (0.94 + Math.random() * 0.12);
    }
    if (this.beats.length && now - this.beats[0].t >= 3) this.beats = this.beats.filter((b) => now - b.t < 3);
    if (this.systoles.length && now - this.systoles[0].t >= 1.2) this.systoles = this.systoles.filter((p) => now - p.t < 1.2);
  }
  // the heartbeat's swell at a moment (lag: a rim further out feels it a little later)
  lub(now, lag = 0) {
    let v = 0;
    for (const p of this.systoles) { const d = now - p.t - lag; v += p.amp * (0.12 * Math.exp(-((d - 0.02) ** 2) / 0.0018) + 0.05 * Math.exp(-((d - 0.33) ** 2) / 0.0018)); }
    return v;
  }
  // ---------------------------------------------------------------------------------------------- shapes
  // a closed, softly deforming outline: a circle whose radius is a sum of slow waves round the rim
  blob(ctx, x, y, r, t, seed, wob, spin = 0) {
    const N = LIGHT ? 24 : 48;
    for (let i = 0; i < N; i++) {
      const a = (i / N) * TAU, b = a - spin;
      const k = 1 + wob * (0.5 * Math.sin(2 * b + t * 0.55 + seed) + 0.38 * Math.sin(3 * b - t * 0.9 + seed * 1.7) + 0.22 * Math.sin(5 * b + t * 1.4 + seed * 2.3));
      BLOB[2 * i] = x + Math.cos(a) * r * k; BLOB[2 * i + 1] = y + Math.sin(a) * r * k;
    }
    ctx.beginPath();
    ctx.moveTo((BLOB[2 * N - 2] + BLOB[0]) / 2, (BLOB[2 * N - 1] + BLOB[1]) / 2);
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      ctx.quadraticCurveTo(BLOB[2 * i], BLOB[2 * i + 1], (BLOB[2 * i] + BLOB[2 * j]) / 2, (BLOB[2 * i + 1] + BLOB[2 * j + 1]) / 2);
    }
    ctx.closePath();
  }
  say(ctx, s, x, y, col, align = "left", font = cf(9)) { return say(ctx, s, x, y, col, align, font); }
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
      const col = c.c[i] || PAL.accent, a = (NEW ? 0.17 : 0.24) * (1 - Math.min(5, Math.floor(age * 6)) / 6.5);
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
      ctx.strokeStyle = rgba(PAL.fg, NEW ? (k % 6 ? 0.02 : 0.05) : k % 6 ? 0.03 : 0.07);
      ctx.beginPath(); ctx.moveTo(cx + c * r0, cy + s * r0 * 0.86); ctx.lineTo(cx + c * r1 * wide, cy + s * r1 * 0.86); ctx.stroke();
      if (k % 3 === 0) {
        ctx.font = cf(8); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = rgba(PAL.fg, 0.24);
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
  // new design: a faint mesh of specks and fine threads behind everything, drawn once for each size and palette
  meshLayer(w, h) {
    const dpr = window.devicePixelRatio || 1, key = `${w}x${h}x${dpr}|${PAL.fg}`;
    if (this.meshKey === key) return this.meshCv;
    const c = this.meshCv || (this.meshCv = document.createElement("canvas"));
    c.width = Math.max(1, Math.round(w * dpr)); c.height = Math.max(1, Math.round(h * dpr));
    const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    let s = 7; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; // the same mesh every time
    const n = clamp(Math.round((w * h) / 2400), 40, 420), xs = new Float32Array(n), ys = new Float32Array(n);
    for (let i = 0; i < n; i++) { xs[i] = rnd() * w; ys[i] = rnd() * h; }
    g.lineWidth = 0.6; g.strokeStyle = rgba(PAL.fg, 0.05); g.beginPath();
    for (let i = 0; i < n; i++) { // each speck threads to its two nearest neighbours, if they're close
      let a = -1, b = -1, da = 1e9, db = 1e9;
      for (let j = 0; j < n; j++) { if (j === i) continue; const d = (xs[i] - xs[j]) ** 2 + (ys[i] - ys[j]) ** 2;
        if (d < da) { db = da; b = a; da = d; a = j; } else if (d < db) { db = d; b = j; } }
      for (const [j, d] of [[a, da], [b, db]]) if (j > i && d < 52 * 52) {
        const mx = (xs[i] + xs[j]) / 2 + (rnd() - 0.5) * 10, my = (ys[i] + ys[j]) / 2 + (rnd() - 0.5) * 10;
        g.moveTo(xs[i], ys[i]); g.quadraticCurveTo(mx, my, xs[j], ys[j]); }
    }
    g.stroke();
    for (let i = 0; i < n; i++) { g.fillStyle = rgba(PAL.fg, 0.07 + rnd() * 0.08); g.beginPath(); g.arc(xs[i], ys[i], 0.6 + rnd() * 0.7, 0, TAU); g.fill(); }
    g.globalCompositeOperation = "destination-in"; // strongest round the ring, gone at the edges where the corners' words are
    const fade = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.1, w / 2, h / 2, Math.max(w, h) * 0.62);
    fade.addColorStop(0, "rgba(0,0,0,0.45)"); fade.addColorStop(0.45, "rgba(0,0,0,1)"); fade.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = fade; g.fillRect(0, 0, w, h); g.globalCompositeOperation = "source-over";
    this.meshKey = key; return c;
  }
  // a point on a nerve (s: 0 at the core, 1 at the cell), into P
  at(o, s, P) { const u = 1 - s; P.x = u * u * this.cx + 2 * u * s * o.q.x + s * s * o.x; P.y = u * u * this.cy + 2 * u * s * o.q.y + s * s * o.y; return P; }
  // new design: a nerve as a tapered axon, thick at the core and fine at the cell, with a second fibre and a twig
  axon(ctx, o, t, cr) {
    const cx = this.cx, cy = this.cy, q = o.q, col = PAL[o.color], hv = o.hv, fill = o.pump || 0;
    if (o.down) { // not running: a thin dashed line, as in classic
      ctx.strokeStyle = rgba(PAL.dim, 0.45 + 0.3 * hv); ctx.lineWidth = 1; ctx.setLineDash([3, 6]);
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(q.x, q.y, o.x, o.y); ctx.stroke(); ctx.setLineDash([]); return;
    }
    const N = 16, w0 = Math.min(cr * 0.32, 2.6 + 3 * o.act + 2 * hv + 1.5 * o.flash + 0.8 * fill), w1 = 0.7 + 0.5 * hv;
    for (let i = 0; i <= N; i++) {
      const s = i / N, u = 1 - s, x = u * u * cx + 2 * u * s * q.x + s * s * o.x, y = u * u * cy + 2 * u * s * q.y + s * s * o.y;
      let tx = 2 * u * (q.x - cx) + 2 * s * (o.x - q.x), ty = 2 * u * (q.y - cy) + 2 * s * (o.y - q.y); const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
      const hill = s > 0.84 ? ((s - 0.84) / 0.16) ** 2 * (o.r || 6) * 0.9 : 0; // it widens into the cell's body
      const half = (w1 + (w0 - w1) * Math.pow(u, 1.6) + hill) / 2;
      AX[4 * i] = x - ty * half; AX[4 * i + 1] = y + tx * half; AX[4 * i + 2] = x + ty * half; AX[4 * i + 3] = y - tx * half;
    }
    ctx.beginPath(); ctx.moveTo(AX[0], AX[1]);
    for (let i = 1; i <= N; i++) ctx.lineTo(AX[4 * i], AX[4 * i + 1]);
    for (let i = N; i >= 0; i--) ctx.lineTo(AX[4 * i + 2], AX[4 * i + 3]);
    ctx.closePath();
    const g = ctx.createLinearGradient(cx, cy, o.x, o.y);
    g.addColorStop(0, rgba(PAL.accent, 0.3 + 0.15 * fill + 0.2 * hv)); g.addColorStop(1, rgba(col, 0.4 + 0.35 * o.act + 0.15 * fill + 0.4 * hv));
    ctx.fillStyle = g; ctx.fill();
    // the second fibre leaves a third of the way out and meets the cell from the side
    const P = this.at(o, 0.32, this.P1 || (this.P1 = {})), dx = o.x - P.x, dy = o.y - P.y, d = Math.hypot(dx, dy) || 1;
    const k = o.side * d * (0.16 + 0.04 * Math.sin(t * 0.5 + o.seed));
    ctx.strokeStyle = rgba(col, 0.16 + 0.18 * o.act + 0.3 * hv); ctx.lineWidth = 0.7;
    ctx.beginPath(); ctx.moveTo(P.x, P.y); ctx.quadraticCurveTo((P.x + o.x) / 2 - (dy / d) * k, (P.y + o.y) / 2 + (dx / d) * k, o.x - (dy / d) * o.side * (o.r || 6) * 0.7, o.y + (dx / d) * o.side * (o.r || 6) * 0.7); ctx.stroke();
    // and a twig on the other side that ends in two tips
    const T = this.at(o, o.twig, this.P2 || (this.P2 = {})), sw = 0.25 * Math.sin(t * 0.8 + o.seed * 3), L = 7 + 5 * o.act;
    const na = Math.atan2(o.y - cy, o.x - cx) - o.side * (1.1 + sw), ex = T.x + Math.cos(na) * L, ey = T.y + Math.sin(na) * L;
    ctx.strokeStyle = rgba(col, 0.22 + 0.2 * hv); ctx.beginPath(); ctx.moveTo(T.x, T.y); ctx.lineTo(ex, ey);
    for (const f of [-0.5, 0.5]) { ctx.moveTo(ex, ey); ctx.lineTo(ex + Math.cos(na + f) * L * 0.45, ey + Math.sin(na + f) * L * 0.45); }
    ctx.stroke();
  }
  // new design: a feature as a small neuron. Five branches reach out round it (not on its nerve's side); each one's
  // length is how busy the feature was in a fifth of the last two minutes (oldest first, clockwise), so a busy
  // feature grows them out and a quiet one keeps them short
  neuron(ctx, o, t, ringR) {
    const base = ringR * 0.066, col = o.down ? PAL.dim : PAL[o.color], breath = 0.5 + 0.5 * Math.sin((TAU * t) / (5.5 - 4.2 * o.act) + o.seed);
    const r = base * (1 + (0.05 + 0.1 * o.act) * breath + 0.2 * o.flash + 0.08 * (o.pump || 0)) * (1 + 0.14 * o.hv); o.r = r;
    const out = Math.atan2(o.y - this.cy, o.x - this.cx), H = o.hist, n = H.length;
    let far = r;
    ctx.lineCap = "round";
    for (let k = 0; k < 5; k++) {
      const D = o.dend[k]; let sum = 0, cnt = 0;
      for (let j = n - 60 + k * 12; j < n - 60 + (k + 1) * 12; j++) if (j >= 0) { sum += H[j]; cnt++; }
      const busy = cnt ? clamp(sum / cnt, 0, 1) : 0, L = base * D.len * (0.95 + 1.25 * busy);
      const a = out + D.off + 0.1 * Math.sin(t * 0.6 + o.seed + k * 1.7), cs = Math.cos(a), sn = Math.sin(a);
      const bx = o.x + cs * r * 0.85, by = o.y + sn * r * 0.85, ex = bx + cs * L, ey = by + sn * L;
      const bend = D.bend * L * (0.5 + 0.12 * Math.sin(t * 0.9 + k)), mx = (bx + ex) / 2 - sn * bend, my = (by + ey) / 2 + cs * bend;
      const alpha = (o.down ? 0.28 : 0.3 + 0.32 * (k / 4)) + 0.25 * o.hv;
      ctx.strokeStyle = rgba(col, alpha); ctx.lineWidth = 1.15;
      ctx.beginPath(); ctx.moveTo(bx, by); ctx.quadraticCurveTo(mx, my, ex, ey); ctx.stroke();
      // it forks: a twig from two thirds of the way out, and two short tips at its end
      const fx = 0.11 * bx + 0.44 * mx + 0.44 * ex, fy = 0.11 * by + 0.44 * my + 0.44 * ey, ta = a + D.bend * 1.6, tl = L * 0.38;
      ctx.lineWidth = 0.75; ctx.strokeStyle = rgba(col, alpha * 0.8); ctx.beginPath();
      ctx.moveTo(fx, fy); ctx.lineTo(fx + Math.cos(ta) * tl, fy + Math.sin(ta) * tl);
      const ea = Math.atan2(ey - my, ex - mx);
      for (const f of [-0.42, 0.42]) { ctx.moveTo(ex, ey); ctx.lineTo(ex + Math.cos(ea + f) * L * 0.22, ey + Math.sin(ea + f) * L * 0.22); }
      ctx.stroke();
      far = Math.max(far, r * 0.85 + L * 1.1);
    }
    ctx.lineCap = "butt";
    if (o.act > 0.05 || o.flash > 0.05) { ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.1 + 0.2 * breath * o.act + 0.45 * o.flash;
      const gs = r * (3.5 + 2 * o.act); ctx.drawImage(glow(col), o.x - gs / 2, o.y - gs / 2, gs, gs); ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over"; }
    const spin = (o.i % 2 ? -1 : 1) * t * (0.2 + o.act) + o.seed;
    this.blob(ctx, o.x, o.y, r, t * (0.7 + o.act), o.seed, 0.11 + 0.06 * o.act + 0.06 * o.flash, spin);
    ctx.fillStyle = PAL.bg; ctx.fill(); ctx.fillStyle = rgba(col, 0.26 + 0.3 * o.act + 0.3 * o.flash + 0.16 * o.hv); ctx.fill();
    ctx.strokeStyle = rgba(col, o.down ? 0.5 : 0.9); ctx.lineWidth = 1.2; ctx.setLineDash(o.down ? [2, 3] : []); ctx.stroke(); ctx.setLineDash([]);
    o.reach = Math.max(r + 2, far * 0.8); // the cell with its branches: what words mustn't cover
  }
  // new design: the core as a membrane: a translucent body with a bright rim (the nerves show through it), two looser
  // rims outside it, each a little later than the one inside, so a heartbeat travels outwards; and in the middle a
  // denser centre that carries the name and swells with each beat
  membrane(ctx, cx, cy, cr, t, now, breath) {
    const A = PAL.accent, l0 = this.lub(now), l1 = this.lub(now, 0.07), l2 = this.lub(now, 0.14);
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.16 + 0.08 * breath + 0.2 * this.beat + l0;
    ctx.drawImage(glow(A), cx - cr * 2.8, cy - cr * 2.8, cr * 5.6, cr * 5.6);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    this.blob(ctx, cx, cy, cr * (1.52 + 0.03 * breath + 0.9 * l2), t * 0.3, 4.1, 0.13, t * 0.021);
    ctx.fillStyle = rgba(A, 0.035); ctx.fill(); ctx.strokeStyle = rgba(A, 0.12); ctx.lineWidth = 1; ctx.stroke();
    this.blob(ctx, cx, cy, cr * (1.24 + 0.025 * breath + 0.8 * l1), t * 0.4, 2.9, 0.1, -t * 0.03);
    ctx.fillStyle = rgba(A, 0.055); ctx.fill(); ctx.strokeStyle = rgba(A, 0.2); ctx.stroke();
    this.blob(ctx, cx, cy, cr * (1 + 0.04 * breath + 0.08 * this.beat + l0), t * 0.5, 1.7, 0.085, t * 0.04);
    const g = ctx.createRadialGradient(cx, cy, cr * 0.2, cx, cy, cr * 1.1);
    g.addColorStop(0, rgba(A, 0.34)); g.addColorStop(0.7, rgba(A, 0.2)); g.addColorStop(1, rgba(A, 0.42));
    ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = rgba(mix(A, PAL.fg, 0.3), 0.9); ctx.lineWidth = 2; ctx.stroke();
    ctx.strokeStyle = rgba(A, 0.3); ctx.lineWidth = 1; ctx.save(); ctx.translate(cx, cy); ctx.scale(0.92, 0.92); ctx.translate(-cx, -cy); ctx.stroke(); ctx.restore();
    const nx = cx + cr * 0.06 * Math.sin(t * 0.3), ny = cy + cr * 0.05 * Math.cos(t * 0.23), nr = cr * (0.6 + 0.5 * l0 + 0.03 * breath);
    this.blob(ctx, nx, ny, nr, t * 0.7, 6.2, 0.07, -t * 0.05);
    const ng = ctx.createRadialGradient(nx - nr * 0.2, ny - nr * 0.25, nr * 0.1, nx, ny, nr);
    ng.addColorStop(0, mix(A, PAL.fg, 0.22)); ng.addColorStop(1, A);
    ctx.fillStyle = ng; ctx.fill(); ctx.strokeStyle = rgba(mix(A, PAL.fg, 0.4), 0.7); ctx.lineWidth = 1; ctx.stroke();
    return nr;
  }
  // where a pulse arrives: a flash at the touching point, an arc on the rim and three sparks
  synapses(ctx, now, cr) {
    if (!this.syn.length) return;
    if (now - this.syn[0].t0 >= 0.6) this.syn = this.syn.filter((s) => now - s.t0 < 0.6);
    ctx.lineCap = "round";
    for (const s of this.syn) {
      const o = s.o, k = (now - s.t0) / 0.6, e = 1 - (1 - k) ** 3, a = Math.atan2(o.y - this.cy, o.x - this.cx);
      const ox = s.core ? this.cx : o.x, oy = s.core ? this.cy : o.y, R = s.core ? cr : o.r || 8, ang = s.core ? a : a + Math.PI;
      const px = ox + Math.cos(ang) * R, py = oy + Math.sin(ang) * R, sz = (s.core ? 30 : 20) * (0.6 + 0.6 * e);
      ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.9 * (1 - k);
      ctx.drawImage(glow(s.col), px - sz / 2, py - sz / 2, sz, sz);
      ctx.globalAlpha = 1; ctx.strokeStyle = rgba(s.col, 0.75 * (1 - k)); ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.arc(ox, oy, R * (1.06 + 0.22 * e), ang - 0.55, ang + 0.55); ctx.stroke();
      ctx.lineWidth = 1; ctx.beginPath();
      for (let j = -1; j <= 1; j++) { const b = ang + j * 0.5, r0 = R * 1.1 + 2 + e * 4, r1 = r0 + 3 + 8 * e;
        ctx.moveTo(ox + Math.cos(b) * r0, oy + Math.sin(b) * r0); ctx.lineTo(ox + Math.cos(b) * r1, oy + Math.sin(b) * r1); }
      ctx.stroke(); ctx.globalCompositeOperation = "source-over";
    }
    ctx.lineCap = "butt";
  }
  // ---------------------------------------------------------------------------------------------- a frame
  draw(t) {
    const { ctx, w, h } = fitCanvas(this.cv);
    ctx.clearRect(0, 0, w, h);
    if (!this.state) return;
    const now = performance.now() / 1000, cpu = this.state.sys.cpu || 0, still = STILL.matches, tm = still ? 0 : t;
    const dt = clamp(now - (this.lastNow || now), 0, 0.05); this.lastNow = now;
    this.springs(now, dt, still);
    let ringR, cx = w / 2, cy = h / 2 + 4;
    if (DENSE) { // room for the four corners: events, the AI, today, what's due (new design: folded to a line or two)
      const lh = Math.round(12 * FSC), rows = NEW && !LEGENDS ? 2 : 6, top = 24 + rows * lh, bottom = h - 18 - rows * lh;
      ringR = clamp(Math.min(w * 0.35, (bottom - top - 88) / 1.72), 56, 420);
      cy = top + 0.86 * ringR + 28 + Math.max(0, (bottom - top - 88 - 1.72 * ringR) / 2);
    } else ringR = clamp(Math.min(w * 0.36, (h - 70) / 1.9), 60, 420);
    const L = this.lay; // the size eases to a new one (L for the legends, a pane resized) instead of jumping
    if (!L || Math.abs(L.r - ringR) > 120 || still) this.lay = { r: ringR, cy };
    else { L.r += (ringR - L.r) * 0.18; L.cy += (cy - L.cy) * 0.18; ringR = L.r; cy = L.cy; }
    ringR *= this.view.zoom;
    const coreR = ringR * (NEW ? 0.29 : 0.18), rc = NEW ? coreR * 1.72 : coreR * 2.2;
    this.cx = cx; this.cy = cy;
    this.tickBeats(now, cpu);
    if (NEW) ctx.drawImage(this.meshLayer(w, h), 0, 0, w, h);
    if (!LIGHT) this.ecg(ctx, w, now, cy, ringR * 0.55);
    const cells = [...this.o.values()], n = Math.max(1, cells.length), orbit = LIGHT ? 0 : (t * TAU) / 180;
    // dense, with many features: the orbit widens sideways, where the pane has room
    const wide = DENSE ? Math.min(w * 0.42 / ringR, clamp(1 + (n - 10) * 0.035, 1, 1.3)) : 1;
    // a crowded ring becomes two: every other cell rides a little closer in, so neighbours and their words have room
    const twoRings = n >= 12 && (TAU * ringR * (1 + wide) / 2) / n < 80;
    const hot = this.hot(), core = { x: cx, y: cy };
    const ctrl = (a, b, seed) => { const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, k = 0.12 * d * Math.sin(tm * 0.37 + seed); return { x: mx - (dy / d) * k, y: my + (dx / d) * k }; };
    for (const o of cells) {
      const a = -Math.PI / 2 + (o.i / n) * TAU + orbit + this.view.rot + 0.05 * Math.sin(tm * 0.13 + o.seed);
      const rr = ringR * (1 + 0.04 * Math.sin(tm * 0.21 + o.seed * 2)) * (twoRings && o.i % 2 ? 0.86 : 1);
      o.x = cx + Math.cos(a) * rr * wide; o.y = cy + Math.sin(a) * rr * 0.86; o.q = ctrl(core, o, o.seed);
      o.act += ((o.target || 0) - o.act) * 0.05; o.flash *= 0.94; o.pump = (o.pump || 0) * 0.88;
      o.hv += ((hot === o.id ? 1 : 0) - o.hv) * (still ? 1 : 0.22);
    }
    if (DENSE) this.grid(ctx, cx, cy, rc + 14, ringR, wide);
    if (NEW) for (const o of cells) this.axon(ctx, o, tm, coreR);
    else {
      for (const o of cells) {
        const c = o.q, fill = o.pump || 0, g = ctx.createLinearGradient(cx, cy, o.x, o.y);
        g.addColorStop(0, rgba(PAL.accent, 0.18 + 0.12 * fill + 0.15 * o.hv)); g.addColorStop(1, rgba(PAL[o.color], 0.28 + 0.4 * o.act + 0.12 * fill + 0.4 * o.hv));
        ctx.strokeStyle = g; ctx.lineWidth = 0.8 + 2 * o.act + o.flash * 1.5 + 0.5 * fill + 1.2 * o.hv;
        ctx.setLineDash(o.down ? [3, 6] : []);
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(c.x, c.y, o.x, o.y); ctx.stroke();
      }
      ctx.setLineDash([]);
    }
    ctx.globalCompositeOperation = "lighter";
    const P = this.P0 || (this.P0 = {});
    for (const p of this.systoles) {
      const d = now - p.t; if (d < 0 || d > 1.0) continue;
      const k = clamp(d / 0.7, 0, 1), ease = 1 - (1 - k) ** 3;
      ctx.strokeStyle = rgba(p.col || PAL.accent, 0.12 * (1 - d) * p.amp); ctx.lineWidth = 1.2 * (1 - d);
      ctx.beginPath(); ctx.arc(cx, cy, coreR * ((NEW ? 1.5 : 1.1) + 4 * ease), 0, TAU); ctx.stroke();
      if (k >= 1 || LIGHT) continue;
      for (const o of cells) {
        this.at(o, ease, P);
        const sz = 10 * p.amp; ctx.globalAlpha = 0.55 * (1 - k * 0.5); ctx.drawImage(glow(p.col || PAL[o.color]), P.x - sz / 2, P.y - sz / 2, sz, sz);
        if (k > 0.86) o.pump = Math.max(o.pump || 0, p.amp);
      }
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    this.clock(ctx, cx, cy, rc, t);
    ctx.globalCompositeOperation = "lighter";
    if (this.pulses.length && now - this.pulses[0].t0 >= this.pulses[0].dur + 0.4) this.pulses = this.pulses.filter((p) => now - p.t0 < p.dur + 0.4);
    for (const p of this.pulses) {
      const o = this.o.get(p.from === "core" ? p.to : p.from); if (!o) continue;
      const sp = clamp((now - p.t0) / p.dur, 0, 1), ease = sp < 0.5 ? 2 * sp * sp : 1 - Math.pow(-2 * sp + 2, 2) / 2;
      for (let k = 0; k < 10; k++) {
        let s = ease - k * 0.025; if (s < 0) break; if (p.to === "core") s = 1 - s;
        this.at(o, s, P);
        const sz = k === 0 ? 22 : 15 - k; ctx.globalAlpha = (1 - k / 10) * (1 - Math.max(0, (now - p.t0 - p.dur) / 0.4));
        ctx.drawImage(glow(p.color), P.x - sz / 2, P.y - sz / 2, sz, sz);
      }
      if (sp >= 1 && !p.done) {
        p.done = true;
        if (p.to === "core") { this.ripples.push({ t0: now, col: p.color }); this.beat = Math.max(this.beat, 0.6); } else o.flash = 1;
        if (NEW) this.syn.push({ t0: now, col: p.color, o, core: p.to === "core" });
        if (p.back) this.pulse(p.to === "core" ? "core" : p.to, p.to === "core" ? p.from : "core", p.color); // a ping comes back
      }
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
    for (const o of cells) if (NEW) this.neuron(ctx, o, tm, ringR); else this.cell(ctx, o, tm, ringR);
    for (const o of cells) if (o.hv > 0.02 && (this.focus === o.id || this.menu === o.id)) { // the keyboard's focus, the open menu's cell
      ctx.strokeStyle = rgba(PAL.fg, 0.85 * o.hv); ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(o.x, o.y, Math.max(o.r * 1.9, o.r + 8), 0, TAU); ctx.stroke();
    }
    this.labels(ctx, cells, cx, cy, NEW ? coreR * 1.3 : coreR, w, h);
    this.beat *= 0.9;
    const breath = still ? 0.5 : 0.5 + 0.5 * Math.sin((TAU * t) / (6.5 - 3.5 * clamp(cpu * 2.5, 0, 1)));
    let cr, nucleus = 0;
    if (NEW) {
      cr = coreR * (1 + (hot === "core" ? 0.05 : 0));
      nucleus = this.membrane(ctx, cx, cy, cr, tm, now, breath);
    } else {
      const lubdub = this.lub(now);
      cr = coreR * (1 + 0.04 * breath + 0.08 * this.beat + lubdub);
      ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.22 + 0.12 * breath + 0.25 * this.beat + lubdub;
      ctx.drawImage(glow(PAL.accent), cx - cr * 2.6, cy - cr * 2.6, cr * 5.2, cr * 5.2);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
      this.blob(ctx, cx, cy, cr, tm * 0.7, 1.7, 0.05, tm * 0.04);
      const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr); cg.addColorStop(0, mix(PAL.accent, PAL.pink, 0.35)); cg.addColorStop(1, PAL.accent);
      ctx.fillStyle = cg; ctx.fill();
    }
    this.cr = cr;
    const fs = NEW ? nucleus * 0.46 : cr * 0.32;
    ctx.fillStyle = PAL.bg; ctx.font = `700 ${Math.max(9, fs)}px ${FONT}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const nm = this.state.name || "Kurooto", word = (NEW ? nm : nm.toUpperCase()).slice(0, 10);
    if (NEW) { const fit = (nucleus * 1.76) / Math.max(1, ctx.measureText(word).width); if (fit < 1) ctx.font = `700 ${Math.max(7, fs * fit)}px ${FONT}`; }
    ctx.fillText(word, cx, cy);
    if (this.ripples.length && now - this.ripples[0].t0 >= 1.8) this.ripples = this.ripples.filter((r) => now - r.t0 < 1.8);
    for (const r of this.ripples) { const k = (now - r.t0) / 1.8; ctx.strokeStyle = rgba(r.col, 0.45 * (1 - k)); ctx.lineWidth = 1.5 * (1 - k); ctx.beginPath(); ctx.arc(cx, cy, coreR * ((NEW ? 1.5 : 1.1) + k * 3.2), 0, TAU); ctx.stroke(); }
    if (NEW) this.synapses(ctx, now, cr);
    if (DENSE) this.panels(ctx, w, h, Math.round(12 * FSC));
    if (!cells.length) this.say(ctx, `No features on yet: turn some on in ${DENSE ? "features (Alt+F)" : "the Features tab below"}.`, cx, h - 16 - (DENSE ? 84 : 0), PAL.dim, "center", cf(11));
    this.hoverCard(hot);
  }
  cell(ctx, o, t, ringR) {
    const base = ringR * 0.075, col = o.down ? PAL.dim : PAL[o.color], breath = 0.5 + 0.5 * Math.sin((TAU * t) / (5.5 - 4.2 * o.act) + o.seed);
    const r = base * (1 + (0.05 + 0.1 * o.act) * breath + 0.2 * o.flash + 0.08 * (o.pump || 0)) * (1 + 0.12 * o.hv); o.r = r;
    const hr = base * 1.32; ctx.lineWidth = 1;
    o.hist.forEach((v, k) => { const a = -Math.PI / 2 + (k / 60) * TAU, L = 1.2 + base * 0.55 * v;
      ctx.strokeStyle = rgba(col, 0.18 + 0.5 * (k / Math.max(1, o.hist.length - 1)));
      ctx.beginPath(); ctx.moveTo(o.x + Math.cos(a) * hr, o.y + Math.sin(a) * hr); ctx.lineTo(o.x + Math.cos(a) * (hr + L), o.y + Math.sin(a) * (hr + L)); ctx.stroke(); });
    const spin = (o.i % 2 ? -1 : 1) * t * (0.2 + o.act) + o.seed;
    if (o.act > 0.05 || o.flash > 0.05) { ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.1 + 0.2 * breath * o.act + 0.45 * o.flash;
      const gs = r * (3.5 + 2 * o.act); ctx.drawImage(glow(col), o.x - gs / 2, o.y - gs / 2, gs, gs); ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over"; }
    this.blob(ctx, o.x, o.y, r, t * (0.6 + o.act), o.seed, 0.05 + 0.05 * o.act + 0.05 * o.flash, spin);
    ctx.fillStyle = PAL.bg; ctx.fill(); ctx.fillStyle = rgba(col, 0.2 + 0.35 * o.act + 0.3 * o.flash + 0.15 * o.hv); ctx.fill();
    ctx.strokeStyle = rgba(col, o.down ? 0.5 : 0.85); ctx.lineWidth = 1.1; ctx.setLineDash(o.down ? [2, 3] : []); ctx.stroke(); ctx.setLineDash([]);
    o.reach = hr + base * 0.55 + 1; // the cell with its halo: what words mustn't cover
  }
  // Each cell's words sit outside it, along the line from the core (never on its own nerve). A label that would touch
  // another cell, another label, the core or a corner panel tries a little further out, then turned a little either
  // way, then with fewer words (no detail, then the name alone, then a shortened name). A label that had to give way
  // needs a few pixels to spare before it grows back, so the words don't flicker as the cells orbit.
  labels(ctx, cells, cx, cy, coreR, w, h) {
    const LH = Math.round(11 * FSC), placed = [], panels = DENSE ? this.panelRects || [] : [];
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
      const name = [o.label, cf(10, 600), rgba(o.down ? PAL.dim : PAL.fg, 0.95)];
      const full = [name, [vital, cf(9), o.down ? rgba(PAL.bad, 0.85) : rgba(col, 0.85)], ...(more ? [[more, cf(8), rgba(PAL.fg, 0.42)]] : [])];
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
      const tiny = [[o.label.length > 8 ? o.label.slice(0, 7) + "…" : o.label, cf(8, 600), name[2]]];
      for (const sp of [...near, ...mid, ...far]) tries.push([tiny, sp]);
      let best = null, rank = 0;
      for (const [lines, [turn, step]] of tries) {
        const bw = Math.max(...lines.map(([s, f]) => width(s, f))) + 4, bh = lines.length * LH;
        const ux = Math.cos(a0 + turn), uy = Math.sin(a0 + turn), dist = o.reach + 3 + step * 10, ax = o.x + ux * dist, ay = o.y + uy * dist;
        const x0 = ax - bw / 2 + (bw / 2) * clamp(ux / 0.55, -1, 1), y0 = ay - bh / 2 + (bh / 2) * clamp(uy / 0.55, -1, 1);
        const b = { x0, y0, x1: x0 + bw, y1: y0 + bh, ux }, moved = turn !== 0 || step > 0;
        if (cost(b, o, rank < (o.labRank != null ? o.labRank : 1e9) ? 5 : 1) === 0) { best = { b, lines, rank, moved }; break; }
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
  panels(ctx, w, h, lh) { } // the dense board's four corners (home.js)
  // ---------------------------------------------------------------------------------------------- the cards
  // where a card goes: beside its cell, on the side away from the core (or beside the core), inside the pane
  place(el, o, cw, ch) {
    const w = this.w || 0, h = this.h || 0, off = this.off || { x: 0, y: 0 };
    let x, y;
    if (o) { // beside it on the side away from the core, else above or below it, else the other side: what fits best
      const right = o.x >= this.cx, below = o.y >= this.cy, gap = Math.max(o.reach || 0, (o.r || 8) * 1.9) + 10, R = (this.cr || 20) * 1.6;
      // (a big card in a small pane: the pane's corner nearest the cell, over the folded corner panels)
      const spots = [[right ? o.x + gap : o.x - gap - cw, o.y - ch / 2, 0], [o.x - cw / 2, below ? o.y + gap : o.y - gap - ch, 0],
        [o.x - cw / 2, below ? o.y - gap - ch : o.y + gap, 10], [right ? o.x - gap - cw : o.x + gap, o.y - ch / 2, 10],
        ...[[6, 6], [w - cw - 6, 6], [6, h - ch - 6], [w - cw - 6, h - ch - 6]].map(([a, b]) => [a, b, 20 + Math.hypot(a + cw / 2 - o.x, b + ch / 2 - o.y) / 20])];
      let best = 1e9;
      for (const [sx, sy, cost] of spots) {
        const fx = clamp(sx, 6, Math.max(6, w - cw - 6)), fy = clamp(sy, 6, Math.max(6, h - ch - 6)), m = (o.r || 8) + 4;
        const core = Math.max(0, R - Math.hypot(clamp(this.cx, fx, fx + cw) - this.cx, clamp(this.cy, fy, fy + ch) - this.cy));
        const bad = cost + Math.abs(fx - sx) + Math.abs(fy - sy) + core * 3 + (fx < o.x + m && fx + cw > o.x - m && fy < o.y + m && fy + ch > o.y - m ? 400 : 0);
        if (bad < best - 0.5) { best = bad; x = fx; y = fy; }
      }
    } else { x = this.cx - cw / 2; y = this.cy + (this.cr || 20) * (NEW ? 1.6 : 1.3); } // the core's card: below it
    x = clamp(x, 6, Math.max(6, w - cw - 6)); y = clamp(y, 6, Math.max(6, h - ch - 6));
    const L = `${Math.round(x + off.x)}px`, T = `${Math.round(y + off.y)}px`;
    if (el.style.left !== L) el.style.left = L;
    if (el.style.top !== T) el.style.top = T;
    if (el.style.right !== "auto") { el.style.right = "auto"; el.style.bottom = "auto"; }
  }
  // the card for the cell pointed at or focused (or the core): what it is and how it's doing
  hoverCard(hot) {
    const card = this.els.card, o = hot && hot !== "core" ? this.o.get(hot) : null;
    if (!card) return;
    if (this.w !== this.cv.clientWidth || this.h !== this.cv.clientHeight) { this.w = this.cv.clientWidth; this.h = this.cv.clientHeight; this.off = { x: this.cv.offsetLeft, y: this.cv.offsetTop }; }
    if (this.menu) { const m = this.o.get(this.menu); if (m && this.els.menu) this.place(this.els.menu, m, this.menuW, this.menuH); }
    if (this.menu || !(o || (hot === "core" && (this.mouse || this.pin)))) { if (!card.classList.contains("hidden")) card.classList.add("hidden"); this.cardHtml = ""; return; }
    const html = this.card(o);
    if (html !== this.cardHtml) { card.innerHTML = html; card.classList.remove("hidden"); this.cardHtml = html; this.cardW = card.offsetWidth; this.cardH = card.offsetHeight; }
    this.place(card, o, this.cardW, this.cardH);
  }
  // what the card says: the cell's feature (o), or the core (o null)
  card(o) {
    let html;
    if (o) {
      const p = o.proc;
      html = `<div class="h">${esc(o.data.title)}</div><div>${o.data.events} event${o.data.events === 1 ? "" : "s"} in the last 2 minutes</div>` +
        (o.down ? '<div class="bad2">its program isn\'t running</div>' : "") +
        (o.idle ? '<div class="d">idle: its program runs now and then</div>' : "") +
        (p ? `<div class="d">${p.n > 1 ? `its ${p.n} processes` : "its process"}: cpu ${(p.cpu * 100).toFixed(1)}% · ${bytes(p.mem)} · ${p.threads} threads · up ${ago(p.up)}</div>` : "") +
        (o.last != null ? `<div class="d">last event ${ago(o.last)} ago</div>` : "") +
        (o.next ? `<div class="d">next scheduled ${hm(o.next)}</div>` : "") + this.hint(o);
    } else {
      const c = this.state.core || {};
      html = `<div class="h">${esc(this.state.name || "Kurooto")}</div><div>beating ${Math.round(this.bpm)} a minute${c.mem ? ` · cpu ${(c.cpu * 100).toFixed(1)}% · ${bytes(c.mem)}` : ""}</div>` +
        this.hint(null);
    }
    return html;
  }
  // the card's last line: what a click does here (the phone's view, which has no actions, puts its health there)
  hint(o) {
    return o ? `<div class="d k">${this.focus === o.id ? "Enter" : "click"} for its actions</div>` : '<div class="d k">click: do something (Ctrl+K)</div>';
  }
}
