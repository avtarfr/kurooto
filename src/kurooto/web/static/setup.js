// The setup wizard: six short steps, each saved as you go, so closing the page and coming back is fine.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const STEPS = ["you", "computer", "brain", "about", "features", "telegram", "finish"];
const LABELS = ["You", "Computer", "AI", "About you", "Features", "Telegram", "Done"];
let state = null;
let step = 0;
let chosen = new Set();

async function api(path, body) {
  const r = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}

function show(i) {
  step = Math.max(0, Math.min(STEPS.length - 1, i));
  $$("section").forEach((s) => s.classList.toggle("on", s.dataset.step === STEPS[step]));
  $("#steps").replaceChildren(...LABELS.map((l, j) => el("li", { class: j === step ? "on" : j < step ? "done" : "" }, l)));
  try { localStorage.setItem("kurooto.setup.step", String(step)); } catch { /* private mode */ }
  ({ computer: renderComputer, brain: renderBrains, about: renderAbout, features: renderFeatures, telegram: renderTelegram, finish: renderFinish }[STEPS[step]] || (() => {}))();
  window.scrollTo(0, 0);
}

async function refresh() { state = await api("state"); }

// ---------------------------------------------------------------------------------------------- you
async function saveYou() {
  await api("you", { name: $("#name").value, timezone: $("#tz").value, assistant_name: $("#aname").value || "Kurooto" });
}

// ------------------------------------------------------------------------------------------ computer
function renderComputer() {
  const hw = state.hardware, m = hw.machine, r = hw.recommendation;
  $("#hw-summary").textContent = r.summary;
  const gpu = m.gpus.map((g) => g.name + (g.vram_gb ? ` (${g.vram_gb} GB)` : "")).join(", ") || "none Kurooto can use";
  $("#hw-chips").replaceChildren(
    chip("System", `${m.os} ${m.os_version}`), chip("Processor", m.cpu), chip("Memory", `${m.ram_gb} GB`),
    chip("Graphics", gpu), chip("Free space", `${m.disk_free_gb} GB`), chip("Profile", r.profile),
  );
  const reco = r.local_models.length
    ? r.local_models.map((x) => el("li", {}, `${x.tag} (${x.size_gb} GB): ${x.use}`))
    : [el("li", {}, "No local AI models: everything runs on the AI service you pick next.")];
  reco.push(el("li", {}, r.reduced_motion ? "A lighter dashboard (fewer animations)." : "The full dashboard."));
  $("#hw-reco").replaceChildren(...reco);
  const room = state.room;
  const notes = [...r.notes];
  notes.push(room.ok ? `Disk: ${room.free_gb} GB free; the recommended setup needs about ${room.need_gb} GB.`
    : `Disk: only ${room.free_gb} GB free. Kurooto keeps ${room.margin_gb} GB spare, so it will skip local models unless you free some space.`);
  $("#hw-notes").textContent = notes.join(" ");
  renderPower();
}

// Laptops: what to do on battery. Saved at once; Settings → power.on_battery changes it later.
const POWER = [
  ["saver", "★ Save battery", "Telegram keeps working (messages, reminders, answers); local AI models and other heavy work wait until it's plugged in."],
  ["normal", "Keep everything running", "As if it were plugged in."],
  ["pause", "Pause everything", "Telegram only says \"paused\" and keeps what you send; it all catches up when you plug in."],
];
function renderPower() {
  const p = state.power, box = $("#power-choice");
  if (!p || !p.laptop) { box.replaceChildren(); return; }
  const cur = p.on_battery || "saver";
  box.replaceChildren(el("h2", {}, "When this laptop is on battery"), el("div", { class: "cards" }, ...POWER.map(([v, label, why]) =>
    el("button", { class: "card" + (v === cur ? " on" : ""), onclick: async () => {
      await api("settings", { key: "power.on_battery", value: v }); state.power.on_battery = v; renderPower();
    } }, el("h3", {}, label), el("p", {}, why)))),
    el("p", { class: "note" }, "You can also pause it by hand (/pause on Telegram), or turn it off completely from the dashboard."));
}
function chip(k, v) { return el("span", { class: "chip" }, `${k}: `, el("b", {}, v)); }

