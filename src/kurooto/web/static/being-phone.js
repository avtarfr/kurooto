/* The being on the phone (0.8.10): the dashboard's own static/being.js in the Android app's Views → Being (ViewsPane,
   views/being.html), with the same anatomy, shaders, bloom and light. This file is the phone's part of it, in two halves:

   window.beingPhone   what being.js calls when opts.mode is "phone" (its hooks are marked "phone:"): touch (one finger
                       turns the organ under it, or the view where there's none; pinch zooms; two fingers pan; a tap
                       picks, with a finger's width of room), the side panel as a bottom sheet (a handle, half and full
                       height, dragged or flung), and the words over the canvas set for a narrow screen.
   window.KurootoBeing what the app calls (evaluateJavascript): take(text) with this phone's copies (the Systems copy,
                       whose "being" block calls/views.py being_snapshot makes, and the Notes map's when it's new),
                       back() for the back button. The page can't call into the app; it asks through two addresses
                       the app answers itself (ViewsPane.serve): /ask (a setting, a feature on or off, a note's
                       preview, mute: sealed call-line requests, BeingRules.java) and /state (how deep you are, WebGL 2).
   Nothing here reaches the network: the page's CSP allows only the app's own files. */
(function () {
"use strict";
const clampN = (v, a, b) => Math.max(a, Math.min(b, v));
const FONT = 'Roboto, "Google Sans", system-ui, sans-serif';
const STATE = { status: "", warn: "" }; // the header's second line: "live" or "as of", and what's wrong

/* ======================================== the adapter being.js calls ======================================== */
const S = { panel: null, close: null, open: 0, y: 0, goal: 0, h: 0, host: 0, drag: null, raf: 0, cam: null, size: null, shift: 0, shiftGoal: 0,
  organ: false, inset: 0, still: false }; // an organ page (being.js opts.only): no sheet; the app's bars cover its top and bottom (inset)
const HALF = .5, TALL = .9; // the sheet's half height and its full one, of the screen

function sheetY(state) { return state === 2 ? 0 : state === 1 ? S.h - S.host * HALF : S.h + 24; }
function sheetMeasure() { // full height leaves the name and the two buttons at the top in sight
  const host = S.panel && S.panel.parentElement; if (!host) return;
  S.host = host.clientHeight; S.h = Math.round(Math.min(S.host * TALL, S.host - 64)); S.panel.style.height = S.h + "px";
}
// the sheet follows the finger 1:1; let go, it settles with a spring (critically damped: no bounce, no overshoot)
function sheetTick() {
  S.raf = 0;
  if (!S.panel && !S.organ) return;
  if (S.panel) {
    if (!S.drag) { const d = S.goal - S.y; S.y += d * .24; if (Math.abs(d) < .5) S.y = S.goal; }
    S.panel.style.transform = `translate3d(0,${S.y.toFixed(1)}px,0)`;
  }
  S.shiftGoal = S.open ? S.host * HALF * .5 : S.inset; S.shift += (S.shiftGoal - S.shift) * (S.still ? 1 : .2); if (Math.abs(S.shiftGoal - S.shift) < .5) S.shift = S.shiftGoal;
  lens();
  if (S.drag || S.y !== S.goal || S.shift !== S.shiftGoal) S.raf = requestAnimationFrame(sheetTick);
  else if (S.panel && !S.open && S.y >= S.h) S.panel.style.visibility = "hidden";
}
const kick = () => { if (!S.raf) S.raf = requestAnimationFrame(sheetTick); };
// with the sheet up, the camera's centre moves up into what's left of the screen, so what you picked stays in view
function lens() {
  if (!S.cam || !S.size) return;
  const [w, h] = S.size();
  if (Math.abs(S.shift) > .5) S.cam.setViewOffset(w, h, 0, S.shift, w, h); else if (S.cam.view && S.cam.view.enabled) S.cam.clearViewOffset();
  S.cam.updateProjectionMatrix();
}
function sheetTo(state) {
  S.open = state; S.goal = sheetY(state);
  S.panel.style.touchAction = state === 2 ? "pan-y" : "none"; // full: the words scroll; half: the sheet moves
  S.panel.classList.toggle("full", state === 2);
  kick();
}
function sheetWire(panel) {
  panel.addEventListener("pointerdown", (e) => {
    const onGrab = e.target.closest(".grab"), r = panel.getBoundingClientRect();
    if (S.open === 2 && !onGrab && e.clientY - r.top > 44) return; // full: the content scrolls; only its top drags
    S.drag = { y0: e.clientY, sy: S.y, t: performance.now(), v: 0, ly: e.clientY, lt: performance.now(), on: false, id: e.pointerId };
  });
  panel.addEventListener("pointermove", (e) => {
    const d = S.drag; if (!d || d.id !== e.pointerId) return;
    const dy = e.clientY - d.y0;
    if (!d.on && Math.abs(dy) > 7) { d.on = true; try { panel.setPointerCapture(e.pointerId); } catch (err) { /* fine */ } }
    if (!d.on) return;
    const now = performance.now(); d.v = (e.clientY - d.ly) / Math.max(1, now - d.lt); d.ly = e.clientY; d.lt = now;
    S.y = Math.max(-8, d.sy + dy); kick();
  });
  const up = (e) => {
    const d = S.drag; if (!d || d.id !== e.pointerId) return; S.drag = null;
    if (!d.on) { kick(); return; } // a tap: the panel's own buttons have it
    e.preventDefault();
    const half = sheetY(1), fling = d.v * 220; // a flick carries it on
    const at = S.y + fling;
    if (at > half + (S.h - half) * .35) { S.goal = sheetY(0); S.open = 0; kick(); setTimeout(() => S.close && S.close(), 180); return; }
    sheetTo(at < half * .55 ? 2 : 1);
  };
  panel.addEventListener("pointerup", up);
  panel.addEventListener("pointercancel", up);
  panel.addEventListener("click", (e) => { if (e.target.closest(".grab") && S.open) sheetTo(S.open === 1 ? 2 : 1); });
}

window.beingPhone = {
  dpr: 1.5, // the 3D drawing's pixels per CSS pixel (the dashboard's cap too)
  room(h) { return h > 0 ? Math.max(.3, Math.min(1, (h - (S.cover || 0)) / h)) : 1; }, // an organ page: the share of its height the app's bars leave
  // a phone held upright sees as wide as the dashboard does (its camera's 30° high on a board about 1.7 times as wide as
  // it's tall): the same framing of every organ and part, with the extra height above and below
  fov(aspect) { return aspect >= 1.7 ? 30 : 2 * Math.atan(Math.tan(15 * Math.PI / 180) * 1.7 / aspect) * 180 / Math.PI; },
  css(P) {
    return `.being{font:13px/1.45 ${FONT};-webkit-tap-highlight-color:transparent;user-select:none;-webkit-user-select:none}
  .being canvas{touch-action:none}
  .being .bp{left:0!important;right:0!important;top:auto!important;bottom:0!important;width:auto!important;max-height:none;border:0;border-top:1px solid ${P.mute}55;border-radius:28px 28px 0 0;padding:6px 18px 32px;background:${P.bg}f0;font-size:14px;overscroll-behavior:contain;will-change:transform;transform:translate3d(0,120%,0);overflow:hidden;box-shadow:0 -12px 32px #0008}
  .being .bp.full{overflow:auto}
  .being .bp .grab{position:sticky;top:-6px;z-index:2;height:30px;width:140px;margin:-6px auto 4px;border-radius:0 0 14px 14px;display:flex;align-items:center;justify-content:center;background:${P.bg}f0;touch-action:none}
  .being .bp .grab:before{content:"";width:36px;height:4px;border-radius:2px;background:${P.mute}aa}
  .being .bp h2{font-size:19px;font-weight:600;margin:2px 44px 4px 0}.being .bp .s{font-size:13px}.being .bp h3{font-size:11px;margin:18px 0 6px}
  .being .bp .grow{min-height:46px;padding:6px 0;font-size:14px}.being .bp .grow span:last-child{text-align:right}
  .being .bp input,.being .bp select{font-size:14px;padding:8px 10px;max-width:46vw;border-radius:10px}.being .bp textarea{font-size:12px}
  .being .tg{width:52px;height:32px}.being .tg:after{width:24px;height:24px;left:4px;top:4px}.being .tg.on:after{left:24px}
  .being .bp .x{right:10px;top:4px;width:44px;height:44px;font-size:26px}
  .being .bp pre{font-size:12.5px;max-height:none}.being .bp button.b{padding:10px 18px;font-size:14px}
  .being .bp .gbars{font-size:11px}.being .bp .gbar{height:20px;line-height:20px}.being .bp .gbar span{width:110px}
  .being .mute{top:12px;right:12px;padding:9px 14px;font:600 12px ${FONT};border-radius:99px}.being .hints{right:106px!important}
  .being .bmode{top:100px;border-radius:99px;white-space:nowrap}.being .bmode button{padding:10px 18px;font:600 13px ${FONT}}
  .being .tip{display:none!important}`;
  },
  // being.js's input, for touch: one finger turns, pinch zooms, two fingers pan, a tap picks
  touch(T) {
    const gl = T.gl, F = new Map(); let g = null;
    S.cam = T.cam; S.size = T.size;
    if (S.organ) kick(); // the app said where its bars are before the being was up
    const two = () => { const [a, b] = [...F.values()]; return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; };
    gl.addEventListener("pointerdown", (e) => {
      try { gl.setPointerCapture(e.pointerId); } catch (err) { /* fine */ }
      F.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (F.size === 1) {
        T.spinning.obj = null;
        g = { n: 1, sx: e.clientX, sy: e.clientY, x: e.clientX, y: e.clientY, t: performance.now(), moved: false, obj: T.organ(T.pickAt(e, true)), e };
        T.setDrag({ b: 0, moved: false });
      } else if (F.size === 2) {
        const m = two(); g = { n: 2, d0: m.d, gd: T.goal.d, x: m.x, y: m.y, moved: true };
        T.setDrag({ b: 2, moved: true });
      }
    });
    gl.addEventListener("pointermove", (e) => {
      if (!F.has(e.pointerId) || !g) return;
      F.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (g.n === 2 && F.size >= 2) {
        const m = two(), G = T.goal;
        const near = T.only() ? .25 : 1.2; // an organ page: as close as a single note
        G.d = clampN(g.gd * g.d0 / m.d, near, T.only() ? 12 : 22);
        const dx = m.x - g.x, dy = m.y - g.y, s = G.d * .0012, r = { x: Math.cos(G.th), z: -Math.sin(G.th) };
        G.tx -= r.x * dx * s; G.tz -= r.z * dx * s; G.ty += dy * s; g.x = m.x; g.y = m.y;
        return;
      }
      if (g.n !== 1) return;
      const dx = e.clientX - g.x, dy = e.clientY - g.y; g.x = e.clientX; g.y = e.clientY;
      if (!g.moved && Math.hypot(e.clientX - g.sx, e.clientY - g.sy) > 8) g.moved = true;
      if (!g.moved) return;
      if (g.obj) { g.obj.rotation.y += dx * .009; g.obj.rotation.x += dy * .009; T.spinning.obj = g.obj; T.spinning.vx = dx * .009; T.spinning.vy = dy * .009; }
      else { const G = T.goal; G.th -= dx * .006; G.ph = clampN(G.ph - dy * .005, .45, 2.7); T.spinning.obj = "cam"; T.spinning.vx = -dx * .006; T.spinning.vy = 0; }
    });
    const up = (e) => {
      if (!F.has(e.pointerId)) return;
      F.delete(e.pointerId);
      if (g && g.n === 1 && !g.moved && e.type === "pointerup" && performance.now() - g.t < 600) tap(e);
      if (F.size === 0) { g = null; T.setDrag(null); }
      else if (F.size === 1) { // one finger left: it turns the view from here, never a tap
        const q = [...F.values()][0]; g = { n: 1, sx: q.x, sy: q.y, x: q.x, y: q.y, t: 0, moved: true, obj: null };
        T.setDrag({ b: 0, moved: true });
      }
    };
    gl.addEventListener("pointerup", up);
    gl.addEventListener("pointercancel", up);
    // a finger is wider than a mouse: inside an organ, a point of light or a note within a few millimetres counts (on
    // the whole body a tap on an organ looks into it, as a click does)
    const OFF = [[0, -10], [0, 10], [-10, 0], [10, 0], [-8, -8], [8, -8], [-8, 8], [8, 8], [0, -16], [0, 16], [-16, 0], [16, 0]];
    function tap(e) {
      const p0 = T.pickAt(e);
      if (T.focus() && !(p0 && (p0.feature || p0.note != null))) {
        for (const [ox, oy] of OFF) {
          const e2 = { clientX: e.clientX + ox, clientY: e.clientY + oy }, p = T.pickAt(e2);
          if (p && (p.feature || p.note != null)) { T.click(e2); report(); return; }
        }
      }
      T.click(e); report();
    }
    addEventListener("resize", () => { if (S.panel) { sheetMeasure(); S.goal = sheetY(S.open); S.y = S.goal; } kick(); });
  },
  // being.js's panel opened (or closed): the bottom sheet, half height the first time, where it was after that
  sheet(panel, open, close, kind) {
    if (S.panel !== panel) { S.panel = panel; sheetWire(panel); }
    S.close = close || S.close;
    if (!open) { S.open = 0; S.goal = S.y = sheetY(0); kick(); report(); return; }
    const grab = document.createElement("div"); grab.className = "grab"; grab.setAttribute("aria-label", "drag to make the panel taller or shorter");
    rewordPanel(panel, kind);
    panel.prepend(grab);
    sheetMeasure();
    panel.style.visibility = "visible";
    if (!S.open) { S.y = sheetY(0); sheetTo(1); } else sheetTo(S.open);
    panel.scrollTop = 0;
    report();
  },
  ui: {
    x0: 16,
    small: `500 11.5px ${FONT}`,
    // the name, its pulse, how fresh this copy is, the hints, and the colours' key in three columns
    header(c, s) {
      const P = s.P; BOXES.length = 0; // a new frame: no labels placed yet
      WIDE = s.W > s.H * 1.2; // turned sideways: too short for the colours' key; the hints beside the name
      c.textAlign = "left"; c.font = `400 11px ${FONT}`; c.fillStyle = P.mute; c.fillText("KUROOTO", 16, 26);
      c.font = `300 21px ${FONT}`; c.fillStyle = P.ink; c.fillText("the being", 16, 50);
      c.font = `400 11px ui-monospace,monospace`; c.fillStyle = P.mute;
      c.fillText(`${Math.round(s.BPM)} / min · ${s.n} events${STATE.status ? " · " + STATE.status : ""}`, 16, 70);
      if (STATE.warn) { c.fillStyle = "#e9b98f"; c.fillText(STATE.warn, 16, 86); }
      let y = STATE.warn ? 104 : 88;
      if (s.HINTS && WIDE) { c.font = `400 11.5px ${FONT}`; c.fillStyle = P.mute; c.fillText(s.focus ? "drag to turn · tap a part · back goes up" : "drag to turn · pinch · tap to look in", 128, 50); y -= 18; }
      else if (s.HINTS) { c.font = `400 11.5px ${FONT}`; c.fillStyle = P.mute; c.fillText(s.focus ? "drag to turn it · tap a part · back goes up" : "drag an organ to turn it · pinch to zoom · tap one to look in", 16, y); }
      const mode = document.querySelector(".being .bmode"), top = (s.HINTS ? y + 12 : y - 6) + "px"; // Solid · Cutaway · X-ray under the words
      if (mode && mode.style.top !== top) mode.style.top = top;
      TOP = WIDE ? 20 : y + 10; // labels stay below the words above, and below the mode bar when it shows
      if (mode && mode.style.display === "flex") TOP = parseFloat(top) + (mode.offsetHeight || 40) + 6;
      if (!s.HINTS || s.focus || WIDE) return; // in an organ its parts are named: the colours' key waits for the whole body
      y += 18; const keys = Object.keys(s.PROC), cols = 3, cw = (s.W - 32) / cols; c.font = `400 10.5px ${FONT}`;
      TOP = y + Math.ceil(keys.length / cols) * 15 - 5; // and below the colours' key
      keys.forEach((k, i) => {
        const x = 16 + (i % cols) * cw, yy = y + Math.floor(i / cols) * 15;
        c.fillStyle = "#" + new THREE.Color(s.PROC[k].c).getHexString(); c.beginPath(); c.arc(x + 3, yy - 3.5, 3, 0, 6.3); c.fill();
        c.fillStyle = P.mute; let name = s.PROC[k].name; while (name.length > 4 && c.measureText(name).width > cw - 16) name = name.slice(0, -2) + "…";
        c.fillText(name, x + 11, yy);
      });
    },
    // a label with its lead line: shorter leads on a narrow screen, larger words, kept on the screen; the line under
    // the name only where it's yours to read (the organs at the start, or the part you picked)
    tag(c, x, y, dx, dy, title, sub, alpha, mine, W, H, P) {
      const k = clampN(W / 760, .4, 1);
      const spot = mine === undefined && (WIDE ? SPOTS_WIDE : SPOTS)[title]; // the four organs at the start: kept apart
      if (spot) { dx = spot[0]; dy = spot[1]; }
      else { dx *= k; dy *= k; if (Math.abs(dx) < 28) dx = dx < 0 ? -28 : 28; }
      if (mine === false) sub = "";
      sub = words(sub);
      if (spot && sub) { // the first words only, and not too wide: four labels share a small screen
        c.font = `400 12px ${FONT}`; sub = clip(c, sub.split(/ · |: /)[0], Math.min(170, W * .42));
      }
      const crowd = mine !== undefined; // an organ's parts: no label on top of another (the one you picked always shows)
      c.save(); c.globalAlpha = alpha;
      c.font = `600 12px ${FONT}`; const T = title.toUpperCase(), wt = c.measureText(T).width;
      c.font = `400 12px ${FONT}`; const ws = sub ? c.measureText(sub).width : 0, w = Math.max(wt, ws) + 8;
      if (spot) { /* never flipped: their places don't cross */ } else if (dx > 0 && x + dx + w > W - 8) dx = -dx; else if (dx < 0 && x + dx - w < 8) dx = -dx;
      const lx = dx < 0 ? Math.max(x + dx, Math.min(x - 8, w + 14)) : Math.min(x + dx, Math.max(x + 8, W - w - 14)), ly = clampN(y + dy, Math.max(20, TOP + 16), H - 20); // kept on the screen, under the header
      const box = [dx < 0 ? lx - 6 - w : lx + 6, ly - 16, dx < 0 ? lx - 6 : lx + 6 + w, ly + (sub ? 16 : 2)];
      if (crowd && !mine && BOXES.some((b) => b[0] < box[2] && box[0] < b[2] && b[1] < box[3] && box[1] < b[3])) { c.restore(); return; }
      if (spot && sub && dx > 0) { // an organ's line stops short of a lead it would cross
        const stop = Math.min(W, ...BOXES.filter((q) => q[4] > lx + 6 && q[5] <= box[3] && q[6] >= box[1]).map((q) => q[4]));
        sub = clip(c, sub, stop - lx - 20);
      }
      box.push(x, Math.min(y, ly), Math.max(y, ly)); BOXES.push(box); // [left, top, right, bottom, the lead's x, its top, its bottom]
      c.strokeStyle = P.mute; c.lineWidth = 1; c.beginPath(); c.moveTo(x, y); c.lineTo(x + dx * .35, ly); c.lineTo(lx, ly); c.stroke();
      c.fillStyle = P.ink; c.beginPath(); c.arc(x, y, 2.5, 0, 6.3); c.fill();
      c.textAlign = dx < 0 ? "right" : "left"; c.lineJoin = "round"; c.lineWidth = 4; c.strokeStyle = P.bg; const tx = lx + (dx < 0 ? -6 : 6);
      c.font = `600 12px ${FONT}`; c.strokeText(T, tx, ly - 4); c.fillText(T, tx, ly - 4);
      if (sub) { c.font = `400 12px ${FONT}`; c.fillStyle = P.mute; const s2 = clip(c, sub, dx < 0 ? lx - 14 : W - lx - 14); c.strokeText(s2, tx, ly + 12); c.fillText(s2, tx, ly + 12); }
      c.restore();
    },
    // the voice's two lanes, lower and thinner than the dashboard's; no talk box here
    lanes(c, lane, L, W, H) {
      lane(c, H - 60, 20, L.you, "YOU", L.you ? (L.you.typed ? "typed to Kurooto" : L.you.heard ? "heard, not to Kurooto" : "heard, and said to Kurooto") : "what you say to it at your computer");
      lane(c, H - 22, 26, L.me, "KUROOTO", L.me ? (L.me.typed ? "answered" : "speaking") : "");
    },
  },
};
// the dashboard's words where a phone differs: you tap, there's no hovering, no keyboard
const WORDS = [[/\bClick\b/g, "Tap"], [/\bclick\b/g, "tap"], [/Hover a note for its title, tap it/g, "Tap a note"],
  [/ on the Features page \(Alt\+F\)/g, " on your computer's dashboard (Features)"], [/\(Esc\)/g, ""]];
function words(t) { for (const [a, b] of WORDS) t = t.replace(a, b); return t; }
function rewordPanel(el, kind) { // its own words only: never a note's title or path (a note, a neighbourhood)
  if (kind !== "note" && kind !== "hood") for (const s of el.querySelectorAll(".s")) { const t = words(s.textContent); if (t !== s.textContent && !s.children.length) s.textContent = t; }
  for (const b of el.querySelectorAll("[title]")) b.removeAttribute("title"); // no hovering on a phone
}
const BOXES = []; // the labels placed this frame
let TOP = 90, WIDE = false; // where the words over the drawing end (the mode bar's bottom when it shows); sideways
// the four organs at the start: Mind and Senses above, Memory beside the brain, Core below (being.js draws Mind first)
const SPOTS = { Mind: [14, -96], Senses: [14, -66], Memory: [-10, -50], Core: [14, 62] };
const SPOTS_WIDE = { Mind: [40, -6], Senses: [-80, 24], Memory: [30, -30], Core: [40, 30] }; // sideways: around the body
function clip(c, s, w) { if (w < 30) return ""; let t = s; while (t.length > 4 && c.measureText(t).width > w) t = t.slice(0, -2); return t === s ? s : t + "…"; }

/* ======================================== the page: what the app hands in ======================================== */
const $ = (s) => document.querySelector(s);
const PV = { being: null, mounting: false, gl: null, demo: false, made: 0, notesMade: -1, graph: null, seen: new Set(), primed: false,
  settings: null, brain: null, voice: null, computer: "", reach: true, off: false, depth: -1, palette: null, look: null, ok: true,
  only: null, still: false, rev: "" }; // only: the organ page (brain, heart, senses, memory), or null for the whole being

function report(extra) {
  const d = PV.being ? PV.being.depth() : 0;
  // an organ page: when what it lists changed (or how fresh the copy is), the app reads it again (organState)
  const rev = PV.being && PV.being.rev ? `${PV.being.rev()}.${STATE.status}.${STATE.warn}` : "";
  if (d === PV.depth && rev === PV.rev && !extra) return;
  PV.depth = d; PV.rev = rev;
  fetch(`/state?depth=${d}${rev ? `&rev=${encodeURIComponent(rev)}` : ""}${extra || ""}&n=${Math.random().toString(36).slice(2)}`, { cache: "no-store" }).catch(() => {});
}
function message(text, small) {
  const el = $("#msg"); if (!el) return;
  el.innerHTML = text ? `<p>${text}</p>${small ? `<p class="small">${small}</p>` : ""}` : "";
  el.classList.toggle("hidden", !text);
}
function webgl2() { // asked once; the probe's context is let go at once (a phone has only a few)
  try { const g = document.createElement("canvas").getContext("webgl2"); if (!g) return false; const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); return true; } catch (err) { return false; }
}

// a request to your computer, through the app (ViewsPane answers /ask with BeingRules: sealed over your call line)
async function ask(op, args) {
  if (PV.demo) return demoAsk(op, args);
  const r = await fetch(`/ask?op=${encodeURIComponent(op)}&a=${encodeURIComponent(JSON.stringify(args || {}))}&n=${Math.random().toString(36).slice(2)}`, { cache: "no-store" });
  return r.json();
}
function setPath(key, value) {
  const S2 = PV.settings; if (!S2) return;
  const [sec, ...rest] = key.split("."), s = (S2.sections || []).find((x) => x.section === sec); if (!s || !rest.length) return;
  let o = s.values; for (let i = 0; i < rest.length - 1; i++) { if (!o[rest[i]] || typeof o[rest[i]] !== "object") return; o = o[rest[i]]; }
  o[rest[rest.length - 1]] = value;
}
// being.js's opts.api: the dashboard's addresses, answered from this phone's copy or by asking your computer
async function api(path, body) {
  const [p, q] = path.split("?"), qs = new URLSearchParams(q || "");
  const off = (r) => (r && r.offline ? "Your computer is off: try again when it's on." : (r && r.note) || "That didn't work.");
  if (body === undefined) {
    if (p === "settings") { if (PV.settings) return PV.settings; throw new Error("the settings come with the next copy"); }
    if (p === "brain3d") { if (PV.brain) return PV.brain; throw new Error("the Brain's parts come with the next copy"); }
    if (p === "voice") return PV.voice || { error: "Voice isn't on this install" };
    if (p === "note") { const r = await ask("note.get", { id: qs.get("id") }); if (r && r.ok) return { text: r.text || "" }; return { text: `(${off(r)})` }; }
    throw new Error("not on the phone");
  }
  if (p === "settings") { const r = await ask("settings.set", { key: body.key, value: body.value }); if (r && r.ok) { setPath(body.key, r.value !== undefined && r.value !== null ? r.value : body.value); return { ok: true }; } return { ok: false, error: off(r) }; }
  if (p === "modules/enable") { const id = (body.ids || [])[0], r = await ask("module", { id, on: true }); return { results: { [id]: { ok: !!(r && r.ok), message: r && r.ok ? r.note : off(r) } } }; }
  if (p === "modules/disable") { const r = await ask("module", { id: body.id, on: false }); return { ok: !!(r && r.ok), message: r && r.ok ? r.note : off(r) }; }
  if (p === "voice/mute") { const r = await ask("voice.mute", {}); if (r && r.ok) { if (PV.voice) PV.voice.muted = !!r.muted; return { muted: !!r.muted, message: r.note || "" }; } return { error: off(r) }; }
  throw new Error("not on the phone"); // voice/shape (being.js estimates it), open-note (nothing to open it in)
}

// the Notes map's copy as the dashboard's graph ({nodes, links}), and its neighbourhoods as the NOTES map draws them
// (views/notesmap.js assignHoods: courses, projects, the hub), so the memory's colours and names match the dashboard's
function graphOf(s) {
  const nodes = (s.nodes || []).map((n) => ({ id: String(n[0]), title: String(n[1] || n[0]) }));
  const links = []; const M = new Map(nodes.map((n) => [n.id, Object.assign({}, n, { nb: new Set(), out: new Set(), snb: new Set() })]));
  for (const l of s.links || []) {
    const a = nodes[l[0]], b = nodes[l[1]]; if (!a || !b) continue;
    links.push(l[2] ? [a.id, b.id, 1] : [a.id, b.id]);
    const A = M.get(a.id), B = M.get(b.id); A.nb.add(b.id); B.nb.add(a.id); A.out.add(b.id); if (!l[2]) { A.snb.add(b.id); B.snb.add(a.id); }
  }
  let hoods = null;
  try { hoods = assignHoods(M, { layout: s.layout || {}, research: s.research || {}, subjects: s.subjects || [] }); } catch (err) { hoods = null; }
  const hoodOf = (id) => { const n = M.get(id), k = n && n.neighborhood; if (!k || !hoods) return null; const h = hoods.get(k); return { key: k, label: h ? h.label : k }; };
  return { g: { nodes, links }, hoodOf };
}

function asOf() {
  const parts = []; let warn = "";
  if (PV.made) {
    const d = new Date(PV.made * 1000), today = new Date().toDateString() === d.toDateString(), hm = d.toTimeString().slice(0, 5);
    parts.push(PV.computer === "online" && Date.now() / 1000 - PV.made < 20 ? `live ${hm}` : `as of ${today ? hm : d.toDateString().slice(4, 10) + " " + hm}`);
  }
  if (!PV.reach) warn = "can't reach your call line"; else if (PV.computer === "offline") warn = "your computer is asleep";
  STATE.status = parts.join(""); STATE.warn = warn;
}
setInterval(asOf, 5000); // "live" fades to "as of" without a new copy

// the sparks: each event once, spread over the few seconds a copy covers, so they don't all fire at once
function feedEvents(list) {
  const fresh = [];
  for (const e of list || []) { const k = `${e.ts}:${e.kind}`; if (!PV.seen.has(k)) { PV.seen.add(k); fresh.push(e); } }
  if (PV.seen.size > 600) PV.seen = new Set([...PV.seen].slice(-300));
  const go = PV.primed ? fresh : fresh.slice(-12); PV.primed = true; // the first copy: its last few, as the dashboard starts
  go.forEach((e, i) => setTimeout(() => { if (PV.being) PV.being.event(e); }, PV.primed && go.length > 1 ? i * (3500 / go.length) : 0));
}

function feed(b) {
  if (b.settings) PV.settings = b.settings;
  if (b.brain) PV.brain = b.brain;
  const vWas = JSON.stringify(PV.voice); PV.voice = b.voice || null;
  if (!PV.being) return;
  PV.being.update({ cells: b.cells || [], sys: b.sys || {}, jobs: b.jobs || [], schedule: b.schedule || [], link: b.link || { off: true }, calls: b.calls || [] });
  if (JSON.stringify(PV.voice) !== vWas) PV.being.voice({ kind: "voice_state" });
  feedEvents(b.events);
  if (b.look && PV.look && b.look.hints !== PV.look.hints) PV.being.setHints(b.look.hints);
  if (b.look && PV.look && b.look.rest !== PV.look.rest) PV.being.setRest(b.look.rest);
  PV.look = b.look || PV.look;
}

async function mount(b) {
  if (PV.being || PV.mounting) return;
  PV.mounting = true;
  message("Waking the being…");
  try {
    const host = $("#being"), look = b.look || {}, pal = PV.palette || {};
    PV.look = look;
    PV.being = await window.beingMount(host, { api, mode: "phone", only: PV.only || undefined, still: PV.still, hoodOf: (id) => (PV.graph ? PV.graph.hoodOf(id) : null),
      theme: look.theme === "theme" ? "theme" : "void", pal: { bg: pal.bg, fg: pal.fg, accent: pal.accent, rose: pal.rose, bad: pal.bad, dim: pal.dim }, hints: look.hints !== false, restSparks: look.rest !== false });
    message("");
    if (PV.graph) PV.being.graph(PV.graph.g);
    feed(b);
    setInterval(() => report(), PV.only ? 200 : 400); // a tap, Esc or a sheet closed: the app's back button knows how deep you are
  } catch (err) {
    message("The being couldn't start on this phone.", String(err && err.message || err).slice(0, 160));
    report("&gl=0");
  } finally { PV.mounting = false; }
}

function take(text) {
  let d; try { d = JSON.parse(text); } catch (err) { return false; }
  if (PV.gl === null) { PV.gl = webgl2(); if (!PV.gl) { report("&gl=0"); message("This phone's web view can't draw the being: it needs WebGL 2."); return true; } }
  if (!PV.gl) return true;
  PV.demo = !!d.demo; PV.palette = d.palette || PV.palette; PV.computer = d.computer || ""; PV.reach = d.reach !== false; PV.off = !!d.off;
  if (!PV.being && !PV.mounting) { PV.only = d.only || null; PV.still = !!d.still; S.still = PV.still; } // set once, as it mounts
  if (d.notes && typeof d.notes === "object" && d.notes.made !== PV.notesMade) {
    PV.notesMade = d.notes.made; PV.graph = graphOf(d.notes);
    if (PV.being) PV.being.graph(PV.graph.g);
  }
  const s = d.snap && typeof d.snap === "object" ? d.snap : null;
  let b = s && s.being;
  if (s && !b && PV.demo) b = s.being = demoBeing(s);
  if (s) PV.made = +s.made || 0;
  asOf();
  if (b) { if (!PV.being) mount(b); else feed(b); return true; }
  if (PV.being) return true; // an older copy without it: keep what's shown
  if (s) message("Your computer isn't sending the being.", "Update Kurooto there, or turn its setting calls.views_being on.");
  else if (PV.off) message("Turned off on your computer.", "On its dashboard: Phone → Show on the phone.");
  else if (PV.reach) message("Nothing here yet.", "Your computer sends it while you watch, when it's on and Show on the phone is on (its dashboard, Phone).");
  else message("Can't reach your call line, and there's no copy on this phone yet.");
  return true;
}

function back() { const used = !!(PV.being && PV.being.escape()); report(); return used; }

/* ---- the organ pages (0.8.10): the app's Brain, Heart, Senses and Memory, one organ each on the same page ---- */
const organ = () => (PV.being && PV.being.only ? PV.being : null); // mounted as an organ page
function only(page) { // another organ, without loading the page again
  if (!organ()) { PV.only = page; return false; }
  const ok = organ().only(page); if (ok) PV.only = page; report(); return ok;
}
function organState() { // what the app lists: the parts, the one picked, how fresh the copy is
  if (!organ()) return "{}";
  const st = JSON.parse(organ().state() || "{}"); st.status = STATE.status; st.warn = STATE.warn; return JSON.stringify(st);
}
function pick(kind, key) { if (organ()) { organ().pick(String(kind || ""), String(key ?? "")); report(); } return true; }
function setting(key, value) { if (organ()) organ().setting(String(key), value); return true; }
function feature(id, on) { if (organ()) organ().feature(String(id), !!on); return true; }
function mode(m) { if (organ()) organ().mode(String(m)); return true; }
function inset(top, bottom) { // CSS pixels the app's bars cover at the top and bottom: the organ sits centred between them
  S.organ = true; S.inset = Math.round(((+bottom || 0) - (+top || 0)) / 2); TOP = Math.max(0, +top || 0); S.cover = Math.max(0, +top || 0) + Math.max(0, +bottom || 0); kick(); return true;
}

/* ---- demo (dev builds' made-up data: the app hands in demo: true): the rest of a being beside Demo's Systems ---- */
const DEMO = { muted: false, n: 0 };
function demoBeing(s) {
  const now = Math.floor(Date.now() / 1000), on = (s.cells || []).map((c) => Object.assign({}, c, { on: true }));
  const offc = [["voice", "Voice"], ["remember", "Remember"], ["calendar", "Calendar"], ["backups", "Backups"], ["study", "Study"], ["integrate", "Integrate"]].map(([id, title]) => ({ id, title, on: false, act: 0, events: 0 }));
  const sec = (section, title, values, choices) => ({ section, title, values, choices: choices || {} });
  return {
    cells: on.concat(offc),
    jobs: [{ status: "running", title: "Summarise the topology lecture" }, { status: "queued", title: "Plan tomorrow's revision" }, { status: "ok", title: "What's due this week?" }, { status: "ok", title: "Make a quiz on eigenvalues" }],
    schedule: [{ when: now + 900, what: "Reminder: lab report" }, { when: now + 3600, what: "Check-in" }, { when: now + 7200, what: "Weekly summary" }],
    calls: [{ when: now + 5400, what: "Wake-up call" }],
    link: { connected: true, beat: 2.4 },
    sys: { cpu: .21, cores: [.3, .12, .18, .4, .08, .22, .1, .15], mem: .52, mem_used: 8.3e9, mem_total: 16e9, swap: .04, gpu: { util: .12, temp: 51, mem_used: 1.1e9, mem_total: 8e9 }, disks: [{ mount: "/", pct: .61, free: 120e9 }], battery: { percent: 78, ac: true }, temps: { cpu: 58 }, cpu_name: "A made-up 8-core processor", load: [1.2, .9, .8] },
    events: [], voice: { on: true, state: "listening", listening: true, why: "", portal: false, muted: DEMO.muted, line: "listens for its name", speak: { engine: "kokoro", voice: "af_heart" } },
    look: { theme: "void", hints: true, rest: true },
    settings: { sections: [
      sec("reminders", "Reminders", { snooze_min: 10, morning: "08:00", repeat: true }),
      sec("checkins", "Check-ins", { evening: true, at: "21:30", effort: "low" }, { effort: [["low", "low"], ["medium", "medium"], ["high", "high"]] }),
      sec("deadlines", "Deadlines", { warn_hours: 48, nudge: true }),
      sec("power", "Power", { mode: "balanced", night: true }, { mode: [["saver", "saver"], ["balanced", "balanced"], ["performance", "performance"]] }),
      sec("jobs", "AI requests", { max_running: 2, effort: "medium" }),
      sec("calls", "Phone calls", { ring_s: 60, later_min: 30, views: true, views_being: true }),
    ] },
    brain: { on: true, islands: [{ id: "hq", comps: [["workspace", "Workspace", 1, "on", [], "mind.workspace.on", ""], ["attention", "Attention schema", 1, "on", [], "mind.attention.on", ""], ["beliefs", "Beliefs", 0, "off", [], "mind.beliefs.on", ""]] },
      { id: "mem", comps: [["log", "Log", 1, "on", [], "mind.log.on", ""], ["journal", "Journal", 1, "on", [], "mind.journal.on", ""], ["forget", "Forgetting", 0, "off", [], "mind.forget.on", ""]] },
      { id: "body", comps: [["budget", "Budget", 1, "on", [], "mind.budget.on", ""], ["heartbeat", "Heartbeat", 1, "on", [], "mind.heartbeat.on", ""], ["gate", "The gate", 1, "on", [], "mind.gate.on", ""]] }] },
  };
}
const DEMO_KINDS = ["job_queued", "job_done", "notified", "message_in", "notes_synced", "calendar_synced", "phone_views_pushed", "study_timer", "setting_changed", "power_mode"];
setInterval(() => { if (PV.demo && PV.being && !document.hidden) PV.being.event({ kind: DEMO_KINDS[(DEMO.n++ * 7) % DEMO_KINDS.length], ts: Math.floor(Date.now() / 1000) }); }, 2600);
async function demoAsk(op, a) {
  await new Promise((r) => setTimeout(r, 350));
  if (op === "note.get") return { ok: true, text: "A made-up note, as a preview shows it.\n\nIts first lines, the links it makes, nothing more." };
  if (op === "voice.mute") { DEMO.muted = !DEMO.muted; return { ok: true, muted: DEMO.muted, note: DEMO.muted ? "Muted." : "Unmuted." }; }
  if (op === "module") return { ok: true, on: !!a.on, note: "" };
  return { ok: true, value: a.value };
}

window.KurootoBeing = { take, back, only, organState, pick, setting, feature, mode, inset };
})();
