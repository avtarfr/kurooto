// The phone app's Systems and Notes map (0.7.0), drawn by the dashboard's own code (common.js, systems.js,
// notesmap.js). The Android app (ViewsActivity) opens the copy your computer sealed for this phone and hands it in with
// KurootoView.take(text): a JSON string
//   {mode: "systems" | "notes", snap: the snapshot | null, made: when your computer made it (s), computer: "online" |
//    "offline" | "", reach: the call line answered, off: turned off on your computer, palette: {bg, fg, accent, lav,
//    pink, peach, sand, rose, bad, panel}}
// as often as it has something new. Nothing here talks to anything: no network (the page's CSP), no calls into the app.
// Read-only and touch-first: tap a feature or a note for its card, drag to turn the ring or move the map, pinch to zoom.
"use strict";
const $ = (s) => document.querySelector(s);
const KEYS = ["bg", "fg", "accent", "lav", "pink", "peach", "sand", "rose", "bad", "panel"];
const PV = { mode: "", snap: null, made: 0, computer: "", reach: true, off: false, pal: "", events: {}, seen: 0 };

// ------------------------------------------------------------------------------------------------ the palette
function setPalette(p) {
  const key = JSON.stringify(p || {});
  if (key === PV.pal) return;
  PV.pal = key;
  for (const k of KEYS) if (p && /^#[0-9a-f]{6}$/i.test(p[k] || "")) PAL[k] = p[k].toLowerCase();
  PAL.dim = mix(PAL.fg, PAL.bg, 0.5); PAL.line = mix(PAL.lav, PAL.bg, 0.62);
  SPRITES.clear();
  const root = document.documentElement.style;
  const vars = { bg: PAL.bg, fg: PAL.fg, dim: PAL.dim, panel: PAL.panel, raised: mix(PAL.panel, PAL.fg, 0.08), accent: PAL.accent, bad: PAL.bad };
  for (const k of Object.keys(vars)) root.setProperty(`--${k}`, vars[k]);
}

// ------------------------------------------------------------------------------------------------ SYSTEMS
// Body draws it as on the dashboard (never dense: the corner panels stay there). A tap on a feature pins its card
// (what it is, how busy, its process, what needs a look) and lights it; on the core, Kurooto's card; elsewhere, none.
class PhoneBody extends Body {
  wire() {
    super.wire(); // a drag turns the ring, springing back, as on the dashboard
    const cv = this.cv, at = (e) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const fingers = new Map();
    let pinch = null;
    cv.addEventListener("pointerdown", (e) => {
      fingers.set(e.pointerId, at(e));
      if (fingers.size === 2) { // a pinch zooms the ring (it springs back once you let go)
        const [a, b] = [...fingers.values()];
        pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: this.view.zt };
        this.view.drag = null;
      }
    });
    cv.addEventListener("pointermove", (e) => {
      if (!fingers.has(e.pointerId)) return;
      fingers.set(e.pointerId, at(e));
      if (pinch && fingers.size === 2) {
        const [a, b] = [...fingers.values()];
        this.view.zt = clamp(pinch.z * Math.hypot(a.x - b.x, a.y - b.y) / pinch.d, 0.8, 1.6); this.view.zAt = performance.now();
      }
    });
    const up = (e) => { fingers.delete(e.pointerId); if (fingers.size < 2) pinch = null; };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", up);
  }
  tap(hit) {
    this.pin = hit === "core";
    this.focus = hit === "core" ? "core" : hit ? hit.id : null;
  }
  // no actions here: the card ends with what needs a look, if anything
  hint(o) {
    if (o) return o.health ? `<div class="bad2">${esc(o.health)}</div>` : "";
    const bad = (this.state && this.state.health) || [];
    if (!bad.length) return '<div class="d">nothing needs a look</div>';
    return `<div class="bad2">${bad.length} thing${bad.length === 1 ? "" : "s"} need${bad.length === 1 ? "s" : ""} a look</div>` +
      bad.slice(0, 4).map((r) => `<div class="d">${esc(r.title)}: ${esc(r.detail)}</div>`).join("");
  }
}

