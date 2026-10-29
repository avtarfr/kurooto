// Your voice (Voice ID, 0.8.10): capture, train, test, improve, manage. Everything runs on the computer; this page only
// shows counts, grades, thresholds and test scores (GET /api/voice/id), and the live stream's voiceid_* messages.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();
const CW = { normal: "your normal voice", quiet: "a quiet voice", far: "far from the microphone", noise: "with noise around you", calls: "short requests", free: "free speech", other: "added later" };
let S = null;
let step = "capture";

function ring(done, need) {
  const r = 14, c = 2 * Math.PI * r, f = need ? Math.min(1, done / need) : 0;
  return `<svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="${r}" fill="none" stroke="var(--line)" stroke-width="4"/><circle cx="18" cy="18" r="${r}" fill="none" stroke="var(--accent)" stroke-width="4" stroke-dasharray="${(c * f).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 18 18)"/></svg>`;
}

function show(name) {
  step = name;
  document.querySelectorAll("#steps button").forEach((b) => b.classList.toggle("on", b.dataset.step === name));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === `p-${name}`));
}

function topBox() {
  const on = S.on;
  let h = `<label class="sw"><input type="checkbox" id="vidon"${on ? " checked" : ""}${S.voice_on ? "" : " disabled"}> Voice ID: only your voice can make Kurooto act; anyone else can only chat</label>`;
  if (!S.voice_on) h += `<p class="warn">Voice is off: turn it on in the dashboard (Features → Voice) first.</p>`;
  if (S.missing && S.missing.length) h += `<p class="warn">Voice ID needs its files first (about ${esc(S.missing_gb)} GB); the switch alone doesn't download them. <button id="setupnow">Set up now</button> <span id="setupmsg"></span><br>Or download the model yourself and install it below (Manage).</p>`;
  if (S.voice_on && !S.listen_on) h += `<p class="warn">Listening is off, so Kurooto doesn't hear you: nothing reaches Voice ID, there's no waveform and no spoken reply. <button id="listenon">Turn listening on</button></p>`;
  if (S.bank !== "ok") h += `<p class="warn">${esc(S.bank)}.</p>`;
  if (S.locked) h += `<p class="warn">Its key can't be read, so every voice can only chat. Forget it (Manage) and enrol again.</p>`;
  if (S.mic && S.mic.enrolled && S.mic.now && S.mic.enrolled !== S.mic.now) h += `<p class="warn">Enrolled with ${esc(S.mic.enrolled)}, listening with ${esc(S.mic.now)}: add a few samples with this microphone.</p>`;
  $("#top").innerHTML = h;
  const lo = $("#listenon");
  if (lo) lo.onclick = async () => { const r = await api("settings", { key: "voice.listen.on", value: true }); $("#line").textContent = r.ok === false ? (r.error || "") : "Listening is on."; load(); };
  const su = $("#setupnow");
  if (su) su.onclick = setupNow;
  const box = $("#vidon");
  if (box) box.onchange = async () => { const r = await api("modules/card", { id: "voice", act: "speaker_id.on", value: box.checked }); $("#line").textContent = r.message || r.error || ""; load(); };
}

