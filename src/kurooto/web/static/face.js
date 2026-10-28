// The Face page (modules/face, 0.8.10): set up, enrol, the report, the live test, manage and forget. Loaded on demand
// by home.js (renderFace), which calls FACE.mount(body, api, opts) and hands every {t: "face"} live message to
// FACE.live(m). The preview comes from this computer's camera through Kurooto (GET /api/face/frame: a JPEG made in
// memory, never kept) and is drawn only on this page's canvas; the page never asks the browser for the camera.
"use strict";
(function () {
  const S = { body: null, api: null, opts: {}, st: null, sid: "", kind: "", last: null, prog: null, loop: 0, say: false, sayAt: 0, step: "", testRes: {}, busy: false };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const pct = (x) => `${Math.round((x || 0) * 100)}%`;
  const day = (t) => (t ? new Date(t * 1000).toLocaleDateString([], { day: "numeric", month: "short" }) : "never");
  const NUDGE = { // a rejection, said aloud at most every 4 s when "Say the steps aloud" is on
    "Too dark": "A bit more light, please.", "Too bright": "A little less light behind you.", "Blurry": "Hold still.",
    "Too far": "Come a little closer.", "Too close": "Move back a little.", "Partly out of view": "Keep your face in the middle of the picture.", "Turn a bit more": "Turn a little more.",
    "Tilt your chin": "A little more.", "Keep your head level": "Keep your head level.", "No face found": "Look at the camera.",
  };
  const CSS = `.fc{max-width:1000px}.fc .row{display:flex;gap:16px;flex-wrap:wrap}.fc .prev{flex:1 1 320px;min-width:260px}
  .fc canvas{width:100%;max-width:480px;aspect-ratio:4/3;background:var(--panel,#111);border:1px solid var(--line,#333);display:block}
  .fc .side{flex:1 1 260px;min-width:220px}.fc .m{height:6px;background:var(--line,#333);margin:3px 0 6px;overflow:hidden}
  .fc .m i{display:block;height:100%;background:var(--accent,#7c7)}.fc ol{padding-left:18px;margin:6px 0}
  .fc li.on{color:var(--accent-text,inherit);font-weight:600}.fc li.done{color:var(--dim,#888)}.fc .why{min-height:1.4em}
  .fc .bad{color:var(--bad,#e77)}.fc .ok{color:var(--ok,#7c7)}.fc .bar{position:relative;height:10px;background:var(--line,#333);margin:4px 0}
  .fc .bar i{position:absolute;left:0;top:0;bottom:0;background:var(--accent,#7c7)}.fc .bar b{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--fg,#ddd)}
  .fc table td{padding:2px 8px 2px 0}.fc .d{color:var(--dim,#888)}.fc button{margin:2px 4px 2px 0}.fc .grade{font-weight:700}
  @media (max-width:560px){.fc .row{flex-direction:column}}`;

  function mount(body, api, opts) {
    S.body = body; S.api = api; S.opts = opts || {};
    try { S.say = localStorage.getItem("kurooto.face.say") === "1"; } catch { S.say = false; }
    if (!document.getElementById("face-css")) { const st = document.createElement("style"); st.id = "face-css"; st.textContent = CSS; document.head.appendChild(st); }
    body.onclick = click; body.onchange = change;
    load();
  }
  const here = () => S.body && S.body.isConnected && S.body.querySelector(".fc");
  async function load() {
    try { S.st = await S.api("face"); } catch { S.body.innerHTML = '<p class="d">Face presence isn\'t available in this version.</p>'; return; }
    const s = S.st.session;
    if (s && s.state !== "ended") { S.sid = s.id; S.kind = s.kind; } else if (!S.busy) { S.sid = ""; S.kind = ""; }
    render();
  }
  function also() { return S.opts.has && S.opts.has("voice_id") ? '<p class="d">Also: <a href="#" data-page="voice_id">Voice ID</a></p>' : ""; }
  function render() {
    const st = S.st, b = S.body; if (!st || !b) return;
    let h = `<div class="fc">${also()}<h3>Face presence</h3><p class="d">${esc(st.line)}</p>`;
    if (st.stage === "off") h += off();
    else if (st.stage === "setup") h += setup();
    else if (st.stage === "capturing" || st.stage === "testing" || st.stage === "calibrating") h += live();
    else if (st.stage === "enrol") h += start();
    else h += manage();
    b.innerHTML = h + "</div>";
    if (S.note) { said(S.note.text, S.note.bad); S.note = null; } // (eyes) the calibration's result, after the reload
    if (S.sid) frames();
  }
  // ------------------------------------------------------------------------------------------------ the stages
  function off() {
    return `<p>Face presence is off. Turn it on in Features: it greets you by voice when you sit down after a while.</p>
      ${S.st.kept ? `<p>Your face model is still kept on this computer (encrypted, never a picture).</p><p><button data-forget>Delete my face data</button></p>` : ""}`;
  }
  function setup() {
    const L = S.st.licences.map((l) => `<li>${esc(l.what)}: ${esc(l.licence)}, about ${l.mb >= 1 ? Math.round(l.mb) + " MB" : l.mb + " MB"}</li>`).join("");
    return `<p>It needs OpenCV and two models, about ${S.st.size_gb} GB, downloaded once. After that it works offline, on this computer's processor.</p>
      <ul class="d">${L}</ul><p><button class="primary" data-setup>Set up</button></p>
      <p>No internet here? <input data-folder placeholder="a folder on this computer" size="32"> <button data-from>Install from a folder</button></p>
      <p class="d">The folder holds the two .onnx files and the wheels (<code>pip download opencv-python-headless numpy --only-binary :all: -d FOLDER</code> on another computer). The Face presence page in the user guide gives the model links.</p>
      <pre class="d" data-log></pre>`;
  }
  function start() {
    const re = S.st.reenrol ? "<p class=\"bad\">The recognition model changed: enrol again (your old samples can't be used with it).</p>" : "";
    return `${re}<p>Enrolling takes a few minutes: nine short steps (${S.st.target} samples; ${S.st.minimum} are enough to start).</p>
      <ul><li>What's kept: numbers that describe your face, encrypted on this computer. Never a picture.</li>
      <li>What never is: the camera's frames. They're looked at and dropped.</li>
      <li>It's a convenience, never a lock: a face match never approves or unlocks anything.</li>
      <li>The camera's light is on while it looks.</li></ul>
      ${sayBox()}<p><button class="primary" data-start="new">Start</button></p>`;
  }
  function sayBox() {
    return S.st.voice_speaks ? `<label><input type="checkbox" data-say${S.say ? " checked" : ""}> Say the steps aloud</label>` : "";
  }
  function live() {
    if (S.kind === "gaze") return `<div class="row"><div class="prev"><canvas data-cv width="320" height="240"></canvas><p class="why" data-why></p></div><div class="side">
      <p><b>Look at the camera's lens</b>, not the screen, with your head turned to it, for about three seconds.</p>
      <div class="m"><i data-gz style="width:0%"></i></div><p class="d">Only four numbers are kept: where your irises sit in your eyes, and how your head was turned. Never a picture.</p>
      <p><button data-stop>Stop</button></p></div></div>`;
    const enrol = S.kind === "enrol";
    const side = enrol ? `<div data-steps>${steps()}</div>${sayBox()}
        <p><button data-pause>${S.paused ? "Resume" : "Pause"}</button> <button data-skip>Skip this step</button> <button data-noglasses>I don't wear glasses</button></p>
        <p><button class="primary" data-train${S.prog && S.prog.ready ? "" : " disabled"}>Finish and train</button> <button data-discard>Discard</button></p>`
      : `<div data-test></div><p><button data-mark="me">I'm testing as me</button> <button data-mark="other">Someone else is in front of the camera</button></p>
        <p class="d">Try a photo of yourself on your phone: it will probably say "you". That's why face presence never unlocks or approves anything.</p>
        <div data-results>${results()}</div><p><button data-stop>End the test</button></p>`;
    return `<div class="row"><div class="prev"><canvas data-cv width="320" height="240"></canvas><p class="why" data-why></p></div><div class="side">${side}</div></div>`;
  }
  function steps() {
    const p = S.prog; if (!p) return '<p class="d">Opening the camera…</p>';
    const all = `<p>${p.total} of ${p.target} samples · step ${p.step_no} of ${p.steps_n}</p><div class="m"><i style="width:${(100 * p.total / p.target).toFixed(1)}%"></i></div>`;
    return all + `<ol>${p.steps.map((s) => `<li class="${s.key === p.step ? "on" : s.done || s.skipped ? "done" : ""}">${s.done ? "✓ " : s.skipped ? "– " : ""}${esc(s.prompt)} <span class="d">${s.got}/${s.need}${s.skippable ? " · optional" : ""}</span><div class="m"><i style="width:${(100 * s.got / s.need).toFixed(0)}%"></i></div></li>`).join("")}</ol>`;
  }
  function results() {
    const r = S.testRes, out = [];
    if (r.me) out.push(`<p>As you: recognised in ${r.me.recognised} of ${r.me.frames} frames; an arrival ${r.me.decided ? "would greet you" : "would not have fired"}.</p>`);
    if (r.other) out.push(r.other.any_accepted ? `<p class="bad">It took someone else for you (best ${r.other.best.toFixed(2)}). Raise strictness to strict, or retrain with more samples.</p>` : `<p class="ok">Someone else: never taken for you (best score ${r.other.best.toFixed(2)}).</p>`);
    return out.join("");
  }
  function manage() {
    const m = S.st.model;
    if (!m) return S.st.locked ? "<p class=\"bad\">Your face model's key can't be read just now (a locked keychain): it waits, and nothing new is made over it.</p>" : "<p>No model.</p>";
    const r = m.report || {}, th = r.thresholds || {}, lt = m.last_test || {};
    const per = Object.entries(m.per_step || {}).map(([k, n]) => `${esc(k)} ${n}`).join(", ");
    const adv = (r.advice || []).map((a) => `<li>${esc(a)}</li>`).join("");
    const test = lt.at ? `${day(lt.at)}${lt.me ? ` · you: ${lt.me.recognised}/${lt.me.frames}` : ""}${lt.other ? ` · someone else: ${lt.other.any_accepted ? "taken for you" : "not you"} (best ${Number(lt.other.best).toFixed(2)})` : ""}` : "not yet";
    const learned = m.learned ? `${m.learned} (${m.learned_at.map(day).join(", ")}) <button data-undo>Undo the last</button> <button data-unlearn>Forget what it learned</button>` : "none";
    return `<table><tr><td>Grade</td><td class="grade">${esc(m.grade || "?")}</td></tr>
      <tr><td>Recognised</td><td>${pct(r.tar)} of held-out samples (median score ${r.median_you ?? "?"}, needs ${m.t_hi}; unsure below that, down to ${m.t_lo})</td></tr>
      <tr><td>Samples</td><td>${m.samples} (${per})</td></tr><tr><td>Learned</td><td>${learned}</td></tr>
      <tr><td>Impostor set</td><td>${m.impostors ? `yes (others' median ${r.median_others})` : "none: calibrated to OpenCV's floor"} · ${esc(th.method || "")}</td></tr>
      <tr><td>Model</td><td>${esc(m.model)} · made ${day(m.created)} · trained ${day(m.trained)}</td></tr>
      <tr><td>Last test</td><td>${test}</td></tr></table>
      ${adv ? `<ul>${adv}</ul>` : ""}
      <p><button class="primary" data-test>Test</button> <button data-start="add">Add samples</button> <button data-retrain>Retrain</button> <button data-start="new">Start over</button>${S.st.can_undo ? ' <button data-untrain>Undo the last training</button>' : ""}
      Strictness <select data-strict>${["loose", "normal", "strict"].map((k) => `<option${k === S.st.strictness ? " selected" : ""}>${k}</option>`).join("")}</select></p>
      <p class="d">Training here is honest: no network is trained. Your template is the centroid of SFace's numbers for your samples, and the cut-off is calibrated on your held-out samples against a set of made-up impostor faces, never below OpenCV's published 0.363.</p>
      ${eyes()}
      <p><button data-forget>Forget everything</button></p><p data-said></p>`;
  }
  function eyes() { // (0.8.17) look to talk by your eyes: the eye model and your calibration
    const g = S.st.gaze; if (!g) return "";
    const by = g.using === "eyes" ? "your eyes on the camera" : `your head's turn (${esc(g.why)})`;
    const now = g.now && g.now.yaw_deg !== undefined ? ` · last look: ${g.now.yaw_deg}° sideways, ${g.now.pitch_deg}° up or down${g.now.looking ? " (at it)" : ""}` : "";
    const act = !g.model ? `<button data-gaze-get>Get the eye model (${g.mb} MB)</button> <span class="d">MediaPipe Iris, Apache-2.0</span>`
      : `<button data-gaze>${g.calibrated ? "Calibrate again" : "Calibrate my eyes"}</button>${g.calibrated ? ` <span class="d">calibrated ${day(g.at)}</span> <button data-gaze-clear>Clear</button>` : ""}`;
    return `<h4>Look to talk</h4><p class="d">Goes by ${by}${now}.</p><p>${act}</p><pre class="d" data-log></pre>`;
  }
  // ------------------------------------------------------------------------------------------------- the preview
  async function frames() {
    const my = ++S.loop;
    while (my === S.loop && S.sid && here()) {
      const cv = S.body.querySelector("[data-cv]"); if (!cv) break;
      try {
        const r = await fetch(`/api/face/frame?s=${encodeURIComponent(S.sid)}`, { cache: "no-store", headers: { "X-Kurooto": S.opts.token } });
        if (r.ok) { const bm = await createImageBitmap(await r.blob()); draw(cv, bm); bm.close(); }
      } catch { /* the next one */ }
      await new Promise((ok) => setTimeout(ok, 125));
    }
  }
  function draw(cv, bm) {
    const g = cv.getContext("2d"), W = cv.width, H = cv.height;
    g.save(); g.translate(W, 0); g.scale(-1, 1); // mirrored, like a mirror: your left is on the left
    g.drawImage(bm, 0, 0, W, H);
    const v = S.last;
    const faces = v ? (v.faces || (v.box ? [{ box: v.box, landmarks: v.landmarks, cls: v.ok ? "ok" : "bad" }] : [])) : [];
    for (const f of faces) {
      const [x, y, w, h] = f.box; const col = f.class ? (f.class === "you" ? "#6c6" : f.class === "unsure" ? "#db4" : "#888") : f.cls === "ok" ? "#6c6" : "#db4";
      g.strokeStyle = col; g.lineWidth = 2; g.strokeRect(x * W, y * H, w * W, h * H);
      g.fillStyle = col; for (const [px, py] of f.landmarks || []) { g.beginPath(); g.arc(px * W, py * H, 2.5, 0, 6.3); g.fill(); }
    }
    g.restore();
  }
  // ------------------------------------------------------------------------------------------------ live messages
  function liveMsg(m) {
    if (m.kind === "camera") return; // the status line's dot (home.js)
    if (m.session && S.sid && m.session !== S.sid) return;
    if (!here()) return;
    if (m.kind === "session") {
      S.paused = m.state === "paused";
      const w = S.body.querySelector("[data-why]"); if (w) w.textContent = m.state === "ended" ? `Ended: ${m.why}.` : m.state === "paused" ? `Paused: ${m.why}.` : "";
      if (m.state === "ended" && !S.busy) { S.sid = ""; load(); }
      const pb = S.body.querySelector("[data-pause]"); if (pb) pb.textContent = S.paused ? "Resume" : "Pause";
      return;
    }
    if (m.kind === "enrol") {
      S.last = m; const before = S.prog && S.prog.step; S.prog = m;
      const el = S.body.querySelector("[data-steps]"); if (el) el.innerHTML = steps();
      const tb = S.body.querySelector("[data-train]"); if (tb) tb.disabled = !m.ready;
      const w = S.body.querySelector("[data-why]"); if (w) { w.textContent = m.ok ? "✓ got it" : m.reason || ""; w.className = `why ${m.ok ? "ok" : "bad"}`; }
      if (S.say && m.step && m.step !== before) speak((m.steps.find((s) => s.key === m.step) || {}).prompt);
      else if (S.say && !m.ok && m.reason && Date.now() - S.sayAt > 4000) { const k = Object.keys(NUDGE).find((p) => m.reason.startsWith(p)); if (k) speak(NUDGE[k]); }
      return;
    }
    if (m.kind === "test") {
      S.last = m;
      const el = S.body.querySelector("[data-test]"); if (!el) return;
      const best = (m.faces || []).reduce((a, f) => (f.score > (a ? a.score : -1) ? f : a), null);
      const word = { you: "You", unsure: "Unsure", "not you": "Not you", "no face": "No face" }[m.decision] || m.decision;
      el.innerHTML = `<p><b>${esc(word)}</b>${best ? ` (${best.score.toFixed(2)}; needs ${m.t_hi.toFixed(2)})` : ""} · ${esc(m.frames_ok)} frames${m.marking ? ` · looking (${m.marking === "me" ? "as you" : "someone else"})…` : ""}</p>
        ${best ? `<div class="bar"><i style="width:${Math.max(0, Math.min(100, best.score * 100)).toFixed(0)}%"></i><b style="left:${(m.t_lo * 100).toFixed(0)}%"></b><b style="left:${(m.t_hi * 100).toFixed(0)}%"></b></div><p class="d">the marks: unsure from ${m.t_lo.toFixed(2)}, you from ${m.t_hi.toFixed(2)}</p>` : ""}`;
      return;
    }
    if (m.kind === "gaze") {
      const bar = S.body.querySelector("[data-gz]"); if (bar) bar.style.width = `${Math.round((m.share || 0) * 100)}%`;
      const w = S.body.querySelector("[data-why]"); if (w) { w.textContent = m.ok ? "✓ keep looking" : m.reason || ""; w.className = `why ${m.ok ? "ok" : "bad"}`; }
      return;
    }
    if (m.kind === "gaze_result") { S.note = { text: m.message, bad: !m.ok }; return; }
    if (m.kind === "test_result") { S.testRes[m.who] = m; const el = S.body.querySelector("[data-results]"); if (el) el.innerHTML = results(); }
  }
  function speak(text) { if (!text) return; S.sayAt = Date.now(); S.api("voice/say", { text }).catch(() => {}); }
  // ------------------------------------------------------------------------------------------------------ buttons
  async function post(path, body) { try { return await S.api(path, body || {}); } catch { return { ok: false, message: "Kurooto didn't answer." }; } }
  function said(text, bad) { const el = S.body.querySelector("[data-said]") || S.body.querySelector("[data-why]"); if (el) { el.textContent = text || ""; el.className = bad ? "bad" : "d"; } }
  async function progress() {
    const log = S.body.querySelector("[data-log]");
    for (let i = 0; i < 2400 && here(); i++) {
      const p = await post("progress"); if (log) log.textContent = (p.lines || []).map((l) => l.line).join("\n");
      if (!p.installing) break;
      await new Promise((ok) => setTimeout(ok, 1000));
    }
    load();
  }
  async function click(e) {
    const t = e.target.closest("button, a[data-page]"); if (!t) return;
    const d = t.dataset;
    if (d.page) { e.preventDefault(); if (S.opts.open) S.opts.open(d.page); return; }
    if (d.setup !== undefined) { await post("modules/setup", { id: "face" }); progress(); return; }
    if (d.from !== undefined) { const f = S.body.querySelector("[data-folder]").value.trim(); if (f) { await post("face/install-from", { folder: f }); progress(); } return; }
    if (d.start) { // the guarded action camera.open: only this button (and Test) opens the camera
      t.disabled = true; S.busy = true;
      const r = await post("face/enrol/start", { cid: S.opts.cid ? S.opts.cid() : null, mode: d.start });
      S.busy = false;
      if (!r.ok) { t.disabled = false; said(r.message, true); return; }
      S.sid = r.session; S.kind = "enrol"; S.prog = r.plan; S.paused = false; S.st.stage = "capturing"; render();
      if (S.say && r.plan) speak((r.plan.steps.find((s) => s.key === r.plan.step) || {}).prompt);
      return;
    }
    if (d.test !== undefined) {
      t.disabled = true; S.busy = true;
      const r = await post("face/test/start", { cid: S.opts.cid ? S.opts.cid() : null });
      S.busy = false;
      if (!r.ok) { t.disabled = false; said(r.message, true); return; }
      S.sid = r.session; S.kind = "test"; S.testRes = {}; S.st.stage = "testing"; render(); return;
    }
    if (d.gaze !== undefined) { // camera.open: Calibrate my eyes, this button only
      t.disabled = true; S.busy = true;
      const r = await post("face/gaze/start", { cid: S.opts.cid ? S.opts.cid() : null });
      S.busy = false;
      if (!r.ok) { t.disabled = false; said(r.message, true); return; }
      S.sid = r.session; S.kind = "gaze"; S.st.stage = "calibrating"; render(); return;
    }
    if (d.gazeGet !== undefined) { t.disabled = true; await post("face/gaze/setup"); progress(); return; }
    if (d.gazeClear !== undefined) { const r = await post("face/gaze/clear"); await load(); said(r.message, !r.ok); return; }
    if (d.pause !== undefined) { const r = await post("face/enrol/pause", { session: S.sid, on: !S.paused }); if (r.ok) { S.paused = r.state === "paused"; t.textContent = S.paused ? "Resume" : "Pause"; } else said(r.message, true); return; }
    if (d.skip !== undefined || d.noglasses !== undefined) { const r = await post("face/enrol/step", { session: S.sid, action: d.skip !== undefined ? "skip" : "no_glasses" }); if (r.plan) { S.prog = { ...(S.prog || {}), ...r.plan }; const el = S.body.querySelector("[data-steps]"); if (el) el.innerHTML = steps(); } said(r.message, !r.ok); return; }
    if (d.discard !== undefined) { await post("face/enrol/discard", { session: S.sid }); S.sid = ""; load(); return; }
    if (d.train !== undefined) {
      t.disabled = true; S.busy = true;
      const r = await post("face/train", { session: S.sid }); S.busy = false;
      if (!r.ok) { t.disabled = false; said(r.message, true); return; }
      S.sid = ""; S.loop++; await load(); said(`Trained: grade ${r.report.grade}, recognised ${pct(r.report.tar)} of held-out samples.`); return;
    }
    if (d.mark) { await post("face/test/mark", { session: S.sid, who: d.mark }); return; }
    if (d.stop !== undefined) { await post("face/test/stop", { session: S.sid }); S.sid = ""; load(); return; }
    if (d.retrain !== undefined) { const r = await post("face/retrain"); await load(); said(r.ok ? `Retrained: grade ${r.grade || (r.report || {}).grade || "?"}.` : r.message, !r.ok); return; }
    if (d.undo !== undefined) { const r = await post("face/learn/undo"); await load(); said(r.message); return; }
    if (d.untrain !== undefined) { const r = await post("face/undo"); await load(); said(r.message, !r.ok); return; }
    if (d.unlearn !== undefined) { const r = await post("face/learn/forget"); await load(); said(r.message); return; }
    if (d.forget !== undefined) { // data.delete: a confirm first
      const box = document.createElement("p");
      box.innerHTML = 'Forget your face model? Kurooto will stop recognising you until you enrol again. <button data-forget-yes>Forget</button> <button data-forget-no>Keep it</button>';
      t.replaceWith(box); return;
    }
    if (d.forgetYes !== undefined) { const r = await post("face/forget"); await load(); said(r.message); return; }
    if (d.forgetNo !== undefined) { load(); return; }
  }
  async function change(e) {
    const t = e.target;
    if (t.dataset.say !== undefined) { S.say = t.checked; try { localStorage.setItem("kurooto.face.say", S.say ? "1" : "0"); } catch { /* fine */ } }
    if (t.dataset.strict !== undefined) { const r = await post("face/strictness", { level: t.value }); await load(); said(r.ok ? "Strictness saved and retrained." : r.message, !r.ok); }
  }
  window.FACE = { mount, live: liveMsg };
})();
