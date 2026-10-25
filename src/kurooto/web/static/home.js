// The dashboard: STATUS (this computer), SYSTEMS (Kurooto's features as living cells round a beating core; what
// happens runs along the nerves), NOTES (your notes and their links) and tabs for activity, AI jobs, the
// schedule, features and settings. Everything comes from /api/stream; nothing loads from the internet.
//
// Two layouts (Settings → look.layout). "dense", the default on screens 1280 px wide or more, is one full-screen
// board: thin borders with each pane's name in its top line, STATUS down the left as a btop-like monitor (processor,
// memory, graphics card, network, disks, processes, study today, projects), SYSTEMS with today, what's due, the AI's
// corner and recent events round the cells, NOTES with its folders and latest edits, and a terminal below whose
// border also holds the other tabs (Alt+1… switches terminals, Alt+/ finds a note). Any pane can fill the board,
// the "panes" menu hides some, and the pages (features, settings…) open over the whole board (Alt+F, Alt+S…).
// "roomy" is the earlier layout with bigger type, used by itself on narrower screens. Study mode (Alt+M) keeps only
// the NOTES map and a STUDY pane: a focus timer, today's study, what's due and the subject's notes.
//
// Two designs (Settings → look.design, or the "classic look" / "new look" button): "new" (home-new.css: a sans-serif,
// Public Sans, with tabular figures; monospace only for terminals, code and paths) and "classic" (home.css alone: the
// monospace look of 0.5.18). <body data-design> holds it; setDesign() switches without a reload.
//
// The drawing of SYSTEMS and the NOTES map, and the helpers they share (palette, fonts, clamp, rgba...), are in
// views/common.js, views/systems.js and views/notesmap.js, loaded before this file: the phone app draws its Systems and
// Notes map views with the very same code (views/phone.html). Board and Notes below add the dashboard's own parts.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
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
// (the new design: the ink, and a warning colour only when it's high)
const grad = (v) => NEW ? ((v || 0) >= 0.9 ? PAL.bad : (v || 0) >= 0.7 ? PAL.peach : PAL.fg)
  : (v = clamp(v || 0, 0, 1)) < 0.5 ? mix(PAL.lav, PAL.peach, v * 2) : mix(PAL.peach, PAL.pink, (v - 0.5) * 2);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();

// ------------------------------------------------------------------------------------------------ layout
const WANT = () => (document.body.dataset.layout === "roomy" ? "roomy" : "dense");
const denseFits = () => WANT() === "dense" && window.innerWidth >= 1280 && window.innerHeight >= 600;

// ------------------------------------------------------------------------------------------------ panes (dense)
// Any pane can fill the board: click its name or double-click its border (⤢); Esc or its name again brings the others
// back (⤡). The "panes" menu in the board's top-right corner hides STATUS, SYSTEMS, NOTES or TERMINAL (one always
// stays) and the grid reflows to use the room; what's hidden is the setting look.panes, so it follows you to other
// browsers. The pages (activity … settings) open over the whole board, Alt and the underlined letter opens one, and
// Esc goes back. Roomy (narrow windows) shows every pane, with the pages in its tabs.
const PANES = { status: "#pane-status", systems: "#pane-systems", notes: "#pane-vault", terminal: "#pane-tabs" };
const PKEY = { today: "t", activity: "a", jobs: "j", schedule: "c", features: "f", phone: "p", research: "r", about: "y", settings: "s" };
let HIDE = new Set(), MAX = null, PAGE = null; // hidden panes, the pane filling the board, the page over the board
let STUDY = false; // Study mode: the NOTES map and the STUDY pane only (look.study_mode); HIDE and MAX wait untouched
let HIDDEN_F = new Set(); // features taken off the Features page (look.hidden_features; only ones that are off)
const inTerm = (el) => !!(el && el.closest && el.closest(".xterm")); // a terminal keeps its own keys
const cleanHide = (v) => { const s = new Set((Array.isArray(v) ? v : []).filter((p) => PANES[p])); return s.size >= Object.keys(PANES).length ? new Set() : s; };
const hideList = () => Object.keys(PANES).filter((p) => HIDE.has(p));
const shownPanes = () => (STUDY ? new Set(["notes"]) : new Set(Object.keys(PANES).filter((p) => (MAX ? p === MAX : !HIDE.has(p)))));
// on screen (not hidden, filled over or under a page); in Study mode only the notes map
const paneShown = (p) => (STUDY ? p === "notes" && !(DENSE && PAGE) : !DENSE || (!PAGE && shownPanes().has(p)));
// the grid for the panes that show: STATUS down the left; SYSTEMS and NOTES on top and TERMINAL below, on the right
// (new design: SYSTEMS, the control centre, gets the larger share of the top row and the top row more of the height)
function paneGrid(vis) {
  const st = vis.has("status"), top = ["systems", "notes"].filter((p) => vis.has(p)), rows = [];
  if (top.length) rows.push(top.length === 2 ? top : [top[0], top[0]]);
  if (vis.has("terminal")) rows.push(["tabs", "tabs"]);
  if (!rows.length) return { areas: '"status"', cols: "minmax(0, 1fr)", rows: "minmax(0, 1fr)" };
  const big = NEW && top.length === 2 && top[0] === "systems";
  return { areas: rows.map((r) => `"${st ? "status " : ""}${r.join(" ")}"`).join(" "),
    cols: `${st ? (NEW ? "minmax(440px, 31%) " : "minmax(440px, 34%) ") : ""}${big ? "minmax(0, 1.45fr) minmax(0, 1fr)" : "1fr 1fr"}`,
    rows: rows.length === 2 ? (NEW && top.includes("systems") ? "63% minmax(0, 1fr)" : "55% minmax(0, 1fr)") : "minmax(0, 1fr)" };
}
function applyPanes() {
  const grid = $(".grid"), vis = shownPanes();
  for (const [p, sel] of Object.entries(PANES)) {
    const el = $(sel);
    el.classList.toggle("gone", DENSE && !vis.has(p)); el.classList.toggle("maxed", DENSE && !STUDY && MAX === p); el.classList.remove("tr");
  }
  $("#pane-study").classList.remove("tr");
  $("#pane-page").classList.toggle("hidden", !(DENSE && PAGE)); grid.classList.toggle("paged", DENSE && !!PAGE);
  if (!DENSE) { grid.style.gridTemplateAreas = grid.style.gridTemplateColumns = grid.style.gridTemplateRows = ""; closeMenu(); return; }
  const g = STUDY ? { areas: '"notes study"', cols: "minmax(0, 1fr) minmax(400px, 31%)", rows: "minmax(0, 1fr)" } : paneGrid(vis);
  Object.assign(grid.style, { gridTemplateAreas: g.areas, gridTemplateColumns: g.cols, gridTemplateRows: g.rows });
  // the pane in the board's top-right corner leaves room in its border for the panes menu
  $(STUDY ? "#pane-study" : PANES[["notes", "systems", "terminal", "status"].find((p) => vis.has(p))]).classList.add("tr");
  grid.style.setProperty("--ctlw", `${$("#panes-ctl").offsetWidth}px`);
  renderMenu(); renderNav();
  requestAnimationFrame(refit);
}
function maxPane(p) { if (STUDY) return; MAX = MAX === p || !PANES[p] ? null : p; applyPanes(); }
function savePanes() {
  try { localStorage.setItem("kurooto.dash.panes", JSON.stringify(hideList())); } catch { /* fine */ }
  api("settings", { key: "look.panes", value: hideList() }).catch(() => {});
}
function setHidden(p, hide) {
  const next = new Set(HIDE); if (hide) next.add(p); else next.delete(p);
  if (next.size >= Object.keys(PANES).length) { renderMenu(); return; } // one pane always stays
  HIDE = next; MAX = null; savePanes(); applyPanes();
}
// the page's name with its key underlined ("s<u>c</u>hedule"), for the borders and the menu
const mnem = (k) => { const l = DLABEL[k], i = l.indexOf(PKEY[k]); return i < 0 ? esc(l) : `${esc(l.slice(0, i))}<u>${esc(l[i])}</u>${esc(l.slice(i + 1))}`; };
const pageTabs = () => Object.keys(DLABEL).map((k) => `<button class="tab${PAGE === k ? " on" : ""}" data-dt="${k}" title="Alt+${PKEY[k].toUpperCase()}">${mnem(k)}</button>`).join("");
function renderMenu() {
  const m = $("#panes-menu"); if (m.classList.contains("hidden")) return;
  const left = Object.keys(PANES).filter((p) => !HIDE.has(p)).length, NAMES = { status: "STATUS", systems: "SYSTEMS", notes: "NOTES", terminal: "TERMINAL" };
  m.innerHTML = `<div class="mh">panes</div>${Object.entries(NAMES).map(([p, l]) => `<label><input type="checkbox" data-pane="${p}"${HIDE.has(p) ? "" : " checked"}${!HIDE.has(p) && left === 1 ? ' disabled title="one pane always stays"' : ""}> ${l}${MAX === p ? ' <span class="d">fills the board</span>' : ""}</label>`).join("")}
    ${MAX || HIDE.size ? '<button data-all="1">show them all</button>' : ""}<p class="d">Click a pane's name or double-click its border and it fills the board; Esc brings the others back.</p>
    <div class="mh">study</div><button data-study-toggle><span>study mode</span><span class="d">alt+m</span></button>
    <div class="mh">look</div><button data-design-toggle><span>${NEW ? "classic look (monospace)" : "new look"}</span><span class="d">look.design</span></button>
    <div class="mh">pages</div>${Object.keys(DLABEL).map((k) => `<button data-pg="${k}"><span>${mnem(k)}</span><span class="d">alt+${PKEY[k]}</span></button>`).join("")}`;
}
function openMenu(open) {
  const m = $("#panes-menu"); m.classList.toggle("hidden", !open);
  $("#panes-btn").setAttribute("aria-expanded", String(open));
  if (open) renderMenu();
}
const closeMenu = () => openMenu(false);
$("#panes-btn").onclick = () => openMenu($("#panes-menu").classList.contains("hidden"));
$("#panes-menu").onchange = (e) => { if (e.target.dataset.pane) setHidden(e.target.dataset.pane, !e.target.checked); };
$("#panes-menu").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.all) { HIDE = new Set(); MAX = null; savePanes(); applyPanes(); }
  if (b.dataset.pg) openPage(b.dataset.pg);
};
document.addEventListener("click", (e) => { if (!e.target.closest("#panes-ctl")) closeMenu(); });
for (const p of ["status", "systems", "notes"]) $(`${PANES[p]} > h3 .t`).addEventListener("click", () => { if (DENSE) maxPane(p); });
// a double-click on (or right by) a pane's border: it fills the board, or comes back
document.addEventListener("dblclick", (e) => {
  if (!DENSE || inTerm(e.target) || e.target.closest("input, textarea, select, button, .page, .chat-log")) return;
  const near = (el) => {
    const r = el.getBoundingClientRect(), x = e.clientX, y = e.clientY;
    if (x < r.left - 9 || x > r.right + 9 || y < r.top - 11 || y > r.bottom + 9) return Infinity;
    return Math.min(Math.abs(x - r.left), Math.abs(x - r.right), Math.abs(y - r.top), Math.abs(y - r.bottom));
  };
  if (PAGE) { if (near($("#pane-page")) <= 8) closePage(); return; }
  let best = null, bd = 8.01;
  for (const p of shownPanes()) { const d = near($(PANES[p])); if (d < bd) { bd = d; best = p; } }
  if (best) { getSelection().removeAllRanges(); maxPane(best); }
});
// the pages, over the whole board (roomy: its tabs)
function openPage(name) {
  if (!DLABEL[name]) return;
  if (!DENSE) { showTab(name); return; }
  closeMenu();
  const host = $("#ov-body");
  if (PAGE !== name) { host.onclick = host.onchange = host.onsubmit = null; host.innerHTML = ""; host.scrollTop = 0; }
  PAGE = name;
  if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); // not the terminal below
  applyPanes(); renderPageNav(); renderPage(name, host);
}
function closePage() {
  if (!PAGE) return;
  PAGE = null; ACT_CELL = null;
  const host = $("#ov-body"); host.onclick = host.onchange = host.onsubmit = null; host.innerHTML = "";
  applyPanes();
  if (dtab === "kurooto" && paneShown("terminal") && $("#chat-input")) $("#chat-input").focus({ preventScroll: true });
}
function renderPageNav() {
  const nav = $("#page-nav"), find = PAGE === "features" || PAGE === "settings";
  nav.innerHTML = `<span class="t" title="back to the board (Esc)">${esc(NEW ? TABS[PAGE] || PAGE : (TABS[PAGE] || PAGE).toUpperCase())}<i class="mx"></i></span><span class="rule">─</span><span class="pages">${pageTabs()}</span><span class="rule">─</span>` +
    `<span class="meta">${find ? "/ or ctrl+f search · " : ""}alt+f features · alt+s settings</span><span class="rule">─</span><button class="tab" data-close="1">esc back</button>`;
  nav.onclick = (e) => {
    if (e.target.closest(".t, [data-close]")) { closePage(); return; }
    const b = e.target.closest("[data-dt]"); if (b) openPage(b.dataset.dt);
  };
}
// find a note (Alt+/ or /): the NOTES pane comes to the front first
function findNote() {
  if (DENSE) { if (PAGE) closePage(); if (!paneShown("notes")) { MAX = HIDE.has("notes") ? "notes" : null; applyPanes(); } }
  mind.openSearch();
}
// what's hidden comes from Settings (look.panes), so it's the same in every browser; this browser remembers it too,
// so the board doesn't flash every pane while the setting loads
function loadLook() {
  try { HIDE = cleanHide(JSON.parse(localStorage.getItem("kurooto.dash.panes") || "[]")); } catch { /* fine */ }
  api("settings").then((r) => {
    const look = ((r && r.sections) || []).find((s) => s.section === "look"); if (!look) return;
    HIDDEN_F = new Set(Array.isArray(look.values.hidden_features) ? look.values.hidden_features : []);
    const v = cleanHide(look.values.panes);
    if (Object.keys(PANES).filter((p) => v.has(p)).join() !== hideList().join()) { HIDE = v; MAX = null; applyPanes(); }
    try { localStorage.setItem("kurooto.dash.panes", JSON.stringify(hideList())); } catch { /* fine */ }
  }).catch(() => {});
}

// the corner panels and legends (views/common.js): L opens or folds them all, remembered in this browser
try { LEGENDS = localStorage.getItem("kurooto.dash.legends") === "1"; } catch { /* fine */ }
window.addEventListener("keydown", (e) => {
  if ((e.key === "l" || e.key === "L") && !e.altKey && !e.ctrlKey && !e.metaKey
    && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !document.activeElement.closest(".xterm")) {
    LEGENDS = !LEGENDS;
    try { localStorage.setItem("kurooto.dash.legends", LEGENDS ? "1" : "0"); } catch { /* fine */ }
  }
});