// --------------------------------------------------------------------------------------------- brain
function renderBrains() {
  if (!state.brain.main) state.brain.main = state.brains.find((b) => b.recommended).id; // the ★ pick until you choose
  const main = state.brain.main;
  $("#brains").replaceChildren(...state.brains.map((b) => el("button", {
    class: "card" + (b.id === main ? " on" : ""), onclick: () => { state.brain.main = b.id; renderBrains(); },
  }, b.recommended ? el("div", { class: "star" }, "★ RECOMMENDED") : null, el("h3", {}, b.label), el("p", {}, b.why),
    b.ready ? el("div", { class: "state" }, "ready") : null)));
  renderBrainPanel(main);
}

function logBox() { return el("div", { class: "log", id: "log" }); }

// log text with its web addresses as links (e.g. the Cloudflare sign-in page)
function linkify(text) {
  return text.split(/(https?:\/\/[^\s<>"]+)/g).map((part, i) =>
    i % 2 ? el("a", { href: part, target: "_blank", rel: "noopener" }, part.length > 90 ? part.slice(0, 87) + "…" : part) : document.createTextNode(part));
}

async function watchInstall(done) {
  const log = $("#log");
  for (;;) {
    const p = await api("progress");
    if (log) log.replaceChildren(...linkify(p.lines.map((l) => l.line).join("\n")));
    if (!p.installing) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  await refresh();
  done && done();
}

function testButton(which) {
  const out = el("p", {});
  const btn = el("button", { class: "primary", onclick: async () => {
    btn.disabled = true; out.textContent = "Asking it to reply…"; out.className = "";
    await api("brain", { main: which });
    const r = await api("brain/test", { which });
    out.textContent = r.message; out.className = r.ok ? "ok" : "bad"; btn.disabled = false;
    if (r.ok) await refresh();
  } }, "Test it");
  return [btn, out];
}

// What a Gemini key's free tier means, said plainly wherever the wizard asks for one.
const GEMINI_TERMS = "On the free tier, Google may use what you send and what it answers to improve its products, and human " +
  "reviewers may read it. You must be 18 or older. In the EEA, the UK and Switzerland you need a paid key (billing on). " +
  "Phone calls and voice notes always go through Gemini, whichever AI answers your messages. If you don't want that, " +
  "use a paid key.";
function geminiTerms() { return el("p", { class: "note" }, GEMINI_TERMS); }

const AGY_NOTE = "Kurooto runs Google's official agy program on this computer, signed in as you, and never touches its " +
  "sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to " +
  "your Google account. For tools like Kurooto, Google recommends a Gemini API key.";

function renderBrainPanel(which) {
  const panel = $("#brain-panel");
  const box = el("div", { class: "box" });
  if (which === "agy") {
    const installed = state.prereqs.agy.installed;
    box.append(el("p", {}, installed ? "agy is installed." : "agy isn't installed yet. Kurooto installs it from Google's official installer."));
    if (!installed) box.append(el("button", { class: "primary", onclick: async (e) => {
      e.target.disabled = true; await api("prereqs/install", { keys: ["agy"] }); watchInstall(() => renderBrainPanel("agy"));
    } }, "Install agy"), logBox());
    else box.append(
      el("p", {}, "Sign in once with your Google account: a window opens, follow it, then close it."),
      el("button", { onclick: async () => { const r = await api("prereqs/signin", { key: "agy" }); alert(r.message); } }, "Open the sign-in window"),
      el("p", {}, "Then check it works. The test also lets agy use Kurooto's tools (reminders, notes, calls…): " +
        "this adds Kurooto to agy's settings; a backup is kept."), ...testButton("agy"));
    box.append(el("p", { class: "note" }, AGY_NOTE));
  } else if (which === "codex" || which === "claude") {
    const key = which, label = which === "codex" ? "Codex" : "Claude Code";
    const installed = state.prereqs[key].installed;
    box.append(el("p", {}, installed ? `${label} is installed.` : `${label} isn't installed yet. Kurooto installs it from the official source.`));
    if (!installed) box.append(el("button", { class: "primary", onclick: async (e) => {
      e.target.disabled = true; await api("prereqs/install", { keys: [key] }); watchInstall(() => renderBrainPanel(which));
    } }, `Install ${label}`), logBox());
    else box.append(
      el("p", {}, `Sign in once with your ${which === "codex" ? "ChatGPT" : "Claude"} account: a window opens, follow it, then close it.`),
      el("button", { onclick: async () => { const r = await api("prereqs/signin", { key }); alert(r.message); } }, "Open the sign-in window"),
      el("p", {}, "Then check it works:"), ...testButton(which));
  } else if (which === "gemini") {
    const key = el("input", { placeholder: "Paste your Gemini API key", autocomplete: "off", spellcheck: "false" });
    box.append(
      el("p", {}, "Get a free key: ", el("a", { href: "https://aistudio.google.com/apikey", target: "_blank", rel: "noopener" }, "Google AI Studio → Create API key"), "."),
      geminiTerms(),
      key, el("p", {}), el("button", { onclick: async () => { await api("brain", { main: "gemini", key: key.value }); } }, "Save"), " ",
      ...testButton("gemini"));
  } else if (which === "freellmapi") { // set up with an earlier version: no longer offered, but it keeps working
    box.append(el("p", {}, "This AI was set up with an earlier version of Kurooto and keeps working. To change it, pick another one above."),
      ...testButton("freellmapi"));
  } else if (which === "ollama") {
    box.append(el("p", {}, "Local models are private and work offline, but they're much weaker than the services above, and need a good graphics card. Kurooto uses them best as a helper next to another AI."),
      el("p", {}, state.prereqs.ollama.installed ? "Ollama is installed." : "Ollama isn't installed."));
    if (!state.prereqs.ollama.installed) box.append(el("button", { onclick: async (e) => {
      e.target.disabled = true; await api("prereqs/install", { keys: ["ollama"] }); watchInstall(() => renderBrainPanel("ollama"));
    } }, "Install Ollama"), logBox());
  } else {
    const url = el("input", { placeholder: "Address, e.g. https://api.example.com/v1" });
    const key = el("input", { placeholder: "Key", autocomplete: "off" });
    const model = el("input", { placeholder: "Model name" });
    box.append(url, key, model, el("p", {}),
      el("button", { onclick: async () => { await api("brain", { main: "custom", base_url: url.value, key: key.value, models: { low: model.value, medium: model.value, high: model.value } }); } }, "Save"),
      " ", ...testButton("custom"));
  }
  panel.replaceChildren(box);
}

// ----------------------------------------------------------------------------------------- about you
// Prompts to run in their other AI accounts, the reports they bring back, and the profile built from them.
let ayTimer = null, ayEd = null;
async function renderAbout() {
  const src = $("#ay-source").value.trim();
  const a = await api(`aboutyou?source=${encodeURIComponent(src)}`);
  const card = (key, title, why) => {
    const text = a.prompts[key], out = el("span", { class: "note" });
    const pre = el("pre", { class: "prompt", hidden: true }, text);
    return el("div", { class: "card" }, el("h3", {}, title), el("p", {}, why),
      el("div", { class: "row" },
        el("button", { class: "primary", onclick: async () => {
          try { await navigator.clipboard.writeText(text); out.textContent = " Copied. Paste it into a new chat."; }
          catch { pre.hidden = false; out.textContent = " Select the text below and copy it."; }
        } }, "Copy the prompt"),
        el("button", { onclick: () => { pre.hidden = !pre.hidden; } }, "Show it"), out),
      pre);
  };
  $("#ay-prompts").replaceChildren(
    card("main", "Your main AI", "For the AI account you use most: the fullest audit."),
    card("other", "Every other account", "For each of your other AI accounts, one at a time."));
  $("#ay-list").replaceChildren(...a.reports.map((r) => el("li", {}, `${r.label} (${Math.round(r.chars / 1000)}k characters, ${r.added}) `,
    el("button", { onclick: async () => { await api("aboutyou/remove", { id: r.id }); renderAbout(); } }, "remove"))));
  const p = a.profile, panel = $("#ay-panel");
  const build = el("button", { class: "primary", disabled: !a.reports.length || p.building, onclick: async () => {
    if (ayEd && ayEd.dirty && !confirm("Your changes in the editor aren't saved. Build the profile anyway? (Save them first to keep them.)")) return;
    let r = await api("aboutyou/merge", {});
    if (r.edited && confirm(r.error)) r = await api("aboutyou/merge", { replace: true }); // changed since it was built
    $("#ay-msg").textContent = r.ok ? r.message : r.edited ? "Not built again: your changes stay." : r.error;
    $("#ay-msg").className = r.ok ? "ok" : "bad";
    renderAbout();
  } }, p.exists ? "Build my profile again" : "Build my profile");
  panel.replaceChildren(el("div", { class: "box" },
    el("p", {}, a.reports.length ? `${a.reports.length} report(s) so far.` : "No reports yet."),
    build,
    p.building ? el("p", {}, "Building your profile… (this page updates by itself)") : null,
    p.exists ? el("p", { class: "ok" }, `✓ Your profile: ${p.path} (updated ${p.updated}${p.edited ? ", with your changes" : ""}). Read it and fix anything that's off, right here:`) : null));
  // the editor (aboutme.js) lives outside the panel, so this page refreshing itself never loses what you're typing
  if (!p.exists) { $("#ay-editor").replaceChildren(); ayEd = null; }
  else if (!ayEd) ayEd = aboutEditor($("#ay-editor"), api);
  else if (!ayEd.dirty) ayEd.load();
  clearTimeout(ayTimer);
  if (p.building && STEPS[step] === "about") ayTimer = setTimeout(renderAbout, 5000);
}

async function addReport(label, text) {
  const r = await api("aboutyou/add", { label, text });
  $("#ay-msg").textContent = r.ok ? `Added: ${r.label}.` : r.error;
  $("#ay-msg").className = r.ok ? "ok" : "bad";
  return r.ok;
}

// ------------------------------------------------------------------------------------------ features
const NEEDS_GEMINI = ["calls", "voice_notes", "alarm"];
function renderFeatures() {
  if (!chosen.size && !renderFeatures.seeded) state.modules.filter((m) => m.on || (restored ? restored.includes(m.id) : m.starter)).forEach((m) => chosen.add(m.id));
  renderFeatures.seeded = true;  // only the first time: unticking everything must stay unticked
  $("#features").replaceChildren(...state.modules.map((m) => {
    const box = el("input", { type: "checkbox", checked: chosen.has(m.id), onchange: (e) => {
      e.target.checked ? chosen.add(m.id) : chosen.delete(m.id);
      $$(".preset").forEach((p) => p.classList.toggle("on", p.dataset.preset === "custom"));
      renderFeatures();  // the card's highlight and its setup form follow at once
    } });
    return el("div", { class: "card" + (chosen.has(m.id) ? " on" : ""), onclick: (e) => {  // the whole card ticks it
      if (e.target.closest("a, button, input, textarea, select, label, .box")) return;
      box.checked = !box.checked;
      box.dispatchEvent(new Event("change"));
    } },
      el("label", {}, box, el("h3", {}, m.title)), el("p", {}, m.description),
      m.starter ? el("div", { class: "star" }, "★ in Starter") : null, el("div", { class: "privacy" }, m.privacy),
      m.setup && !m.ready && m.why ? el("p", { class: "note" }, m.why[0].toUpperCase() + m.why.slice(1) + ".") : null,
      m.form && chosen.has(m.id) && !m.ready ? setupForm(m) : null,
      m.form && chosen.has(m.id) && m.ready ? el("p", { class: "ok" }, "✓ Set up") : null,
      m.id === "calls" && chosen.has(m.id) ? callsBox(m) : null,
      m.id === keyCard() ? keyBox() : null);
  }));
  renderKeyBox();
}

// The Gemini key box goes right under the first ticked card that needs it.
function keyCard() {
  if (state.keys.gemini) return null;
  const m = state.modules.find((x) => NEEDS_GEMINI.includes(x.id) && chosen.has(x.id));
  return m ? m.id : null;
}

// Phone calls: what it needs, in order, and the call line set up right here (not only when you press Done).
function callsBox(m) {
  const key = state.keys.gemini, out = el("div", {});
  const btn = el("button", { class: "primary", disabled: !key || m.ready, onclick: async () => {
    btn.disabled = true;
    out.replaceChildren(el("p", {}, "Setting up your call line on Cloudflare. A Cloudflare sign-in page opens (its link is in the log too): sign in or make a free account, then come back."), logBox());
    const r = await api("modules/setup", { id: "calls" });
    if (r.started === false) { out.replaceChildren(el("p", { class: "bad" }, r.message)); btn.disabled = false; return; }
    await watchInstall();
    const c = state.modules.find((x) => x.id === "calls");
    if (c && c.ready) { renderFeatures(); return; }
    out.append(el("p", { class: "bad" }, `Not ready yet: ${c ? c.why : "it didn't finish"}. Press Set up now to try again.`));
    btn.disabled = false;
  } }, "Set up now");
  return el("div", { class: "box", onclick: (e) => e.stopPropagation() },
    el("p", {}, "Phone calls need, in this order:"),
    el("ol", {},
      el("li", {}, "a free Gemini API key (needed even if agy or another AI answers your messages: calls talk through Gemini Live)", key ? " ✓" : ""),
      el("li", {}, "a free Cloudflare account: Kurooto makes your own call line on it", m.ready ? " ✓" : ""),
      el("li", {}, "then pair your phone (after Done)")),
    m.ready ? el("p", { class: "ok" }, "✓ Your call line is set up. Press Done at the end: then you pair your phone.")
      : el("p", {}, btn, key ? "" : el("span", { class: "note" }, " First save your Gemini key in the box below.")),
    out);
}

// A feature's own details (an iCal link, a repository and token, a Google client): shown when it's ticked.
function setupForm(m) {
  const inputs = {};
  const out = el("p", {});
  const fields = m.form.fields.map((f) => {
    const input = f.type === "textarea" ? el("textarea", { rows: 4, placeholder: f.placeholder || "", spellcheck: "false" })
      : el("input", { type: f.type === "password" ? "password" : "text", placeholder: f.placeholder || "", autocomplete: "off", spellcheck: "false" });
    inputs[f.name] = input;
    // a file to read into the box (Google's client JSON): chosen here instead of pasted
    const file = f.accept ? el("input", { type: "file", accept: f.accept, onchange: async (e) => {
      if (e.target.files[0]) input.value = await e.target.files[0].text();
    } }) : null;
    return el("label", {}, f.label, input, file);
  });
  const g = m.form;
  return el("div", { class: "box", onclick: (e) => e.stopPropagation() },
    el("p", {}, g.intro),
    g.steps ? el("ol", { class: "form-steps" }, ...g.steps.map((s) => el("li", {}, s))) : null,
    g.guide ? el("p", {}, el("a", { href: g.guide[1], target: "_blank", rel: "noopener" }, g.guide[0])) : null,
    ...(g.copy || []).map(([label, value]) => el("div", { class: "copy-row" }, el("span", { class: "note" }, `${label}: `),
      el("code", {}, value), el("button", { type: "button", onclick: (e) => copyValue(value, e.target) }, "Copy"))),
    el("p", { class: "note" }, ...g.links.flatMap(([label, href], i) => [i ? " · " : "", el("a", { href, target: "_blank", rel: "noopener" }, label)])),
    ...fields,
    el("button", { class: "primary", onclick: async () => {
      out.textContent = "Checking…"; out.className = "";
      const values = Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, v.value]));
      const r = await api("modules/configure", { id: m.id, values, enable: false });
      out.textContent = r.message; out.className = r.ok ? "ok" : "bad";
      if (r.ok) { state.modules = r.modules; }
      if (r.open) {
        try { window.open(r.open, "_blank", "noopener"); } catch { /* blocked: the link below always works */ }
        out.replaceChildren(signinLink(r.open), signinNote());
        out.className = "";
        waitReady(m.id, out);
      }
    } }, "Save"), out);
}

