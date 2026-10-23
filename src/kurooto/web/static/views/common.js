// Shared by the dashboard (home.js) and the phone app's views (phone.html): the canvases' palette, fonts and small
// helpers. Plain scripts, no modules: each file's top-level names are shared with the others on the page, so this one
// is loaded first. The phone app runs these in its WebView from Android 6 on, so they keep to what Chrome 58 can
// parse (no ?. or ??, no object spread, no catch without a binding); tests/unit/test_views.py checks that.
"use strict";
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const TAU = Math.PI * 2;
const MONO = '"JetBrains Mono", "Cascadia Mono", "SF Mono", Consolas, monospace'; // terminals, code, paths
const SANS = '"Public Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'; // static/fonts/
let NEW = document.body.dataset.design !== "classic"; // look.design
let FONT = MONO, FSC = 1; // the canvases' words and their scale: set by useDesign() below
// a canvas font: the new design's sans-serif is set a little larger than the classic monospace
const cf = (px, weight = "", fam = FONT) => `${weight ? weight + " " : ""}${Math.round(px * FSC * 2) / 2}px ${fam}`;
function useDesign() { NEW = document.body.dataset.design !== "classic"; FONT = NEW ? SANS : MONO; FSC = NEW ? 1.12 : 1; }
useDesign();
// the canvases' colours are the page's palette (style.css: "kuro" by default, "rose"; the system palette and the named
// themes come as a <style> from core/palette.py; the phone app hands in its own: phone.js)
const css = (name, fallback) => { const v = getComputedStyle(document.body).getPropertyValue(name).trim(); return /^#[0-9a-f]{6}$/i.test(v) ? v : fallback; };
const PAL = { bg: css("--bg", "#0b0f0a"), fg: css("--fg", "#dad3c8"), accent: css("--accent-text", "#a6c07a"), lav: css("--lav", "#8dbdb3"),
  pink: css("--pink", "#d6967a"), peach: css("--peach", "#ddb866"), sand: css("--sand", "#e4d8b4"), rose: css("--rose", "#b9a6cc"),
  bad: css("--bad", "#e8735a"), panel: css("--panel", "#151b12") };
const hexRgb = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const mix = (a, b, t) => "#" + hexRgb(a).map((v, i) => Math.round(v + (hexRgb(b)[i] - v) * t).toString(16).padStart(2, "0")).join("");
const RGBA = new Map(); // the canvases ask for the same few colours hundreds of times a frame: each string is made once
const rgba = (h, a) => { const k = h + Math.round(a * 200); let v = RGBA.get(k);
  if (v === undefined) { const [r, g, b] = hexRgb(h); v = `rgba(${r},${g},${b},${Math.round(a * 200) / 200})`; if (RGBA.size > 5000) RGBA.clear(); RGBA.set(k, v); } return v; };
PAL.dim = mix(PAL.fg, PAL.bg, 0.5); PAL.line = mix(PAL.lav, PAL.bg, 0.62);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ago = (sec) => { if (sec == null || !isFinite(sec)) return "—"; sec = Math.max(0, sec); if (sec < 60) return `${Math.round(sec)}s`; if (sec < 3600) return `${Math.round(sec / 60)}m`; if (sec < 86400) return `${Math.floor(sec / 3600)}h${String(Math.floor((sec % 3600) / 60)).padStart(2, "0")}`; return `${Math.floor(sec / 86400)}d`; };
const bytes = (n) => { if (!n) return "0"; const u = ["B", "K", "M", "G", "T"]; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return `${n.toFixed(i > 1 ? 1 : 0)}${u[i]}`; };
const hm = (ts) => new Date(ts * 1000).toTimeString().slice(0, 5);
let LIGHT = false; // lighter drawing on modest computers (hardware profile "light") or with reduced motion
let DENSE = false; // the dense board (home.js's applyLayout; the phone's views are never dense)
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
// The corner panels and legends are folded to their first line, for a calmer board: one opens while the pointer is
// over it, and L opens (or folds) them all (home.js remembers the choice in this browser).
let LEGENDS = false;
const inside = (m, r, pad = 6) => !!(m && r && m.x >= r.x0 - pad && m.x <= r.x1 + pad && m.y >= r.y0 - pad && m.y <= r.y1 + pad);
// text on a plate of background, so it stays readable over whatever moves behind it
function say(ctx, s, x, y, col, align = "left", font = cf(9)) {
  ctx.font = font; ctx.textAlign = align; ctx.textBaseline = "alphabetic";
  const wd = ctx.measureText(s).width, x0 = align === "right" ? x - wd : align === "center" ? x - wd / 2 : x;
  ctx.fillStyle = rgba(PAL.bg, 0.72); ctx.fillRect(x0 - 2, y - 9 * FSC, wd + 4, 12 * FSC); ctx.fillStyle = col; ctx.fillText(s, x, y);
  return wd;
}
