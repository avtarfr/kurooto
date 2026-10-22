// The setup wizard: six short steps, each saved as you go, so closing the page and coming back is fine.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const STEPS = ["you", "computer", "brain", "about", "features", "telegram", "finish"];
const LABELS = ["You", "Computer", "AI", "About you", "Features", "Telegram", "Done"];
const HINTS = ["Your name and time zone", "What it found here", "Who answers you", "Optional: what other AIs know",
  "What it does for you", "Where you talk to it", "Install and turn on"];
let state = null;
let step = 0;
let chosen = new Set();

async function api(path, body) {
  let r;
  try {
    r = await fetch(`/api/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    trouble("Kurooto isn't answering. Is it still running? Start it again from your apps menu (or run kurooto on in a terminal), then press the button again. What you typed here is kept.");
    throw e;
  }
  if (r.status === 403) trouble("This page is out of date (Kurooto was restarted). Reload the page: everything you saved is kept.");
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  trouble(null);
  return r.json();
}

// A bar at the top when Kurooto can't be reached, saying what to do; it goes away by itself when it answers again.
function trouble(text) {
  let bar = $("#trouble");
  if (!text) { if (bar) bar.remove(); return; }
  if (!bar) { bar = el("div", { id: "trouble", class: "trouble", role: "alert" }); document.body.prepend(bar); }
  bar.textContent = text;
}
window.addEventListener("unhandledrejection", (e) => { e.preventDefault(); }); // trouble() has said what to do

// Words that need a line of explanation: the first one in each card or step gets a dotted underline; tap it to read.
const GLOSSARY = [
  ["API key", "A password that lets a program use your account on a service. Keep it private; you can delete it and make a new one any time."],
  ["OpenAI-compatible", "Works the same way as ChatGPT's service, so Kurooto can talk to it: e.g. OpenRouter, Groq, Together, or LM Studio on this computer."],
  ["fine-grained token", "A GitHub token limited to the repositories and permissions you pick."],
  ["token", "A password made for one program or one bot. Keep it private: whoever has it can use what it opens."],
  ["repository", "A folder on GitHub that keeps the history of every change. Make it private, so only you can see it."],
  ["iCal", "A private web address of your calendar that other apps can read (Google Calendar: Settings → your calendar → Secret address in iCal format)."],
  ["Cloudflare", "A web company with a free plan. Kurooto puts your own call line on your account there, so your phone can reach it when this computer is off."],
  ["Gemini Live", "Google's real-time voice AI: it does the talking on calls."],
  ["Ollama", "A free program that runs AI models on this computer, without the internet."],
  ["GBrain", "An open-source index of your notes: it lets the AI find notes by what they mean, not only by exact words."],
  ["embeddings", "Numbers that capture what a piece of text means, so notes can be found by meaning."],
  ["MCP", "A standard way for AI programs (agy, Claude Code) to use another program's tools; here, Kurooto's."],
  ["OAuth", "Signing in on Google's own page and approving access there, so Kurooto never sees your password."],
  ["agy", "Antigravity, Google's agent program: it can read and write files and run commands on this computer for you."],
  ["passphrase", "A long password you choose. Only you know it: without it, the saved setup can't be opened."],
  ["keychain", "Your computer's safe place for passwords (Credential Manager on Windows, Keychain on macOS, the Secret Service on Linux)."],
  ["webhook", "A setting that sends your bot's messages to another program instead of Kurooto."],
  ["BotFather", "Telegram's own bot for making bots. It's official: the blue tick shows it."],
  ["LaTeX", "A way of writing maths that turns into neat PDFs."],
  ["Markdown", "Plain text with a few marks for headings and lists; any text editor opens it."],
  ["matugen", "A tool that makes a colour scheme from your wallpaper (Material You); some desktop setups run it for you."],
  ["pywal", "A tool that makes terminal and desktop colours from your wallpaper."],
];
const GLOSS_RE = new RegExp(`\\b(${GLOSSARY.map(([t]) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})s?\\b`, "i");
const glossed = new WeakMap(); // card or step -> the words already explained in it
function gloss(root) {
  const skip = "a, button, code, pre, input, textarea, h1, h2, h3, .chip, .star, .state, .tip, .log, .term, .eyebrow";
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement && !n.parentElement.closest(skip) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  });
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  for (let node of nodes) {
    const scope = node.parentElement.closest(".card, .box, section") || root;
    const done = glossed.get(scope) || new Set();
    glossed.set(scope, done);
    for (;;) {
      const m = GLOSS_RE.exec(node.data);
      if (!m) break;
      const entry = GLOSSARY.find(([t]) => t.toLowerCase() === m[1].toLowerCase());
      const after = node.splitText(m.index);
      const rest = after.splitText(m[0].length);
      node = rest;
      if (done.has(entry[0])) continue;
      done.add(entry[0]);
      const tip = el("span", { class: "tip", role: "note", hidden: true }, entry[1]);
      const term = el("button", { type: "button", class: "term", "aria-expanded": "false", title: entry[1], onclick: (e) => {
        e.stopPropagation();
        tip.hidden = !tip.hidden;
        term.setAttribute("aria-expanded", String(!tip.hidden));
      } }, after.data);
      after.replaceWith(term);
      (term.parentElement.closest("p, li, label, .privacy, .note, div") || term).after(tip); // under the line, not inside it
    }
  }
}

// A line that shows a long step is still working, with the time so far.
function working(text) {
  const out = el("p", { class: "working" }, el("span", { class: "spin", "aria-hidden": "true" }), el("span", {}, text), el("span", { class: "t" }));
  const t0 = Date.now();
  const tick = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    out.querySelector(".t").textContent = s < 3 ? "" : ` ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
  out.stop = () => { clearInterval(tick); out.remove(); };
  return out;
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
  // the steps: a row on phones, a rail with what each is for on wide screens; any of them can be opened
  // (a step passed but not finished, like an AI that doesn't answer yet, shows "!" instead of a tick)
  const brain = state && state.brains.find((b) => b.id === state.brain.main);
  const open = { brain: state && !(brain && brain.ready), telegram: state && !state.telegram.paired };
  $("#steps").replaceChildren(...LABELS.map((l, j) => {
    const todo = j < step && open[STEPS[j]], hint = todo ? "not finished yet" : HINTS[j];
    return el("li", { class: j === step ? "on" : todo ? "todo" : j < step ? "done" : "" },
      el("button", { type: "button", title: `${l}: ${hint.toLowerCase()}`, "aria-current": j === step ? "step" : false, onclick: () => go(j) },
        el("span", { class: "n" }, todo ? "!" : j < step ? "✓" : String(j + 1)), el("span", { class: "lbl" }, l, el("small", {}, hint))));
  }));
  const sec = $(`section[data-step="${STEPS[step]}"]`);
  if (!$(".eyebrow", sec)) sec.prepend(el("p", { class: "eyebrow" }));
  $(".eyebrow", sec).textContent = `Step ${step + 1} of ${STEPS.length}`;
  try { localStorage.setItem("kurooto.setup.step", String(step)); } catch { /* private mode */ }
  ({ computer: renderComputer, brain: renderBrains, about: renderAbout, features: renderFeatures, telegram: renderTelegram, finish: renderFinish }[STEPS[step]] || (() => {}))();
  navHint();
  gloss(sec);
  window.scrollTo(0, 0);
}

// Beside Next: what happens if you go on now (nothing is lost by skipping; every step can be opened again).
function navHint() {
  const nav = $(`section[data-step="${STEPS[step]}"] .nav`);
  if (!nav || !state) return;
  let hint = $(".nav-hint", nav);
  if (!hint) { hint = el("span", { class: "nav-hint" }); nav.lastElementChild.before(hint); }
  const brain = state.brains.find((b) => b.id === state.brain.main);
  hint.textContent = {
    brain: brain && brain.ready ? "" : "Not working yet? You can go on and finish it later: this page opens again from the dashboard.",
    about: "Optional: Next skips it.",
    features: `${chosen.size} of ${state.modules.length} on.`,
    telegram: state.telegram.paired ? "" : "Not connected yet? You can go on and connect it later.",
  }[STEPS[step]] || "";
}

async function refresh() { state = await api("state"); }

// Leaving a step saves what it holds (Next, Back or a step in the list alike).
async function go(i) {
  if (STEPS[step] === "you" && i > step && !checkYou()) return;
  if (STEPS[step] === "you") await saveYou();
  if (STEPS[step] === "brain" && state.brain.main) await api("brain", { main: state.brain.main });
  await refresh();
  show(i);
}

// ---------------------------------------------------------------------------------------------- you
// The time zone: picked from today's names (Kurooto's list, core/zones.py) as you type; a name it doesn't know is said
// before going on. The browser's own list may hold old names (Europe/Kiev for Europe/Kyiv): those are accepted
// too, and saved under today's name.
const BROWSER_ZONES = (() => { try { return Intl.supportedValuesOf("timeZone"); } catch { return []; } })();
let ZONES = BROWSER_ZONES;
function checkYou() {
  const tz = $("#tz"), msg = $("#you-msg"), v = tz.value.trim();
  const known = !v || !ZONES.length || ZONES.includes(v) || BROWSER_ZONES.includes(v) || v === "UTC";
  const near = known ? null : ZONES.find((z) => z.toLowerCase() === v.toLowerCase() || z.toLowerCase().endsWith("/" + v.toLowerCase().replace(/ /g, "_")));
  if (near) { tz.value = near; msg.textContent = ""; return true; }
  msg.textContent = known ? "" : `"${v}" isn't a time zone name. Start typing your city or region and pick it from the list (e.g. Europe/Berlin, America/New_York), or leave it empty to use this computer's.`;
  if (!known) tz.focus();
  return known;
}

async function saveYou() {
  const r = await api("you", { name: $("#name").value, timezone: $("#tz").value, assistant_name: $("#aname").value || "Kurooto" });
  if (r && typeof r.timezone === "string") $("#tz").value = r.timezone;  // under today's name
}

// ------------------------------------------------------------------------------------------ computer
const PROFILES = {  // the hardware profile (core/hardware.py), in words
  light: "AI services only (no local models)",
  "small-gpu": "small local AI models",
  "big-gpu": "local AI models (8 GB graphics card)",
  "big-gpu-12": "bigger local AI models",
  apple: "local AI models (Apple silicon)",
  "apple-8": "small local AI models (Apple silicon)",
};
function renderComputer() {
  const hw = state.hardware, m = hw.machine, r = hw.recommendation;
  $("#hw-summary").textContent = r.summary;
  const gpu = m.gpus.map((g) => g.name + (g.vram_gb ? ` (${g.vram_gb} GB)` : "")).join(", ") || "none Kurooto can use";
  $("#hw-chips").replaceChildren(
    chip("System", `${m.os} ${m.os_version}`), chip("Processor", m.cpu), chip("Memory", `${m.ram_gb} GB`),
    chip("Graphics", gpu), chip("Free space", `${m.disk_free_gb} GB`), chip("Suits", PROFILES[r.profile] || r.profile),
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
  renderLook();
  gloss($('section[data-step="computer"]'));
}

// The pages' colours (core/palette.py): this computer's own colours are recommended when they're found.
async function renderLook() {
  const box = $("#look-choice");
  let look;
  try { look = await api("look"); } catch { return; }
  const light = matchMedia("(prefers-color-scheme: light)").matches;
  const sys = look.system;
  const about = {
    kuro: "Deep greens. The default.",
    rose: "The pinks of earlier versions.",
    system: sys ? `${sys.label}${sys.mode ? `, ${sys.mode} mode` : ""}. Changes when they do.`
      : "Nothing found here yet. Kurooto reads matugen, pywal, KDE, GNOME and GTK colours, and the accent colour of Windows and macOS.",
  };
  box.replaceChildren(el("h2", {}, "Colours"), el("div", { class: "cards looks" }, ...look.choices.map(({ id, label }) =>
    el("button", { class: "card" + (id === look.chosen ? " on" : ""), "aria-pressed": String(id === look.chosen), disabled: id === "system" && !sys,
      onclick: async () => {
        await api("settings", { key: "look.palette", value: id });
        if (window.kurootoLook) await window.kurootoLook.refresh();
        renderLook();
      } },
    id === "system" && sys ? el("div", { class: "star" }, "★ RECOMMENDED: FOUND HERE") : null,
    el("div", { class: "swatches", "aria-hidden": "true" }, ...((look.previews[id] || {})[light ? "light" : "dark"] || []).map((c) => el("i", { style: `background:${c}` }))),
    el("h3", {}, label), el("p", {}, about[id])))),
  el("p", { class: "note" }, "Only how Kurooto's pages look. Change it any time: Settings → Look."));
  gloss(box);
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
    class: "card" + (b.id === main ? " on" : ""), "aria-pressed": String(b.id === main),
    onclick: () => { state.brain.main = b.id; renderBrains(); },
  }, b.recommended ? el("div", { class: "star" }, "★ RECOMMENDED") : null, el("h3", {}, b.label), el("p", {}, b.why),
    b.ready ? el("div", { class: "state" }, "✓ working") : null)));
  renderBrainPanel(main);
  gloss($("#brains"));
  navHint();
}