// Popup blockers stop a tab opened after waiting for Kurooto, so the sign-in is always a link you can press.
function signinLink(href) {
  return el("p", {}, el("a", { class: "button primary", href, target: "_blank", rel: "noopener" }, "Open Google sign-in"));
}
function signinNote() {
  return el("p", { class: "note" }, "After you approve, Google brings you back to this computer (a 127.0.0.1 page) that says 'Signed in with Google'. This card then turns to ✓ by itself.");
}

// Until the feature is ready (you signed in), look again every few seconds; then show it on the card.
const waiting = {};
async function waitReady(id, out) {
  const run = (waiting[id] = (waiting[id] || 0) + 1);
  for (let i = 0; i < 300 && run === waiting[id]; i++) {
    await new Promise((ok) => setTimeout(ok, 3000));
    let st;
    try { st = await api("state"); } catch { continue; }
    const m = st.modules.find((x) => x.id === id);
    if (m && m.ready) { state.modules = st.modules; out.replaceChildren(el("p", { class: "ok" }, "✓ Signed in.")); renderFeatures(); return; }
  }
}

// A value for another site's form (Google's Branding page): onto the clipboard, or selected if that isn't allowed.
function copyValue(value, button) {
  const done = () => { button.textContent = "Copied"; setTimeout(() => { button.textContent = "Copy"; }, 1600); };
  (navigator.clipboard ? navigator.clipboard.writeText(value) : Promise.reject()).then(done).catch(() => {
    const r = document.createRange(); r.selectNodeContents(button.previousSibling);
    getSelection().removeAllRanges(); getSelection().addRange(r); button.textContent = "Press Ctrl+C";
  });
}

