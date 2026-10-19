// The dashboard: STATUS (this computer), SYSTEMS (Kurooto's features as living cells round a beating core; what
// happens runs along the nerves), NOTES (your notes and their links) and tabs for activity, AI jobs, the
// schedule, features and settings. Everything comes from /api/stream; nothing loads from the internet.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const TAU = Math.PI * 2;
const FONT = '"JetBrains Mono", "Cascadia Mono", "SF Mono", Consolas, monospace';
const PAL = { bg: "#22181a", fg: "#efd1d0", accent: "#ff4e79", lav: "#b3a3d5", pink: "#ec8fa8", peach: "#ffba92", sand: "#f9d7ac", rose: "#ffbcb2" };
const hexRgb = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const mix = (a, b, t) => "#" + hexRgb(a).map((v, i) => Math.round(v + (hexRgb(b)[i] - v) * t).toString(16).padStart(2, "0")).join("");
const rgba = (h, a) => { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; };
PAL.dim = mix(PAL.fg, PAL.bg, 0.5); PAL.line = mix(PAL.lav, PAL.bg, 0.62);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ago = (sec) => { if (sec == null || !isFinite(sec)) return "—"; sec = Math.max(0, sec); if (sec < 60) return `${Math.round(sec)}s`; if (sec < 3600) return `${Math.round(sec / 60)}m`; if (sec < 86400) return `${Math.floor(sec / 3600)}h${String(Math.floor((sec % 3600) / 60)).padStart(2, "0")}`; return `${Math.floor(sec / 86400)}d`; };
const bytes = (n) => { if (!n) return "0"; const u = ["B", "K", "M", "G", "T"]; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return `${n.toFixed(i > 1 ? 1 : 0)}${u[i]}`; };
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();
let LIGHT = false; // lighter drawing on modest computers (hardware profile "light") or with reduced motion

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

// ------------------------------------------------------------------------------------------------ SYSTEMS
const COLORS = { telegram: "lav", chat: "peach", reminders: "pink", checkins: "rose", deadlines: "accent", gbrain: "lav",
  local_models: "sand", subjects: "sand", quiz: "pink", weekly: "rose", files: "peach" };
const SHORT = { telegram: "telegram", chat: "chat", reminders: "reminders", checkins: "check-ins", deadlines: "deadlines",
  gbrain: "notes brain", local_models: "local models", subjects: "subjects", quiz: "quiz", weekly: "weekly", files: "files" };
const OUTBOUND = /fired|asked|told|notified|done|reply/;