function logBox() { return el("div", { class: "log", id: "log" }); }

// log text with its web addresses as links (e.g. the Cloudflare sign-in page)
function linkify(text) {
  return text.split(/(https?:\/\/[^\s<>"]+)/g).map((part, i) =>
    i % 2 ? el("a", { href: part, target: "_blank", rel: "noopener" }, part.length > 90 ? part.slice(0, 87) + "…" : part) : document.createTextNode(part));
}

async function watchInstall(done, label = "Installing… this can take a few minutes; keep this page open.") {
  const log = $("#log");
  const busy = working(label);
  if (log) log.before(busy);
  try {
    for (;;) {
      const p = await api("progress");
      if (log) log.replaceChildren(...linkify(p.lines.map((l) => l.line).join("\n")));
      if (!p.installing) break;
      await new Promise((r) => setTimeout(r, 1000));
    }
  } finally { busy.stop(); }
  await refresh();
  done && done();
}

// When a test fails: what to do about it, for each kind of AI.
const FIX = {
  gemini: "Copy the key again from Google AI Studio (all of it; it starts with AIza) and press Save and test. If it says it's at its limit, wait a minute or use a paid key.",
  agy: "Press Open the sign-in window, finish signing in with your Google account, close the window, then test again.",
  claude: "Press Open the sign-in window, finish signing in with your Claude account, close the window, then test again.",
  ollama: "Make sure Ollama is running (open the Ollama app, or run ollama serve in a terminal), then test again.",
  custom: "Check the address (it usually ends in /v1), the key and the model name: the service's own help pages list them.",
};
function fixFor(which, message) {
  if (/limit/i.test(message)) return "Wait a minute and test again, or pick another AI above (you can add this one as a fallback later).";
  return FIX[which] || FIX.custom;
}

async function runTest(which, out) {
  const busy = working("Asking it to reply… (up to a minute, longer the first time)");
  out.replaceChildren(busy); out.className = "";
  let r;
  try {
    await api("brain", { main: which });
    r = await api("brain/test", { which });
  } catch { busy.stop(); out.textContent = "Couldn't ask Kurooto to test it (see the bar at the top)."; out.className = "bad"; return false; }
  busy.stop();
  out.replaceChildren(el("span", {}, (r.ok ? "✓ " : "") + r.message), r.ok ? null : el("span", { class: "fix" }, " " + fixFor(which, r.message)));
  out.className = r.ok ? "ok" : "bad";
  if (r.ok) { await refresh(); renderBrains(); }
  return r.ok;
}

function testButton(which, label = "Test it") {
  const out = el("p", { "aria-live": "polite" });
  const btn = el("button", { class: "primary", onclick: async () => {
    btn.disabled = true; await runTest(which, out); btn.disabled = false;
  } }, label);
  return [btn, out];
}

// Opening a program's sign-in window; what happened is said here (not in a pop-up).
function signinButton(key, account) {
  const out = el("span", { class: "note", "aria-live": "polite" });
  return el("p", {}, el("button", { onclick: async () => {
    const r = await api("prereqs/signin", { key });
    out.textContent = " " + (r.message || (r.ok ? `A window opened: sign in with your ${account} account there, then close it.` : ""));
    out.className = r.ok ? "note" : "bad";
  } }, "Open the sign-in window"), out);
}

function installButton(key, label, which) {
  return el("button", { class: "primary", onclick: async (e) => {
    e.target.disabled = true;
    const r = await api("prereqs/install", { keys: [key] });
    if (r.started === false) { e.target.disabled = false; e.target.after(el("p", { class: "bad" }, r.message || "Something else is being installed: try again when it has finished.")); return; }
    watchInstall(() => renderBrainPanel(which));
  } }, label);
}

function field(label, input, note) {
  return el("label", {}, label, input, note ? el("span", { class: "field-note" }, note) : null);
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
  const brain = state.brains.find((b) => b.id === which) || {};
  if (brain.ready) box.append(el("p", { class: "ok" }, `✓ ${brain.label} is working. Go on to the next step, or test it again.`));
  if (which === "agy") {
    const installed = state.prereqs.agy.installed;
    box.append(el("p", {}, installed ? "1. agy is installed." : "1. agy isn't installed yet. Kurooto installs it from Google's official installer."));
    if (!installed) box.append(installButton("agy", "Install agy", "agy"), logBox());
    else box.append(
      el("p", {}, "2. Sign in once with your Google account: a window opens, follow it, then close it."),
      signinButton("agy", "Google"),
      el("p", {}, "3. Check it works. When it does, Kurooto lets agy work for you unattended, in agy's own " +
        "settings (a backup is kept; nothing of yours is removed): use Kurooto's tools (reminders, notes, calls…); " +
        "read your notes, Documents, Downloads, Screenshots and Kurooto's copies of Classroom and mail; write in your " +
        "notes folder and course files (Documents and Downloads stay read-only); read web pages; run harmless " +
        "commands such as ls, grep and git, and latexmk for PDFs."), ...testButton("agy"));
    box.append(el("p", { class: "note" }, AGY_NOTE));
  } else if (which === "claude") {
    const key = which, label = "Claude Code", account = "Claude";
    const installed = state.prereqs[key].installed;
    box.append(el("p", {}, installed ? `1. ${label} is installed.` : `1. ${label} isn't installed yet. Kurooto installs it from the official source.`));
    if (!installed) box.append(installButton(key, `Install ${label}`, which), logBox());
    else box.append(
      el("p", {}, `2. Sign in once with your ${account} account: a window opens, follow it, then close it.`),
      signinButton(key, account),
      el("p", {}, "3. Check it works:" + (which === "claude" ? " Each request then gets only what Kurooto gives it, for that " +
        "request and nothing saved in Claude Code's own settings: Kurooto's tools, your notes and course files " +
        "(it may write only in your notes and course folders; Documents and Downloads are read-only), web pages and " +
        "harmless commands such as ls, grep and git. Nothing else, and never the kurooto command itself." : "")), ...testButton(which));
  } else if (which === "gemini") {
    const key = el("input", { placeholder: "AIza…", autocomplete: "off", spellcheck: "false" });
    const out = el("p", { "aria-live": "polite" });
    const go = el("button", { class: "primary", onclick: async () => {
      if (!key.value.trim() && !brain.ready) {
        out.textContent = "Paste your key first: it starts with AIza, and Google AI Studio (the link above) makes one."; out.className = "bad";
        return;
      }
      go.disabled = true;
      if (key.value.trim()) await api("brain", { main: "gemini", key: key.value.trim() });
      await runTest("gemini", out);
      go.disabled = false;
    } }, brain.ready ? "Test it again" : "Save and test");
    box.append(
      el("p", {}, "1. Get a free API key: ", el("a", { href: "https://aistudio.google.com/apikey", target: "_blank", rel: "noopener" }, "Google AI Studio → Create API key"), " (sign in with your Google account)."),
      geminiTerms(),
      field("2. Paste it here", key, brain.ready ? "A key is saved. Paste a new one only to replace it." : "It stays on this computer, in its password store."),
      el("div", { class: "row" }, go), out);
  } else if (which === "freellmapi") { // set up with an earlier version: no longer offered, but it keeps working
    box.append(el("p", {}, "This AI was set up with an earlier version of Kurooto and keeps working. To change it, pick another one above."),
      ...testButton("freellmapi"));
  } else if (which === "ollama") {
    box.append(el("p", {}, "Local models are private and work offline, but they're much weaker than the services above, and need a good graphics card. Kurooto uses them best as a helper next to another AI."),
      el("p", {}, state.prereqs.ollama.installed ? "Ollama is installed." : "Ollama isn't installed."));
    if (!state.prereqs.ollama.installed) box.append(installButton("ollama", "Install Ollama", "ollama"), logBox());
  } else {
    const url = el("input", { placeholder: "https://api.example.com/v1", spellcheck: "false" });
    const key = el("input", { type: "password", placeholder: "Its API key", autocomplete: "off" });
    const model = el("input", { placeholder: "e.g. llama-3.3-70b", spellcheck: "false" });
    const out = el("p", { "aria-live": "polite" });
    const go = el("button", { class: "primary", onclick: async () => {
      if (!url.value.trim() || !model.value.trim()) { out.textContent = "Fill in the address and the model name first (the key too, if the service needs one)."; out.className = "bad"; return; }
      go.disabled = true;
      await api("brain", { main: "custom", base_url: url.value, key: key.value, models: { low: model.value, medium: model.value, high: model.value } });
      await runTest("custom", out);
      go.disabled = false;
    } }, "Save and test");
    box.append(el("p", {}, "Any OpenAI-compatible service: its help pages give these three."),
      field("Address", url, "Usually ends in /v1."), field("Key", key), field("Model name", model), el("div", { class: "row" }, go), out);
  }
  if (brain.ready) box.append(tryBox());
  panel.replaceChildren(box);
  gloss(panel);
}

// Try it: once the AI answers its test, a box that talks to Kurooto here, before Telegram is set up. It goes through
// the same handler as a Telegram message (web/tryit.py); nothing said here goes to the phone.
const tried = []; // what was said in the box, kept while the page is open
function tryBox() {
  const who = (state.you && state.you.assistant_name) || "Kurooto";
  const log = el("div", { class: "log tryit", "aria-live": "polite" });
  const show = () => log.replaceChildren(...tried.map((t) => el("div", { class: "said" + (t.you ? " you" : "") }, `${t.you ? "You" : who}: ${t.text}`)));
  const input = el("input", { placeholder: "remind me in 2 minutes to stretch", autocomplete: "off", "aria-label": `Say something to ${who}` });
  const say = (text, you = false) => { tried.push({ you, text }); show(); };
  const send = el("button", { class: "primary", onclick: async () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = ""; send.disabled = true;
    say(text, true);
    try {
      const r = await api("tryit", { text });
      r.replies.forEach((t) => say(t));
      for (let i = 0; r.job && i < 200; i++) { // an AI request: its answer comes back here (up to five minutes)
        await new Promise((ok) => setTimeout(ok, 1500));
        const j = await api(`job?id=${encodeURIComponent(r.job)}`);
        if (j.status === "ok" || j.status === "failed") { say(j.answer || "(no answer)"); break; }
      }
    } catch { say("It didn't answer. Test your AI again above, then try once more."); }
    send.disabled = false; input.focus();
  } }, "Send");
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); send.click(); } });
  show();
  return el("div", { class: "tryit-box" },
    el("h3", {}, "Try it now"),
    el("p", { class: "note" }, `Talk to ${who} here before Telegram is set up: try "remind me in 2 minutes to stretch" (it pops up on this computer), or ask it something. Nothing said here goes to your phone.`),
    el("div", { class: "row" }, input, send), log);
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
    el("p", {}, a.reports.length ? `${a.reports.length} report(s) so far. Add more, or build your profile from them.`
      : "No reports yet. Copy a prompt above, paste it into a new chat in that AI, then paste its whole answer in the box above and press Add this report."),
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
  navHint();
  gloss($("#features"));
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
    await watchInstall(null, "Setting up your call line… a few minutes; keep this page open.");
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
  if (state.telegram.paired) p.replaceChildren(el("div", { class: "box" }, el("p", { class: "ok" }, "✓ Telegram is connected. Your bot only answers you. Go on to the last step.")));
  navHint();
}