// Phone calls, voice notes and the alarm use a free Gemini key (whichever AI answers your messages). The box sits
// under the first ticked card that needs it (keyCard); the old panel at the bottom stays empty.
function renderKeyBox() {
  $("#key-panel").replaceChildren();
}
function keyBox() {
  const key = el("input", { placeholder: "Paste your Gemini API key", autocomplete: "off", spellcheck: "false" });
  const out = el("p", {});
  return el("div", { class: "box", id: "gemini-box", onclick: (e) => e.stopPropagation() },
    el("p", {}, "Phone calls, voice notes and the alarm need a free Gemini API key, even if agy or another AI answers your messages (calls talk through Gemini Live). It takes a minute: open ",
      el("a", { href: "https://aistudio.google.com/apikey", target: "_blank", rel: "noopener" }, "Google AI Studio"),
      ", sign in with your Google account, tap Create API key, and paste it here."),
    geminiTerms(),
    el("div", { class: "row" }, key, el("button", { class: "primary", onclick: async () => {
      out.textContent = "Checking…"; out.className = "";
      const r = await api("keys/gemini", { key: key.value });
      if (r.ok) { state.keys.gemini = true; renderFeatures(); }
      else { out.textContent = r.error; out.className = "bad"; }
    } }, "Check")), out);
}