function capture() {
  const s = S.session;
  const plan = s ? s.plan : S.conditions.map((c) => ({ cond: c.cond, label: c.label, samples: c.samples }));
  const by = s ? s.by_cond : S.samples.by_cond;
  const need = s ? s.need : 21, done = s ? s.done : S.samples.total;
  $("#overall").style.width = `${Math.min(100, Math.round((100 * done) / Math.max(1, need)))}%`;
  const condsDone = plan.filter((c) => (by[c.cond] || 0) >= c.samples).length;
  const left = Math.max(0, need - done);
  $("#overall-t").textContent = `${done} of ${need} · ${condsDone} of ${plan.length} conditions${s && left ? ` · about ${Math.max(1, Math.round(left * 15 / 60))} minute${left * 15 >= 90 ? "s" : ""} left` : ""}`;
  $("#conds").innerHTML = plan.map((c) => `<div class="cond${s && s.cond === c.cond ? " cur" : ""}${s && s.skipped.includes(c.cond) ? " skip" : ""}">${ring(by[c.cond] || 0, c.samples)}<div><b>${esc(c.label)}</b><small>${by[c.cond] || 0}/${c.samples}${s && s.skipped.includes(c.cond) ? " · skipped" : ""}</small></div></div>`).join("");
  $("#prompt").textContent = s && s.prompt ? s.prompt : s ? "" : (S.enrolled ? "You're enrolled. Add samples or Start over from Manage." : "Press Start, then follow the prompts.");
  $("#smsg").textContent = s ? `${s.state}${s.message ? `: ${s.message}` : ""}` : "";
  $("#attempts").innerHTML = (s ? s.attempts : []).slice().reverse().map((a) => `<li class="${a.ok ? "ok" : "no"}">${a.ok ? "✓" : "✗"} #${a.n} · ${esc(CW[a.cond] || a.cond)}${a.reason ? ` · ${esc(a.reason)}` : ""}</li>`).join("");
  const live = s && !["done", "stopped", "kept"].includes(s.state);
  $("#start").textContent = s && s.state === "paused" ? "Continue" : "Start";
  $("#start").disabled = !!(live && s.state !== "paused");
  for (const id of ["#pause", "#skip", "#stop", "#keep"]) $(id).disabled = !live;
}

function histo(h, th) {
  if (!h) return "";
  const W = 320, H = 110, n = h.genuine.length, bw = W / n;
  const gm = Math.max(1, ...h.genuine), im = Math.max(1, ...h.impostor);
  const x = (v) => ((v - h.lo) / (h.hi - h.lo)) * W;
  const bars = (arr, m, col) => arr.map((c, i) => c ? `<rect x="${(i * bw + 1).toFixed(1)}" y="${(H - 18 - (c / m) * (H - 26)).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${((c / m) * (H - 26)).toFixed(1)}" fill="${col}" opacity=".7"/>` : "").join("");
  const line = (v, col, label, end) => `<line x1="${x(v).toFixed(1)}" x2="${x(v).toFixed(1)}" y1="4" y2="${H - 18}" stroke="${col}" stroke-width="2"/><text x="${(x(v) + (end ? -3 : 3)).toFixed(1)}" y="14" font-size="10" fill="${col}"${end ? ' text-anchor="end"' : ""}>${label}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Your scores against strangers' scores">${bars(h.impostor, im, "var(--dim)")}${bars(h.genuine, gm, "var(--ok)")}${th ? line(th.long.unsure, "var(--warn)", "unsure", true) + line(th.long.accept, "var(--ok)", "accept") : ""}<text x="0" y="${H - 4}" font-size="10" fill="var(--dim)">strangers (grey) · you (green), score ${h.lo} to ${h.hi}</text></svg>`;
}

function report() {
  const r = S.pending || S.report;
  if (!r) { $("#report").innerHTML = `<p class="note">Nothing built yet.</p>`; return; }
  const th = S.thresholds;
  const rows = Object.entries(r.frr_by_cond || {}).map(([c, f]) => `<tr><td>${esc(CW[c] || c)}</td><td>${Math.round(f * 10)} in 10</td></tr>`).join("");
  $("#report").innerHTML = `<p>${S.pending ? "<b>Not saved yet.</b> " : ""}<span class="grade ${esc(r.grade)}">${esc(r.grade)}</span> · ${r.used} of ${r.n} samples used${r.dropped ? ` · ${esc(r.dropped_line)}` : ""}</p>${r.advice ? `<p class="warn">${esc(r.advice)}</p>` : ""}
    <table><tr><th>Thresholds</th><td>${th ? `long turns: accept ${th.long.accept}, unsure from ${th.long.unsure}<br>short turns: accept ${th.short.accept}, unsure from ${th.short.unsure}` : ""}${S.threshold ? `<br><span class="warn">your own threshold ${S.threshold} (calibrated: ${S.calibrated ? S.calibrated.long.accept : "?"})</span>` : ""}</td></tr>
    <tr><th>Strangers who'd pass</th><td>${r.bank_pass_long} of ${r.bank_rows} (${esc(r.strictness)})</td></tr>
    <tr><th>Synthetic voices that'd pass</th><td>${r.synthetic ? `${r.synthetic_pass} of ${r.synthetic}` : "not checked (needs Kokoro)"}</td></tr>
    <tr><th>Turns you away</th><td>${Math.round((r.frr_long || 0) * 100)}% of long turns, ${Math.round((r.frr_short || 0) * 100)}% of short ones</td></tr></table>
    ${rows ? `<table><tr><th>By condition</th><th>turned away</th></tr>${rows}</table>` : ""}${histo(r.histogram, th)}`;
  $("#anyway").classList.toggle("hidden", !S.pending);
  $("#undo-build").disabled = !S.can_undo;
}