class Body {
  constructor(cv) {
    this.cv = cv; this.state = null; this.o = new Map(); this.pulses = []; this.ripples = [];
    this.beats = []; this.systoles = []; this.nextBeat = 0; this.beat = 0;
    cv.addEventListener("mousemove", (e) => { const r = cv.getBoundingClientRect(); this.mouse = { x: e.clientX - r.left, y: e.clientY - r.top }; });
    cv.addEventListener("mouseleave", () => { this.mouse = null; });
  }
  update(m) {
    this.state = m;
    const on = m.cells.filter((c) => c.on);
    const ids = on.map((c) => c.id);
    for (const id of [...this.o.keys()]) if (!ids.includes(id)) this.o.delete(id);
    on.forEach((c, i) => {
      let o = this.o.get(c.id);
      if (!o) { o = { id: c.id, label: SHORT[c.id] || c.title, color: COLORS[c.id] || "fg", seed: Math.random() * 10, act: 0, flash: 0, hist: [] }; this.o.set(c.id, o); }
      o.i = i; o.target = c.act; o.data = c; o.hist.push(c.act); if (o.hist.length > 60) o.hist.shift();
    });
    $("#sys-meta").textContent = `${on.length} feature${on.length === 1 ? "" : "s"} on`;
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
  say(ctx, s, x, y, col, align = "left", font = `9px ${FONT}`) {
    ctx.font = font; ctx.textAlign = align; ctx.textBaseline = "alphabetic";
    const wd = ctx.measureText(s).width, x0 = align === "right" ? x - wd : align === "center" ? x - wd / 2 : x;
    ctx.fillStyle = rgba(PAL.bg, 0.72); ctx.fillRect(x0 - 2, y - 9, wd + 4, 12); ctx.fillStyle = col; ctx.fillText(s, x, y);
  }
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
  clock(ctx, cx, cy, r, t) {
    ctx.strokeStyle = rgba(PAL.line, 0.9); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.stroke();
    for (let h = 0; h < 24; h++) { const a = -Math.PI / 2 + (h / 24) * TAU, L = h % 6 === 0 ? 6 : 3;
      ctx.strokeStyle = rgba(PAL.fg, h % 6 === 0 ? 0.45 : 0.18);
      ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * (r - L), cy + Math.sin(a) * (r - L)); ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); ctx.stroke(); }
    const ang = (d) => -Math.PI / 2 + ((d.getHours() + d.getMinutes() / 60) / 24) * TAU;
    for (const j of (this.state && this.state.schedule) || []) {
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
    const ringR = clamp(Math.min(w * 0.36, (h - 70) / 1.9), 60, 420), cx = w / 2, cy = h / 2 + 4;
    const coreR = ringR * 0.18, rc = coreR * 2.2;
    this.tickBeats(now, cpu);
    if (!LIGHT) this.ecg(ctx, w, now, cy, ringR * 0.55);
    const cells = [...this.o.values()], n = Math.max(1, cells.length), orbit = LIGHT ? 0 : (t * TAU) / 180;
    for (const o of cells) {
      const a = -Math.PI / 2 + (o.i / n) * TAU + orbit + 0.05 * Math.sin(t * 0.13 + o.seed);
      const rr = ringR * (1 + 0.04 * Math.sin(t * 0.21 + o.seed * 2));
      o.x = cx + Math.cos(a) * rr; o.y = cy + Math.sin(a) * rr * 0.86;
      o.act += ((o.target || 0) - o.act) * 0.05; o.flash *= 0.94; o.pump = (o.pump || 0) * 0.88;
    }
    const ctrl = (a, b, seed) => { const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, k = 0.12 * d * Math.sin(t * 0.37 + seed); return { x: mx - (dy / d) * k, y: my + (dx / d) * k }; };
    const core = { x: cx, y: cy };
    for (const o of cells) {
      const c = ctrl(core, o, o.seed), fill = o.pump || 0, g = ctx.createLinearGradient(cx, cy, o.x, o.y);
      g.addColorStop(0, rgba(PAL.accent, 0.18 + 0.12 * fill)); g.addColorStop(1, rgba(PAL[o.color], 0.28 + 0.4 * o.act + 0.12 * fill));
      ctx.strokeStyle = g; ctx.lineWidth = 0.8 + 2 * o.act + o.flash * 1.5 + 0.5 * fill;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(c.x, c.y, o.x, o.y); ctx.stroke();
    }
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
    if (!cells.length) this.say(ctx, "No features on yet: turn some on in the Features tab below.", cx, h - 16, PAL.dim, "center", `11px ${FONT}`);
    this.hoverCard();
  }
  cell(ctx, o, t, ringR) {
    const base = ringR * 0.075, col = PAL[o.color], breath = 0.5 + 0.5 * Math.sin((TAU * t) / (5.5 - 4.2 * o.act) + o.seed);
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
    ctx.strokeStyle = rgba(col, 0.85); ctx.lineWidth = 1.1; ctx.stroke();
    const ly = o.y + hr + base * 0.55 + 10;
    this.say(ctx, o.label, o.x, ly, rgba(PAL.fg, 0.95), "center", `600 10px ${FONT}`);
    const ev = o.data.events;
    this.say(ctx, ev ? `${ev} in 2 min` : "quiet", o.x, ly + 11, rgba(col, 0.85), "center", `9px ${FONT}`);
  }
  hoverCard() {
    const card = $("#body-card");
    if (!this.mouse) { card.classList.add("hidden"); return; }
    let best = null, bd = 1e9;
    for (const o of this.o.values()) { const d = Math.hypot(o.x - this.mouse.x, o.y - this.mouse.y); if (d < (o.r || 10) * 2.2 && d < bd) { bd = d; best = o; } }
    if (!best) { card.classList.add("hidden"); return; }
    card.innerHTML = `<div class="h">${esc(best.data.title)}</div><div>${best.data.events} event${best.data.events === 1 ? "" : "s"} in the last 2 minutes</div>`;
    card.classList.remove("hidden");
  }
}

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
    this.anchor = new Map(groups.map((gname, i) => [gname, { x: Math.cos((i / groups.length) * TAU) * 210, y: Math.sin((i / groups.length) * TAU) * 190 }]));
    if (first) for (const n of this.nodes.values()) { const a = this.anchor.get(n.group); n.x = a.x + (Math.random() - 0.5) * 120; n.y = a.y + (Math.random() - 0.5) * 120; }
    else for (const id of g.changed || []) { const n = this.nodes.get(id); if (n) this.flares.push({ n, t0: performance.now() / 1000 }); this.alpha = Math.max(this.alpha, 0.35); }
    $("#mind-meta").textContent = `${this.nodes.size} notes · ${this.links.length} links`;
  }
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
    const k = Math.min((w - 160) / Math.max(50, x1 - x0), (h - 90) / Math.max(50, y1 - y0)), tk = clamp(k, 0.25, 2.5);
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
  }
  pick(x, y) { let best = null, bd = 14; for (const n of this.nodes.values()) { const S = this.toScreen(n, this.w, this.h), d = Math.hypot(S.x - x, S.y - y); if (d < bd) { bd = d; best = n; } } return best; }
  async showCard(n, pinned) {
    const card = $("#mind-card"); if (!n) { card.classList.add("hidden"); return; }
    card.innerHTML = `<div class="h">${esc(n.title)}</div><div class="d">${esc(n.id)}</div><div>${n.deg} links · ${n.words} words · edited ${ago(Date.now() / 1000 - (n.mtime || 0))} ago</div>` + (pinned ? '<pre>…</pre><div class="d">double-click: open it</div>' : "");
    card.classList.remove("hidden");
    if (pinned) { try { const r = await api(`note?id=${encodeURIComponent(n.id)}`); if (this.selected === n) card.querySelector("pre").textContent = (r.text || "").trim().split("\n").slice(0, 14).join("\n"); } catch { /* leave it */ } }
  }
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
    s.addEventListener("keydown", (e) => { if (e.key === "Escape") { this.query = ""; s.value = ""; s.classList.add("hidden"); } });
    window.addEventListener("keydown", (e) => { if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); s.classList.remove("hidden"); s.focus(); } });
  }
}