// After setup: pair a phone with the call line (QR code, or the link on the phone itself).
async function pairBox() {
  const box = el("div", { class: "box" }, el("p", {}, "Making a pairing code…"));
  const r = await api("phone/pair", {});
  if (!r.ok) { box.replaceChildren(el("p", { class: "bad" }, `Couldn't make a pairing code yet: ${r.error}. Try again from the dashboard's Phone tab in a minute.`)); return box; }
  const qr = el("div", { class: "qr" });
  qr.innerHTML = r.svg; // made by Kurooto from the link below
  box.replaceChildren(el("h3", {}, "Pair your phone"),
    el("p", {}, "Scan this with your phone. The page that opens has 1) Download the app (Android) or Add to Home Screen (iPhone), then 2) pairing. It works for 15 minutes (or send /phone to your bot and tap the link on your phone)."),
    qr, el("p", { class: "note" }, "Code: ", el("code", {}, r.code), " · ", el("a", { href: r.link, target: "_blank", rel: "noopener" }, "the link")));
  return box;
}

// ------------------------------------------------------------------------------------------ telegram
function renderTelegram() {
  const p = $("#tg-panel");
  if (state.telegram.paired) p.replaceChildren(el("div", { class: "box" }, el("p", { class: "ok" }, "✓ Telegram is connected. Your bot only answers you.")));
}

