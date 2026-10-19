// The About-you profile editor (about-me/profile.md in your notes), on the setup page and the dashboard's About you
// tab. Save keeps the previous version beside it; Revert goes back to what's saved; "Preview In brief" shows exactly
// the part that goes along with every AI request (worked out by Kurooto itself, so it's the real thing).
"use strict";
function aboutEditor(host, call, onSaved) {
  const make = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const ta = make("textarea", "about-ed");
  ta.rows = 18; ta.spellcheck = false;
  const save = make("button", "primary", "Save"), revert = make("button", "", "Revert");
  const brief = make("pre", "about-brief"), warn = make("p", "bad"), msg = make("p", "about-msg");
  const ed = { dirty: false, updated: "", load };
  let saved = "", timer = null;
  const dirty = (d) => { ed.dirty = d; save.disabled = !d; revert.disabled = !d; };
  const show = (r) => {
    brief.textContent = r.brief || "(nothing)";
    warn.textContent = r.warning || "";
  };
  async function preview() { show(await call("aboutyou/preview", { text: ta.value })); }
  async function load() {
    const r = await call("aboutyou/profile");
    if (ed.dirty) return r; // they started typing while it loaded: what they type wins
    saved = r.text || ""; ta.value = saved; ed.updated = r.updated; dirty(false); show(r);
    return r;
  }
  ta.addEventListener("input", () => { dirty(ta.value !== saved); clearTimeout(timer); timer = setTimeout(preview, 400); });
  save.addEventListener("click", async () => {
    save.disabled = true;
    const r = await call("aboutyou/profile", { text: ta.value });
    if (!r.ok) { msg.textContent = r.error; msg.className = "about-msg bad"; dirty(true); return; }
    saved = r.text; ta.value = saved; ed.updated = r.updated; dirty(false); show(r);
    msg.textContent = r.changed ? "Saved. The previous version is kept beside it (profile-<date>.md)." : "No changes to save.";
    msg.className = "about-msg ok";
    if (onSaved) onSaved(r);
  });
  revert.addEventListener("click", () => { ta.value = saved; dirty(false); preview(); msg.textContent = ""; });
  const row = make("div", "about-row"); row.append(save, revert);
  host.replaceChildren(ta, row, msg, make("p", "about-label", "Preview In brief: what goes along with every AI request"), brief, warn);
  load();
  return ed;
}