// -------------------------------------------------------------------------------------- STATUS and tabs
let last = null;
function renderStatus(m) {
  const s = m.sys, pct = (v) => `${Math.round((v || 0) * 100)}%`;
  const meter = (v, col) => `<div class="meter"><i style="width:${clamp(v * 100, 0, 100)}%;background:var(--${col})"></i></div>`;
  const gpu = (s.gpus || []).map((g) => esc(g.name) + (g.vram_gb ? ` (${g.vram_gb} GB)` : "")).join(", ") || "none in use";
  $("#status").innerHTML = `
    <div class="row2"><span class="k">cpu</span><span>${pct(s.cpu)}${s.temps.cpu ? ` · ${s.temps.cpu}°C` : ""}</span></div>
    <div class="cores">${s.cores.map((c) => `<i style="height:${Math.max(4, c * 100)}%"></i>`).join("")}</div>
    <div class="row2"><span class="k">memory</span><span>${bytes(s.mem_used)} / ${bytes(s.mem_total)}</span></div>${meter(s.mem, "lav")}
    <div class="row2"><span class="k">network</span><span>↓ ${bytes(s.rx)}/s ↑ ${bytes(s.tx)}/s</span></div>
    <div class="row2"><span class="k">disk free</span><span>${bytes(s.disk_free)} of ${bytes(s.disk_total)}</span></div>${meter(1 - s.disk_free / s.disk_total, "peach")}
    ${s.battery ? `<div class="row2"><span class="k">battery</span><span>${Math.round(s.battery.percent)}% ${s.battery.ac ? "on charger" : "on battery"}</span></div>` : ""}
    <div class="row2"><span class="k">graphics</span><span>${gpu}</span></div>
    <div class="row2"><span class="k">profile</span><span>${esc(s.profile || "—")}</span></div>
    <div class="row2"><span class="k">up</span><span>${ago(s.uptime)}</span></div>
    <div class="row2"><span class="k">kurooto</span><span class="${m.power && m.power.mode !== "normal" ? "warn" : ""}">${
      !m.power || m.power.mode === "normal" ? "running" : m.power.mode === "saver" ? "saving battery: heavy work waits for the charger" : `paused ${esc(m.power.why)}`}</span></div>
    <div class="pw">${m.power && m.power.mode === "paused" ? '<button data-pw="resume">Resume</button>' : '<button data-pw="pause">Pause 1 h</button>'}<button data-pw="off">Turn off</button></div>`;
  $("#meta").textContent = `${m.cells.filter((c) => c.on).length} features on · ${m.jobs.filter((j) => j.status === "running").length} AI request running · cpu ${pct(s.cpu)}`;
  const u = m.updates || {};
  const badge = $("#update-badge");
  if (u.ready && u.ready.version) { badge.textContent = `update ${u.ready.version} ${u.ready.staged ? "ready tonight" : "available"}`; badge.classList.remove("hidden"); } else badge.classList.add("hidden");
  $("#ver").textContent = m.version;
}