async function checkToken() {
  const p = $("#tg-panel");
  p.replaceChildren(el("p", {}, "Checking…"));
  let r;
  try { r = await api("telegram/token", { token: $("#tg-token").value }); }
  catch { p.replaceChildren(el("p", { class: "bad" }, "Lost touch with Kurooto: is it still running? Try again in a moment.")); return; }
  if (!r.ok) { p.replaceChildren(el("p", { class: "bad" }, r.error)); return; }
  showPairing(r);
}

// The one-time link, the message to send by hand if the link does nothing, and what Telegram says meanwhile.
let pairRun = 0;
function showPairing(r) {
  const p = $("#tg-panel"), run = ++pairRun;
  const msg = `/start ${r.code}`, copied = el("span", { class: "note" }), manual = el("code", {}, msg);
  const wait = el("p", { id: "tg-wait" }, "Waiting for you to press Start…"), fix = el("div", {});
  p.replaceChildren(el("div", { class: "box" },
    el("p", {}, `Found your bot @${r.bot}. Now tap this, then press Start in Telegram:`),
    el("a", { class: "big", href: r.link, target: "_blank", rel: "noopener" }, `Open @${r.bot}`),
    el("p", { class: "note" }, `If nothing happens, send this message to @${r.bot}: `, manual, " ",
      el("button", { onclick: async () => {
        try { await navigator.clipboard.writeText(msg); copied.textContent = " Copied."; }
        catch { getSelection().selectAllChildren(manual); copied.textContent = " Select it and copy it."; }
      } }, "Copy"), copied),
    wait, fix));
  pollPairing(run, wait, fix);
}