async function checkToken() {
  const p = $("#tg-panel"), token = $("#tg-token").value.trim();
  if (!token) { p.replaceChildren(el("p", { class: "bad" }, "Paste the token BotFather sent you first: it looks like 123456789:AAH… (step 3 above).")); return; }
  if (!/^\d+:[\w-]{20,}$/.test(token)) {
    p.replaceChildren(el("p", { class: "bad" }, "That doesn't look like a bot token: it's a number, a colon and a long code, like 123456789:AAH… Copy the whole line from BotFather's message (not the bot's name or link)."));
    return;
  }
  p.replaceChildren(working("Asking Telegram about your bot…"));
  let r;
  try { r = await api("telegram/token", { token: $("#tg-token").value }); }
  catch { p.replaceChildren(el("p", { class: "bad" }, "Lost touch with Kurooto: is it still running? Try again in a moment.")); return; }
  if (!r.ok) {
    const fix = /accept/i.test(r.error) ? " Copy the token again from BotFather's message (all of it), or send /token to BotFather to get it again." : " Check this computer is online, then try again.";
    p.replaceChildren(el("p", { class: "bad" }, r.error + fix));
    return;
  }
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
    if (got.paired) { await refresh(); renderTelegram(); return; }  // the hint beside Next goes too
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
  const row = (ok, label, text, back) => el("li", { class: ok ? "is-ok" : "is-todo" },
    el("span", { class: "mark", "aria-hidden": "true" }, ok ? "✓" : "–"), el("b", {}, label + ": "), text,
    back != null && !ok ? el("button", { type: "button", class: "link", onclick: () => go(back) }, "Go back to it") : null);
  $("#summary").replaceChildren(
    row(brain && brain.ready, "Your AI", brain ? brain.label + (brain.ready ? ", working" : ", not working yet (you can finish it later)") : "none picked yet", STEPS.indexOf("brain")),
    row(state.telegram.paired, "Telegram", state.telegram.paired ? "connected" : "not connected yet", STEPS.indexOf("telegram")),
    row(true, "Features", titles.join(", ") || "none: you can turn some on later"),
    row(true, "Your notes folder", el("code", {}, state.workspace)));
  gloss($("#summary"));
}

