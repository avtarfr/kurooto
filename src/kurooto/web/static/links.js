// Links to other sites open in this computer's default browser (Settings → look.links_in = "default"), not in the
// window showing this page: that may be another browser's app window (`google-chrome --app=…`) while your default is
// Firefox, Zen or anything else. A click on a link to another site, or window.open for a sign-in page, goes to
// POST /api/open-url, which hands it to the system (core/opener.py); when that fails, the page opens it itself as
// before. This computer's own pages (127.0.0.1 and localhost, like the Google sign-in's return page) stay here, and
// so do clicks with Ctrl, Shift, Alt or ⌘ held (the browser's own ways to open a link). look.links_in = "here" turns
// it off. Every Kurooto page gets this file (web/server.py, fill).
"use strict";
(() => {
  const meta = (n) => (document.querySelector(`meta[name="${n}"]`) || {}).content || "";
  const here = () => meta("kurooto-links") === "here";
  const LOCAL = /^(127\.\d+\.\d+\.\d+|localhost|\[::1\])$/i;
  const outside = (url) => { // the full address of a page on another site, else null
    let u; try { u = new URL(url, location.href); } catch { return null; }
    return /^https?:$/.test(u.protocol) && u.origin !== location.origin && !LOCAL.test(u.hostname) ? u.href : null;
  };
  const native = window.open.bind(window);
  async function send(url) {
    try {
      const r = await fetch("/api/open-url", { method: "POST", headers: { "X-Kurooto": meta("kurooto-token"), "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      return !!(await r.json()).ok;
    } catch { return false; }
  }
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || here()) return;
    const a = e.target.closest && e.target.closest("a[href]");
    const url = a && !a.hasAttribute("download") ? outside(a.getAttribute("href")) : null;
    if (!url) return;
    e.preventDefault();
    send(url).then((ok) => { if (ok) return; if (a.target && a.target !== "_self") native(url, a.target, "noopener"); else location.assign(url); });
  });
  // window.open(…) for a sign-in page: the same; it gives null back, as a blocked popup does (the pages show a link)
  window.open = (url, target, features) => {
    const out = url && !here() ? outside(String(url)) : null;
    if (!out) return native(url, target, features);
    send(out).then((ok) => { if (!ok) native(out, target || "_blank", features || "noopener"); });
    return null;
  };
})();