// ------------------------------------------------------------------------------------------------ SYSTEMS
// views/systems.js draws it (Body); Board adds the dashboard's own parts: a click on a cell opens its menu (ping, sync
// now, quiet, its settings, its activity) and on the core Ctrl+K; the cells as buttons for Tab and screen readers; and
// the dense board's four corners (recent events, the AI, today, what's due).
const BRAIN = { agy: "agy", claude: "claude", gemini: "gemini", ollama: "local AI" };
// agy, claude…; an extra Claude account by its name ("claude (work)"); any other brain is "your AI"
const brainName = (b) => (b && (BRAIN[b.id] || (/^claude:/.test(b.id || "") ? `claude (${((b.label || "").match(/\((.*)\)$/) || [0, b.id.slice(7)])[1]})` : ""))) || "AI";
class Board extends Body {
  constructor(cv) { super(cv, { meta: $("#sys-meta"), card: $("#body-card"), menu: $("#body-menu") }); }
  wire() {
    super.wire();
    // the cells as buttons, for Tab and screen readers (the canvas shows which one has the focus)
    const list = $("#body-cells");
    list.addEventListener("focusin", (e) => { const b = e.target.closest("[data-cell]"); this.focus = b ? b.dataset.cell : null; });
    list.addEventListener("focusout", () => { this.focus = null; });
    list.addEventListener("click", (e) => {
      const b = e.target.closest("[data-cell]"); if (!b) return;
      if (b.dataset.cell === "core") { cmdOpen(); return; }
      const o = this.o.get(b.dataset.cell); if (o) this.openMenu(o, true);
    });
    list.addEventListener("keydown", (e) => { // arrows walk round the ring
      if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
      const bs = [...list.querySelectorAll("[data-cell]")], i = bs.indexOf(document.activeElement); if (i < 0) return;
      e.preventDefault(); bs[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + bs.length) % bs.length].focus();
    });
    const menu = $("#body-menu");
    menu.addEventListener("click", (e) => { const b = e.target.closest("[data-bm]"); if (b) this.menuAct(b.dataset.bm, b); });
    menu.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const bs = [...menu.querySelectorAll("button")], i = bs.indexOf(document.activeElement);
      e.preventDefault(); bs[(i + (e.key === "ArrowDown" ? 1 : -1) + bs.length) % bs.length].focus();
    });
    window.addEventListener("keydown", (e) => { // Esc closes the menu before anything else hears it
      if (e.key !== "Escape" || !this.menu) return;
      e.preventDefault(); e.stopImmediatePropagation(); this.closeMenu(true);
    }, true);
    document.addEventListener("mousedown", (e) => { if (this.menu && !e.target.closest("#body-menu, #body")) this.closeMenu(); });
  }
  tap(hit) {
    if (hit === "core") { this.closeMenu(); cmdOpen(); }
    else if (hit) { if (this.menu === hit.id) this.closeMenu(); else this.openMenu(hit, false); }
    else this.closeMenu();
  }
  updated(on) {
    this.cellList(on);
    if (this.menu && !this.o.has(this.menu)) this.closeMenu();
  }
  // one button per cell, in ring order, under the canvas: Tab reaches them, a screen reader reads them
  cellList(on) {
    const list = $("#body-cells"), key = on.map((c) => c.id).join();
    if (key !== this.cellIds) {
      this.cellIds = key;
      const had = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.cell : null;
      list.innerHTML = `<button data-cell="core">${esc(this.state.name || "Kurooto")}: do something (Ctrl+K)</button>` +
        on.map((c) => `<button data-cell="${esc(c.id)}"></button>`).join("");
      if (had) { const b = list.querySelector(`[data-cell="${CSS.escape(had)}"]`); if (b) b.focus({ preventScroll: true }); }
    }
    for (const b of list.querySelectorAll("[data-cell]")) {
      const o = this.o.get(b.dataset.cell); if (!o) continue;
      const text = `${o.data.title}: ${this.vital(o)}. Enter for its actions.`;
      if (b.textContent !== text) b.textContent = text;
    }
  }
  event(e) {
    super.event(e);
    const o = this.o.get(e.cell);
    if (o && this.menu === o.id) this.menuLog();
  }
  // the four corners: recent events, the AI's corner, today, what's due
  panels(ctx, w, h, lh) {
    const st = this.state || {}, nowS = Date.now() / 1000;
    const dim = rgba(PAL.fg, 0.42), mid = rgba(PAL.fg, 0.64);
    const cut = Math.max(16, Math.floor((w * 0.5 - 24) / 5.4));
    // a row is [text, colour] or [[title, tail], colour]: the title gives way so the tail (a time, a status) survives
    const fitRow = (s) => (Array.isArray(s) ? (s[0].length + s[1].length > cut ? s[0].slice(0, Math.max(4, cut - s[1].length - 1)) + "…" : s[0]) + s[1] : s.slice(0, cut));
    const rects = (this.panelRects = []); // where the corners' words are: the cells' labels keep clear of them
    this.openRects = this.openRects || {};
    const block = (rows, x, align, fromTop) => {
      const key = `${align}${fromTop ? "t" : "b"}`, open = LEGENDS || inside(this.mouse, this.openRects[key]);
      if (!open && rows.length > 1) {
        const more = rows.length - 1, head = [rows[0][0] + `  ▸ ${more}`, rows[0][1]];
        rows = [head];
      }
      const r = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
      rows.slice(0, 6).forEach(([s, col], i, arr) => {
        const y = fromTop ? 24 + i * lh : h - 20 - (arr.length - 1 - i) * lh, wd = say(ctx, fitRow(s), x, y, col, align), x0 = align === "right" ? x - wd : x;
        Object.assign(r, { x0: Math.min(r.x0, x0 - 2), x1: Math.max(r.x1, x0 + wd + 2), y0: Math.min(r.y0, y - 9), y1: Math.max(r.y1, y + 3) });
      });
      rects.push(r);
      this.openRects[key] = r; // where the pointer keeps it open (the open panel's own area, once it's open)
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
  // a cell's menu: ping (a pulse there and back), sync now and quiet where the feature has them, its settings, its
  // activity. Opened from the keyboard it shows at once with the focus on its first action; from a click it fades in.
  openMenu(o, byKey) {
    const el = $("#body-menu"), more = this.detail(o);
    this.menu = o.id; this.menuKey = byKey;
    el.innerHTML = `<div class="h">${esc(o.data.title)}</div><div class="d">${esc(this.vital(o))}${more ? " · " + esc(more) : ""}</div>` +
      `<div class="bm-acts" role="menu" aria-label="${esc(o.data.title)}">` +
      '<button role="menuitem" data-bm="ping">ping<span>a pulse there and back</span></button>' +
      '<button role="menuitem" data-bm="settings">settings<span>its card on Features</span></button>' +
      '<button role="menuitem" data-bm="log">activity<span>everything it did</span></button></div>' +
      '<ul class="bm-log" aria-label="lately"></ul><p class="bm-said" aria-live="polite"></p>';
    el.classList.toggle("instant", !!byKey); el.classList.remove("hidden");
    this.menuLog();
    this.place(el, o, this.menuW, this.menuH);
    if (byKey) el.querySelector("button").focus({ preventScroll: true });
    api(`cell?id=${encodeURIComponent(o.id)}`).then((r) => {
      if (this.menu !== o.id || !r || r.error) return;
      const add = [];
      if (r.sync) add.push('<button role="menuitem" data-bm="sync">sync now<span>this one alone</span></button>');
      if (r.quiet) add.push('<button role="menuitem" data-bm="quiet">quiet<span>works on, stops messaging you</span></button>');
      if (add.length) { el.querySelector('[data-bm="ping"]').insertAdjacentHTML("afterend", add.join("")); this.measureMenu(); }
    }).catch(() => {});
  }
  measureMenu() { const el = $("#body-menu"); this.menuW = el.offsetWidth; this.menuH = el.offsetHeight; }
  // the cell's last few events, in its menu
  menuLog() {
    const ul = $("#body-menu .bm-log"); if (!ul) return;
    const rows = feed.filter((e) => e.cell === this.menu).slice(0, 3);
    ul.innerHTML = rows.length ? rows.map((e) => `<li><span>${esc((e.ts || "").slice(11, 16))}</span> ${esc(String(e.kind).replace(/_/g, " "))}</li>`).join("") : '<li class="d">nothing in the last while</li>';
    this.measureMenu();
  }
  closeMenu(refocus = false) {
    if (!this.menu) return;
    const id = this.menu, el = $("#body-menu"), back = refocus || this.menuKey;
    this.menu = null; el.classList.add("hidden"); el.innerHTML = "";
    if (back) { const b = $(`#body-cells [data-cell="${CSS.escape(id)}"]`); if (b) b.focus({ preventScroll: true }); }
  }
  async menuAct(act, b) {
    const o = this.o.get(this.menu); if (!o) return;
    const said = (text, bad) => { const p = $("#body-menu .bm-said"); if (p) { p.textContent = text; p.classList.toggle("bad", !!bad); this.measureMenu(); } };
    if (act === "ping") { const col = PAL[o.color]; this.pulse("core", o.id, col).back = true; this.extraBeat(1, col); this.closeMenu(); return; }
    if (act === "settings") { // the Features page, searched for it, with its card scrolled into view once it's drawn
      FIND.features = o.data.title.split(" (")[0]; this.closeMenu(); openPage("features");
      let tries = 0; const find = () => { const c = (DENSE ? $("#ov-body") : $("#tab-body")).querySelector(`.card2[data-id="${CSS.escape(o.id)}"]`);
        if (c) c.scrollIntoView({ block: "center" }); else if (tries++ < 30) setTimeout(find, 100); };
      find(); return;
    }
    if (act === "log") { ACT_CELL = o.id; this.closeMenu(); openPage("activity"); return; }
    b.disabled = true;
    let r;
    try { r = act === "undo" ? await api("calm/undo", { id: b.dataset.uid }) : await api(`cell/${act}`, { id: o.id }); }
    catch { r = { ok: false, message: "Kurooto didn't answer." }; }
    said(r.message || (r.ok ? "Done." : "That didn't work."), !r.ok);
    if (act === "quiet" && r.ok && r.undo) b.outerHTML = `<button role="menuitem" data-bm="undo" data-uid="${esc(r.undo)}">undo<span>messages again</span></button>`;
    else if (act === "sync") b.disabled = false;
    else b.remove();
    this.measureMenu();
  }
}
// an event's details in a few words (never message text: the events hold names, counts and times)
const detailOf = (e) => Object.entries(e).filter(([k]) => !["ts", "kind", "t", "cell"].includes(k))
  .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 60);


// ------------------------------------------------------------------------------------------------ NOTES
// views/notesmap.js draws it (Mind); Notes adds the dashboard's own parts: point at a note for its card (click: its
// first lines, double-click: open it), drag a note or the map, scroll to zoom, / to find a note, R for recent ones.
class Notes extends Mind {
  meta() {
    $("#mind-meta").textContent = `${this.nodes.size} notes · ${this.links.length} links · ${new Set([...this.nodes.values()].map((n) => n.neighborhood)).size} neighborhoods`;
  }
  async showCard(n, pinned) {
    const card = $("#mind-card"); if (!n) { card.classList.add("hidden"); return; }
    card.innerHTML = `<div class="h">${esc(n.title)}</div><div class="d">${esc(n.id)}</div><div>${n.deg - (n.via || 0)} links${n.via ? ` (+${n.via} from reading)` : ""} · ${n.words} words · edited ${ago(Date.now() / 1000 - (n.mtime || 0))} ago</div>` + (pinned ? '<pre>…</pre><div class="d">double-click: open it</div>' : "");
    card.classList.remove("hidden");
    if (pinned) { try { const r = await api(`note?id=${encodeURIComponent(n.id)}`); if (this.selected === n) card.querySelector("pre").textContent = (r.text || "").trim().split("\n").slice(0, 14).join("\n"); } catch { /* leave it */ } }
  }
  // the arrow keys (the map focused: Tab to it): from the chosen note to the linked note that way, else the nearest
  // note that way; with none chosen, the note nearest the middle
  stepTo([dx, dy]) {
    const from = this.selected || this.hover, all = [...this.nodes.values()];
    if (!from) {
      const c = this.toWorld(this.w / 2, this.h / 2, this.w, this.h), d = (n) => Math.hypot(n.x - c.x, n.y - c.y);
      return all.reduce((b, n) => (!b || d(n) < d(b) ? n : b), null);
    }
    const best = (pool) => { let pick = null, bs = Infinity;
      for (const n of pool) { if (n === from) continue; const vx = n.x - from.x, vy = n.y - from.y, d = Math.hypot(vx, vy) || 1, cos = (vx * dx + vy * dy) / d;
        if (cos < 0.5) continue; const sc = d / (cos * cos); if (sc < bs) { bs = sc; pick = n; } }
      return pick; };
    return best([...from.nb].map((id) => this.nodes.get(id)).filter(Boolean)) || best(all);
  }
  // a note chosen with the keys that's near the edge (or off it): the map glides to it
  keepInView(n) {
    const S = this.toScreen(n, this.w, this.h), m = 60;
    if (S.x > m && S.y > m && S.x < this.w - m && S.y < this.h - m) return;
    this.autofit = false; this.glide = { x: -n.x, y: -n.y };
    if (STILL.matches) this.glideStep(1);
  }
  openSearch() { const s = $("#mind-search"); s.classList.remove("hidden"); s.value = this.query; s.focus(); }
  // a note to the middle of the map, with its card and first lines
  goTo(n) { if (!n) return; this.selected = n; this.autofit = false; this.view.x = -n.x; this.view.y = -n.y; this.view.k = Math.max(this.view.k, 1.6); this.showCard(n, true); }
  wire() {
    const cv = this.cv; let down = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); this.autofit = false; this.glide = null; const r = cv.getBoundingClientRect(), before = this.toWorld(e.clientX - r.left, e.clientY - r.top, this.w, this.h);
      this.view.k = clamp(this.view.k * Math.exp(-e.deltaY * 0.0015), 0.08, 6); const after = this.toWorld(e.clientX - r.left, e.clientY - r.top, this.w, this.h);
      this.view.x += after.x - before.x; this.view.y += after.y - before.y; }, { passive: false });
    cv.addEventListener("mousedown", (e) => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      if (this.showRecent && x < 240 && y < 40) { this.toggleRecent(); return; }
      const n = this.pick(x, y); this.glide = null;
      down = { x, y, n, vx: this.view.x, vy: this.view.y, moved: false }; if (n) this.dragging = n; });
    // the pointer leaving the map lets go of the note it pointed at (the chosen one stays lit)
    cv.addEventListener("mouseleave", (e) => { if (down || !this.hover || e.relatedTarget?.closest?.("#mind-card")) return;
      this.hover = null; this.showCard(this.selected, !!this.selected); });
    cv.addEventListener("keydown", (e) => {
      const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (dir && !e.altKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); this.hover = null;
        const n = this.stepTo(dir); if (n) { this.selected = n; this.showCard(n, true); this.keepInView(n); } return; }
      if (e.key === "Enter" && this.selected) { e.preventDefault(); api("open-note", { id: this.selected.id }); return; }
      if (e.key === "Escape" && this.selected) { e.preventDefault(); this.selected = null; this.showCard(null); }
    });
    window.addEventListener("mousemove", (e) => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      this.mouse = x < 0 || y < 0 || x > r.width || y > r.height ? null : { x, y };
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
        this.goTo(hit);
      }
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "/" && !e.altKey && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName) && !document.activeElement.closest(".xterm")) { e.preventDefault(); findNote(); }
      // R: only while the notes map is on screen (not hidden, nor under a page), and never while typing in a field
      const el = document.activeElement;
      if ((e.key === "r" || e.key === "R") && !e.altKey && !e.ctrlKey && !e.metaKey && paneShown("notes") && this.cv.getClientRects().length
        && !["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) && !el.isContentEditable && !el.closest(".xterm")) {
        this.toggleRecent();
      }
    });
  }
}