function newLinkButton(wait, fix) {
  fix.replaceChildren(el("button", { class: "primary", onclick: async () => {
    const n = await api("telegram/relink", {});
    if (n.ok) showPairing(n); else { wait.textContent = n.error; wait.className = "bad"; }
  } }, "Get a new link"));
}

async function pollPairing(run, wait, fix) {
  const deadline = Date.now() + 60 * 60 * 1000; // the link works for an hour
  let hinted = false; // a /start without the code came: keep saying what to send until something else happens
  while (run === pairRun && Date.now() < deadline) {
    let got;
    try { got = await api("telegram/poll", { wait: 20 }); }
    catch {
      wait.textContent = "Lost touch with Kurooto (is it still running?). Still trying…"; wait.className = "bad";
      await new Promise((ok) => setTimeout(ok, 5000));
      continue;
    }
    if (run !== pairRun) return;
    if (got.paired) { await refresh(); renderTelegram(); return; }
    if (!got.error) {
      if (!hinted) { wait.textContent = "Waiting for you to press Start…"; wait.className = ""; fix.replaceChildren(); }
      continue;
    }
    fix.replaceChildren();
    hinted = got.problem === "no_code";
    wait.textContent = got.error; wait.className = hinted ? "" : "bad";
    if (got.problem === "webhook") {
      fix.append(el("button", { class: "primary", onclick: async () => {
        const d = await api("telegram/webhook-off", {});
        wait.textContent = d.ok ? "Disconnected. Waiting for you to press Start…" : d.error;
        wait.className = d.ok ? "" : "bad"; fix.replaceChildren();
      } }, "Disconnect it"));
    }
    if (got.problem === "expired") newLinkButton(wait, fix);
    if (got.retry === false) return;
    if (!hinted) await new Promise((ok) => setTimeout(ok, 5000)); // Telegram or the network had a problem: a pause
  }
  if (run === pairRun) { wait.textContent = "This link expired: get a new one."; wait.className = "bad"; newLinkButton(wait, fix); }
}

// -------------------------------------------------------------------------------------------- finish
function renderFinish() {
  const brain = state.brains.find((b) => b.id === state.brain.main);
  const titles = state.modules.filter((m) => chosen.has(m.id)).map((m) => m.title);
  $("#summary").replaceChildren(
    el("li", {}, `AI: ${brain ? brain.label + (brain.ready ? "" : " (not working yet: you can finish it later)") : "none yet"}`),
    el("li", {}, `Telegram: ${state.telegram.paired ? "connected" : "not connected yet"}`),
    el("li", {}, `Features: ${titles.join(", ") || "none"}`),
    el("li", {}, `Your notes folder: ${state.workspace}`));
}

async function finish() {
  const btn = $("#finish"), out = $("#finish-panel");
  btn.disabled = true;
  // features that need installing first (e.g. the notes brain): set each up, showing its progress; every log stays
  out.replaceChildren();
  for (const m of state.modules.filter((m) => chosen.has(m.id) && !m.ready && m.setup)) {
    const box = el("div", { class: "box" }, el("p", {}, `Setting up ${m.title}…`), logBox());
    out.append(box);
    const r = await api("modules/setup", { id: m.id });
    if (r.started === false) box.append(el("p", { class: "bad" }, r.message));
    else await watchInstall();
    box.querySelector("#log").removeAttribute("id"); // the next feature's box gets the live log
  }
  const res = await api("modules/enable", { ids: [...chosen] });
  const failed = Object.entries(res.results).filter(([, v]) => !v.ok);
  if ($("#autostart").checked) await api("autostart", { on: true });
  await api("setup/done", {});
  out.append(el("div", { class: "box" },
    el("p", { class: "ok" }, "✓ Set up. Send /help to your bot to see what it can do."),
    failed.length ? el("p", { class: "bad" }, "Not turned on yet: " + failed.map(([k, v]) => `${k} (${v.message})`).join("; ")) : null));
  if (chosen.has("calls") && !(res.results.calls && !res.results.calls.ok)) out.append(await pairBox());
  btn.disabled = false;
}