function dial(res) {
  if (!res || res.score == null) { $("#dial").innerHTML = ""; return; }
  const th = res.thresholds && res.thresholds[res.short ? "short" : "long"];
  const W = 240, cx = 120, cy = 112, R = 92;
  const pt = (v) => { const a = Math.PI * (1 - Math.max(0, Math.min(1, v))); return [cx + R * Math.cos(a), cy - R * Math.sin(a)]; };
  const mark = (v, col) => { const [x1, y1] = pt(v); const a = Math.PI * (1 - v); return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${(cx + (R - 14) * Math.cos(a)).toFixed(1)}" y2="${(cy - (R - 14) * Math.sin(a)).toFixed(1)}" stroke="${col}" stroke-width="3"/>`; };
  const [nx, ny] = pt(res.score);
  const word = { owner: "You", unsure: "Not sure", guest: "Someone else" }[res.decision] || res.decision;
  $("#dial").innerHTML = `<svg viewBox="0 0 ${W} 130" role="img" aria-label="Score ${res.score}"><path d="M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}" fill="none" stroke="var(--line)" stroke-width="10"/>${th ? mark(th.unsure, "var(--warn)") + mark(th.accept, "var(--ok)") : ""}<line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="var(--fg)" stroke-width="3"/><text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="14" fill="var(--fg)">${res.score.toFixed(2)}</text></svg>
    <p><span class="chipd ${esc(res.decision)}">${esc(word)}</span> ${esc(res.why || "")}${res.speech_s != null ? ` · ${res.speech_s} s of speech${res.short ? " (short-turn thresholds)" : ""}` : ""}${res.as === "other" || res.pass !== undefined ? ` · ${res.pass ? "as it should be" : "not what it should be"}` : ""}</p>`;
}

function improve() {
  const a = S.adapt;
  $("#adapt").checked = !!a.on;
  $("#amsg").textContent = `Learned from ${a.count} turn${a.count === 1 ? "" : "s"} (cap ${a.cap})${a.last ? `, last ${a.last}` : ""}${a.today ? `, ${a.today} today` : ""}.${a.drift_stopped ? " Improving stopped: your voice print would drift too far from your enrolment; retrain or undo." : ""}`;
}

const MIC_STATE = { learning: "learning", weak: "learning (weak so far)", ready: "ready", on: "in use", declined: "not used" };
function mics() { // (0.9.2) per microphone: counts, states and grades only
  const d = S.devices || [];
  $("#mics").innerHTML = !S.per_device ? `<p class="note">Off (voice.speaker_id.per_device).</p>` : !d.length ? `<p class="note">None yet.</p>` : `<table>${d.map((m) => `<tr><th>${esc(m.name)}${m.now ? " (now)" : ""}</th><td>${esc(MIC_STATE[m.state] || m.state)} · ${m.samples} of ${m.need} turns${m.grade ? ` · <span class="grade ${esc(m.grade)}">${esc(m.grade)}</span>` : ""}</td><td>${m.state === "ready" || m.state === "weak" ? `<button data-mic="${esc(m.ref)}" data-act="use">Use it</button><button data-mic="${esc(m.ref)}" data-act="no">No</button>` : ""}<button data-mic="${esc(m.ref)}" data-act="forget">Forget</button></td></tr>`).join("")}</table>`;
  document.querySelectorAll("[data-mic]").forEach((b) => b.onclick = async () => { const r = await api("voice/id/device", { device: b.dataset.mic, action: b.dataset.act }); $("#mmsg").textContent = r.message || r.error || ""; load(); });
}

function manage() {
  const t = S.last_test;
  const by = Object.entries(S.samples.by_cond).map(([c, n]) => `${esc(CW[c] || c)}: ${n}`).join(", ");
  $("#quality").innerHTML = S.enrolled || S.samples.total ? `<table>
    <tr><th>Samples</th><td>${S.samples.total}${by ? ` (${by})` : ""}</td></tr>
    <tr><th>Grade</th><td>${S.grade ? `<span class="grade ${esc(S.grade)}">${esc(S.grade)}</span>` : "not built"}</td></tr>
    <tr><th>Thresholds</th><td>${S.thresholds ? `long ${S.thresholds.long.accept}, short ${S.thresholds.short.accept} (${esc(S.strictness)})` : ""}</td></tr>
    <tr><th>Dates</th><td>${esc(S.dates.created || "")}${S.dates.updated ? ` · updated ${esc(S.dates.updated)}` : ""}</td></tr>
    <tr><th>Microphone</th><td>${esc(S.mic.enrolled || "")}</td></tr>
    <tr><th>Model</th><td>${esc(S.enrolled_model || S.model)}</td></tr>
    <tr><th>Last test</th><td>${t ? `${esc(t.day)}: you passed ${t.me_passed} of ${t.me_tries}; someone else turned away ${t.other_passed} of ${t.other_tries}` : "none yet"}</td></tr>
    <tr><th>Since Kurooto started</th><td>${S.who.owner} you, ${S.who.guest} someone else, ${S.who.unsure} unsure · ${S.guest_turns} guest turns answered</td></tr></table>` : `<p class="note">No voice print yet.</p>`;
  $("#addc").innerHTML = [...S.conditions.map((c) => [c.cond, c.label]), ["other", "This microphone, or a cold"]].map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
  $("#model").innerHTML = S.models.map((m) => `<option${m === S.model ? " selected" : ""}>${esc(m)}</option>`).join("");
}

async function setupNow() { // Voice's own Set up (what its switches need, Voice ID's files among them), here instead of the dashboard
  const btn = $("#setupnow"), say = (t) => { const m = $("#setupmsg"); if (m) m.textContent = t; };
  if (btn) btn.disabled = true;
  const r = await api("modules/setup", { id: "voice" });
  if (r.started === false || r.error) { say(r.message || r.error || ""); if (btn) btn.disabled = false; return; }
  say("Starting…");
  for (;;) {
    await new Promise((ok) => setTimeout(ok, 1000));
    let p;
    try { p = await api("progress"); } catch { continue; }
    const last = (p.lines || []).slice(-1)[0];
    if (last) say(last.line);
    if (!p.installing) break;
  }
  load();
}

async function load() {
  const was = S && S.session && !["done", "stopped", "kept"].includes(S.session.state);
  try { S = await api("voice/id"); } catch { $("#line").textContent = "Kurooto isn't answering right now."; return; }
  if (was && step === "capture" && (!S.session || S.session.state === "done") && (S.pending || S.report)) show("train"); // the capture ended and was built: its report
  $("#line").textContent = S.line || (S.on ? "" : "Voice ID is off.");
  topBox(); capture(); report(); improve();
  mics(); manage(); dial(S.test);
}

// ------------------------------------------------------------------------------------------------- actions
document.querySelectorAll("#steps button").forEach((b) => b.onclick = () => { show(b.dataset.step); history.replaceState(null, "", `#${b.dataset.step}`); });
if (["capture", "train", "test", "improve", "manage"].includes(location.hash.slice(1))) show(location.hash.slice(1));
const session = async (action, extra) => { const r = await api("voice/id/session", { action, own_words: $("#own").checked, ...(extra || {}) }); $("#smsg").textContent = r.message || ""; load(); };
$("#start").onclick = () => session(S && S.session && S.session.state === "paused" ? "continue" : "start");
$("#pause").onclick = () => session("pause");
$("#stop").onclick = () => session("stop");
$("#keep").onclick = () => session("keep");
$("#skip").onclick = async () => { if (S.session && S.session.cond) { await api("voice/id/skip", { cond: S.session.cond }); load(); } };
$("#build").onclick = async () => { $("#tmsg").textContent = "Building…"; const r = await api("voice/id/train", {}); $("#tmsg").textContent = r.message || ""; load(); };
$("#anyway").onclick = async () => { const r = await api("voice/id/train", { use_anyway: true }); $("#tmsg").textContent = r.message || ""; load(); };
$("#undo-build").onclick = async () => { const r = await api("voice/id/undo", {}); $("#tmsg").textContent = r.message || ""; load(); };
document.querySelectorAll("[data-test]").forEach((b) => b.onclick = async () => {
  const as = b.dataset.test;
  $("#xmsg").textContent = as === "synthetic" ? "Scoring Kokoro's voices…" : as === "other" ? "Listening… someone else, say a sentence. It should be Someone else." : "Listening… say a sentence or two.";
  const r = await api("voice/id/test", { as });
  $("#xmsg").textContent = r.ok ? "" : (r.message || "");
  if (r.ok) dial({ ...r, as });
  load();
});
$("#adapt").onchange = async () => { const r = await api("modules/card", { id: "voice", act: "speaker_id.adapt", value: $("#adapt").checked }); $("#amsg").textContent = r.message || r.error || ""; load(); };
document.querySelectorAll("[data-undo]").forEach((b) => b.onclick = async () => { const r = await api("voice/id/adapt", { undo: b.dataset.undo }); $("#amsg").textContent = r.message || ""; load(); });
$("#add").onclick = async () => { await session("start", { conds: [$("#addc").value] }); show("capture"); };
$("#again").onclick = async () => {
  if (!confirm("Start over? You'll record all six steps again; your voice print keeps working until the new one is built.")) return;
  await session("again"); show("capture");
};
$("#retrain").onclick = async () => { const r = await api("voice/id/train", {}); $("#fmsg").textContent = ""; $("#tmsg").textContent = r.message || ""; show("train"); load(); };
$("#setmodel").onclick = async () => {
  const m = $("#model").value;
  if (m === S.model) return;
  if (!confirm("Changing the model means enrolling again. Change it?")) return;
  const r = await api("settings", { key: "voice.speaker_id.model", value: m });
  $("#imsg").textContent = r.ok === false ? (r.error || "") : `Model: ${m}. Enrol again (Capture).`;
  load();
};
$("#install").onclick = async () => { $("#imsg").textContent = "Checking…"; const r = await api("voice/id/parts/add", { path: $("#path").value.trim() }); $("#imsg").textContent = r.message || ""; load(); };
$("#forget").onclick = () => $("#confirm").showModal();
$("#no").onclick = () => $("#confirm").close();
$("#yes").onclick = async () => { $("#confirm").close(); const r = await api("voice/id/forget", { confirm: true }); $("#fmsg").textContent = r.message || ""; load(); };

// ------------------------------------------------------------------------------------------- the live stream
const meter = $("#meter");
meter.innerHTML = Array.from({ length: 40 }, () => "<i></i>").join("");
const bars = [...meter.children];
function level(levels) {
  for (const v of levels) { bars.push(bars.shift()); const b = bars[bars.length - 1]; b.style.height = `${Math.max(2, Math.min(34, Number(v) * 34))}px`; meter.appendChild(b); }
}
function connect() {
  const es = new EventSource(`/api/stream?t=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.t !== "voice") return;
    if (m.kind === "voice_level" && m.levels) level(m.levels);
    if (m.kind === "voiceid_session" || m.kind === "voiceid_attempt") load();
  };
  es.onerror = () => { es.close(); setTimeout(connect, 3000); };
}
load();
connect();
setInterval(() => { if (S && S.session && !["done", "stopped", "kept"].includes(S.session.state)) load(); }, 4000);