// -------------------------------------------------------------------------------------- STATUS and tabs
let last = null;
function renderStatus(m) {
  if (DENSE) { barStatus(m); if (paneShown("status")) renderBoard(m); return; }
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
  barStatus(m);
}
// the top bar: a line on what's on and running, the update and health badges, the version
function barStatus(m) {
  const running = m.jobs.filter((j) => j.status === "running").length;
  $("#meta").textContent = `${m.cells.filter((c) => c.on).length} features on · ${running} AI request${NEW && running !== 1 ? "s" : ""} running · cpu ${pct(m.sys.cpu)}`;
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
// steps skipped on the setup page (core/setupsteps.py): the setup link in the corner says how many, the Features tab
// lists them, each a link back to its step
let SETUP_LEFT = [];
function setupLeft(s) {
  SETUP_LEFT = (s && s.left) || [];
  const a = $("#setup-link");
  if (a) { a.href = SETUP_LEFT.length ? SETUP_LEFT[0].link : "/setup"; a.textContent = setupWord(); a.title = setupTitle(); }
}
const setupWord = () => (SETUP_LEFT.length ? `finish setup (${SETUP_LEFT.length})` : "setup");
const setupTitle = () => (SETUP_LEFT.length ? `Skipped for now: ${SETUP_LEFT.map((x) => x.title).join(", ")}` : "the setup page");
function setupBlock() {
  if (!SETUP_LEFT.length) return "";
  return `<div class="card2 later"><b>Finish setting up</b>${SETUP_LEFT.map((x) => `<p><a href="${esc(x.link)}">${esc(x.title)}</a>: ${esc(x.what)}</p>`).join("")}</div>`;
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
  if (NEW) { areaGraph(cv, vals, { max, mirror, lines }); return; }
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
// the new design's graphs: one line in the data colour over a faint fill, newest on the right (network: down above
// the middle in lav, up below it in pink, the colours of its arrows)
function areaGraph(cv, vals, { max = 1, mirror = null, lines = null } = {}) {
  const { ctx, w, h } = fitCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const step = 3, cols = Math.max(4, Math.floor(w / step));
  const draw = (series, top, height, down, peak, col) => {
    const v = series.slice(-cols); if (!v.length) return;
    const x0 = w - (v.length - 1) * step, base = down ? top : top + height;
    const y = (x) => { const k = clamp((x || 0) / (peak || 1), 0, 1) * (height - 1.5); return down ? top + 0.75 + k : top + height - 0.75 - k; };
    ctx.beginPath(); ctx.moveTo(x0, base); v.forEach((x, i) => ctx.lineTo(x0 + i * step, y(x))); ctx.lineTo(w, base); ctx.closePath();
    ctx.fillStyle = rgba(col, 0.13); ctx.fill();
    ctx.beginPath(); v.forEach((x, i) => (i ? ctx.lineTo(x0 + i * step, y(x)) : ctx.moveTo(x0, y(x))));
    ctx.strokeStyle = col; ctx.lineWidth = 1.25; ctx.lineJoin = "round"; ctx.stroke();
  };
  ctx.fillStyle = rgba(PAL.fg, 0.07);
  if (mirror) {
    const half = h / 2;
    draw(vals, 0, half, false, max, PAL.lav); draw(mirror, half, half, true, lines || max, PAL.pink);
    ctx.fillStyle = rgba(PAL.fg, 0.1); ctx.fillRect(0, Math.round(half), w, 1);
  } else { ctx.fillRect(0, h - 1, w, 1); draw(vals, 0, h, false, max, PAL.accent); }
}
const meter = (v, cls = "") => `<span class="m grow ${cls}${(v || 0) >= 0.9 ? " hi" : ""}"><i style="clip-path:inset(0 ${(100 - clamp((v || 0) * 100, 0, 100)).toFixed(1)}% 0 0)"></i></span>`;
const pct = (v) => `${Math.round((v || 0) * 100)}%`;
const temp = (c) => (c == null ? "" : `<span class="${c >= 90 ? "hot" : c >= 80 ? "warm" : "v"}">${Math.round(c)}°</span>`);
function buildBoard() {
  const st = $("#status");
  const L = (classic, fresh) => (NEW ? fresh : classic); // a box's name in each design
  st.className = "board";
  st.innerHTML = `
  <div class="hd"><span><b id="sb-name">KUROOTO</b> <span class="k" id="sb-ver"></span> <span id="sb-mode" class="warm"></span><span id="sb-badge" class="warm"></span> <span id="sb-health" class="hot"></span></span><span class="clock" id="sb-clock"></span></div>
  <div class="hd"><span id="sb-up"></span><span id="sb-act"></span></div>
  <div class="box" id="bx-cpu"><div class="lab"><span class="t">${L("CPU", "CPU")}</span><span class="meta" id="cpu-meta"></span></div>
    <div class="graph"><canvas class="cv" id="g-cpu"></canvas><span class="pct" id="cpu-pct"></span></div>
    <div class="cpus" id="cpu-cores"></div><div class="row" id="cpu-info"></div></div>
  <div class="duo" id="duo-mem">
    <div class="box" id="bx-mem"><div class="lab"><span class="t">${L("MEM", "Memory")}</span><span class="meta" id="mem-meta"></span></div><div id="mem-body"></div></div>
    <div class="box" id="bx-gpu"><div class="lab"><span class="t">${L("GPU", "Graphics")}</span><span class="meta" id="gpu-meta"></span></div><div id="gpu-body"></div><div class="graph"><canvas class="cv" id="g-gpu"></canvas></div></div>
  </div>
  <div class="duo">
    <div class="box" id="bx-net"><div class="lab"><span class="t">${L("NET", "Network")}</span><span class="meta" id="net-meta"></span></div>
      <div class="graph"><canvas class="cv" id="g-net"></canvas><span class="tag top" id="net-rx"></span><span class="tag top right k" id="net-peak"></span><span class="tag bot" id="net-tx"></span></div><div class="row" id="net-tot"></div></div>
    <div class="box" id="bx-disk"><div class="lab"><span class="t">${L("DISKS", "Disks")}</span><span class="meta" id="disk-meta"></span></div><div id="disk-body"></div></div>
  </div>
  <div class="box procs" id="bx-proc"><div class="lab"><span class="t">${L("PROCESSES", "Processes")}</span><span class="meta" id="proc-meta"></span></div><div id="proc-body"></div></div>
  <div class="box study" id="bx-study"><div class="lab"><span class="t">${L("STUDY TODAY", "Study today")}</span><span class="meta" id="study-meta"></span></div><div id="study-body"></div></div>
  <div class="box proj" id="bx-proj"><div class="lab"><span class="t">${L("PROJECTS", "Projects")}</span><span class="meta" id="proj-meta"></span></div><div id="proj-body"></div></div>`;
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
  const day = d.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" }).replace(",", "");
  c.innerHTML = `${NEW ? day : day.toUpperCase()} <b>${d.toTimeString().slice(0, 8)}</b>`;
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
  $("#sb-act").innerHTML = `${m.power && m.power.mode === "paused" ? '<button data-pw="resume">resume</button>' : '<button data-pw="pause">pause 1h</button>'} · <button data-pw="off">off</button> · <a href="${esc(SETUP_LEFT.length ? SETUP_LEFT[0].link : "/setup")}" title="${esc(setupTitle())}">${esc(setupWord())}</a>`;
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
    row.querySelector(".m").classList.toggle("hi", v >= 0.9);
    row.querySelector(".r").textContent = pct(v);
    if (cols <= 2 && H.cores && H.cores[i]) dotGraph(row.querySelector("canvas"), H.cores[i]);
  });
  const t = s.temps || {}, info = [];
  if (s.freq) info.push(`<span class="v">${(s.freq.cur / 1000).toFixed(1)}</span><span class="k">GHz</span>`);
  if (s.load) info.push(`<span class="k">load</span> <span class="v">${s.load.map((x) => x.toFixed(2)).join(" ")}</span>`);
  if (t.cpu != null) info.push(`<span class="k">cpu</span> ${temp(t.cpu)}`);
  if (t.disk != null) info.push(`<span class="k">disk</span> ${temp(t.disk)}`);
  if (s.fans && s.fans.length) info.push(`<span class="k">fans</span> <span class="v">${s.fans.join("/")}</span><span class="k"> rpm</span>`);
  $("#cpu-info").innerHTML = info.map((x) => `<span class="item">${x}</span>`).join(" "); // each reading stays in one piece when the row wraps
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
  $("#proc-meta").innerHTML = `<button data-sort="cpu" class="${SB.sort === "cpu" ? "on" : ""}">cpu</button><button data-sort="mem" class="${SB.sort === "mem" ? "on" : ""}">mem</button> · <span class="mine" style="color:var(--pink)">${NEW ? "" : "✦"}</span> kurooto`;
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
  body.innerHTML = `<table>${head}${procs.slice(0, fit).map((r) => `<tr><td class="id">${r.pid}</td><td class="n">${r.own ? `<span class="mine">${NEW ? "" : "✦ "}${esc(r.own === "kurooto" ? "kurooto" : r.name)}</span>` : `<span class="v">${esc(r.name)}</span>`}</td><td class="k">${r.threads ?? ""}</td><td style="color:${grad(Math.min(1, r.cpu))}">${(r.cpu * 100).toFixed(1)}%</td><td class="v">${bytes(r.mem)}</td></tr>`).join("")}</table>`;
}

