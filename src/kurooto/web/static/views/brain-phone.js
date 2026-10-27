// The phone app's Brain (0.8.10): hosts the dashboard's Brain console (brainconsole.js, written by the brain-console
// part to run here too) in the Android app's WebView. The app (ViewsPane, mode "brain") hands in its sealed copy with
// KurootoBrain.take(text): {mode: "brain", snap: the "brain" copy | null, computer, reach, off, palette, demo}.
// brainconsole.js is expected to define window.brainConsoleMount(host, {phone: true, palette}) -> {update(data)};
// until it does (or while this phone has no copy), the page says so plainly. Read-only: nothing here talks to anything.
"use strict";
(function () {
  const KEYS = ["bg", "fg", "accent", "lav", "pink", "peach", "sand", "rose", "bad", "panel"];
  let view = null, made = -1;
  function note(text) {
    const el = document.getElementById("empty");
    el.textContent = text || "";
    el.classList.toggle("hidden", !text);
  }
  function palette(p) {
    if (!p) return;
    for (const k of KEYS) if (/^#[0-9a-f]{6}$/i.test(p[k] || "")) PAL[k] = p[k].toLowerCase();
    PAL.dim = mix(PAL.fg, PAL.bg, 0.5);
    const root = document.documentElement.style;
    root.setProperty("--bg", PAL.bg); root.setProperty("--fg", PAL.fg); root.setProperty("--dim", PAL.dim);
    root.setProperty("--panel", PAL.panel); root.setProperty("--accent", PAL.accent); root.setProperty("--bad", PAL.bad);
  }
  function take(text) {
    let d;
    try { d = JSON.parse(text); } catch (err) { return false; }
    palette(d.palette);
    if (typeof window.brainConsoleMount !== "function") { note("The Brain console comes with this update."); return true; }
    const s = d.snap && typeof d.snap === "object" ? d.snap : null;
    if (!s) {
      note(d.off ? "Turned off on your computer: on its dashboard, Phone → Show on the phone."
        : d.reach === false ? "Can't reach your call line, and there's no copy on this phone yet."
          : "Nothing here yet. Your computer sends the Brain when it's on and Show on the phone is on.");
      return true;
    }
    note("");
    if (!view) view = window.brainConsoleMount(document.getElementById("brain"), { phone: true, palette: d.palette || {} });
    if (view && s.made !== made) { made = s.made; view.update(s); }
    return true;
  }
  window.KurootoBrain = { take };
})();