async function finish() {
  const btn = $("#finish"), out = $("#finish-panel");
  btn.disabled = true;
  // features that need installing first (e.g. the notes brain): set each up, showing its progress; every log stays
  out.replaceChildren();
  const todo = state.modules.filter((m) => chosen.has(m.id) && !m.ready && m.setup);
  for (const [i, m] of todo.entries()) {
    const box = el("div", { class: "box" }, el("p", {}, el("b", {}, `Setting up ${m.title}`), todo.length > 1 ? ` (${i + 1} of ${todo.length})` : ""), logBox());
    out.append(box);
    const r = await api("modules/setup", { id: m.id });
    if (r.started === false) box.append(el("p", { class: "bad" }, r.message));
    else await watchInstall(null, `Setting up ${m.title}… this can take a few minutes; keep this page open.`);
    box.querySelector("#log").removeAttribute("id"); // the next feature's box gets the live log
  }
  const turning = working("Turning your features on…");
  out.append(turning);
  const res = await api("modules/enable", { ids: [...chosen] });
  const failed = Object.entries(res.results).filter(([, v]) => !v.ok);
  if ($("#autostart").checked) await api("autostart", { on: true });
  await api("setup/done", {});
  turning.stop();
  const title = (id) => (state.modules.find((m) => m.id === id) || {}).title || id;
  out.append(el("div", { class: "box done" },
    el("p", { class: "ok" }, "✓ Set up."),
    failed.length ? el("p", { class: "bad" }, "Not turned on yet: " + failed.map(([k, v]) => `${title(k)} (${v.message})`).join("; ") +
      ". Fix what it says, then turn it on in the dashboard's Features tab.") : null,
    el("p", {}, "Next:"),
    el("ol", { class: "next" },
      state.telegram.paired ? el("li", {}, "Send /help to your bot in Telegram to see what it can do.")
        : el("li", {}, "Connect Telegram (step 6), so you can talk to your assistant."),
      el("li", {}, "Open the dashboard: what's happening, your features and settings, all in one place.")),
    el("p", {}, el("a", { class: "button primary", href: "/" }, "Open the dashboard"))));
  if (chosen.has("calls") && !(res.results.calls && !res.results.calls.ok)) out.append(await pairBox());
  btn.disabled = false;
}