// ------------------------------------------------------------------------------- restore (Profile sync)
// "I've used Kurooto before": the profile comes back from their repository, then the rest of the steps check what
// can't move with it (the AI's sign-in, programs to install), with what they had on already ticked.
let restored = null;
function showRestore() {
  $$("section").forEach((s) => s.classList.toggle("on", s.dataset.step === "restore"));
  window.scrollTo(0, 0);
}
async function restore() {
  const btn = $("#pr-go"), panel = $("#pr-panel"), msg = el("p", {}, "Restoring…");
  btn.disabled = true;
  panel.replaceChildren(el("div", { class: "box" }, msg, logBox()));
  const r = await api("profile/restore", { repo: $("#pr-repo").value, token: $("#pr-token").value, passphrase: $("#pr-pass").value });
  if (r.started === false) { msg.textContent = r.message; msg.className = "bad"; btn.disabled = false; return; }
  await watchInstall();
  const st = await api("profile"), rep = st.report || {};
  btn.disabled = false;
  if (!rep.counts) { msg.textContent = rep.error || "It didn't work; the log below says why."; msg.className = "bad"; return; }
  $("#pr-pass").value = ""; $("#pr-token").value = "";
  restored = st.wanted || [];
  chosen = new Set();
  const c = rep.counts, b = rep.brain || {};
  const todo = [
    ...rep.left.map((x) => el("li", {}, `${x.title}: ${x.why}`)),
    b.main && !b.ready ? el("li", {}, `Your AI (${b.label}): ${b.why || "not ready here"}. The AI step installs it and signs it in.`) : null,
    ...rep.notes.map((n) => el("li", {}, n)),
  ].filter(Boolean);
  panel.replaceChildren(el("div", { class: "box" },
    el("p", { class: "ok" }, `✓ Restored ${c.settings} settings, ${c.secrets} passwords and keys, ${c.files} saved items and ${c.scheduled} things scheduled.`),
    el("p", {}, `On: ${rep.on.join(", ") || "nothing yet"}.`),
    todo.length ? el("p", {}, "Still to do on this computer (the next steps help):") : null,
    todo.length ? el("ul", { class: "list" }, ...todo) : null));
  await refresh();
  $("#name").value = state.you.name || "";  // the first step saves these fields again if they go back to it
  $("#tz").value = state.you.timezone || $("#tz").value;
  $("#aname").value = state.you.assistant_name || "Kurooto";
  $("#pr-next").hidden = false;
}
$("#pr-open").addEventListener("click", showRestore);
$("#pr-back").addEventListener("click", () => show(0));
$("#pr-go").addEventListener("click", restore);
$("#pr-next").addEventListener("click", async () => { await refresh(); show(STEPS.indexOf("computer")); });

// ---------------------------------------------------------------------------------------------- start
document.addEventListener("click", async (e) => {
  if (e.target.matches("[data-next]")) {
    if (STEPS[step] === "you") await saveYou();
    if (STEPS[step] === "brain" && state.brain.main) await api("brain", { main: state.brain.main });
    await refresh();
    show(step + 1);
  } else if (e.target.matches("[data-back]")) show(step - 1);
  else if (e.target.matches("[data-preset]")) {
    const p = e.target.dataset.preset;
    $$(".preset").forEach((b) => b.classList.toggle("on", b === e.target));
    if (p !== "custom") { chosen = new Set(state.modules.filter((m) => p === "all" || m.starter).map((m) => m.id)); renderFeatures(); }
  }
});
$("#tg-check").addEventListener("click", checkToken);
$("#ay-source").addEventListener("change", renderAbout);
$("#ay-add").addEventListener("click", async () => {
  if (await addReport($("#ay-source").value.trim() || "an AI account", $("#ay-text").value)) { $("#ay-text").value = ""; renderAbout(); }
});
$("#ay-files").addEventListener("change", async (e) => {
  for (const f of e.target.files) await addReport($("#ay-source").value.trim() || f.name.replace(/\.[^.]+$/, ""), await f.text());
  e.target.value = "";
  renderAbout();
});
$("#finish").addEventListener("click", finish);

(async () => {
  await refresh();
  $("#name").value = state.you.name || "";
  $("#tz").value = state.you.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  $("#aname").value = state.you.assistant_name || "Kurooto";
  let saved = 0;
  try { saved = Number(localStorage.getItem("kurooto.setup.step") || 0); } catch { /* fine */ }
  show(location.hash === "#about" ? STEPS.indexOf("about") : state.setup_done ? 0 : saved); // /aboutme links to #about
})();