const feed = [];
const SEEN = new WeakMap(); // when each live event arrived (fresh ones are bright in SYSTEMS)
const TABS = { today: "Today", activity: "Activity", jobs: "AI jobs", schedule: "Schedule", features: "Features", phone: "Phone", research: "Research", about: "About you", settings: "Settings" };
const DLABEL = { today: "today", activity: "activity", jobs: "jobs", schedule: "schedule", features: "features", phone: "phone", research: "research", about: "you", settings: "settings" };
let tab = "activity"; // roomy: the tab below the panes
let dtab = "kurooto"; // dense: the terminal pane shows "kurooto" (the chat) or a terminal; the pages open over the board
const current = () => (DENSE ? PAGE || dtab : tab);
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
  let html = '<span class="t" title="fill the board with it (or double-click its border); Esc or a click again: back">TERMINAL<i class="mx"></i></span><span class="rule">─</span>';
  terms.forEach((t, i) => { html += `<button class="tab${dtab === t.name ? " on" : ""}" data-dt="${esc(t.name)}" title="Alt+${i + 1}"><span class="k">${i + 1}</span>${esc(t.label)}<span class="dot${t.live ? " live" : ""}"></span></button><span class="rule">─</span>`; });
  if (!TERM.on) html += `<button class="tab off${dtab === "termsoff" ? " on" : ""}" data-dt="termsoff" title="a shell, your AI's program and the log, right here">+ terminals</button><span class="rule">─</span>`;
  if (isTerm) html += '<button class="tab" data-restart="1" title="end the program in this terminal and start it again">restart</button><span class="rule">─</span>';
  html += `<span class="rule">┤</span><span class="pages">${pageTabs()}</span><span class="rule">├</span>`;
  html += `<span class="meta">? what's this · ctrl+k do · alt+1..${terms.length} tabs · alt+f features · alt+s settings · alt+/ find note · alt+m study · l legends</span>`;
  nav.innerHTML = html;
  nav.onclick = (e) => {
    if (e.target.closest(".t")) { maxPane("terminal"); return; }
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.dt) showDense(b.dataset.dt);
    if (b.dataset.restart && TERM.shown) api(`term/${TERM.shown}/restart`, {}).then(() => termAttach(TERM.shown));
  };
}
// Activity: everything Kurooto did, newest first; or one SYSTEMS cell's (its menu's "activity"), until "show everything"
let ACT_CELL = null;
function activity(body) {
  const rows = ACT_CELL ? feed.filter((e) => e.cell === ACT_CELL) : feed;
  const only = ACT_CELL ? `<p class="d act-only">only ${esc(SHORT[ACT_CELL] || ACT_CELL)} · <button data-act-all="1">show everything</button></p>` : "";
  body.innerHTML = only + (rows.length ? `<table>${rows.slice(0, 80).map((e) => `<tr><td>${esc((e.ts || "").slice(11, 19))}</td><td>${esc(e.kind.replace(/_/g, " "))}</td><td class="d">${esc(Object.entries(e).filter(([k]) => !["ts", "kind", "t", "cell"].includes(k)).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 160))}</td></tr>`).join("")}</table>` : ACT_CELL ? "Nothing from it yet." : "Nothing yet. Things Kurooto does appear here as they happen.");
  body.onclick = (e) => { if (e.target.closest("[data-act-all]")) { ACT_CELL = null; activity(body); } };
}
function renderTab() {
  if (DENSE) { if (PAGE) renderPage(PAGE, $("#ov-body")); return; }
  renderPage(tab, $("#tab-body"));
}
function renderPage(name, body) {
  if (!body) return;
  if (name === "activity") activity(body);
  else if (name === "jobs" && last) {
    // running and waiting requests get a Cancel button (a running agent program stops with what it started)
    body.innerHTML = last.jobs.length ? `<table><tr><th>when</th><th>request</th><th>effort</th><th>took</th><th>result</th><th></th></tr>${last.jobs.map((j) => `<tr><td>${ago(Date.now() / 1000 - j.created)} ago</td><td>${esc(j.title)}</td><td>${esc(j.effort || "")}</td><td>${j.seconds ? Math.round(j.seconds) + "s" : ""}</td><td class="${j.status === "ok" ? "ok2" : j.status === "failed" ? "bad2" : ""}" title="${esc(j.receipt || "")}">${esc(j.status)}${j.brain ? " · " + esc(j.brain) : ""}${j.model ? " " + esc(j.model) : ""}${j.verdict && j.verdict !== "ok" ? " · " + esc(j.verdict) : ""}</td><td>${j.status === "running" || j.status === "queued" ? `<button data-cancel="${esc(j.id)}">Cancel</button>` : ""}</td></tr>`).join("")}</table>` : "No AI requests yet.";
    body.onclick = async (e) => {
      const b = e.target.closest("[data-cancel]"); if (!b) return;
      b.disabled = true;
      const r = await api("jobs/cancel", { id: b.dataset.cancel });
      b.textContent = r.ok ? "cancelled" : "finished";
    };
  }
  else if (name === "schedule" && last) body.innerHTML = last.schedule.length ? `<table><tr><th>when</th><th>what</th></tr>${last.schedule.map((s) => `<tr><td>${new Date(s.when * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}</td><td>${esc(s.what)}</td></tr>`).join("")}</table>` : "Nothing scheduled.";
  else if (name === "today") renderToday(body);
  else if (name === "features") renderFeatures(body);
  else if (name === "phone") renderPhone(body);
  else if (name === "research") renderResearch(body);
  else if (name === "about") renderAboutTab(body);
  else if (name === "settings") renderSettings(body);
  else if (name === "terminals") renderTerminals(body);
}
// Today (Alt+T): the day, and the everyday things done right here (core/actions.py: the same as the commands).
// One box takes anything: plain words go to Kurooto as if typed on Telegram; "j …" is a journal line, ". …" a note
// in the inbox, "! …" a reminder ("! 18:30 call mum").
let TODAY = null;
const REM_WHEN = /^(in \d+\s*\w+|tomorrow(?: \d{1,2}(?::\d\d)?\s*(?:am|pm)?)?|\d{1,2}(?::\d\d)?\s*(?:am|pm)?|\w{3,9}day \d{1,2}(?::\d\d)?)\s+(.+)$/i;
const DUE_WHEN = /^(.*?)\s+((?:mon|tue|wed|thu|fri|sat|sun)\w*\s+\d{1,2}(?::\d\d)?|tomorrow(?:\s+\d{1,2}(?::\d\d)?)?|\d{4}-\d\d-\d\d(?:\s+\d\d:\d\d)?|in \d+\s*\w+)$/i;
// the box's shorthand to an action: {action, args} or {error}
function quick(v) {
  if (/^j\s+/i.test(v)) return { action: "journal.add", args: { text: v.replace(/^j\s+/i, "") } };
  if (/^\.\s*/.test(v)) return { action: "note.capture", args: { text: v.replace(/^\.\s*/, "") } };
  if (/^!\s*/.test(v)) {
    const m = v.replace(/^!\s*/, "").match(REM_WHEN);
    return m ? { action: "reminder.add", args: { when: m[1], what: m[2] } } : { error: "Write the time first: ! 18:30 call mum, ! in 20m tea, ! tomorrow 9am gym" };
  }
  return { action: "ask", args: { text: v } };
}
async function renderToday(body) {
  if (!body.querySelector("#td-box")) {
    body.innerHTML = `<div class="today">
      <div class="td-cap"><input id="td-box" placeholder="type anything · j journal line · . note · ! 18:30 reminder" spellcheck="true" autocomplete="off"><button id="td-go">↵</button></div>
      <p class="td-said" id="td-said" aria-live="polite"></p>
      <div id="td-body">loading…</div></div>`;
    const box = body.querySelector("#td-box");
    const go = async () => {
      const v = box.value.trim(); if (!v) return;
      const q = quick(v);
      if (q.error) { tdSay(q.error, true); return; }
      box.value = "";
      await tdAct(q.action, q.args);
    };
    box.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    body.querySelector("#td-go").onclick = go;
    body.onclick = async (e) => {
      const pg = e.target.closest("[data-page]"); if (pg) { e.preventDefault(); openPage(pg.dataset.page); return; }
      const b = e.target.closest("button[data-act]"); if (!b) return;
      let args = JSON.parse(b.dataset.args || "{}");
      if (b.dataset.ask) { const v = prompt(b.dataset.ask, b.dataset.def || ""); if (v === null || !v.trim()) return; args = { ...args, [b.dataset.field]: v.trim() }; }
      b.disabled = true;
      await tdAct(b.dataset.act, args);
    };
    body.onsubmit = async (e) => {
      e.preventDefault();
      const f = e.target, ta = f.querySelector("textarea, input[name]");
      if (!f.dataset.act || !ta || !ta.value.trim()) return;
      await tdAct(f.dataset.act, { [ta.name]: ta.value.trim() });
      ta.value = "";
    };
    setTimeout(() => box.focus({ preventScroll: true }), 30);
  }
  try { TODAY = await api("today"); } catch { body.querySelector("#td-body").textContent = "Kurooto didn't answer (is it running?)."; return; }
  tdDraw(body.querySelector("#td-body"));
}
function tdSay(text, bad) { const el = $("#td-said"); if (el) { el.textContent = text; el.className = "td-said" + (bad ? " bad" : ""); } }
// one action; its sentence (and an AI request's answer when it comes) goes to say, and an open Today page redraws
async function tdAct(action, args, say = tdSay) {
  let r; try { r = await api("act", { action, args }); } catch { say("Kurooto didn't answer (is it running?).", true); return; }
  say(r.message || (r.ok ? "Done." : "That didn't work."), !r.ok);
  if (r.job) tdWait(r.job, say);
  const host = [$("#ov-body"), $("#tab-body")].find((b) => b && b.querySelector("#td-body"));
  if (host) try { TODAY = await api("today"); tdDraw(host.querySelector("#td-body")); } catch { /* the next refresh */ }
}
async function tdWait(job, say = tdSay) {
  for (let i = 0; i < 450; i++) {
    await sleep(i < 10 ? 1000 : 3000);
    let j; try { j = await api(`job?id=${encodeURIComponent(job)}`); } catch { continue; }
    if (j.ok === false) return;
    if (j.status === "ok" || j.status === "failed") {
      const who = j.receipt ? "" : [j.label || j.brain, j.effort, j.seconds ? `${Math.round(j.seconds)} s` : ""].filter(Boolean).join(" · ");
      say(`${who ? who + "\n" : ""}${String(j.answer || "").trim() || "(no answer)"}`, j.status !== "ok");
      return;
    }
    say(`working${j.brain ? " · " + j.brain : ""} · ${Math.round((Date.now() / 1000) - (j.created || Date.now() / 1000))} s`);
  }
}
function tdDraw(el) {
  if (!el || !TODAY) return;
  const t = TODAY, on = new Set(t.features || []), btn = (label, action, args, ask) =>
    `<button class="mini" data-act="${action}" data-args="${esc(JSON.stringify(args || {}))}"${ask ? ` data-ask="${esc(ask[0])}" data-field="${ask[1]}" data-def="${esc(ask[2] || "")}"` : ""}>${esc(label)}</button>`;
  const off = (what, id) => `<p class="d">${what} is off. <a href="#" data-page="features">Turn it on in Features</a>.</p>`;
  const sec = [];
  sec.push(`<h2>${esc(t.day || "")}</h2>`);
  // alarm
  if (on.has("alarm") && t.alarm_state) {
    const a = t.alarm_state;
    sec.push(`<section class="td-sec"><h4>Alarm</h4><p>${esc(a.status)}</p>
      <form data-act="alarm.set"><input name="when" placeholder="7:30, tomorrow 6:45" autocomplete="off"><button>set</button></form>
      <p>${btn("skip tomorrow", "alarm.skip", { day: "tomorrow" })} ${a.next ? btn("turn this one off", "alarm.clear") : ""} ${btn(a.daily ? "change daily" : "daily alarm…", "alarm.daily", {}, ["Daily alarm time (or off):", "time", a.daily || "07:00"])}</p></section>`);
  } else sec.push(`<section class="td-sec"><h4>Alarm</h4>${off("The alarm (it needs Phone calls)")}</section>`);
  // classes
  if ((t.classes || []).length) sec.push(`<section class="td-sec"><h4>Classes</h4>${t.classes.map((c) => `<p>${esc(c.time)} ${esc(c.name)}${c.skipping ? ' <span class="d">(skipping)</span>' : ""}</p>`).join("")}</section>`);
  // deadlines
  if (on.has("deadlines")) {
    const ds = t.deadlines || [];
    sec.push(`<section class="td-sec"><h4>Due</h4>${ds.length ? ds.map((d) => `<p class="${d.hours < 0 ? "bad" : d.hours < 24 ? "warn" : ""}">${esc(d.due.replace("T", " "))} ${esc(d.title)}${d.subject ? ` <span class="d">${esc(d.subject)}</span>` : ""}
      ${btn("done", "deadline.done", { id: d.id })} ${btn("new date", "deadline.move", { id: d.id }, ["New date:", "when", "tomorrow 23:59"])}</p>`).join("") : "<p class=\"d\">Nothing due in the next three weeks.</p>"}
      <form class="td-add"><input name="title" placeholder="add: essay draft fri 17:00"><button>add</button></form></section>`);
  }
  // reminders
  if (on.has("reminders")) {
    const rs = t.reminders || [];
    sec.push(`<section class="td-sec"><h4>Reminders</h4>${rs.length ? rs.map((r) => `<p>${esc(r.when)} ${esc(r.what)} ${btn("+10 min", "reminder.snooze", { key: r.key, minutes: 10 })} ${btn("cancel", "reminder.cancel", { key: r.key })}</p>`).join("") : '<p class="d">None set. In the box above: ! 18:30 call mum</p>'}</section>`);
  }
  // check-ins
  if (on.has("checkins") && (t.checkin_names || []).length) {
    sec.push(`<section class="td-sec"><h4>Check-ins</h4>${t.checkin_names.map((c) => `<p>${esc(c.time)} ${esc(c.name)} <span class="d">${esc(c.status || "")}</span>${["planned", "waiting", ""].includes(c.status || "") ? ` ${btn("+30 min", "checkin.postpone", { name: c.name, minutes: 30 })} ${btn("skip", "checkin.skip", { name: c.name })}` : ""}</p>`).join("")}</section>`);
  }
  // open questions
  if ((t.questions_full || []).length) {
    sec.push(`<section class="td-sec"><h4>Waiting for you</h4>${t.questions_full.map((q) => `<p>${esc(q.text)}<br>${(q.choices || []).map((c) => btn(c, "question.answer", { id: q.id, answer: c })).join(" ")} ${btn("answer…", "question.answer", { id: q.id }, ["Your answer:", "answer", ""])}</p>`).join("")}</section>`);
  }
  // journal
  const js = t.journal || [];
  sec.push(`<section class="td-sec td-journal"><h4>Journal</h4>${js.length ? js.map((j) => `<p class="d">${esc(j).replace(/\n/g, "<br>")}</p>`).join("") : '<p class="d">Nothing yet today. One line is enough.</p>'}
    <form data-act="journal.add"><textarea name="text" rows="3" placeholder="How did today go? (Ctrl+Enter saves)"></textarea><button>save</button></form>
    <p class="d">${t.inbox_today ? `${t.inbox_today} note${t.inbox_today === 1 ? "" : "s"} in the inbox today. ` : ""}Saved in your notes, nowhere else.</p></section>`);
  el.innerHTML = sec.join("");
  // the deadline box: "essay draft fri 17:00" -> title and when (the server reads the time; we only split it off)
  const add = el.querySelector(".td-add");
  if (add) add.onsubmit = async (e) => {
    e.preventDefault(); const v = add.querySelector("input").value.trim(); if (!v) return;
    const m = v.match(DUE_WHEN);
    if (!m) { tdSay("End with when it's due: essay draft fri 17:00", true); return; }
    await tdAct("deadline.add", { title: m[1], when: m[2] });
  };
  const ta = el.querySelector(".td-journal textarea");
  if (ta) ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ta.form.requestSubmit(); } });
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
  if (DLABEL[name]) { openPage(name); return; } // a page: over the board
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
    p.innerHTML = '<p>Terminals is off. With it on, this pane also has your AI\'s own program (agy or Claude Code), a shell and Kurooto\'s log, each a real terminal. Turn it on in <a href="#" data-goto="features">features</a>, only on a computer that\'s yours alone: anyone who can open this page can type into them.</p>';
    p.onclick = (e) => { if (e.target.dataset.goto) { e.preventDefault(); showDense(e.target.dataset.goto); } };
  }
}
// the terminal tabs: your AI's program, a shell, the kurooto chat, the log (the chat works without Terminals)
function agentLabel(title) {
  const b = last && last.agent && last.agent.brain;
  if (b && BRAIN[b.id]) return BRAIN[b.id];
  const known = { "Antigravity (agy)": "agy", "Claude Code": "claude", "Claude Code (Advanced)": "claude" }; // the last: a terminal opened before 0.6.0
  return known[title] || String(title || "agent").toLowerCase().split(/[ (/]/)[0];
}
function denseTerms() {
  const by = Object.fromEntries(TERM.list.map((t) => [t.name, t])), out = [];
  const add = (name, label) => { if (by[name]) out.push({ name, label, live: by[name].alive || TERM.live.has(name) }); };
  add("agent", by.agent ? agentLabel(by.agent.title) : "");
  add("shell", "shell");
  out.push({ name: "kurooto", label: ((last && last.name) || "Kurooto").toLowerCase(), live: true });
  add("logs", "logs");
  for (const t of TERM.list) if (t.name.startsWith("agent-")) add(t.name, t.name.slice(6)); // your other AI programs
  for (const t of TERM.list) if (!["agent", "shell", "ask", "logs"].includes(t.name) && !t.name.startsWith("agent-")) add(t.name, String(t.title).toLowerCase());
  return out;
}
// ----------------------------------------------------------------------------- search (the Features and Settings pages)
// A box at the top of each: it filters as you type (any case; every word has to be found somewhere), marks the words
// it found and counts what's left. "/" or Ctrl+F goes to it while the page is open (Ctrl+F again: the browser's own);
// Esc empties it. It only looks through what the page already has: nothing is asked of Kurooto.
const FIND = { features: "", settings: "" };
const findBar = (page, what) => `<div class="find"><input type="search" class="find-in" data-find="${page}" placeholder="search ${what}  (/ or ctrl+f · esc empties it)" spellcheck="false" autocomplete="off" aria-label="search ${what}"><span class="find-n d" aria-live="polite"></span></div><p class="find-none hidden"></p>`;
const findWords = (q) => q.toLowerCase().split(/\s+/).filter(Boolean);
function findWire(host, page, refocus) {
  const inp = host.querySelector(".find-in"); if (!inp) return;
  const apply = () => (page === "features" ? featuresFind : settingsFind)(host);
  inp.value = FIND[page];
  inp.oninput = () => { FIND[page] = inp.value; apply(); };
  inp.onkeydown = (e) => { if (e.key === "Escape" && inp.value) { e.preventDefault(); inp.value = ""; FIND[page] = ""; apply(); } };
  apply();
  if (refocus) { inp.focus({ preventScroll: true }); inp.setSelectionRange(inp.value.length, inp.value.length); }
}
const findInput = () => {
  const page = DENSE ? PAGE : tab;
  return page === "features" || page === "settings" ? (DENSE ? $("#ov-body") : $("#tab-body")).querySelector(".find-in") : null;
};
function unmark(root) {
  for (const m of [...root.querySelectorAll("mark.hit")]) { const p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); }
}
function mark(root, words) {
  if (!words.length) return;
  const re = new RegExp(words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length).join("|"), "gi");
  const skip = "button, select, option, textarea, script, style, mark, .find";
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.parentElement.closest(skip) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
  const nodes = []; while (walk.nextNode()) nodes.push(walk.currentNode);
  for (const n of nodes) {
    const text = n.nodeValue, frag = document.createDocumentFragment(); let at = 0, m, hit = false;
    re.lastIndex = 0;
    while ((m = re.exec(text))) { hit = true; frag.append(text.slice(at, m.index)); const k = document.createElement("mark"); k.className = "hit"; k.textContent = m[0]; frag.append(k); at = m.index + m[0].length; }
    if (hit) { frag.append(text.slice(at)); n.replaceWith(frag); }
  }
}
function findSay(host, q, n, total, what, extra = "") {
  host.querySelector(".find-n").textContent = q ? `${n} of ${total} ${what}` : `${total} ${what}${extra}`;
  const none = host.querySelector(".find-none");
  none.textContent = q && !n ? `nothing matches '${q}'` : ""; none.classList.toggle("hidden", !(q && !n));
}
function featuresFind(host) {
  const q = FIND.features.trim(), words = findWords(q), cards = [...host.querySelectorAll(".card2[data-hay]")];
  unmark(host);
  let n = 0;
  for (const c of cards) {
    const ok = words.length ? words.every((w) => c.dataset.hay.includes(w)) : !c.classList.contains("hid"); // hidden ones only in a search
    c.classList.toggle("hidden", !ok);
    const why = c.querySelector(".find-why"); why.textContent = ""; why.classList.add("hidden");
    if (!ok || !words.length) continue;
    n++;
    // found by its settings, not by what the card says: say which
    const seen = c.textContent.toLowerCase(), more = words.filter((w) => !seen.includes(w));
    const keys = (FSET[c.dataset.id] || []).filter((x) => more.some((w) => x.hay.includes(w))).map((x) => x.key);
    if (keys.length) { why.textContent = `its settings: ${keys.slice(0, 4).join(", ")}${keys.length > 4 ? "…" : ""}`; why.classList.remove("hidden"); }
    mark(c, words);
  }
  for (const g of host.querySelectorAll(".feat")) g.classList.toggle("hidden", ![...g.children].some((c) => !c.classList.contains("hidden")));
  host.querySelectorAll(".addons-h").forEach((ah) => ah.classList.toggle("hidden", !!ah.nextElementSibling && ah.nextElementSibling.classList.contains("hidden")));
  const hb = host.querySelector(".hid-box"); if (hb) hb.classList.toggle("hidden", !!words.length);
  const nh = cards.filter((c) => c.classList.contains("hid")).length;
  const on = cards.filter((c) => c.classList.contains("on")).length;
  findSay(host, q, n, cards.length, "features", ` · ${on} on${nh ? ` · ${nh} hidden` : ""}`);
}
function settingsFind(host) {
  const q = FIND.settings.trim(), words = findWords(q), rows = [...host.querySelectorAll(".set[data-hay]")];
  unmark(host);
  let n = 0;
  for (const r of rows) {
    const ok = words.every((w) => r.dataset.hay.includes(w));
    r.classList.toggle("hidden", !ok); if (ok) n++;
    for (const i of r.querySelectorAll("input:not([type=checkbox]), select, textarea")) i.classList.toggle("hit", ok && words.some((w) => String(i.value).toLowerCase().includes(w)));
  }
  for (const fs of host.querySelectorAll(".form fieldset")) {
    const any = [...fs.querySelectorAll(".set")].some((r) => !r.classList.contains("hidden"));
    fs.classList.toggle("hidden", !any); if (any) mark(fs, words);
  }
  findSay(host, q, n, rows.length, "settings");
}
const stale = (host, name) => (host.id === "ov-body" ? PAGE !== name : host.id === "tab-body" && !DENSE && tab !== name);
const saveHiddenF = () => api("settings", { key: "look.hidden_features", value: [...HIDDEN_F] }).catch(() => {});