const feed = [];
const TABS = { activity: "Activity", jobs: "AI jobs", schedule: "Schedule", features: "Features", phone: "Phone", research: "Research", settings: "Settings" };
let tab = "activity";
function showTab(name) {
  tab = name;
  $("#tabs").replaceChildren(...Object.entries(TABS).map(([k, v]) => { const b = document.createElement("button"); b.textContent = v; b.className = k === tab ? "on" : ""; b.onclick = () => showTab(k); return b; }));
  try { localStorage.setItem("kurooto.dash.tab", name); } catch { /* fine */ }
  // the settings-like tabs get room (the canvases above shrink and redraw by themselves)
  $(".grid").classList.toggle("tall", ["features", "phone", "research", "settings", "terminals"].includes(name));
  renderTab();
}
function renderTab() {
  const body = $("#tab-body");
  if (tab === "activity") body.innerHTML = feed.length ? `<table>${feed.slice(0, 80).map((e) => `<tr><td>${esc((e.ts || "").slice(11, 19))}</td><td>${esc(e.kind.replace(/_/g, " "))}</td><td class="d">${esc(Object.entries(e).filter(([k]) => !["ts", "kind", "t", "cell"].includes(k)).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 160))}</td></tr>`).join("")}</table>` : "Nothing yet. Things Kurooto does appear here as they happen.";
  else if (tab === "jobs" && last) body.innerHTML = last.jobs.length ? `<table><tr><th>when</th><th>request</th><th>effort</th><th>took</th><th>result</th></tr>${last.jobs.map((j) => `<tr><td>${ago(Date.now() / 1000 - j.created)} ago</td><td>${esc(j.title)}</td><td>${esc(j.effort || "")}</td><td>${j.seconds ? Math.round(j.seconds) + "s" : ""}</td><td class="${j.status === "ok" ? "ok2" : j.status === "failed" ? "bad2" : ""}">${esc(j.status)}${j.verdict && j.verdict !== "ok" ? " · " + esc(j.verdict) : ""}</td></tr>`).join("")}</table>` : "No AI requests yet.";
  else if (tab === "schedule" && last) body.innerHTML = last.schedule.length ? `<table><tr><th>when</th><th>what</th></tr>${last.schedule.map((s) => `<tr><td>${new Date(s.when * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}</td><td>${esc(s.what)}</td></tr>`).join("")}</table>` : "Nothing scheduled.";
  else if (tab === "features") renderFeatures(body);
  else if (tab === "phone") renderPhone(body);
  else if (tab === "research") renderResearch(body);
  else if (tab === "settings") renderSettings(body);
  else if (tab === "terminals") renderTerminals(body);
}
async function renderFeatures(body) {
  const st = await api("state");
  const form = (m) => !m.form || m.ready ? "" : `<form class="sf" data-form="${m.id}"><p class="d">${esc(m.form.intro)}</p>
    <p class="d">${m.form.links.map(([l, h]) => `<a href="${esc(h)}" target="_blank" rel="noopener">${esc(l)}</a>`).join(" · ")}</p>
    ${m.form.fields.map((f) => `<label>${esc(f.label)}${f.type === "textarea" ? `<textarea name="${esc(f.name)}" rows="3" placeholder="${esc(f.placeholder || "")}"></textarea>`
      : `<input name="${esc(f.name)}" type="${f.type === "password" ? "password" : "text"}" placeholder="${esc(f.placeholder || "")}" autocomplete="off">`}</label>`).join("")}
    <button class="primary" type="submit">Save</button></form>`;
  const card = (m) => `<div class="card2 ${m.on ? "on" : ""}"><b>${esc(m.title)}</b><p>${esc(m.description)}</p><p style="color:var(--lav)">${esc(m.privacy)}</p>${m.id === "mail_digest" && m.on ? `<p><a href="/confidential" target="_blank" rel="noopener">Confidential mail (summarised on this computer)</a></p>` : ""}
    ${m.on ? `<button data-off="${m.id}">Turn off</button>` : m.ready ? `<button class="primary" data-on="${m.id}">Turn on</button>` : m.setup ? `<button class="primary" data-setup="${m.id}">Set up</button> <span class="d">${esc(m.why)}</span>` : `<span class="d">${esc(m.why)}</span>`}${form(m)}</div>`;
  const addons = st.modules.filter((m) => m.addon); // features from your own add-ons folder (core/overlay.py)
  body.innerHTML = `<div class="feat">${st.modules.filter((m) => !m.addon).map(card).join("")}</div>${addons.length
    ? `<p class="d">Your add-ons: your own code, from your add-ons folder</p><div class="feat">${addons.map(card).join("")}</div>` : ""}<div class="log" id="flog"></div>`;
  body.onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target, flog = $("#flog");
    const values = Object.fromEntries([...f.querySelectorAll("input, textarea")].map((i) => [i.name, i.value]));
    const r = await api("modules/configure", { id: f.dataset.form, values });
    flog.textContent = r.message || "";
    if (r.open) window.open(r.open, "_blank", "noopener");
    if (r.ok && !r.open) renderFeatures(body);
  };
  body.onclick = async (e) => {
    const t = e.target, flog = $("#flog");
    if (t.dataset.on) { const r = await api("modules/enable", { ids: [t.dataset.on] }); flog.textContent = Object.values(r.results).map((x) => x.message).join("\n"); renderFeatures(body); }
    if (t.dataset.off) { const r = await api("modules/disable", { id: t.dataset.off }); flog.textContent = r.message; renderFeatures(body); }
    if (t.dataset.setup) { t.disabled = true; await api("modules/setup", { id: t.dataset.setup });
      for (;;) { const p = await api("progress"); flog.innerHTML = linkify(p.lines.map((l) => l.line).join("\n")); if (!p.installing) break; await new Promise((r) => setTimeout(r, 1000)); }
      renderFeatures(body); }
  };
}
// escaped text with its web addresses as links (the Cloudflare sign-in page shows up in a setup log)
const linkify = (text) => text.split(/(https?:\/\/[^\s<>"]+)/g).map((part, i) => (i % 2
  ? `<a href="${esc(part)}" target="_blank" rel="noopener">${esc(part.length > 90 ? part.slice(0, 87) + "…" : part)}</a>` : esc(part))).join("");

async function renderPhone(body) {
  const ph = await api("phone");
  if (!ph.on) { body.innerHTML = "Phone calls are off. Turn them on in the Features tab (you'll need a free Gemini key and a free Cloudflare account; setup does the rest)."; return; }
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
        ? `<div class="qr">${r.svg}</div><p>Scan with the phone's camera, or send /phone to your bot and tap the link on the phone. Works for 15 minutes. Code <code>${esc(r.code)}</code> · <a href="${esc(r.link)}" target="_blank" rel="noopener">link</a></p>`
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

async function renderSettings(body) {
  const { sections } = await api("settings");
  const field = (key, v) => {
    if (typeof v === "boolean") return `<label>${esc(key)}<input type="checkbox" data-key="${key}" ${v ? "checked" : ""}></label>`;
    if (Array.isArray(v) || (v && typeof v === "object")) return `<label>${esc(key)}<input data-key="${key}" data-json value="${esc(JSON.stringify(v))}"></label>`;
    return `<label>${esc(key)}<input data-key="${key}" ${typeof v === "number" ? 'type="number" data-num' : ""} value="${esc(v ?? "")}"></label>`;
  };
  body.innerHTML = `<div class="form">${sections.map((s) => `<fieldset><legend>${esc(s.title)}</legend>${Object.entries(s.values).map(([k, v]) => field(`${s.section}.${k}`, v)).join("")}</fieldset>`).join("")}</div><p class="d" id="saved"></p>`;
  body.onchange = async (e) => {
    const t = e.target; if (!t.dataset.key) return;
    let value = t.type === "checkbox" ? t.checked : t.dataset.num !== undefined ? Number(t.value) : t.value;
    if (t.dataset.json !== undefined) { try { value = JSON.parse(t.value); } catch { $("#saved").textContent = "That isn't valid; it wasn't saved."; return; } }
    const r = await api("settings", { key: t.dataset.key, value });
    $("#saved").textContent = r.ok ? `Saved ${t.dataset.key}.` : r.error;
  };
}

// ------------------------------------------------------------------------------------------------ wiring
let body, mind;
function connect() {
  const es = new EventSource(`/api/stream?t=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.t === "graph") mind.update(m);
    else if (m.t === "body") { last = m; LIGHT = m.sys.profile === "light" || matchMedia("(prefers-reduced-motion: reduce)").matches; body.update(m); renderStatus(m); if (tab === "jobs" || tab === "schedule") renderTab(); }
    else if (m.t === "event") { feed.unshift(m); feed.length = Math.min(feed.length, 200); body.event(m); if (tab === "activity") renderTab(); }
    else if (m.t === "hello") { TERM.cid = m.cid; if (TERM.shown) termAttach(TERM.shown); }
    else if (m.t === "pty") termData(m);
  };
  es.onerror = () => { $("#meta").textContent = "reconnecting…"; };
}
// Pause, resume, or off completely (until Kurooto is opened again from the app menu or `kurooto on`)
document.addEventListener("click", async (e) => {
  const what = e.target.dataset && e.target.dataset.pw;
  if (!what) return;
  if (what === "off" && !confirm("Turn Kurooto off completely?\n\nIt stops now and won't start when you sign in, and your call line won't call you, until you open Kurooto from your app menu again (or run `kurooto on`).")) return;
  const r = await api(`power/${what}`, what === "pause" ? { when: "1h" } : {});
  $("#meta").textContent = r.message || "";
  if (what === "off") document.body.innerHTML = `<p style="padding:40px;font:16px var(--sans)">${esc(r.message || "Kurooto is off.")}</p>`;
});

// ------------------------------------------------------------------------------------------------ terminals
// Real terminals (modules/terminals.py): xterm.js (vendored, loaded the first time the tab opens) draws them; what you
// type goes to /api/term/<name>/input, their output comes back on the stream, only to this page.
const TERM = { cid: null, shown: null, list: [], xs: {}, loading: null };
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
    theme: { background: PAL.bg, foreground: PAL.fg, cursor: PAL.accent, selectionBackground: rgba(PAL.lav, 0.35) } });
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
document.addEventListener("keydown", (e) => {
  if (tab !== "terminals" || !e.altKey || !/^[1-9]$/.test(e.key)) return;
  const t = TERM.list[Number(e.key) - 1]; if (t) { e.preventDefault(); termShow(t.name); }
});
window.addEventListener("resize", () => { if (tab === "terminals" && TERM.shown && TERM.xs[TERM.shown]) try { TERM.xs[TERM.shown].fit.fit(); } catch { /* hidden */ } });

(function main() {
  body = new Body($("#body")); mind = new Mind($("#mind"));
  let saved = "activity"; try { saved = localStorage.getItem("kurooto.dash.tab") || "activity"; } catch { /* fine */ }
  api("events").then((r) => { for (const e of (r.events || []).reverse()) feed.push(e); if (tab === "activity") renderTab(); }).catch(() => {});
  showTab(TABS[saved] ? saved : "activity");
  api("term").then((r) => { if (r.on) { TABS.terminals = "Terminals"; showTab(saved === "terminals" ? "terminals" : tab); } }).catch(() => {});
  connect();
  let lastT = 0;
  const frame = (ts) => { requestAnimationFrame(frame); if (document.hidden || ts - lastT < (LIGHT ? 33 : 16)) return; lastT = ts;
    const t = ts / 1000; try { body.draw(t); } catch (e) { console.error(e); } try { mind.step(); mind.draw(); } catch (e) { console.error(e); } };
  requestAnimationFrame(frame);
})();