// ------------------------------------------------------------------------------------------------ NOTES
// Mind draws the map as on the dashboard. One finger moves the map, two zoom it round their middle; a tap on a note
// lights it and its links and shows its card (its title, where it is, links, words, when it changed: never what it
// says); a tap on nothing lets the map fit itself again.
class PhoneMind extends Mind {
  wire() {
    this.fitPad = 40; // a narrow screen: the map fills more of it
    const cv = this.cv, fingers = new Map();
    const at = (e) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    let pan = null, pinch = null;
    cv.addEventListener("pointerdown", (e) => {
      const p = at(e);
      fingers.set(e.pointerId, p);
      this.touched = performance.now();
      if (fingers.size === 1) pan = { x: p.x, y: p.y, vx: this.view.x, vy: this.view.y, moved: false };
      else if (fingers.size === 2) {
        const [a, b] = [...fingers.values()];
        pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, k: this.view.k };
        if (pan) pan.moved = true; // not a tap
      }
    });
    cv.addEventListener("pointermove", (e) => {
      if (!fingers.has(e.pointerId)) return;
      const p = at(e);
      fingers.set(e.pointerId, p);
      this.touched = performance.now();
      if (pinch && fingers.size === 2) {
        const [a, b] = [...fingers.values()], mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const before = this.toWorld(mx, my, this.w, this.h);
        this.view.k = clamp(pinch.k * Math.hypot(a.x - b.x, a.y - b.y) / pinch.d, 0.08, 6);
        const after = this.toWorld(mx, my, this.w, this.h);
        this.view.x += after.x - before.x; this.view.y += after.y - before.y;
        this.autofit = false;
      } else if (pan && fingers.size === 1) {
        if (Math.hypot(p.x - pan.x, p.y - pan.y) > 8) pan.moved = true;
        if (pan.moved) { this.autofit = false; this.view.x = pan.vx + (p.x - pan.x) / this.view.k; this.view.y = pan.vy + (p.y - pan.y) / this.view.k; }
      }
    });
    const up = (e) => {
      if (!fingers.has(e.pointerId)) return;
      const p = fingers.get(e.pointerId);
      fingers.delete(e.pointerId);
      this.touched = performance.now();
      if (fingers.size === 0) {
        if (pan && !pan.moved && e.type === "pointerup") this.tapAt(p.x, p.y);
        pan = null; pinch = null;
      } else if (fingers.size === 1) { // one finger left: it moves the map from here
        const q = [...fingers.values()][0];
        pinch = null; pan = { x: q.x, y: q.y, vx: this.view.x, vy: this.view.y, moved: true };
      }
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", up);
  }
  tapAt(x, y) {
    const n = this.pickNear(x, y);
    this.selected = n;
    if (!n) this.autofit = true;
    this.showCard(n);
  }
  // a finger is wider than a mouse: the nearest note within 24 px
  pickNear(x, y) {
    let best = null, bd = 24;
    for (const n of this.nodes.values()) { const S = this.toScreen(n, this.w, this.h), d = Math.hypot(S.x - x, S.y - y); if (d < bd) { bd = d; best = n; } }
    return best;
  }
  showCard(n) {
    const el = $("#sheet");
    if (!n) { el.classList.add("hidden"); return; }
    el.innerHTML = `<div class="h">${esc(n.title)}</div><div class="d">${esc(n.id)}</div>` +
      `<div>${n.deg - (n.via || 0)} link${n.deg - (n.via || 0) === 1 ? "" : "s"}${n.via ? ` (+${n.via} from reading)` : ""} · ${n.words} words · edited ${ago(Date.now() / 1000 - (n.mtime || 0))} ago</div>`;
    el.classList.remove("hidden");
  }
  meta() {
    const hoods = new Set([...this.nodes.values()].map((n) => n.neighborhood)).size;
    $("#meta").textContent = `${this.nodes.size} notes · ${this.links.length} links · ${hoods} neighborhoods`;
  }
  // the layout settles, then rests (a phone's battery): it moves again when touched or given a new copy
  step() {
    const quiet = this.alpha <= 0.0401 && performance.now() - (this.touched || 0) > 1500;
    this.rested = quiet ? (this.rested || 0) + 1 : 0;
    if (this.rested > 90) return;
    super.step();
  }
}

// ------------------------------------------------------------------------------------------------ what's shown
let view = null;
function status() {
  const el = $("#asof"), parts = [];
  if (PV.made) {
    const d = new Date(PV.made * 1000), today = new Date().toDateString() === d.toDateString();
    const when = today ? d.toTimeString().slice(0, 5) : `${d.toDateString().slice(0, 10)} ${d.toTimeString().slice(0, 5)}`;
    const live = PV.mode === "systems" && PV.computer === "online" && Date.now() / 1000 - PV.made < 20;
    parts.push(live ? `<span class="live">live</span> · ${when}` : `as of ${esc(when)}`);
  }
  if (!PV.reach) parts.push('<span class="warn">can\'t reach your call line</span>');
  else if (PV.computer === "offline") parts.push('<span class="warn">your computer is asleep</span>');
  el.innerHTML = parts.join(" · ");
}