const said = {}; // a feature's last Set up result (✓ or ✗), shown on its card
let SHOW_HIDDEN = false, FSET = {}; // the list of hidden features is open; each feature's own settings (for the search)
async function renderFeatures(body) {
  const typing = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.find === "features";
  const [st, sets, al] = await Promise.all([api("state"), api("settings").catch(() => ({ sections: [] })), api("addons").catch(() => ({ linked: [], kept: [] }))]);
  let health = {};
  try { health = await api("health"); } catch { /* an older Kurooto */ }
  if (stale(body, "features")) return; // another page was opened meanwhile
  const look = (sets.sections || []).find((x) => x.section === "look");
  if (look && Array.isArray(look.values.hidden_features)) HIDDEN_F = new Set(look.values.hidden_features);
  // a feature's settings (while it's on), so the search finds it by them too: keys and what they mean
  FSET = {};
  for (const x of sets.sections || []) FSET[x.section] = Object.keys(x.values).map((k) => ({ key: `${x.section}.${k}`, hay: `${x.section}.${k} ${k.replace(/_/g, " ")} ${((x.help || {})[k]) || ""}`.toLowerCase() }));
  // what the search looks through: only what the card shows, and the feature's settings
  const hay = (m) => [m.title, m.description, m.privacy, !m.on && !m.ready ? m.why : "", m.form && !m.ready ? [m.form.intro, ...(m.form.fields || []).map((f) => f.label)].join(" ") : "",
    m.on && m.card ? [...(m.card.lines || []), ...(m.card.toggles || []).map((x) => x.label)].join(" ") : "", ...(FSET[m.id] || []).map((x) => x.hay)].join("\n").toLowerCase();
  const hid = (m) => !m.on && HIDDEN_F.has(m.id); // a feature that's on is never hidden
  const hideBtn = (m) => m.on ? "" : hid(m) ? `<button class="hide-f" data-unhide="${m.id}" title="back on this page">unhide</button>`
    : `<button class="hide-f" data-hide="${m.id}" title="take it off this page (Show hidden, at the bottom, brings it back)">hide</button>`;
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
  const card = (m) => `<div class="card2 ${m.on ? "on" : ""}${hid(m) ? " hid hidden" : ""}" data-id="${m.id}" data-hay="${esc(hay(m))}">${hideBtn(m)}<b>${esc(m.title)}</b>${hid(m) ? ' <span class="tag-h">hidden</span>' : ""}<p>${esc(m.description)}</p><p style="color:var(--lav)">${esc(m.privacy)}</p>${m.id === "mail_digest" && m.on ? `<p><a href="/confidential" target="_blank" rel="noopener">Confidential mail (summarised on this computer)</a></p>` : ""}${m.id === "projects" ? `<p><a href="/proposals" target="_blank" rel="noopener">Proposals waiting for your OK</a></p>` : ""}
    ${m.on ? `<button data-off="${m.id}">Turn off</button>` : m.ready ? `<button class="primary" data-on="${m.id}">Turn on</button>` : m.setup ? `<button class="primary" data-setup="${m.id}">Set up</button> <span class="d">${esc(m.why)}</span>` : m.id === "telegram" ? `<button class="primary" data-goto-setup="telegram">Connect on the setup page</button> <span class="d">${esc(m.why)}</span>` : `<span class="d">${esc(m.why)}</span>`}${calls(m)}${form(m)}${pieces(m)}${said[m.id] ? `<p class="${said[m.id].startsWith("✓") ? "ok2" : "bad2"}" style="font-weight:600">${esc(said[m.id])}</p>` : ""}<p class="find-why d hidden"></p></div>`;
  const addons = st.modules.filter((m) => m.addon && !m.linked); // features from your own add-ons folder (core/overlay.py)
  const linked = st.modules.filter((m) => m.linked); // features of the add-ons by link (core/addons.py)
  const extras = st.modules.filter((m) => m.extra && !m.addon && !m.bundle); // add-ons that come with Kurooto (Module.extra); a bundle's members are switches on its card
  const kept = $("#flog") ? $("#flog").innerHTML : ""; // what the last step said survives the re-render
  const hidden = st.modules.filter(hid);
  const onFirst = (ms) => [...ms.filter((m) => m.on), ...ms.filter((m) => !m.on)]; // what's running first, then the rest in their order
  const hiddenBox = !hidden.length ? "" : `<div class="hid-box"><button class="linkish" data-showhidden="1">${SHOW_HIDDEN ? "close the hidden list" : `Show hidden (${hidden.length})`}</button>${SHOW_HIDDEN
    ? `<ul class="hid-list">${hidden.map((m) => `<li><b>${esc(m.title)}</b><span class="d">${esc(m.description)}</span><button data-unhide="${m.id}">Unhide</button></li>`).join("")}</ul>` : ""}</div>`;
  setupLeft(st.setup);
  body.innerHTML = `${findBar("features", "features")}${setupBlock()}${healthBlock(health)}<div class="feat">${onFirst(st.modules.filter((m) => !m.addon && !m.extra && !m.bundle)).map(card).join("")}</div>${extras.length
    ? `<p class="d addons-h">Add-ons: they come with Kurooto, and are off until you turn them on</p><div class="feat">${onFirst(extras).map(card).join("")}</div>` : ""}${addons.length
    ? `<p class="d addons-h">Your add-ons: your own code, from your add-ons folder</p><div class="feat">${onFirst(addons).map(card).join("")}</div>` : ""}${linkBlock(al, onFirst(linked).map(card).join(""))}<div class="log" id="flog">${kept}</div>${hiddenBox}`;
  findWire(body, "features", typing);
  body.onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target, flog = $("#flog");
    if (f.dataset.addlink !== undefined) { // Add-ons by link: its card first (core/addons.py)
      const btn = f.querySelector("button"); btn.disabled = true; flog.textContent = "Cloning it to read its card…";
      const r = await api("addons/look", { url: f.url.value.trim(), ref: f.ref.value.trim() });
      btn.disabled = false; flog.textContent = r.ok ? "" : r.message;
      if (r.ok) { AL_CARD = { ...r, kind: "add" }; renderFeatures(body); }
      return;
    }
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
      for (let i = 0; i < 300 && run === renderFeatures.wait && current() === "features"; i++) {
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
    if (t.dataset.hide || t.dataset.unhide) { // only this page changes: the feature itself stays as it is
      if (t.dataset.hide) HIDDEN_F.add(t.dataset.hide); else HIDDEN_F.delete(t.dataset.unhide);
      await saveHiddenF(); renderFeatures(body); return;
    }
    if (t.dataset.showhidden) { SHOW_HIDDEN = !SHOW_HIDDEN; renderFeatures(body); return; }
    if (t.dataset.gotoSetup) { location.href = `/setup#${t.dataset.gotoSetup}`; return; } // set up on the setup page's own step
    if (t.dataset.aloff) { // an official add-on: its card first, at the commit Kurooto pins (core/official.py)
      t.disabled = true; flog.textContent = "Fetching its card…";
      const r = await api("addons/look", { official: t.dataset.aloff });
      flog.textContent = r.ok ? "" : r.message;
      if (r.ok) AL_CARD = { ...r, kind: "add" };
      renderFeatures(body); return;
    }
    if (t.dataset.alcheck) { // a newer commit's card and what it changes
      t.disabled = true; flog.textContent = `Looking for a newer commit of ${t.dataset.alcheck}…`;
      const r = await api("addons/check", { name: t.dataset.alcheck });
      flog.textContent = r.ok && !r.same ? "" : r.message;
      if (r.ok && !r.same) AL_CARD = { ...r, kind: "update" };
      renderFeatures(body); return;
    }
    if (t.dataset.aladd) { // yes to the card (with the box ticked when it runs code)
      const box = body.querySelector("[data-alcode]");
      const r = await api(`addons/${AL_CARD && AL_CARD.kind === "update" ? "update" : "add"}`, { token: t.dataset.aladd, code: !!(box && box.checked) });
      flog.textContent = r.message || "";
      if (r.ok) { AL_CARD = null; renderFeatures(body); }
      return;
    }
    if (t.dataset.aldrop) { await api("addons/drop", { token: t.dataset.aldrop }); AL_CARD = null; flog.textContent = "Dropped; nothing was kept."; renderFeatures(body); return; }
    if (t.dataset.alremove || t.dataset.alundo) {
      const r = await api(t.dataset.alremove ? "addons/remove" : "addons/undo", { name: t.dataset.alremove || t.dataset.alundo });
      flog.textContent = r.message || ""; renderFeatures(body); return;
    }
    if (t.dataset.card) { const r = await api("modules/card", { id: t.dataset.card, act: t.dataset.act, value: t.checked }); flog.textContent = r.message || r.error || ""; renderFeatures(body); return; }
    if (t.dataset.fix) { t.disabled = true; const r = await api("health/fix", { id: t.dataset.fix }); flog.textContent = r.message || ""; renderFeatures(body); return; }
    if (t.dataset.on && HIDDEN_F.delete(t.dataset.on)) await saveHiddenF(); // turned on from the search: not hidden any more
    if (t.dataset.on) {
      const r = await api("modules/enable", { ids: [t.dataset.on] });
      // what's left to set it up, every time it's switched on: what to do, the exact command, how to undo it
      const steps = Object.entries(r.setup || {}).map(([id, ss]) => ss.filter((s) => !s.done).map((s) => `• ${s.what}${s.how ? `: ${s.how}` : ""}${s.undo ? ` (undo: ${s.undo})` : ""}`).join("\n")).filter(Boolean).join("\n");
      flog.textContent = Object.values(r.results).map((x) => x.message).join("\n") + (steps ? `\nTo finish setting it up:\n${steps}` : "");
      renderFeatures(body);
    }
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
// ----------------------------------------------------------------------- Add-ons by link (core/addons.py)
// A git address, then its card (what it adds, may reach and start, whether it runs code) before anything is added;
// each added one with Check for update (what changes, then its card again) and Remove (Undo puts it back).
let AL_CARD = null; // the card waiting for an answer: {token, text, changes_text?, card, kind: add|update}
// Official add-ons (core/official.py): Kurooto's own list, each at the commit it pins. Add fetches its card first (the
// same card and yes as any add-on by link); Update when a newer Kurooto pins a newer commit of one you have.
function officialBlock(al) {
  const linked = Object.fromEntries((al.linked || []).map((r) => [r.name, r]));
  const rows = (al.official || []).map((o) => {
    const r = linked[o.name], mine = o.have === "official" || o.have === "update";
    const btn = o.have === "" ? `<button class="primary" data-aloff="${esc(o.name)}">Add</button>`
      : o.have === "other" ? `<span class="d">You have an add-on of this name from another address or commit, so it isn't marked official.</span>`
      : `${o.have === "update" ? `<button class="primary" data-alcheck="${esc(o.name)}">Update to ${esc(o.tag)}</button>` : `<button data-alcheck="${esc(o.name)}">Check for update</button>`} <button data-alremove="${esc(o.name)}">Remove</button>`;
    return `<div class="card2 al-row${mine ? " on" : ""}"><b>${esc(o.title)}</b> <span class="tag-off" title="in Kurooto's official list, at the commit it pins">Official</span>${mine ? ' <span class="d">added</span>' : ""}
      <p>${esc(o.line)}</p><p class="d">Needs: ${esc(o.needs)} · <a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.url.replace(/^https:\/\//, ""))}</a> · ${esc(o.tag)} (${esc(o.commit.slice(0, 12))})</p>
      ${mine && r && r.problem ? `<p class="bad2">Didn't load: ${esc(r.problem)}</p>` : ""}<p>${btn}</p></div>`;
  }).join("");
  return rows ? `<p class="d addons-h">Official add-ons: published with Kurooto, each pinned to one commit; you read its card before anything is added</p><div class="feat">${rows}</div>` : "";
}
function linkBlock(al, featureCards) {
  const mine = new Set((al.official || []).filter((o) => o.have === "official" || o.have === "update").map((o) => o.name)); // shown with the official ones
  const rows = (al.linked || []).filter((r) => !mine.has(r.name)).map((r) => `<div class="card2 al-row"><b>${esc(r.title)}</b> <span class="d">${esc(r.name)} · ${esc(String(r.commit).slice(0, 12))} · ${esc(r.url)}</span>
    ${r.problem ? `<p class="bad2">Didn't load: ${esc(r.problem)}</p>` : ""}
    <p><button data-alcheck="${esc(r.name)}">Check for update</button> <button data-alremove="${esc(r.name)}">Remove</button></p></div>`).join("");
  const have = new Set((al.linked || []).map((r) => r.name));
  const undo = (al.kept || []).map((k) => `<p class="d">${esc(k.name)}: ${k.why === "removed" && !have.has(k.name) ? "removed" : "an earlier version is kept"} · <button data-alundo="${esc(k.name)}">Undo</button></p>`).join("");
  const c = AL_CARD;
  const pending = !c ? "" : `<div class="card2 al-pending"><b>${c.kind === "update" ? "What this update brings" : "Its card: read it before adding"}</b>${c.card && c.card.official ? ' <span class="tag-off">Official</span>' : ""}
    ${c.changes_text ? `<div class="al-card">${esc(c.changes_text)}</div>` : ""}<div class="al-card">${esc(c.text)}</div>
    ${c.card && c.card.code && c.card.code.length ? `<label><input type="checkbox" data-alcode> I trust this code: it runs inside Kurooto with its access to this computer</label>` : ""}
    <p><button class="primary" data-aladd="${esc(c.token)}">${c.kind === "update" ? "Update" : "Add"}</button> <button data-aldrop="${esc(c.token)}">Don't</button></p></div>`;
  const offPending = c && c.card && c.card.official; // an official one's card shows under the official list
  return `${officialBlock(al)}${offPending ? pending : ""}<p class="d addons-h">Add-ons by link: made by others, each pinned to one commit; you read its card before anything is added</p>
    <div class="feat"><div class="card2 al-row"><b>Add one from its git address</b><form class="sf" data-addlink><label>Git address<input name="url" placeholder="https://github.com/someone/kurooto-habits" autocomplete="off" spellcheck="false"></label>
    <label>Tag, branch or commit (optional: the newest commit, pinned)<input name="ref" autocomplete="off" spellcheck="false"></label><button class="primary" type="submit">Look at it</button></form>${undo}</div>${rows}</div>
    ${offPending ? "" : pending}${featureCards ? `<div class="feat">${featureCards}</div>` : ""}`;
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
      ? `<table><tr><th>phone</th><th>kind</th><th>paired</th><th></th></tr>${devs.map((d) => `<tr><td>${esc(d.name)}</td><td>${esc(d.kind)}${d.push ? " · notifications on" : ""}${d.kind === "android" && d.connected !== undefined ? (d.connected ? ' · <span class="ok2">connected</span>' : ' · <span class="d">not connected (ntfy.sh carries its messages)</span>') : ""}</td><td>${esc(d.created.slice(0, 10))}</td><td><button data-revoke="${esc(d.id)}">Remove</button></td></tr>`).join("")}</table>`
      : "<p class=\"d\">No phones paired yet.</p>"}
    ${ph.shortcuts && ph.shortcuts.length ? `<h3>Tell Kurooto (iPhone Shortcut)</h3>
    <p class="d">Each link lets its Shortcut send you a chat message as that phone, and nothing else. Revoke one and its Shortcut stops working at once; the phone stays paired.</p>
    <table><tr><th>phone</th><th>made</th><th>last used</th><th></th></tr>${ph.shortcuts.map((s) => `<tr><td>${esc(s.device_name || s.device)}</td><td>${esc((s.created || "").slice(0, 10))}</td><td>${esc(s.used ? s.used.slice(0, 16).replace("T", " ") : "never")}</td><td><button data-shortcut="${esc(s.id)}">Revoke</button></td></tr>`).join("")}</table>` : ""}
    <h3>On the phone</h3>
    <p><label class="views-tg"><input type="checkbox" data-views ${ph.views ? "checked" : ""}> Show Systems and the Notes map in the Android app</label></p>
    <p class="d">The app draws them as this page does. What goes: your notes' titles, where they are in your notes folder and which link to which (never what they say), and each feature's health. Sealed on this computer for each phone, so your call line can't read them; Systems only while you're looking at it. Turning it off drops your call line's copies. The iPhone app doesn't get them.</p>
    <h3>ntfy.sh (the fallback)</h3>
    <p class="d">The Android app (0.7.0 and later) gets calls and messages straight from your call line while it's connected ("connected" above). ntfy.sh only carries them when it isn't, and a second copy of each ring. ntfy limits each internet address, and yours may be shared (a campus or office); a free ntfy account is counted by address too, so only a paid ntfy plan's token lifts that.${ph.ntfy_limited ? ` <span class="bad2">ntfy refused ${ph.ntfy_limited} ring(s) or message(s) this week.</span>` : ""}</p>
    <p>${ph.ntfy_token ? "<span class=\"ok2\">Token kept.</span> " : ""}<input type="password" id="ntfy-token" placeholder="tk_..." autocomplete="off" spellcheck="false"> <button data-ntfy>Save</button>${ph.ntfy_token ? " <button data-ntfy-clear>Remove</button>" : ""}</p>
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
    if (t.dataset.ntfy !== undefined || t.dataset.ntfyClear !== undefined) {
      const token = t.dataset.ntfy !== undefined ? $("#ntfy-token").value.trim() : "";
      if (t.dataset.ntfy !== undefined && !token) { msg.textContent = "Paste the token first."; return; }
      msg.textContent = "Checking…";
      const r = await api("phone/ntfy", { token });
      if (r.ok) renderPhone(body);
      setTimeout(() => { const m = $("#phone-msg"); if (m) m.textContent = r.message; }, 300);
    }
    if (t.dataset.views !== undefined) {
      const r = await api("settings", { key: "calls.views", value: t.checked });
      msg.textContent = r.error ? r.error : t.checked ? "On: your Android phone gets them within a few minutes." : "Off: your call line drops its copies within a few minutes.";
      if (r.error) t.checked = !t.checked;
    }
    if (t.dataset.ring !== undefined) { const r = await api("phone/test", {}); msg.textContent = r.ok ? "Ringing your paired phones…" : r.error; }
    if (t.dataset.shortcut) { const r = await api("phone/shortcut/revoke", { id: t.dataset.shortcut }); await renderPhone(body); const m = $("#phone-msg"); if (m) m.textContent = r.ok ? "Revoked: that Shortcut no longer works." : (r.error || "Not found."); }
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
    <section><div><b>Add a project from a repository</b> <span class="d">(a GitHub address or a folder: it's read, never run; your AI writes its project note, its commits go into the Log, its README and docs go into the concept graph, each with Undo)</span></div>
      ${(r.repo_projects || []).length ? `<ul class="rs-feeds">${r.repo_projects.map((p) => `<li>${esc(p.project || p.label)} <span class="d">← ${esc(p.label)}, updated ${esc(p.updated)}</span></li>`).join("")}</ul>` : ""}
      <div class="rs-row"><input id="rs-proj" placeholder="github.com/owner/name or ~/code/my-project"> <input id="rs-proj-name" placeholder="name (optional)"> <button class="primary" data-rs-proj>Add a project from a repository</button></div></section>
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
    else if (d.rsProj !== undefined) { const x = await api("research/project", { target: $("#rs-proj").value, name: $("#rs-proj-name").value }); msg(x.ok ? x.message : (x.error || x.message), !x.ok); }
  };
}

// About you: your persona card (aboutme.js personaEditor, /persona on Telegram) and your profile
// (about-me/profile.md), edited right here (aboutme.js); /aboutme on Telegram links here
async function renderAboutTab(body) {
  body.onclick = body.onchange = body.onsubmit = null; // another tab's handlers mustn't see the editor's clicks
  const a = await api("aboutyou/profile");
  const card = `<h4>Persona card</h4><p class="d">How I talk to you, the same on chat, the app and calls. Empty means plain. It sets wording only: no feelings, backstory or "I missed you".</p><div class="about-editor" id="persona-host"></div><h4>Profile</h4>`;
  if (!a.exists) { body.innerHTML = card + `<p class="d">No profile yet. Build one on the <a href="/setup">setup page</a> (its About you step): what your other AI accounts know about you, merged by your AI.</p>`; personaEditor($("#persona-host"), api); return; }
  body.innerHTML = card + `<p class="d">Your profile, ${esc(a.path)}. Edit it here or in your notes; building it again (on the <a href="/setup">setup page</a>) asks first if you've changed it.</p><div class="about-editor" id="about-host"></div>`;
  personaEditor($("#persona-host"), api);
  aboutEditor($("#about-host"), api);
}

async function renderSettings(body) {
  const typing = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.find === "settings";
  const { sections } = await api("settings");
  if (stale(body, "settings")) return;
  // a section may offer choices for a setting (a list) and a line of help under it; "fixed" shows a value that can't
  // change here, and "post" sends changes to the section's own request (Settings → Starting: /api/autostart);
  // "remove" puts a Remove button by each value that isn't fixed, which asks first (Settings → Claude accounts)
  const LAYOUTS = [["dense", "dense: one full-screen board (screens 1280 px wide or more)"], ["roomy", "roomy: bigger panes and type"]];
  const NOTES = [["kurooto", "kurooto: journal/, about-me/, a folder per subject"], ["zettelkasten", "zettelkasten: dailies/, master/, sources/, zettel/"]];
  const LINKS = [["default", "default: this computer's default browser"], ["here", "here: the browser showing this page"]];
  const field = (key, v, sec) => {
    const k = key.split(".").slice(1).join("."), help = ((sec && sec.help) || {})[k], fixed = ((sec && sec.fixed) || {})[k], tip = ((sec && sec.tips) || {})[k];
    const choices = ((sec && sec.choices) || {})[k] || (key === "look.layout" ? LAYOUTS : key === "notes.layout" ? NOTES : key === "look.links_in" ? LINKS : null);
    const post = sec && sec.post ? ` data-post="${esc(sec.post)}"` : "";
    const gone = !fixed && sec && sec.remove ? ` <button data-remove="${esc(k)}" data-remove-post="${esc(sec.remove)}">Remove</button>` : "";
    const html = fixed ? `<label><span>${esc(key)}</span><span class="fixed">${esc(fixed)}</span></label>`
      : choices ? `<label><span>${esc(key)}</span><select data-key="${key}"${post}>${(choices.some(([id]) => id === v) ? choices : [[v, String(v)], ...choices]) // a value not in the list stays shown, not silently the first
        .map(([id, label]) => `<option value="${esc(id)}"${id === v ? " selected" : ""}>${esc(label)}</option>`).join("")}</select></label>`
      : typeof v === "string" && post ? `<label><span>${esc(key)}</span><input data-key="${key}"${post} value="${esc(v)}">${gone}</label>` : plain(key, v);
    const tipped = tip ? html.replace(/^<label>/, `<label title="${esc(tip)}">`) : html; // hover: what the setting does
    return help ? tipped.replace(/<\/label>$/, `</label><div class="help d">${esc(help)}</div>`) : tipped;
  };
  const plain = (key, v) => {
    if (typeof v === "boolean") return `<label><span>${esc(key)}</span><input type="checkbox" data-key="${key}" ${v ? "checked" : ""}></label>`;
    if (Array.isArray(v) || (v && typeof v === "object")) { // the whole value in view (a one-line box cut it off), saved when you leave the box
      const short = JSON.stringify(v), text = short.length <= 40 ? short : JSON.stringify(v, null, 2);
      return `<label><span>${esc(key)}</span><textarea data-key="${key}" data-json spellcheck="false" rows="${Math.min(8, text.split("\n").length)}">${esc(text)}</textarea></label>`;
    }
    return `<label><span>${esc(key)}</span><input data-key="${key}" ${typeof v === "number" ? 'type="number" data-num' : ""} value="${esc(v ?? "")}"></label>`;
  };
  // what the search looks through: the section, the key, what it's called and means, and its value
  const shay = (key, v, sec) => {
    const k = key.split(".").slice(1).join("."), choices = ((sec.choices || {})[k] || (key === "look.layout" ? LAYOUTS : key === "notes.layout" ? NOTES : key === "look.links_in" ? LINKS : null) || []);
    const chosen = choices.find(([id]) => id === v);
    return [sec.section, sec.title, key, k.replace(/[._]/g, " "), (sec.help || {})[k] || "", (sec.fixed || {})[k] || "", chosen ? chosen[1] : "", typeof v === "string" ? v : JSON.stringify(v)].join("\n").toLowerCase();
  };
  body.innerHTML = `${findBar("settings", "settings")}<div class="form">${sections.map((s) => `<fieldset><legend>${esc(s.title)}</legend>${Object.entries(s.values).map(([k, v]) => `<div class="set" data-hay="${esc(shay(`${s.section}.${k}`, v, s))}">${field(`${s.section}.${k}`, v, s)}</div>`).join("")}</fieldset>`).join("")}</div><p class="d" id="saved"></p>`;
  findWire(body, "settings", typing);
  const notesSet = body.querySelector('[data-key="notes.layout"]');  // the setup page's Notes step (core/notesfit.py)
  if (notesSet) notesSet.closest("fieldset").insertAdjacentHTML("beforeend", `<div class="help d"><a href="/setup#notes">Fit Kurooto to your notes</a>: it reads your notes folder, proposes where each kind of note goes, and moves its own notes there, with Undo.</div>`);
  // the chosen palette's colours under its choice: the dashboard's (always dark) and the light pages' (core/palette.py)
  const palSet = body.querySelector('[data-key="look.palette"]');
  if (palSet) api("look").then((look) => {
    const p = (look.previews || {})[palSet.value], row = palSet.closest(".set");
    if (!p || !row || stale(body, "settings")) return;
    const dots = (cs) => (cs || []).map((c) => `<i style="background:${esc(c)}"></i>`).join("");
    row.insertAdjacentHTML("beforeend", `<div class="help d swatch-row" aria-hidden="true"><span>dashboard</span>${dots(p.dark)}<span>light pages</span>${dots(p.light)}</div>`);
  }).catch(() => {});
  // what happened, right under the setting you changed (the page can be long: a line at its end went unseen)
  const say = (t, text, bad) => {
    $("#saved").textContent = text;
    const row = t.closest(".set");
    let line = row.querySelector(".said");
    if (!line) { line = document.createElement("div"); line.setAttribute("aria-live", "polite"); row.append(line); }
    line.className = `help said${bad ? " bad2" : ""}`;
    line.textContent = text;
    clearTimeout(line.t);
    if (!bad) line.t = setTimeout(() => line.remove(), 4000);
  };
  body.onclick = async (e) => { // Remove (Settings → Claude accounts): only after a yes
    const t = e.target; if (!t.dataset || !t.dataset.remove) return;
    e.preventDefault();
    if (!confirm(`Remove ${t.dataset.remove}? Kurooto's sign-in folder for it is deleted (nothing of yours); to use it again, add it and sign in again.`)) return;
    const r = await api(t.dataset.removePost, { id: t.dataset.remove, yes: true });
    say(t, r.message || r.error || (r.ok ? "Removed." : "That didn't work."), !r.ok);
    if (r.ok) setTimeout(() => renderSettings(body), 1500);
  };
  body.onchange = async (e) => {
    const t = e.target; if (!t.dataset.key) return;
    let value = t.type === "checkbox" ? t.checked : t.dataset.num !== undefined ? Number(t.value) : t.value;
    if (t.dataset.json !== undefined) { try { value = JSON.parse(t.value); } catch { say(t, "That isn't valid JSON; it wasn't saved.", true); return; } }
    if (t.dataset.post) { // its own request, which says what it did (and what's in effect when it couldn't)
      say(t, "…");
      const r = await api(t.dataset.post, { [t.dataset.key.split(".").slice(1).join(".")]: value });
      say(t, r.message || r.error || (r.ok ? "Saved." : "That didn't work."), !r.ok);
      if (r.when && r.when !== value) t.value = r.when;
      return;
    }
    const r = await api("settings", { key: t.dataset.key, value });
    say(t, r.ok ? "Saved." : r.error, !r.ok);
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
  if (NEW) inp.placeholder = "Ask in plain English, or type help";
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
  const nm = (last && last.name) || "Kurooto", name = NEW ? nm : nm.toUpperCase().split("").join(" ");
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
Alt+1… switches the terminal pane's tabs; Alt+/ finds a note; Alt and a page's underlined letter opens it
(Alt+F features, Alt+S settings), over the whole board; Esc goes back. Alt+M: Study mode (notes and a study timer).`;
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

// ------------------------------------------------------------------------------------------------ Study mode
// Alt+M, "study" in the board's top-right corner (roomy: the top bar), Ctrl+K → study, or /study mode on|off on
// Telegram or in a terminal (core/actions.py: study_mode). The board keeps the NOTES map, large, and a STUDY pane: a
// focus and break timer (modules/study.py: a focus is focus time, so calls and messages wait, and its minutes are
// logged to the subject), today's study per subject, what's due in two weeks with start-by dates, recall cards (Quiz)
// and the subject's own notes, which light up on the map. Everything else waits as it was (hidden panes, a pane that
// filled the board, an open page) and comes back when it ends. The mode is the setting look.study_mode.
const SM = { v: null, subject: "", note: "", page: null, poll: null, tick: null, soon: null, ended: false };
const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const dur = (s) => (s < 3600 ? `${Math.round(s / 60)}m` : `${(s / 3600).toFixed(1)}h`);
const smSay = (text, bad) => { const el = $("#sm-said"); if (el) { el.textContent = text; el.className = "sm-said" + (bad ? " bad" : ""); } };
function setStudy(on, save = true, animate = true) {
  on = !!on;
  if (on === STUDY) return;
  if (on) { SM.page = PAGE; closeMenu(); }
  STUDY = on;
  document.body.classList.toggle("study", on);
  for (const b of document.querySelectorAll("#study-btn, .study-tg")) { b.textContent = on ? "leave study" : "study"; b.setAttribute("aria-pressed", String(on)); }
  if (save) api("settings", { key: "look.study_mode", value: on }).catch(() => {});
  if (on && PAGE) closePage(); else applyPanes();
  if (on) {
    if (document.activeElement && document.activeElement.closest && document.activeElement.closest("#pane-tabs")) document.activeElement.blur();
    smBuild(); smLoad();
    SM.poll = setInterval(smLoad, 30000); SM.tick = setInterval(smTick, 1000);
  } else {
    clearInterval(SM.poll); clearInterval(SM.tick); document.title = "Kurooto";
    mind.only = null; mind.autofit = true;
    const page = SM.page; SM.page = null;
    if (page) openPage(page);
  }
  if (animate) swapIn();
}
const toggleStudy = () => setStudy(!STUDY);
// the panes that come (or come back) slide in a little and fade up; nothing moves with reduced motion
function swapIn() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const g = $(".grid"); g.classList.remove("swap"); void g.offsetWidth; g.classList.add("swap");
  clearTimeout(SM.swap); SM.swap = setTimeout(() => g.classList.remove("swap"), 450);
}
document.addEventListener("click", (e) => { if (e.target.closest("[data-study-toggle]")) { e.preventDefault(); toggleStudy(); } });
function smBuild() {
  const b = $("#sm-body");
  if (b.querySelector("#sm-time")) return;
  b.innerHTML = `
  <div class="box sm-timer"><div class="lab"><span class="t">TIMER</span><span class="meta" id="sm-hold"></span></div>
    <div class="sm-sub"><label class="k" for="sm-subject">subject</label><select id="sm-subject"></select></div>
    <div class="sm-clock"><span class="sm-time" id="sm-time">25:00</span><span class="sm-phase" id="sm-phase"></span></div>
    <div class="row" id="sm-bar">${meter(0)}</div>
    <div class="sm-btns"><button data-t="start" id="sm-go">start</button><button data-t="pause" id="sm-pause">pause</button><button data-t="reset" id="sm-reset">reset</button></div>
    <div class="sm-opts k"><label>focus <input type="number" min="1" max="240" id="sm-fmin" aria-label="focus minutes"></label><label>break <input type="number" min="1" max="240" id="sm-bmin" aria-label="break minutes"></label><span>min</span>
      <label class="sm-then"><input type="checkbox" id="sm-then"> then leave Study mode</label></div>
    <p class="sm-said" id="sm-said" aria-live="polite"></p></div>
  <div class="box" id="sm-subj-box"><div class="lab"><span class="t">SUBJECTS</span><span class="meta">Study mode and the notes map</span></div>
    <div id="sm-subj-list"></div>
    <form class="sm-sub" id="sm-subj-add"><input id="sm-subj-name" placeholder="add a subject, e.g. Linear Algebra" autocomplete="off" aria-label="a new subject's name"><input id="sm-subj-al" placeholder="short names: la, linalg" autocomplete="off" aria-label="its short names"><select id="sm-subj-folder" aria-label="the folder of your notes that is this subject's" title="the folder of your notes that is this subject: its notes show in Study mode and make a neighbourhood on the notes map"></select><button>add</button></form>
    <p class="sm-said" id="sm-subj-said" aria-live="polite"></p></div>
  <div class="box"><div class="lab"><span class="t">TODAY</span><span class="meta" id="sm-today-meta"></span></div><div id="sm-today"><span class="k">loading…</span></div></div>
  <div class="box"><div class="lab"><span class="t">DUE</span><span class="meta">two weeks</span></div><div id="sm-due"></div></div>
  <div class="box" id="sm-recall-box"><div class="lab"><span class="t">RECALL</span><span class="meta" id="sm-recall-meta"></span></div><div id="sm-recall"></div></div>
  <div class="box sm-course" id="sm-course-box"><div class="lab"><span class="t">COURSE</span><span class="meta">AI help, notes as a PDF, a draft to check</span></div>
    <div class="sm-sub"><label class="k" for="sm-policy">AI help</label><select id="sm-policy" title="the course's AI policy: Check my draft and the Hint ladder go by it"><option value="">not set (allowed)</option><option value="allowed">allowed</option><option value="hints">hints only</option><option value="off">off</option></select><button id="sm-pdf" title="this course's notes as one PDF (/notes pdf)">notes → pdf</button></div>
    <form class="sm-sub" id="sm-check"><input id="sm-draft" placeholder="a draft to check: its path, e.g. ~/proof.tex" autocomplete="off" spellcheck="false" aria-label="a draft's path to check"><button>check</button></form>
    <p class="sm-said" id="sm-csaid" aria-live="polite"></p></div>
  <div class="box sm-notes" title="click: find it on the map · double-click: open it"><div class="lab"><span class="t" id="sm-notes-t">NOTES</span><span class="meta" id="sm-notes-meta"></span></div><div id="sm-notes"></div></div>`;
  $("#sm-subject").onchange = (e) => { SM.subject = e.target.value; mind.autofit = true; smLoad(); };
  // the subjects: add one (with the folder of notes that is it) or remove one; its notes and files stay as they are
  const sSay = (text, bad) => { const el = $("#sm-subj-said"); if (el) { el.textContent = text; el.className = "sm-said" + (bad ? " bad" : ""); } };
  $("#sm-subj-add").onsubmit = async (e) => {
    e.preventDefault();
    const name = $("#sm-subj-name").value.trim(); if (!name) return;
    let r; try { r = await api("subjects/add", { name, aliases: $("#sm-subj-al").value, folder: $("#sm-subj-folder").value }); } catch { sSay("Kurooto didn't answer (is it running?).", true); return; }
    sSay(r.message || "", !r.ok);
    if (r.ok) { $("#sm-subj-name").value = ""; $("#sm-subj-al").value = ""; SM.subject = null; smLoad(); }
  };
  $("#sm-subj-list").onclick = async (e) => {
    const b = e.target.closest("[data-rm]"); if (!b) return;
    if (!confirm(`Remove the subject ${b.dataset.name}? Its notes and files stay where they are.`)) return;
    const r = await api("subjects/remove", { slug: b.dataset.rm });
    sSay(r.message || "", !r.ok); SM.subject = null; smLoad();
  };
  // the course: its AI policy, its notes as a PDF, a draft to check (core/actions.py)
  const cSay = (text, bad) => { const el = $("#sm-csaid"); if (el) { el.textContent = text; el.className = "sm-said" + (bad ? " bad" : ""); } };
  $("#sm-policy").onchange = async (e) => { await tdAct("subject.policy", { subject: SM.subject, policy: e.target.value }, cSay); smLoad(); };
  $("#sm-pdf").onclick = async (e) => { e.target.disabled = true; await tdAct("notes.pdf", { subject: SM.subject }, cSay); e.target.disabled = false; };
  $("#sm-check").onsubmit = async (e) => {
    e.preventDefault();
    const f = $("#sm-draft"); if (!f.value.trim()) return;
    await tdAct("draft.check", { path: f.value.trim(), subject: SM.subject }, cSay);
  };
  b.onclick = async (e) => {
    const pg = e.target.closest("[data-page]"); if (pg) { e.preventDefault(); openPage(pg.dataset.page); return; }
    const t = e.target.closest("[data-t]");
    if (t) { t.disabled = true; await tdAct("study.timer", { do: t.dataset.t, subject: SM.subject }, smSay); smLoad(); return; }
    const n = e.target.closest("[data-note]");
    if (n) { SM.note = n.dataset.note; mind.goTo(mind.nodes.get(SM.note)); smNotes(); }
  };
  b.ondblclick = (e) => { const n = e.target.closest("[data-note]"); if (n) api("open-note", { id: n.dataset.note }); };
  b.onchange = (e) => {
    const key = { "sm-fmin": "study.focus_min", "sm-bmin": "study.break_min", "sm-then": "study.timer_ends_mode" }[e.target.id];
    if (!key) return;
    const value = e.target.type === "checkbox" ? e.target.checked : clamp(Math.round(Number(e.target.value) || 0), 1, 240);
    api("settings", { key, value }).then((r) => { if (r && r.error) smSay(r.error, true); else smLoad(); }).catch(() => {});
  };
}
async function smLoad() {
  let v; try { v = await api(`study${SM.subject ? `?subject=${encodeURIComponent(SM.subject)}` : ""}`); } catch { smSay("Kurooto didn't answer (is it running?).", true); return; }
  if (!STUDY) return;
  const changed = !SM.v || v.subject !== SM.v.subject || (v.notes || []).length !== (SM.v.notes || []).length;
  SM.v = v; SM.subject = v.subject || ""; SM.ended = false;
  if (changed || !mind.only) { mind.only = new Set((v.notes || []).map((n) => n.id)); mind.autofit = true; }
  smDraw();
}
// a refresh soon after something happened (a timer's end, a deadline, a setting), not one per event
function smSoon() { clearTimeout(SM.soon); SM.soon = setTimeout(smLoad, 600); }
function smDraw() {
  const v = SM.v; if (!v || !$("#sm-time")) return;
  const on = new Set(v.features || []);
  const off = (what) => `<div class="row"><span class="k">${what} is off: <a href="#" data-page="features">turn it on in Features</a></span></div>`;
  // the subject, the timer's lengths
  const sl = (v.subjects || []).map((s) => `<div class="row"><span class="v">${esc(s.name)}</span><span class="k">${s.folder ? esc(s.folder) + "/" : "no folder"}</span>${s.own ? ` <button data-rm="${esc(s.slug)}" data-name="${esc(s.name)}" title="remove this subject (its notes stay)" aria-label="remove ${esc(s.name)}">remove</button>` : '<span class="k">from your term note</span>'}</div>`).join("");
  $("#sm-subj-list").innerHTML = sl || '<div class="row"><span class="k">no subjects yet: add the first one below</span></div>';
  $("#sm-subj-box").classList.toggle("hidden", !on.has("subjects"));
  const fo = '<option value="">(no folder: the usual places)</option>' + (v.folders || []).map((f) => `<option value="${esc(f)}">${esc(f)}/</option>`).join("");
  if ($("#sm-subj-folder").dataset.opts !== fo) { $("#sm-subj-folder").innerHTML = fo; $("#sm-subj-folder").dataset.opts = fo; }
  const sel = $("#sm-subject"), opts = (v.subjects || []).map((s) => `<option value="${esc(s.slug)}"${s.slug === v.subject ? " selected" : ""}>${esc(s.name)}</option>`).join("");
  if (sel.dataset.opts !== opts) { sel.innerHTML = opts || '<option value="">no subjects yet</option>'; sel.dataset.opts = opts; }
  sel.value = v.subject || "";
  const t = v.timer, tracker = !!t;
  sel.disabled = !(v.subjects || []).length || !!(t && t.running);
  for (const id of ["#sm-go", "#sm-pause", "#sm-reset", "#sm-fmin", "#sm-bmin", "#sm-then"]) $(id).classList.toggle("hidden", !tracker);
  $("#sm-bar").classList.toggle("hidden", !tracker);
  if (!tracker) smSay(on.has("subjects") ? "The timer needs the Study tracker: turn it on in Features." : "The timer needs Subjects and the Study tracker: turn them on in Features.");
  else {
    $("#sm-go").textContent = t.phase && !t.running && t.left && t.left < t.total ? "resume" : "start";
    $("#sm-go").disabled = t.running || !v.subject; $("#sm-pause").disabled = !t.running; $("#sm-reset").disabled = !t.phase;
    const active = document.activeElement;
    if (active !== $("#sm-fmin")) $("#sm-fmin").value = v.focus_min || 25;
    if (active !== $("#sm-bmin")) $("#sm-bmin").value = v.break_min || 5;
    $("#sm-then").checked = t.then === "end";
  }
  $("#sm-hold").textContent = v.focus ? `calls and messages wait till ${v.focus}` : "";
  // the course box: its AI policy (Subjects), notes → pdf, a draft to check (Check my draft)
  const pol = $("#sm-policy");
  if (document.activeElement !== pol) pol.value = v.ai_policy || "";
  pol.disabled = $("#sm-pdf").disabled = !v.subject;
  $("#sm-check").classList.toggle("hidden", !on.has("drafts"));
  // today, per subject
  const today = v.today || [], top = Math.max(1, ...today.map((r) => r.seconds));
  $("#sm-today-meta").textContent = today.length ? dur(today.reduce((a, r) => a + r.seconds, 0)) : "";
  $("#sm-today").innerHTML = !tracker ? off("The Study tracker") : today.slice(0, 5).map((r) => `<div class="row${r.slug === v.subject ? " on" : ""}"><span class="v sm-name">${esc(r.name)}</span>${meter(r.seconds / top)}<span class="v r sm-h">${dur(r.seconds)}</span></div>`).join("") ||
    '<div class="row"><span class="k">no study time yet today</span></div>';
  // what's due: quizzes and exams, tasks; then what to start
  const due = v.due || [], when = (hr) => (hr < 0 ? `overdue ${ago(-hr * 3600)}` : `in ${ago(hr * 3600)}`);
  $("#sm-due").innerHTML = !on.has("deadlines") ? off("Deadlines") : (due.map((d) => `<div class="row${d.subject === v.subject ? " on" : ""}"><span class="sm-kind ${d.kind === "exam" ? "exam" : ""}">${d.kind === "exam" ? "exam" : "task"}</span><span class="v grow sm-t">${esc(d.title)}</span><span class="r ${d.hours < 0 ? "hot" : d.hours < 24 ? "warm" : "k"}">${when(d.hours)}</span></div>`).join("") ||
    '<div class="row"><span class="k">nothing due in the next two weeks</span></div>') +
    (v.start_by || []).slice(0, 3).map((r) => `<div class="row"><span class="sm-kind start">start</span><span class="v grow sm-t">${esc(r.title)}</span><span class="r k">${esc(r.when.split(" · ")[0])}</span></div>`).join("");
  // recall cards: point at one (or tab to it) and it turns over
  const rc = v.recall;
  $("#sm-recall-box").classList.toggle("hidden", !on.has("quiz"));
  $("#sm-recall-meta").textContent = rc ? `${rc.due} due` : "";
  $("#sm-recall").innerHTML = !rc ? `<div class="row"><span class="k">no exam-prep or quiz notes for ${esc(v.name || "this subject")} yet</span></div>` :
    rc.cards.map((c, i) => `<details class="sm-card"><summary><span class="k">${esc(c.section || "card")} · ${i + 1}</span></summary><p>${mathHtml(c.text, smRecallAgain)}</p></details>`).join("") +
    `<div class="row"><span class="k">${rc.due ? `practise them: /quiz ${esc(v.subject)}` : "nothing to go over today"}</span></div>`;
  smNotes();
  smTick();
}
function smRecallAgain() { if (SM.v) smDraw(); }
function smNotes() {
  const v = SM.v; if (!v) return;
  const KIND = { course: "course", exam_prep: "prep", doubts: "doubts", class_log: "log", lecture: "lecture", concept: "concept" };
  const notes = v.notes || [], nowS = Date.now() / 1000;
  $("#sm-notes-t").textContent = v.name ? `NOTES · ${v.name.toUpperCase()}` : "NOTES";
  $("#sm-notes-meta").textContent = notes.length ? String(notes.length) : "";
  $("#sm-notes").innerHTML = notes.map((n) => `<button class="sm-note${n.id === SM.note ? " on" : ""}" data-note="${esc(n.id)}" title="${esc(n.id)}"><span class="k sm-nk">${KIND[n.kind] || n.kind}</span><span class="v sm-t">${esc(n.title)}</span><span class="k r">${ago(nowS - n.mtime)}</span></button>`).join("") ||
    `<div class="row"><span class="k">${v.subject ? `no notes for ${esc(v.name)} yet` : "add your subjects first: /subject add Linear Algebra"}</span></div>`;
}
// once a second: the timer's digits, its bar and phase (and the tab's title while it runs)
function smTick() {
  const v = SM.v, t = v && v.timer; if (!t || !$("#sm-time")) return;
  const total = t.total || 1500, left = t.running ? Math.max(0, t.ends - Date.now() / 1000) : t.phase ? (t.left ?? total) : total;
  $("#sm-time").textContent = mmss(left);
  $("#sm-time").className = `sm-time ${t.phase === "break" ? "brk" : t.running ? "run" : ""}`;
  $("#sm-phase").textContent = !t.phase ? "ready" : t.running ? (t.phase === "focus" ? `focus · ${t.name} · until ${hm(t.ends)}` : `break · until ${hm(t.ends)}`)
    : t.left && t.left < total ? `${t.phase} · paused` : `round ${t.round} · ready`;
  const i = $("#sm-bar i"); if (i) i.style.clipPath = `inset(0 ${(100 * left / total).toFixed(1)}% 0 0)`;
  document.title = t.running ? `${mmss(left)} ${t.phase} · Kurooto` : "Kurooto";
  if (t.running && left <= 0 && !SM.ended) { SM.ended = true; setTimeout(smLoad, 1500); } // its end is the server's
}

// ------------------------------------------------------------------------------------------------ wiring
let body, mind;
// out of sight (another tab, a minimised window), the page says so and Kurooto stops reading the machine and the notes
// for it; back in sight, a fresh reading comes at once (web/live.py: Live.seen)
const saySeen = () => { if (TERM.cid) api("stream/seen", { cid: TERM.cid, visible: !document.hidden }).catch(() => {}); };
document.addEventListener("visibilitychange", saySeen);
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
    else if (m.t === "event") {
      SEEN.set(m, performance.now() / 1000); feed.unshift(m); feed.length = Math.min(feed.length, 200); body.event(m); if (current() === "activity") renderTab();
      if (m.kind === "study_mode") setStudy(!!m.on, false); // /study mode on|off, or the timer's end
      else if (m.kind === "setting_changed" && m.key === "look.design") loadDesign(); // changed somewhere else
      else if (STUDY && /^(study|deadline|quiz|setting_changed)/.test(m.kind)) smSoon();
    }
    else if (m.t === "hello") { TERM.cid = m.cid; if (TERM.shown) termAttach(TERM.shown); if (document.hidden) saySeen(); }
    else if (m.t === "pty") { termData(m); if (!TERM.live.has(m.n)) { TERM.live.add(m.n); if (DENSE) renderNav(); } }
  };
  es.onerror = () => { (DENSE ? $("#sys-meta") : $("#meta")).textContent = "reconnecting…"; };
}
// a setting changed on the Settings tab that changes this page
function settingChanged(key, value) {
  if (key === "look.layout") { document.body.dataset.layout = value; applyLayout(); }
  if (key === "look.design") applyDesign(value);
  if (key === "look.palette") setTimeout(() => location.reload(), 300); // the canvases take their colours at load
  if (key === "look.panes") { HIDE = cleanHide(value); MAX = null; try { localStorage.setItem("kurooto.dash.panes", JSON.stringify(hideList())); } catch { /* fine */ } applyPanes(); }
  if (key === "look.hidden_features") HIDDEN_F = new Set(Array.isArray(value) ? value : []);
  if (key === "look.study_mode") setStudy(!!value, false);
  if (key === "look.links_in" && $('meta[name="kurooto-links"]')) $('meta[name="kurooto-links"]').content = value; // links.js
}
// The design (look.design): "new" or "classic". It applies at once: the board's boxes, the canvases' words and the
// borders are redrawn in the other one, and a page that's open stays open.
function setDesign(v) {
  v = v === "classic" ? "classic" : "new";
  applyDesign(v);
  api("settings", { key: "look.design", value: v }).catch(() => {});
}
function loadDesign() {
  api("settings").then((r) => {
    const look = ((r && r.sections) || []).find((s) => s.section === "look");
    if (look && look.values.design) applyDesign(look.values.design);
  }).catch(() => {});
}
function applyDesign(v) {
  v = v === "classic" ? "classic" : "new";
  const changed = document.body.dataset.design !== v;
  document.body.dataset.design = v; useDesign();
  for (const b of document.querySelectorAll(".design-tg")) b.textContent = NEW ? "classic look" : "new look";
  const inp = $("#chat-input"); if (inp) inp.placeholder = NEW ? "Ask in plain English, or type help" : "";
  placeCtl();
  if (!changed) return;
  if (body) body.widths.clear();
  SB.built = false; if (last) renderStatus(last);
  if (DENSE) { renderNav(); if (PAGE) renderPageNav(); chatDraw(); }
  renderMenu(); applyPanes();
}
// the new design keeps the panes menu and Study mode's button in the top bar; classic sets them into the board's border
function placeCtl() {
  const ctl = $("#panes-ctl"), bar = NEW && DENSE ? $(".bar .right") : $(".grid");
  if (ctl.parentElement === bar) return;
  if (bar.classList.contains("grid")) bar.prepend(ctl); else bar.insertBefore(ctl, bar.querySelector(".design-tg"));
}
document.addEventListener("click", (e) => { if (e.target.closest("[data-design-toggle]")) { e.preventDefault(); closeMenu(); setDesign(NEW ? "classic" : "new"); } });
function applyLayout(force = false) {
  const d = denseFits();
  if (d === DENSE && !force) return;
  // a page stays open across the switch: in roomy's tabs, or (the roomier ones) over the dense board
  const keep = force ? null : DENSE ? PAGE : ["features", "phone", "research", "about", "settings"].includes(tab) ? tab : null;
  if (!force && DENSE && PAGE) tab = PAGE;
  PAGE = null; closeMenu();
  DENSE = d;
  document.body.classList.toggle("dense", DENSE);
  placeCtl();
  $(".grid").classList.remove("tall");
  SB.built = false;
  const tb = $("#tab-body"); tb.onclick = tb.onchange = tb.onsubmit = null; tb.innerHTML = "";
  if (last) renderStatus(last);
  if (mind) mind.meta();
  if (DENSE) showDense(dtab); else showTab(tab === "terminals" && !TERM.on ? "activity" : tab);
  applyPanes();
  if (DENSE && keep) openPage(keep);
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
// maths in recall cards: $...$ and $$...$$ are typeset with KaTeX (vendored, loaded the first time a card has any)
const KATEX = { loading: null, rerender: [] };
function loadKatex() {
  if (window.katex || KATEX.loading) return KATEX.loading;
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/static/vendor/katex/katex.min.css"; document.head.appendChild(css);
  KATEX.loading = new Promise((ok, bad) => { const s = document.createElement("script"); s.src = "/static/vendor/katex/katex.min.js"; s.onload = ok; s.onerror = bad; document.head.appendChild(s); })
    .then(() => { KATEX.rerender.forEach((f) => f()); }).catch(() => {});
  return KATEX.loading;
}
function mathHtml(text, again) {
  const parts = String(text).split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g);
  if (parts.length > 1 && !window.katex) { if (again && !KATEX.rerender.includes(again)) KATEX.rerender.push(again); loadKatex(); }
  return parts.map((p, i) => {
    if (i % 2 === 0 || !window.katex) return esc(p);
    const dsp = p.startsWith("$$"), tex = p.slice(dsp ? 2 : 1, dsp ? -2 : -1);
    try { return window.katex.renderToString(tex, { displayMode: dsp, throwOnError: false, trust: false, output: "html" }); } catch (e) { return esc(p); }
  }).join("");
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
  const term = new window.Terminal({ fontFamily: MONO, fontSize: 13, cursorBlink: true, scrollback: 5000, allowProposedApi: false,
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
// Alt+1… switches terminals (dense: the terminal pane's tabs), Alt+/ finds a note; caught before a terminal sees them.
// Alt and a page's underlined letter (Alt+F features, Alt+S settings…) opens it, or closes it again; not from inside a
// terminal, which keeps its own Alt keys (Alt+F is a word forward in a shell)
window.addEventListener("keydown", (e) => {
  if (!e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "/") { e.preventDefault(); e.stopPropagation(); findNote(); return; }
  const pg = Object.keys(PKEY).find((k) => e.code === `Key${PKEY[k].toUpperCase()}`);
  const types = /Mac/.test(navigator.platform) && ["INPUT", "TEXTAREA"].includes(e.target.tagName); // Option+letter types a character
  if (e.code === "KeyM" && !e.shiftKey && !inTerm(e.target) && !types) { e.preventDefault(); e.stopPropagation(); toggleStudy(); return; } // Study mode
  if (pg && !e.shiftKey && !inTerm(e.target) && !types) { e.preventDefault(); e.stopPropagation(); if (DENSE && PAGE === pg) closePage(); else openPage(pg); return; }
  if (!/^[1-9]$/.test(e.key) || STUDY) return; // Study mode keeps the terminals out of the way
  const t = DENSE ? denseTerms()[Number(e.key) - 1] : tab === "terminals" ? TERM.list[Number(e.key) - 1] : null;
  if (!t) return;
  e.preventDefault(); e.stopPropagation();
  if (DENSE) { closePage(); if (!paneShown("terminal")) { MAX = HIDE.has("terminal") ? "terminal" : null; applyPanes(); } showDense(t.name); } else termShow(t.name);
}, true);
// "/" or Ctrl+F with the Features or Settings page open: its search box (before "/" finds a note)
window.addEventListener("keydown", (e) => {
  const inp = findInput(); if (!inp || inTerm(e.target)) return;
  const ctrlF = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.code === "KeyF" && document.activeElement !== inp;
  const slash = e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (!ctrlF && !slash) return;
  e.preventDefault(); e.stopImmediatePropagation(); inp.focus(); inp.select();
}, true);
// Esc: the panes menu closes, then a page, then a pane that fills the board gives the others back
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !DENSE || e.defaultPrevented || inTerm(e.target) || e.target.id === "mind-search") return;
  if (!$("#panes-menu").classList.contains("hidden")) { closeMenu(); $("#panes-btn").focus(); return; }
  if (PAGE) { closePage(); return; }
  if (MAX && (!["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) || e.target.id === "chat-input")) maxPane(MAX);
});
// Ctrl+K (or ⌘K): one line for the everyday things from anywhere on the board, the same actions as the Today page:
// ask, journal, note, remind, due, alarm, find (a note), open (a page), and the Today box's shorthand (j, ., !).
// Enter does the highlighted line (a bare word is completed first); what happened shows under it, and an AI
// request's answer arrives there too. Not from inside a terminal, where Ctrl+K belongs to the shell.
const CMD = { sel: 0, rows: [] };
const cmdSay = (text, bad) => { const el = $("#cmdk-said"); el.textContent = text; el.className = bad ? "bad" : ""; };
const pageOf = (r) => { const s = r.toLowerCase(); return Object.keys(TABS).find((k) => k.startsWith(s) || TABS[k].toLowerCase().startsWith(s)); };
const VERBS = [
  { w: "ask", hint: "ask Kurooto anything", run: (r) => tdAct("ask", { text: r }, cmdSay) },
  { w: "journal", hint: "a line in today's journal", run: (r) => tdAct("journal.add", { text: r }, cmdSay) },
  { w: "note", hint: "a note in the inbox", run: (r) => tdAct("note.capture", { text: r }, cmdSay) },
  { w: "remind", hint: "remind 18:30 call mum · remind in 20m tea", run: (r) => { const m = r.match(REM_WHEN);
    return m ? tdAct("reminder.add", { when: m[1], what: m[2] }, cmdSay) : cmdSay("Time first: remind 18:30 call mum", true); } },
  { w: "due", hint: "due essay draft fri 17:00", run: (r) => { const m = r.match(DUE_WHEN);
    return m ? tdAct("deadline.add", { title: m[1], when: m[2] }, cmdSay) : cmdSay("End with when it's due: due essay draft fri 17:00", true); } },
  { w: "alarm", hint: "alarm 7:30 · alarm skip tomorrow · alarm off", run: (r) => { const s = r.match(/^skip\b\s*(.*)$/i);
    return s ? tdAct("alarm.skip", { day: s[1] || "tomorrow" }, cmdSay) : /^off$/i.test(r) ? tdAct("alarm.clear", {}, cmdSay) : tdAct("alarm.set", { when: r }, cmdSay); } },
  { w: "find", hint: "find a note by its name", run: (r) => { cmdClose(); findNote(); const s = $("#mind-search"); s.value = r;
    s.dispatchEvent(new Event("input")); s.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); } },
  { w: "open", hint: `open a page: ${Object.keys(TABS).join(", ")}`, run: (r) => { const p = pageOf(r);
    if (!p) return cmdSay(`Which page? ${Object.keys(TABS).join(", ")}`, true); cmdClose(); openPage(p); } },
  { w: "study", hint: "study on · study off: Study mode (Alt+M)", run: (r) => { const on = /^(on|start)$/i.test(r) ? true : /^(off|stop|end)$/i.test(r) ? false : null;
    if (on === null) return cmdSay("study on, or study off", true); cmdClose(); setStudy(on); } },
];
function cmdRows(v) {
  v = v.replace(/^j\s+/i, "journal ").replace(/^\.\s*(?=\S)/, "note ").replace(/^!\s*(?=\S)/, "remind ");
  if (!v.trim()) return VERBS.map((verb) => ({ verb, rest: "" }));
  const m = v.trimStart().match(/^(\S+)(\s+([\s\S]*))?$/), w = m[1].toLowerCase(), rest = (m[3] || "").trim();
  const exact = VERBS.find((x) => x.w === w);
  if (exact && m[2] !== undefined) return [{ verb: exact, rest }];
  const pre = m[2] === undefined ? VERBS.filter((x) => x.w.startsWith(w) && (x.w !== "ask" || w === "ask")) : [];
  return [...pre.map((verb) => ({ verb, rest: "" })), { verb: VERBS[0], rest: v.trim() }];
}
function cmdDraw() {
  CMD.rows = cmdRows($("#cmdk-in").value); CMD.sel = clamp(CMD.sel, 0, CMD.rows.length - 1);
  $("#cmdk-list").innerHTML = CMD.rows.map((r, i) => `<li role="option" data-i="${i}" class="${i === CMD.sel ? "on" : ""}"><b>${r.verb.w}</b>${esc(r.rest || r.verb.hint)}</li>`).join("");
}
function cmdOpen() {
  const box = $("#cmdk"), inp = $("#cmdk-in");
  box.classList.remove("hidden"); inp.value = ""; CMD.sel = 0; cmdSay(""); cmdDraw(); inp.focus();
}
function cmdClose() { $("#cmdk").classList.add("hidden"); if (document.activeElement === $("#cmdk-in")) $("#cmdk-in").blur(); }
// a bare word is completed ("re" → "remind "); with something after it, it runs, and the line clears for the next
async function cmdGo(i = CMD.sel) {
  const row = CMD.rows[i], inp = $("#cmdk-in"); if (!row) return;
  if (!row.rest) { inp.value = row.verb.w + " "; CMD.sel = 0; cmdDraw(); cmdSay(row.verb.hint); inp.focus(); return; }
  inp.value = ""; cmdDraw();
  await row.verb.run(row.rest);
}
window.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey || e.code !== "KeyK" || inTerm(e.target)) return;
  e.preventDefault(); e.stopPropagation();
  if ($("#cmdk").classList.contains("hidden")) cmdOpen(); else cmdClose();
}, true);
(() => {
  const inp = $("#cmdk-in"), list = $("#cmdk-list");
  inp.addEventListener("input", () => { CMD.sel = 0; cmdDraw(); });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cmdClose(); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); CMD.sel += e.key === "ArrowDown" ? 1 : -1; cmdDraw(); }
    else if (e.key === "Tab") { const r = CMD.rows[CMD.sel]; if (r && r.verb.w !== "ask") { e.preventDefault(); inp.value = r.verb.w + " " + r.rest; cmdDraw(); } }
    else if (e.key === "Enter") { e.preventDefault(); cmdGo(); }
  });
  list.addEventListener("mousedown", (e) => { const li = e.target.closest("li"); if (li) { e.preventDefault(); cmdGo(Number(li.dataset.i)); } });
  document.addEventListener("mousedown", (e) => { if (!e.target.closest("#cmdk")) cmdClose(); });
})();
// ? : what the board shows (the cells, the nerves, the notes' colours, the keys); ? again or Esc closes it
window.addEventListener("keydown", (e) => {
  const g = $("#guide"), typing = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) || inTerm(e.target);
  if (e.key === "?" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); g.classList.toggle("hidden"); }
  else if (e.key === "Escape" && !g.classList.contains("hidden")) { e.preventDefault(); e.stopImmediatePropagation(); g.classList.add("hidden"); }
}, true);
document.addEventListener("mousedown", (e) => { if (!e.target.closest("#guide")) $("#guide").classList.add("hidden"); });
// after the window or a pane changes size: STATUS shows as many processes as fit, the terminal fills its pane
function refit() {
  if (DENSE && last) renderStatus(last);
  const showing = DENSE ? TERM.list.some((t) => t.name === dtab) && paneShown("terminal") : tab === "terminals";
  if (showing && TERM.shown && TERM.xs[TERM.shown]) try { TERM.xs[TERM.shown].fit.fit(); } catch { /* hidden */ }
}
window.addEventListener("resize", () => { applyLayout(); refit(); });

(function main() {
  body = new Board($("#body")); mind = new Notes($("#mind"));
  try { tab = localStorage.getItem("kurooto.dash.tab") || "activity"; dtab = localStorage.getItem("kurooto.dash.dtab") || "kurooto"; } catch { /* fine */ }
  if (!TABS[tab] && tab !== "terminals") tab = "activity";
  if (DLABEL[dtab]) dtab = "kurooto"; // 0.5.0 kept the pages in the terminal pane: they open over the board now
  const asked = location.hash.slice(1); // e.g. /#about, the link /aboutme sends
  if (TABS[asked]) tab = asked;
  loadLook();
  api("setup").then(setupLeft).catch(() => {}); // an older Kurooto: the plain setup link
  applyDesign(document.body.dataset.design);
  // the typeface arrives after the first drawing: measure the words again (the cells' labels, the STATUS columns)
  if (document.fonts) document.fonts.addEventListener("loadingdone", () => { body.widths.clear(); SB.built = false; if (last) renderStatus(last); });
  api("events").then((r) => { for (const e of (r.events || []).reverse()) feed.push(e); if (current() === "activity") renderTab(); }).catch(() => {});
  applyLayout(true);
  if (document.body.dataset.study === "on") setStudy(true, false, false); // look.study_mode: as it was left
  if (DENSE && DLABEL[asked]) openPage(asked);
  refreshTerms().then(() => { if (DENSE && !PAGE && TERM.list.some((t) => t.name === dtab)) showDense(dtab); else if (!DENSE && tab === "terminals") showTab("terminals"); });
  setInterval(refreshTerms, 20000);
  setInterval(() => { if (DENSE) clockTick(); }, 1000);
  connect();
  let lastT = 0;
  const frame = (ts) => { requestAnimationFrame(frame); if (document.hidden || ts - lastT < (LIGHT ? 33 : 16)) return; lastT = ts;
    const t = ts / 1000; // only what's on screen is drawn (a hidden pane, or one under a page, waits)
    if (paneShown("systems")) try { body.draw(t); } catch (e) { console.error(e); }
    if (paneShown("notes")) try { mind.step(); mind.draw(); } catch (e) { console.error(e); } };
  requestAnimationFrame(frame);
})();
