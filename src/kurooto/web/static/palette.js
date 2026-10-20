// The pages' colours, kept current: with look.palette = system they follow this computer's accent colour and light
// or dark mode (core/palette.py). Every 30 seconds, and when the page comes back into view, it asks /api/look and
// swaps the colours in place if they changed; a "kurooto:palette" event then tells the page (e.g. to redraw canvases).
// window.kurootoLook.refresh() asks at once (after a change in Settings).
"use strict";
(() => {
  const meta = document.querySelector('meta[name="kurooto-token"]');
  const style = document.getElementById("kurooto-palette");
  if (!meta || !style) return;
  let busy = false;
  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      const r = await fetch("/api/look", { headers: { "X-Kurooto": meta.content } });
      if (!r.ok) return;
      const look = await r.json();
      const root = document.documentElement;
      if (root.dataset.palette === look.palette && style.textContent === look.css) return;
      root.dataset.palette = look.palette;
      style.textContent = look.css;
      window.dispatchEvent(new CustomEvent("kurooto:palette", { detail: look }));
    } catch { /* Kurooto is restarting: the next round tries again */ } finally { busy = false; }
  }
  window.kurootoLook = { refresh };
  setInterval(() => { if (!document.hidden) refresh(); }, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