function empty(text) {
  const el = $("#empty");
  el.textContent = text || "";
  el.classList.toggle("hidden", !text);
}

// a snapshot of SYSTEMS: the dashboard's message, as far as the phone's copy holds it
function showSystems(s) {
  const age = Math.max(0, Date.now() / 1000 - (s.made || Date.now() / 1000));
  const m = Object.assign({}, s, {
    sys: s.sys || { cpu: 0 },
    cells: (s.cells || []).map((c) => Object.assign({}, c, { on: true })),
    features: (s.features || []).map((f) => Object.assign({}, f, { last: f.last != null ? f.last + age : null })),
  });
  const fresh = s.made !== PV.seen;
  view.update(m);
  if (fresh && PV.seen) { // what happened since the last copy runs along the nerves, as it does on the dashboard
    for (const c of m.cells) if ((c.events || 0) > (PV.events[c.id] || 0)) view.event({ cell: c.id, kind: "event" });
  }
  PV.events = {};
  for (const c of m.cells) PV.events[c.id] = c.events || 0;
  PV.seen = s.made;
}

// a snapshot of the notes map: notes as [id, title, mtime, words], links as pairs of their places in that list
// ([i, j, 1]: a link only in a "Seen in" or a reading list, drawn fainter and not sizing a note, as on the dashboard)
function showNotes(s) {
  if (s.made === PV.seen) return;
  PV.seen = s.made;
  const nodes = (s.nodes || []).map((n) => ({ id: String(n[0]), title: String(n[1] || n[0]), mtime: +n[2] || 0, words: +n[3] || 0 }));
  const links = [];
  for (const l of s.links || []) if (nodes[l[0]] && nodes[l[1]]) links.push(l[2] ? [nodes[l[0]].id, nodes[l[1]].id, 1] : [nodes[l[0]].id, nodes[l[1]].id]);
  view.update({ nodes, links, changed: [], version: s.made, layout: s.layout || {}, research: s.research || {}, subjects: s.subjects || [] });
  view.alpha = Math.max(view.alpha, 0.6);
  view.touched = performance.now();
  if (view.selected && !view.nodes.has(view.selected.id)) { view.selected = null; view.showCard(null); }
}

function take(text) {
  let d;
  try { d = JSON.parse(text); } catch (err) { return false; }
  setPalette(d.palette);
  if (!view) {
    PV.mode = d.mode === "notes" ? "notes" : "systems";
    $("#what").textContent = PV.mode === "notes" ? "Notes map" : "Systems";
    view = PV.mode === "notes" ? new PhoneMind($("#view")) : new PhoneBody($("#view"), { meta: $("#meta"), card: $("#card") });
    requestAnimationFrame(frame);
  }
  PV.computer = d.computer || ""; PV.reach = d.reach !== false; PV.off = !!d.off;
  const s = d.snap && typeof d.snap === "object" ? d.snap : null;
  if (s) {
    PV.made = +s.made || 0;
    PV.snap = s;
    if (PV.mode === "notes") showNotes(s); else showSystems(s);
    empty("");
  } else if (!PV.snap) {
    empty(PV.off ? "Turned off on your computer: on its dashboard, Phone → Show on the phone."
      : PV.reach ? "Nothing here yet. Your computer sends it when it's on and Show on the phone is on (its dashboard, Phone)."
        : "Can't reach your call line, and there's no copy on this phone yet.");
  }
  status();
  return true;
}

let lastT = 0;
function frame(ts) {
  requestAnimationFrame(frame);
  if (document.hidden || ts - lastT < 33) return; // 30 frames a second is plenty on a phone
  lastT = ts;
  try {
    if (!PV.snap) return;
    if (PV.mode === "notes") { view.step(); view.draw(); } else view.draw(ts / 1000);
  } catch (err) { /* a bad frame: the next one tries again */ }
  if (Math.floor(ts / 5000) !== Math.floor((ts - 40) / 5000)) status(); // "live" fades to "as of" without a new copy
}

LIGHT = STILL.matches; // with "Remove animations" on, the drawing holds still and is lighter
window.KurootoView = { take };