// ------------------------------------------------------------------------------- restore (Profile sync)
// "I've used Kurooto before": the profile comes back from their repository, then the rest of the steps check what
// can't move with it (the AI's sign-in, programs to install), with what they had on already ticked.
let restored = null;
function showRestore() {
  $$("section").forEach((s) => s.classList.toggle("on", s.dataset.step === "restore"));
  gloss($('section[data-step="restore"]'));
  window.scrollTo(0, 0);
}
async function restore() {
  const btn = $("#pr-go"), panel = $("#pr-panel"), msg = el("p", {}, "Restoring…");
  btn.disabled = true;
  panel.replaceChildren(el("div", { class: "box" }, msg, logBox()));
  const r = await api("profile/restore", { repo: $("#pr-repo").value, token: $("#pr-token").value, passphrase: $("#pr-pass").value });
  if (r.started === false) { msg.textContent = r.message; msg.className = "bad"; btn.disabled = false; return; }
  await watchInstall(null, "Restoring your setup… keep this page open.");
  const st = await api("profile"), rep = st.report || {};
  btn.disabled = false;
  if (!rep.counts) { msg.textContent = rep.error || "It didn't work; the log below says why."; msg.className = "bad"; return; }
  $("#pr-pass").value = ""; $("#pr-token").value = "";
  restored = st.wanted || [];
  chosen = new Set(restored);
  renderFeatures.seeded = true;
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
  if (e.target.matches("[data-next]")) await go(step + 1);
  else if (e.target.matches("[data-back]")) await go(step - 1);
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
  if (state.zones && state.zones.length) ZONES = state.zones;
  $("#tz-list").replaceChildren(...ZONES.map((z) => el("option", { value: z })));
  $("#name").value = state.you.name || "";
  $("#tz").value = state.you.timezone || state.computer_zone || Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  $("#aname").value = state.you.assistant_name || "Kurooto";
  let saved = 0;
  try { saved = Number(localStorage.getItem("kurooto.setup.step") || 0); } catch { /* fine */ }
  show(location.hash === "#about" ? STEPS.indexOf("about") : state.setup_done ? 0 : saved); // /aboutme links to #about
})();
