// The Brain console (0.8.10): everything Brain keeps, read-only, on the dashboard (its "Brain console" page, Alt+O)
// and in the phone app's Views (brain.html). The same code draws both:
//   BrainConsole.mount(host, opts) -> { update(data), stop() }
//     opts.api(query)   the dashboard: GET /api/brain/console?<query> (mind/console.py); the console asks it for the
//                       whole copy every few seconds while it's in sight, and for a decision, a timeline page or a search
//     opts.toggle(key, on)  the dashboard: a part's on/off settings become switches (POST /api/settings)
//     opts.mode         "phone": one column, a sheet for a decision, and everything from the copy it was handed
//     opts.data         a copy to start from (the phone: mind/console.py snapshot(phone=True), with each decision's
//                       evidence, so it opens without the computer)
// On the phone page (brain.html) the app hands copies in with KurootoView.take(text), as phone.js's views do:
//   {mode: "brain", snap, computer: "online"|"offline"|"", reach, off, palette: {bg, fg, ...}}
// Plain facts only (the server leaves out anything named for money or health; senses are counts). No inline styles
// (the phone page's CSP): colours and widths are set through the DOM after drawing. Chrome 58 syntax: no ?. or ??,
// no object spread, no class fields, no catch without a binding (tests/unit/test_views.py).
(function () {
  "use strict";
  const TABS = [
    ["now", "Now"], ["timeline", "Timeline"], ["decisions", "Decisions"], ["parts", "Parts"], ["beliefs", "Beliefs"],
    ["experiments", "Experiments"], ["skills", "Skills"], ["plans", "Plans"], ["model", "Model of you"], ["memory", "Memory"],
  ];
  const POLL_MS = 5000;
  const SOURCES = { said: "you said it", saw: "it saw it", inferred: "it inferred it", imagined: "a guess" };
  const STATE = { on: "on", off: "off", shadow: "shadow" };

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (n) => (n == null ? "—" : Number(n).toLocaleString());
  const pct = (x) => (x == null || !isFinite(x) ? "—" : `${Math.round(x * 100)}%`);
  const clamp01 = (x) => Math.max(0, Math.min(1, Number(x) || 0));
  function ago(ts) {
    if (!ts) return "never";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    return `${Math.round(s / 86400)} d ago`;
  }
  function dur(s) {
    s = Math.max(0, s);
    if (s < 90) return `${Math.round(s)} s`;
    if (s < 5400) return `${Math.round(s / 60)} min`;
    if (s < 172800) return `${(s / 3600).toFixed(1)} h`;
    return `${(s / 86400).toFixed(1)} days`;
  }
  const pad = (n) => String(n).padStart(2, "0");
  const hhmm = (ts) => { const d = new Date(ts * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const dayOf = (ts) => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  function dayName(day) {
    const today = dayOf(Date.now() / 1000), y = dayOf(Date.now() / 1000 - 86400);
    if (day === today) return "Today";
    if (day === y) return "Yesterday";
    const d = new Date(`${day}T12:00:00`);
    return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  }
  const when = (ts) => (ts ? `${dayOf(ts) === dayOf(Date.now() / 1000) ? "" : dayName(dayOf(ts)) + " "}${hhmm(ts)}` : "—");
  const shortKey = (k) => String(k).replace(/^mind\./, "");
  const bar = (x, cls) => `<i class="bc-bar${cls ? " " + cls : ""}"><b data-w="${clamp01(x)}"></b></i>`;
  const chip = (t, cls) => `<span class="bc-chip${cls ? " " + cls : ""}">${esc(t)}</span>`;
  const empty = (t) => `<p class="bc-empty">${esc(t)}</p>`;
  const card = (title, body, extra) => `<div class="bc-card${extra ? " " + extra : ""}">${title ? `<h3>${title}</h3>` : ""}${body}</div>`;
  const kv = (rows, cls) => `<dl class="bc-kv${cls ? " " + cls : ""}">${rows.map((r) => `<dt>${esc(r[0])}</dt><dd>${r[1]}</dd>`).join("")}</dl>`;
  function fields(body) {
    const keys = Object.keys(body || {});
    if (!keys.length) return "";
    return `<dl class="bc-fields">${keys.map((k) => { const v = body[k]; return `<dt>${esc(k)}</dt><dd>${esc(typeof v === "object" && v !== null ? JSON.stringify(v) : v)}</dd>`; }).join("")}</dl>`;
  }

  function mount(host, opts) {
    opts = opts || {};
    const phone = opts.mode === "phone";
    const S = {
      data: null, tab: "now", part: "", day: "", q: "", open: null, openRow: null, paged: false,
      tl: null, found: null, tlKey: "", poll: null, stopped: false, sig: {}, beliefSrc: "", sticky: {},
    };
    try { const t = localStorage.getItem("kurooto.console.tab"); if (t && TABS.some((x) => x[0] === t)) S.tab = t; } catch (e) { /* fine */ }
    host.innerHTML = `<div class="bc${phone ? " bc-phone" : ""}">
      <div class="bc-head">
        <div class="bc-title"><h2>Brain console</h2><span class="bc-status" role="status"></span></div>
        <label class="bc-find"><input type="search" placeholder="Search what it logged, believes and plans" spellcheck="false" autocomplete="off" aria-label="search the Brain"></label>
      </div>
      <div class="bc-tabs" role="tablist">${TABS.map((t) => `<span tabindex="0" role="tab" data-tab="${t[0]}">${t[1]}</span>`).join("")}</div>
      <div class="bc-wrap"><div class="bc-body"></div><div class="bc-detail hidden" aria-live="polite"></div></div>
    </div>`;
    const root = host.querySelector(".bc"), body = root.querySelector(".bc-body"), detail = root.querySelector(".bc-detail");
    const status = root.querySelector(".bc-status"), find = root.querySelector(".bc-find input"), tabs = root.querySelector(".bc-tabs");

    // ------------------------------------------------------------------------------------------- after drawing
    function paint(el) {
      const bars = el.querySelectorAll("[data-w]");
      for (let i = 0; i < bars.length; i++) bars[i].style.width = `${Math.round(clamp01(bars[i].getAttribute("data-w")) * 1000) / 10}%`;
      const dots = el.querySelectorAll("[data-c]");
      for (let i = 0; i < dots.length; i++) { const c = dots[i].getAttribute("data-c"); if (/^#[0-9a-f]{6}$/i.test(c)) dots[i].style.setProperty("--c", c); }
    }
    function show(el, html) {
      const keep = el.scrollTop;
      el.innerHTML = html;
      paint(el);
      el.scrollTop = keep;
    }

    // --------------------------------------------------------------------------------------------- the parts
    function partIndex() {
      const idx = {};
      for (const isl of (S.data && S.data.islands) || []) for (const p of isl.parts) idx[p.id] = { name: p.name, color: isl.color, island: isl.name };
      idx.log = idx.log || { name: "Mind log", color: "", island: "" };
      return idx;
    }
    const dot = (part) => { const p = partIndex()[part] || {}; return `<i class="bc-dot" data-c="${esc(p.color || "")}" title="${esc(p.name || part)}"></i>`; };
    const partName = (part) => (part === "log" ? "What it saw" : (partIndex()[part] || {}).name || part);
    function partOptions() {
      let html = `<option value="">Every part</option><option value="log"${S.part === "log" ? " selected" : ""}>What it saw (Kurooto's events)</option>`;
      for (const isl of (S.data && S.data.islands) || []) {
        html += `<optgroup label="${esc(isl.name)}">${isl.parts.filter((p) => p.id !== "log").map((p) => `<option value="${esc(p.id)}"${S.part === p.id ? " selected" : ""}>${esc(p.name)}</option>`).join("")}</optgroup>`;
      }
      return html;
    }

    // --------------------------------------------------------------------------------------------- the status
    function head() {
      const d = S.data;
      if (!d) { status.textContent = "loading…"; return; }
      if (d.off) { status.textContent = d.why || "off"; return; }
      const bits = [];
      if (!d.on) bits.push("Brain is off");
      else {
        bits.push(`${d.parts_on} of ${d.parts_total} parts on`);
        bits.push(`${num(d.records)} records`);
        bits.push(d.running ? "scorekeeper running" : "scorekeeper not running");
      }
      const fresh = d.made && Date.now() / 1000 - d.made < (phone ? 20 : 12) && (!phone || S.computer === "online");
      const asof = d.made ? (fresh ? '<span class="bc-live">live</span>' : `as of ${esc(when(d.made))}`) : "";
      const warn = phone && S.reach === false ? ' · <span class="bc-warn">can\'t reach your call line</span>'
        : phone && S.computer === "offline" ? ' · <span class="bc-warn">your computer is asleep</span>' : "";
      status.innerHTML = `${asof}${asof ? " · " : ""}${esc(bits.join(" · "))}${warn}`;
    }

    // ------------------------------------------------------------------------------------------------- Now
    const GOOD = /^(acted|answered|done|kept|ok|helped)$/, BAD = /^(undo|undone|complaint|rejected|muted|less|broken)$/;
    const outcomeChip = (o) => (o ? chip(o, GOOD.test(o) ? "bc-ok" : BAD.test(o) ? "bc-bad" : "") : "");
    function rowsOfDecisions(list) {
      if (!list.length) return empty("No decisions yet. A message it starts, a request it queues or a proposal it makes at night is recorded here before it acts.");
      let html = "", last = "";
      for (const d of list) {
        const day = dayOf(d.ts);
        if (day !== last) { html += `<li class="bc-day">${esc(dayName(day))}</li>`; last = day; }
        html += `<li class="bc-row bc-click" data-dec="${esc(d.id)}">
          <span class="bc-time">${esc(hhmm(d.ts))}</span>
          <span class="bc-main"><b>${esc(d.action)}</b>${d.reason ? `<span class="bc-sub">${esc(d.reason)}</span>` : ""}</span>
          <span class="bc-tags">${chip(d.source === "rules" ? "rules" : d.source.replace(/^ai:/, "AI: "))}${outcomeChip(d.outcome)}</span></li>`;
      }
      return `<ul class="bc-list">${html}</ul>`;
    }
    function tabNow() {
      const d = S.data, th = d.thinking || {};
      const spot = th.on === false ? empty("The workspace is off (mind.workspace.on).") : (th.rows || []).length
        ? `<ul class="bc-list">${th.rows.map((w) => `<li class="bc-row"><span class="bc-main"><b>${w.text ? esc(w.text) : '<span class="bc-dim">about you: kept private</span>'}</b><span class="bc-sub">${esc(w.kind)} · ${esc(SOURCES[w.source] || w.source)}${w.pinned ? " · pinned" : ""}${w.since ? ` · since ${esc(when(w.since))}` : ""}</span></span><span class="bc-tags">${bar(w.salience)}</span></li>`).join("")}</ul>`
        : empty("Nothing in the spotlight right now.");
      const parts = [];
      for (const isl of d.islands || []) for (const p of isl.parts) if (p.doing && p.doing.n24) parts.push([p, isl]);
      parts.sort((a, b) => b[0].doing.n24 - a[0].doing.n24);
      const top = parts.length ? Math.max.apply(null, parts.map((x) => x[0].doing.n24)) : 1;
      const busy = parts.length ? `<ul class="bc-list">${parts.slice(0, 7).map((x) => `<li class="bc-row bc-click" data-goto-part="${esc(x[0].id)}"><i class="bc-dot" data-c="${esc(x[1].color)}"></i><span class="bc-main"><b>${esc(x[0].name)}</b><span class="bc-sub">${esc(x[0].doing.line || "")}${x[0].doing.last ? " · " + esc(ago(x[0].doing.last)) : ""}</span></span><span class="bc-tags"><span class="bc-n">${num(x[0].doing.n24)}</span>${bar(x[0].doing.n24 / top)}</span></li>`).join("")}</ul>`
        : empty("No part has written anything in the last day.");
      const mem = d.memory || {};
      const limits = (mem.limits || []).length ? kv(mem.limits.map((r) => [r[0], esc(r[1])])) : empty("The gate is off: no limits counted.");
      const senses = `<ul class="bc-senses">${((d.senses || {}).rows || []).map((r) => `<li class="${r.on ? "" : "bc-offline"}"><span>${esc(r.name)}</span><b>${r.on ? num(r.today) : "off"}</b></li>`).join("")}</ul><p class="bc-note">Readings kept today, counted. What they were stays on your computer.</p>`;
      return `<div class="bc-grid">
        ${card("In the spotlight", spot)}
        ${card('Latest decisions <span tabindex="0" role="button" class="bc-link" data-tab="decisions">all</span>', rowsOfDecisions((d.decisions || []).slice(0, 5)))}
        ${card('Busiest parts, last 24 hours <span tabindex="0" role="button" class="bc-link" data-tab="parts">all parts</span>', busy)}
        ${card("Limits today", limits)}
        ${card("Senses", senses)}
      </div>`;
    }

    // -------------------------------------------------------------------------------------------- Timeline
    function localTimeline() {
      const rows = (S.data.timeline || {}).rows || [];
      return rows.filter((r) => (!S.part || r.part === S.part) && (!S.day || dayOf(r.ts) === S.day));
    }
    function timelineRows(rows) {
      let html = "", last = "";
      for (const r of rows) {
        const day = dayOf(r.ts);
        if (day !== last) { html += `<li class="bc-day">${esc(dayName(day))}</li>`; last = day; }
        const open = S.openRow === r.seq;
        html += `<li class="bc-row bc-click${open ? " open" : ""}" ${r.kind === "decision" && r.body && r.body.id ? `data-dec="${esc(r.body.id)}"` : `data-seq="${r.seq}"`}>
          <span class="bc-time">${esc(hhmm(r.ts))}</span>${dot(r.part)}
          <span class="bc-main"><b>${esc(r.text)}</b><span class="bc-sub">${esc(partName(r.part))} · ${esc(r.kind)} · #${r.seq}</span>${open ? fields(r.body) : ""}</span></li>`;
      }
      return html;
    }
    function tabTimeline() {
      const days = (S.data.days || []).map((x) => `<option value="${esc(x.day)}"${S.day === x.day ? " selected" : ""}>${esc(dayName(x.day))} (${num(x.n)})</option>`).join("");
      const bar_ = `<div class="bc-filters"><select data-f="part" aria-label="part">${partOptions()}</select>
        <select data-f="day" aria-label="day"><option value="">Every day</option>${days}</select>
        ${S.part || S.day ? '<span tabindex="0" role="button" class="bc-link" data-f="clear">clear</span>' : ""}</div>`;
      const rows = S.tl && S.tlKey === tlKey() ? S.tl.rows : localTimeline();
      const more = !!opts.api && (S.tl && S.tlKey === tlKey() ? S.tl.more : !S.part && !S.day && !!(S.data.timeline || {}).more);
      const list = rows.length ? `<ul class="bc-list bc-tl">${timelineRows(rows)}</ul>`
        : empty(S.part || S.day ? "Nothing from that part on that day." : "The log is empty. Brain writes here once it's on.");
      const foot = more ? '<span tabindex="0" role="button" class="bc-more" data-more="1">Older</span>'
        : phone && rows.length ? '<p class="bc-note">The newest records are on the phone; older ones stay on your computer.</p>' : "";
      return bar_ + list + foot;
    }
    const tlKey = () => `${S.part}|${S.day}`;
    // the dashboard asks for a filtered page (and older pages) itself; with no filter the copy's newest rows show
    function fetchTimeline(older) {
      if (!opts.api) return;
      const key = tlKey();
      if (!older && !S.part && !S.day) { S.tl = null; S.paged = false; return; }
      const shown = S.tl && S.tlKey === key ? S.tl.rows : older ? (S.data.timeline || {}).rows || [] : [];
      const before = older && shown.length ? shown[shown.length - 1].seq : 0;
      opts.api(`view=timeline&part=${encodeURIComponent(S.part)}&day=${encodeURIComponent(S.day)}&before=${before}&limit=100`).then((r) => {
        if (tlKey() !== key || !r || !r.rows) return;
        S.tl = { rows: older ? shown.concat(r.rows) : r.rows, more: !!r.more };
        S.tlKey = key;
        S.paged = !!older;
        render();
      }).catch(() => {});
    }

    // ------------------------------------------------------------------------------------------- Decisions
    function tabDecisions() {
      const list = S.data.decisions || [];
      return `<p class="bc-note">What it decided on its own, before acting: the reason its rules gave, the AI's words when an AI chose, what it weighed and what came of it. Open one for the evidence.</p>${rowsOfDecisions(list)}`;
    }
    function openDecision(id) {
      S.open = { id: id, d: null };
      const local = (S.data.decisions || []).find((x) => x.id === id);
      if (local && local.evidence) S.open.d = local;
      else if (opts.api) {
        opts.api(`view=decision&id=${encodeURIComponent(id)}`).then((d) => { if (S.open && S.open.id === id) { S.open.d = d && d.id ? d : { missing: true }; drawDetail(); } }).catch(() => {});
      } else S.open.d = local ? Object.assign({}, local, { evidence: null }) : { missing: true };
      drawDetail();
      // a narrow dashboard puts it above the list: bring it into sight
      if (!phone && detail.scrollIntoView && detail.getBoundingClientRect().top < 0) detail.scrollIntoView({ block: "start" });
    }
    function evRows(rows) {
      if (!rows || !rows.length) return empty("Nothing in the log then.");
      return `<ul class="bc-list bc-tight">${rows.map((r) => `<li class="bc-row"><span class="bc-time">${esc(hhmm(r.ts))}</span>${dot(r.part)}<span class="bc-main"><b>${esc(r.text)}</b><span class="bc-sub">${esc(r.kind)} · #${r.seq}</span></span></li>`).join("")}</ul>`;
    }
    function drawDetail() {
      if (!S.open) { detail.classList.add("hidden"); root.classList.remove("bc-detail-open"); detail.innerHTML = ""; return; }
      detail.classList.remove("hidden"); root.classList.add("bc-detail-open");
      const d = S.open.d;
      const top = `<div class="bc-dhead"><span tabindex="0" role="button" class="bc-back" data-close="1" aria-label="close">${phone ? "‹ Back" : "Close"}</span><span class="bc-dim">decision</span></div>`;
      if (!d) { show(detail, top + '<p class="bc-empty">loading…</p>'); return; }
      if (d.missing) { show(detail, top + empty("That decision isn't in the log any more.")); return; }
      const best = Math.max.apply(null, [0.0001].concat((d.candidates || []).map((c) => Math.abs(c.score || 0))));
      const cands = (d.candidates || []).length ? `<ul class="bc-list bc-tight">${d.candidates.map((c, i) => `<li class="bc-row"><span class="bc-main"><b>${esc(c.action)}</b>${i === 0 && c.action === d.action ? '<span class="bc-sub">chosen</span>' : ""}</span><span class="bc-tags"><span class="bc-n">${esc(Number(c.score).toFixed(2))}</span>${bar(Math.abs(c.score) / best)}</span></li>`).join("")}</ul>` : empty("It weighed nothing else: a rule decided.");
      const claim = d.claim ? `<p>It claimed this moves <b>${esc(d.claim.setpoint)}</b> ${d.claim.effect === "+" ? "up" : "down"}${d.claim.by ? ` by ${esc(d.claim.by)}` : ""}. Only claims made before acting teach it.</p>` : "";
      const setp = (d.setpoints || []).length ? `<p class="bc-sub">Setpoints it named: ${d.setpoints.map(esc).join(", ")}</p>` : "";
      const out = (d.outcomes || []).length ? `<ul class="bc-list bc-tight">${d.outcomes.map((o) => `<li class="bc-row"><span class="bc-time">${esc(when(o.ts))}</span><span class="bc-main"><b>${outcomeChip(o.result)}</b>${o.value != null ? `<span class="bc-sub">value ${esc(o.value)}</span>` : ""}</span></li>`).join("")}</ul>` : empty("Nothing recorded of what came of it yet.");
      const ev = d.evidence;
      let evh = "";
      if (ev) {
        evh = card("What it has learned about this kind of action", (ev.learned || []).length ? kv(ev.learned.map((r) => [r[0], esc(r[1])])) : empty("Nothing yet."), "bc-flat") +
          card("In the log just before", evRows(ev.before), "bc-flat") +
          card("And just after", evRows(ev.after), "bc-flat") +
          card("Its journal on it", (ev.journal || []).length ? `<ul class="bc-quote">${ev.journal.map((j) => `<li>${esc(j.text)} <span class="bc-dim">${esc(dayName(j.day))}</span></li>`).join("")}</ul>` : empty("Its journal doesn't cite this one."), "bc-flat") +
          card("Earlier decisions of the same kind", (ev.earlier || []).length ? `<p>${ev.earlier.map((e) => `<span class="bc-chip">${esc(when(e.ts))}</span>`).join(" ")}</p>` : empty("This is the first."), "bc-flat");
      } else evh = empty(phone ? "Its evidence stays on your computer for older decisions: open it on the dashboard." : "loading the evidence…");
      show(detail, `${top}<h3 class="bc-dtitle">${esc(d.action)}</h3>
        <p class="bc-sub">${esc(when(d.ts))} · ${esc(d.source === "rules" ? "decided by rules" : "chosen by " + d.source.replace(/^ai:/, "an AI: "))}${d.risk ? ` · class ${esc(d.risk)}` : ""} · #${d.seq}</p>
        ${card("Why", kv([["The reason its rules gave", d.reason ? `<code>${esc(d.reason)}</code>` : '<span class="bc-dim">none given</span>']].concat(d.stated ? [["What the AI said", `“${esc(d.stated)}”`]] : []), "bc-stack") + claim + setp, "bc-flat")}
        ${card("What it weighed", cands, "bc-flat")}
        ${card("What came of it", out, "bc-flat")}
        <h4 class="bc-ev">Evidence</h4>${evh}`);
      detail.scrollTop = 0;
    }

    // ------------------------------------------------------------------------------------------------ Parts
    function settingRow(p, s) {
      const isBool = typeof s.value === "boolean";
      const sw = isBool && opts.toggle && S.data.on !== false
        ? `<span tabindex="0" class="bc-switch${s.value ? " on" : ""}" role="switch" aria-checked="${s.value}" data-key="${esc(s.key)}" data-v="${s.value ? 1 : 0}" aria-label="${esc(shortKey(s.key))}"><i></i></span>`
        : `<span class="bc-val${isBool ? (s.value ? " on" : " off") : ""}">${esc(isBool ? (s.value ? "on" : "off") : Array.isArray(s.value) ? s.value.join(", ") || "none" : typeof s.value === "object" && s.value ? JSON.stringify(s.value) : s.value === "" ? "—" : s.value)}</span>`;
      return `<li><span class="bc-skey"><code>${esc(shortKey(s.key))}</code>${s.tip ? `<span class="bc-tip">${esc(s.tip)}</span>` : ""}</span>${sw}</li>`;
    }
    function tabParts() {
      const d = S.data;
      if (!d.on) return empty("Brain is off. Turn it on in Features → Brain; each part then has its own switch here.") + partsHtml(d);
      return partsHtml(d);
    }
    function partsHtml(d) {
      return (d.islands || []).map((isl) => `<div class="bc-island"><h3><i class="bc-dot" data-c="${esc(isl.color)}"></i>${esc(isl.name)} <span class="bc-dim">${esc(isl.tag)}</span></h3>
        <div class="bc-grid">${isl.parts.map((p) => {
          const g = p.doing || {};
          const doing = [];
          if (g.now) doing.push(esc(g.now));
          if (g.last) doing.push(`last: ${esc(g.line)} <span class="bc-dim">${esc(ago(g.last))}</span>`);
          if (g.n24) doing.push(`${num(g.n24)} record${g.n24 === 1 ? "" : "s"} in the last day`);
          for (const m of g.metrics || []) doing.push(`${esc(m[0])}: ${esc(m[1])}`);
          return `<div class="bc-part${p.on ? "" : " bc-offline"}${S.sticky.part === p.id ? " bc-hl" : ""}" id="bc-part-${esc(p.id)}">
            <div class="bc-ph"><b>${esc(p.name)}</b><span class="bc-state bc-${esc(p.state)}">${esc(STATE[p.state] || p.state)}</span></div>
            <p class="bc-sub">${esc(p.desc)}</p>
            <div class="bc-doing">${doing.length ? doing.map((x) => `<div>${x}</div>`).join("") : '<div class="bc-dim">' + (p.on ? "quiet so far" : "doing nothing: it's off") + "</div>"}
              ${g.n ? `<span tabindex="0" role="button" class="bc-link" data-goto-tl="${esc(p.id)}">its timeline</span>` : ""}</div>
            ${p.settings.length ? `<ul class="bc-settings">${p.settings.map((s) => settingRow(p, s)).join("")}</ul>` : `<p class="bc-note">${p.switch ? "" : "Always there with Brain: no switch of its own."}</p>`}
          </div>`;
        }).join("")}</div></div>`).join("");
    }

    // ---------------------------------------------------------------------------------------------- Beliefs
    function tabBeliefs() {
      const b = S.data.beliefs || {};
      if (b.on === false && !(b.rows || []).length) return empty("Beliefs are off (mind.beliefs.on).");
      const brier = Object.keys(b.brier || {}).length ? `<p class="bc-note">How each kind has fared (Brier score, lower is better, 0.25 is a coin flip): ${Object.keys(b.brier).map((k) => `${esc(SOURCES[k] || k)} ${esc(b.brier[k].brier.toFixed(2))} over ${num(b.brier[k].n)}`).join(" · ")}</p>` : "";
      const srcs = ["", "said", "saw", "inferred", "imagined"];
      const filt = `<div class="bc-filters bc-seg">${srcs.map((s) => `<span tabindex="0" role="button" data-bsrc="${s}" class="${S.beliefSrc === s ? "on" : ""}">${s ? esc(s) : "all"}</span>`).join("")}</div>`;
      const rows = (b.rows || []).filter((r) => !S.beliefSrc || r.source === S.beliefSrc);
      const list = rows.length ? `<ul class="bc-list">${rows.map((r) => `<li class="bc-row"><span class="bc-main"><b>${esc(r.text)}</b><span class="bc-sub">${esc(SOURCES[r.source] || r.source)}${r.topic ? " · " + esc(r.topic) : ""} · ${esc(ago(r.at))}</span></span>
        <span class="bc-tags">${r.outcome === true ? chip("came true", "bc-ok") : r.outcome === false ? chip("was wrong", "bc-bad") : chip("open")}<span class="bc-n">${pct(r.confidence)}</span>${bar(r.confidence)}</span></li>`).join("")}</ul>` : empty("No beliefs of that kind yet.");
      const hidden = b.hidden ? `<p class="bc-note">${num(b.hidden)} belief${b.hidden === 1 ? "" : "s"} about money or health aren't shown here.</p>` : "";
      return `<p class="bc-note">Every belief keeps where it came from. Only what you said or it saw may be said to you as fact; the rest is worded as a guess.</p>${filt}${brier}${list}${hidden}`;
    }

    // ------------------------------------------------------------------------------------------ Experiments
    function tabExperiments() {
      const e = S.data.experiments || {};
      const lab = (e.lab || []).length ? `<div class="bc-grid">${e.lab.map((p) => card(`${esc(p.project)} <span class="bc-state bc-${p.protocol === "approved" ? "on" : "shadow"}">protocol ${esc(p.protocol)}</span>`,
        `${p.objective ? `<p>${esc(p.objective)}</p>` : ""}${p.hypothesis ? `<p class="bc-sub">Hypothesis: ${esc(p.hypothesis)}</p>` : ""}
        ${kv([["Metric", esc(p.metric || "—")], ["Batches", `${num(p.registered)} pre-registered, ${num(p.finished)} finished`], ["Wins", `${num(p.wins)}, ${num(p.replicated)} replicated (${pct(p.rate)})`]].concat(p.waiting ? [["Waiting", `${num(p.waiting)} runs`]] : []).concat(p.last ? [["Last batch", `${num(p.last.ok)} ran, ${num(p.last.failed)} failed, ${num(p.last.wins)} won${p.last.nulls && p.last.nulls.length ? "; null on " + esc(p.last.nulls.join(", ")) : ""}`]] : []))}`)).join("")}</div>`
        : empty(e.lab_on ? "No projects in the lab yet: add a folder to mind.lab.projects." : "The lab is off (mind.lab.on).");
      const imp = (e.improve || []).length ? `<ul class="bc-list">${e.improve.map((r) => `<li class="bc-row"><span class="bc-main"><b>${esc(r.title)}</b><span class="bc-sub">${esc(r.id)} · layer ${esc(r.layer)}${r.status === "shadow" && r.shadow_until ? ` · in shadow until ${esc(dayName(dayOf(r.shadow_until)))}` : ""}</span></span><span class="bc-tags">${chip(r.status.replace(/_/g, " "), r.status === "promoted" ? "bc-ok" : r.status === "rejected" || r.status === "rolled_back" ? "bc-bad" : "")}</span></li>`).join("")}</ul>`
        : empty(e.improve_on ? "No challengers. Nothing changes itself without the hidden harness and your say-so." : "Self-improvement is off (mind.improve.on).");
      const p = e.play || {};
      const play = p.on ? kv([["Questions explored", num(p.explored)], ["Credited (gains that transferred)", num(p.credited)], ["Outputs kept", num(p.outputs)]]) : empty("Play is off (mind.play.on).");
      return `${card("Research lab", `<p class="bc-note">Pre-registered overnight experiments: the hypothesis and the analysis are fixed before a run; null results count as much as wins.</p>${lab}`, "bc-flat")}
        ${card("Self-improvement", imp, "bc-flat")}${card("Play", play, "bc-flat")}`;
    }

    // ----------------------------------------------------------------------------------------------- Skills
    function tabSkills() {
      const s = S.data.skills || {};
      if (!(s.rows || []).length) return empty(s.on === false ? "Learned skills are off (mind.skills.on)." : "No learned skills yet. Tasks that worked out become tested skills; each asks first.");
      return `<ul class="bc-list">${s.rows.map((r) => `<li class="bc-row${r.retired ? " bc-offline" : ""}"><span class="bc-main"><b>${esc(r.title)}</b><span class="bc-sub">${esc(r.slug)} · ${esc(r.when)}${r.last_used ? " · used " + esc(ago(r.last_used)) : ""}</span></span>
        <span class="bc-tags">${chip(r.retired ? "retired" : r.status.replace(/-/g, " "))}<span class="bc-n">${r.uses ? `${num(r.ok)}/${num(r.uses)}` : "unused"}</span>${r.uses ? bar(r.ok / r.uses) : ""}</span></li>`).join("")}</ul>`;
    }

    // ------------------------------------------------------------------------------------------------ Plans
    function tabPlans() {
      const p = S.data.plans || {};
      if (!p.on) return empty("Week plans are off (mind.plans.on).");
      const c = p.calibration || {};
      const cal = `<p class="bc-note">${c.on_time == null ? `How well past plans held: ${num(c.n)} milestone(s) scored, too few to say.` : `How well past plans held: ${pct(c.on_time)} finished by their likely date (about 50% is calibrated).`}${p.planned ? ` Last planned ${esc(dayName(p.planned))}.` : ""} A suggestion, never a to-do.</p>`;
      if (!(p.rows || []).length) return cal + empty("Nothing to plan: no open deadlines or milestones in the next weeks.");
      return cal + `<ul class="bc-list">${p.rows.map((r) => `<li class="bc-row"><span class="bc-time">${esc(dayName(dayOf(r.due)))}</span><span class="bc-main"><b>${esc(r.title)}</b><span class="bc-sub">${esc(r.source)} · ${esc(r.effort_h)} h${r.guessed ? " (a guess)" : ""}${r.done ? ` · ${pct(r.done)} done` : ""}${r.p50 ? ` · likely done ${esc(dayName(r.p50))}` : ""}</span></span>
        <span class="bc-tags">${r.risk == null ? chip("not planned yet") : `<span class="bc-n">${pct(r.risk)} late</span>${bar(r.risk, r.risk >= 0.3 ? "bc-hot" : "")}`}</span></li>`).join("")}</ul>`;
    }

    // ------------------------------------------------------------------------------------------ Model of you
    function tabModel() {
      const m = S.data.model || {};
      if (m.on === false && !(m.rows || []).length) return empty("The model of you is off (mind.tom.on).");
      const counts = Object.keys(m.counts || {}).map((k) => chip(`${k} ${num(m.counts[k])}`)).join(" ");
      const rows = (m.rows || []).length ? `<ul class="bc-list">${m.rows.map((r) => `<li class="bc-row"><span class="bc-main"><b>${esc(r.claim)}</b><span class="bc-sub">${esc(r.part)}${r.subject ? " · " + esc(r.subject) : ""} · ${esc(SOURCES[r.source] || r.source)} · ${num(r.evidence)} piece${r.evidence === 1 ? "" : "s"} of evidence</span></span><span class="bc-tags"><span class="bc-n">${pct(r.confidence)}</span>${bar(r.confidence)}</span></li>`).join("")}</ul>`
        : empty("Nothing yet.");
      return `<p class="bc-note">What it thinks you know, believe, want, prefer and attend to. It may only make Kurooto more helpful and quieter, never more persuasive; it never models your inner life. Mark a row wrong or forget it with /model.</p>
        <p>${counts}</p>${rows}<p class="bc-note">${num(m.forgot)} forgotten at your word · ${num(m.denied)} left unkept because of their topic.</p>`;
    }

    // ---------------------------------------------------------------------------------------------- Memory
    function tabMemory() {
      const m = S.data.memory || {}, f = m.forgot || {}, st = m.stops || {}, pr = m.promises || {};
      const forgot = `${kv([["Times you asked it to forget", num(f.times)], ["Rows of the model of you forgotten", num(f.model)]])}${(f.events || []).length ? `<ul class="bc-list bc-tight">${f.events.map((e) => `<li class="bc-row"><span class="bc-time">${esc(when(e.ts))}</span><span class="bc-main"><b>forgot ${num(e.n)} thing${e.n === 1 ? "" : "s"}</b><span class="bc-sub">what, it doesn't keep · #${e.seq}</span></span></li>`).join("")}</ul>` : ""}`;
      const stops = `${(st.spans || []).length ? `<ul class="bc-list bc-tight">${st.spans.map((s) => `<li class="bc-row"><span class="bc-time">${esc(when(s.start))}</span><span class="bc-main"><b>${esc(s.kind.replace(/_/g, " "))} for ${esc(dur(s.end - s.start))}</b><span class="bc-sub">its drive was frozen; stopping is fine</span></span></li>`).join("")}</ul>` : empty("No stops in the last 30 days.")}<p class="bc-note">${num(st.crashes)} crash${st.crashes === 1 ? "" : "es"} in the last 30 days.</p>`;
      const limits = (m.limits || []).length ? kv(m.limits.map((r) => [r[0], esc(r[1])])) : empty("The gate is off.");
      const pc = pr.counts || {};
      const prom = `<p>${chip(`${num(pc.open)} open`)} ${chip(`${num(pc.kept)} kept`, pc.kept ? "bc-ok" : "")} ${chip(`${num(pc.broken)} broken`, pc.broken ? "bc-bad" : "")} ${chip(`${num(pc.renegotiated)} renegotiated`)}</p>${(pr.rows || []).length ? `<ul class="bc-list bc-tight">${pr.rows.map((r) => `<li class="bc-row"><span class="bc-time">${esc(when(r.due))}</span><span class="bc-main"><b>${esc(r.text)}</b></span><span class="bc-tags">${chip(r.state, r.state === "kept" ? "bc-ok" : r.state === "broken" ? "bc-bad" : "")}</span></li>`).join("")}</ul>` : ""}`;
      const jour = (m.journal || []).length ? `<ul class="bc-list bc-tight">${m.journal.map((j) => `<li class="bc-row"><span class="bc-main"><b>${esc(dayName(j.day))}</b><span class="bc-sub">${num(j.lines)} line${j.lines === 1 ? "" : "s"} from ${num(j.facts)} facts${j.rejected ? `, ${num(j.rejected)} reworded to the fixed words` : ""}</span></span></li>`).join("")}</ul>` : empty("No journal yet.");
      const story = (m.story || []).length ? `<ul class="bc-list bc-tight">${m.story.map((c) => `<li class="bc-row"><span class="bc-main"><b>Week ${esc(c.week)}</b><span class="bc-sub">${num(c.lines)} line${c.lines === 1 ? "" : "s"}${c.struck ? `, ${num(c.struck)} struck` : ""}${c.quoted ? `, ${num(c.quoted)} quoted` : ""}</span></span></li>`).join("")}</ul>` : empty("No chapters yet.");
      return `<div class="bc-grid">${card("What it forgot", forgot)}${card("Stops", stops)}${card("Limits today", limits)}${card("Promises", prom)}
        ${card("Journal", `<p class="bc-note">Headings only; /mindjournal reads a day.</p>${jour}`)}${card("Life story", `<p class="bc-note">Headings only; /story reads it.</p>${story}`)}</div>`;
    }

    // ---------------------------------------------------------------------------------------------- Search
    function localSearch(q) {
      const ql = q.toLowerCase(), d = S.data, has = (s) => String(s || "").toLowerCase().indexOf(ql) >= 0;
      const log = ((d.timeline || {}).rows || []).filter((r) => has(r.kind) || has(r.text) || has(JSON.stringify(r.body)));
      const other = [];
      for (const r of (d.beliefs || {}).rows || []) if (has(r.text) || has(r.topic)) other.push({ in: "beliefs", text: r.text, note: r.source });
      for (const r of (d.model || {}).rows || []) if (has(r.claim) || has(r.subject)) other.push({ in: "model", text: r.claim, note: r.part });
      for (const r of (d.skills || {}).rows || []) if (has(r.title) || has(r.slug) || has(r.when)) other.push({ in: "skills", text: r.title, note: r.slug });
      for (const r of (d.plans || {}).rows || []) if (has(r.title)) other.push({ in: "plans", text: r.title, note: r.kind });
      for (const r of (d.experiments || {}).lab || []) if (has(r.project) || has(r.objective)) other.push({ in: "experiments", text: r.project, note: r.protocol });
      for (const isl of d.islands || []) for (const p of isl.parts) {
        if (has(p.name) || has(p.desc)) other.push({ in: "parts", text: p.name, note: p.state, part: p.id });
        for (const s of p.settings) if (has(s.key) || has(s.tip)) other.push({ in: "settings", text: s.key, note: typeof s.value === "boolean" ? (s.value ? "on" : "off") : String(s.value), part: p.id });
      }
      return { q: q, log: log, other: other.slice(0, 60) };
    }
    const IN = { beliefs: "Beliefs", model: "Model of you", skills: "Skills", plans: "Plans", experiments: "Experiments", parts: "Parts", settings: "Settings" };
    function tabSearch() {
      const r = S.found;
      if (!r) return '<p class="bc-empty">searching…</p>';
      r.log = r.log || []; r.other = r.other || [];
      const log = r.log.length ? `<ul class="bc-list bc-tl">${timelineRows(r.log)}</ul>` : empty("Nothing in the log.");
      const other = r.other.length ? `<ul class="bc-list">${r.other.map((o) => `<li class="bc-row${o.part ? " bc-click" : ""}"${o.part ? ` data-goto-part="${esc(o.part)}"` : ""}><span class="bc-main"><b>${esc(o.text)}</b><span class="bc-sub">${esc(o.note)}</span></span><span class="bc-tags">${chip(IN[o.in] || o.in)}</span></li>`).join("")}</ul>` : empty("Nothing else matches.");
      return `${card(`What it kept${phone ? " (on this phone)" : ""}`, other, "bc-flat")}${card(`In the log${phone ? ", the newest records" : ""}`, log, "bc-flat")}`;
    }
    let searchT = null;
    function runSearch() {
      const q = S.q.trim();
      if (q.length < 2) { S.found = null; render(); return; }
      if (!opts.api) { S.found = localSearch(q); render(); return; }
      S.found = null; render();
      opts.api(`view=search&q=${encodeURIComponent(q)}`).then((r) => { if (S.q.trim() === q && r) { S.found = r; render(); } }).catch(() => {});
    }

    // --------------------------------------------------------------------------------------------- drawing
    const DRAW = { now: tabNow, timeline: tabTimeline, decisions: tabDecisions, parts: tabParts, beliefs: tabBeliefs, experiments: tabExperiments, skills: tabSkills, plans: tabPlans, model: tabModel, memory: tabMemory };
    // what has the keyboard's focus in the body, so a redraw can give it back
    const FOCUS = ["data-key", "data-f", "data-bsrc", "data-dec", "data-seq", "data-more", "data-goto-tl", "data-goto-part", "data-tab"];
    function focusSel() {
      const a = document.activeElement;
      if (!a || a === body || !body.contains(a)) return "";
      for (const k of FOCUS) if (a.hasAttribute(k)) return `[${k}="${String(a.getAttribute(k)).replace(/["\\]/g, "\\$&")}"]`;
      return "";
    }
    // soft: a fresh copy arrived (every few seconds). It waits while a filter of the body is in use (redrawing would
    // close its list under the hand) and draws when that filter lets go of the focus.
    function render(soft) {
      if (S.stopped) return;
      head();
      const searching = S.q.trim().length >= 2;
      const tb = tabs.querySelectorAll("[data-tab]");
      for (let i = 0; i < tb.length; i++) {
        const on = !searching && tb[i].getAttribute("data-tab") === S.tab;
        tb[i].className = on ? "on" : ""; tb[i].setAttribute("aria-selected", on ? "true" : "false");
        if (on && S.shownTab !== S.tab) { // a narrow screen: the chosen tab scrolls into sight
          S.shownTab = S.tab;
          if (tb[i].offsetLeft < tabs.scrollLeft || tb[i].offsetLeft + tb[i].offsetWidth > tabs.scrollLeft + tabs.clientWidth) tabs.scrollLeft = Math.max(0, tb[i].offsetLeft - 16);
        }
      }
      const d = S.data;
      let html;
      if (!d) html = '<p class="bc-empty">loading…</p>';
      else if (d.off) html = empty(d.why || "Off on your computer.");
      else if (searching) html = tabSearch();
      else html = DRAW[S.tab]();
      const sig = (searching ? "?" + S.q : S.tab) + "|" + html.length + "|" + html;
      if (sig !== S.sig.body) {
        const a = document.activeElement;
        if (soft && a && a.tagName === "SELECT" && body.contains(a)) S.waiting = true;
        else {
          const f = focusSel();
          S.sig.body = sig; S.waiting = false; show(body, html);
          const back = f ? body.querySelector(f) : null;
          if (back && back.focus) back.focus();
        }
      }
      if (S.sticky.part && S.tab === "parts" && !searching) {
        const el = body.querySelector(`#bc-part-${S.sticky.part}`);
        if (el && el.scrollIntoView) el.scrollIntoView({ block: "center" });
        S.sticky.part = "";
      }
    }
    function setTab(t) {
      S.tab = t; S.q = ""; find.value = ""; S.found = null;
      try { localStorage.setItem("kurooto.console.tab", t); } catch (e) { /* fine */ }
      body.scrollTop = 0;
      render();
    }

    // ---------------------------------------------------------------------------------------------- input
    tabs.addEventListener("click", (e) => { const b = e.target.closest("[data-tab]"); if (b) setTab(b.getAttribute("data-tab")); });
    find.addEventListener("input", () => { S.q = find.value; clearTimeout(searchT); searchT = setTimeout(runSearch, opts.api ? 250 : 60); });
    find.addEventListener("keydown", (e) => { if (e.key === "Escape" && find.value) { e.preventDefault(); e.stopPropagation(); find.value = ""; S.q = ""; render(); } });
    body.addEventListener("change", (e) => {
      const f = e.target.getAttribute("data-f");
      if (f === "part") S.part = e.target.value;
      else if (f === "day") S.day = e.target.value;
      else return;
      S.openRow = null; S.tl = null; S.paged = false;
      fetchTimeline(false); render();
    });
    body.addEventListener("click", (e) => {
      const t = e.target;
      const tabBtn = t.closest(".bc-link[data-tab]"); if (tabBtn) { setTab(tabBtn.getAttribute("data-tab")); return; }
      if (t.closest('[data-f="clear"]')) { S.part = ""; S.day = ""; S.tl = null; S.paged = false; render(); return; }
      if (t.closest("[data-more]")) { fetchTimeline(true); return; }
      const bs = t.closest("[data-bsrc]"); if (bs) { S.beliefSrc = bs.getAttribute("data-bsrc"); render(); return; }
      const sw = t.closest(".bc-switch");
      if (sw && opts.toggle) {
        const key = sw.getAttribute("data-key"), want = sw.getAttribute("data-v") !== "1";
        if (sw.classList.contains("busy")) return;
        sw.classList.add("busy"); sw.setAttribute("aria-disabled", "true");
        Promise.resolve(opts.toggle(key, want)).then((ok) => { if (ok) { sw.classList.toggle("on", want); sw.setAttribute("data-v", want ? "1" : "0"); sw.setAttribute("aria-checked", String(want)); refresh(); } }).catch(() => {}).then(() => { sw.classList.remove("busy"); sw.removeAttribute("aria-disabled"); });
        return;
      }
      const tl = t.closest("[data-goto-tl]"); if (tl) { S.part = tl.getAttribute("data-goto-tl"); S.day = ""; S.tl = null; S.paged = false; fetchTimeline(false); setTab("timeline"); return; }
      const gp = t.closest("[data-goto-part]"); if (gp) { S.sticky.part = gp.getAttribute("data-goto-part"); setTab("parts"); return; }
      const dec = t.closest("[data-dec]"); if (dec) { openDecision(dec.getAttribute("data-dec")); return; }
      const row = t.closest("[data-seq]");
      if (row && !t.closest("dl")) { const s = Number(row.getAttribute("data-seq")); S.openRow = S.openRow === s ? null : s; S.sig.body = ""; render(); }
    });
    // the controls are spans with a role (the dashboard styles every <button> on its pages): Enter and Space press them
    root.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.getAttribute && /^(button|tab|switch)$/.test(e.target.getAttribute("role") || "") && e.target !== find) {
        e.preventDefault(); e.target.click();
      }
    });
    body.addEventListener("focusout", (e) => { if (S.waiting && e.target.tagName === "SELECT") setTimeout(() => { if (S.waiting) render(); }, 0); });
    detail.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) { S.open = null; drawDetail(); } });
    const onKey = (e) => { if (e.key === "Escape" && S.open && root.isConnected) { e.preventDefault(); e.stopPropagation(); S.open = null; drawDetail(); } };
    window.addEventListener("keydown", onKey, true);

    // ------------------------------------------------------------------------------------------------ data
    function update(data) {
      if (!data || typeof data !== "object") return;
      S.data = data;
      if (S.open && !S.open.d && !opts.api) openDecision(S.open.id);
      if (!opts.api && S.q.trim().length >= 2) S.found = localSearch(S.q.trim());
      render(true);
    }
    function refresh() {
      if (!opts.api || S.stopped) return;
      opts.api("view=all").then((d) => { if (!S.stopped) update(d); }).catch(() => { status.textContent = "can't reach Kurooto right now"; });
      if (S.tab === "timeline" && (S.part || S.day) && !S.paged) fetchTimeline(false);
    }
    function tick() {
      if (S.stopped) return;
      if (!root.isConnected) { stop(); return; }
      if (!document.hidden && root.offsetWidth > 0) refresh();
      else head();
    }
    function stop() {
      S.stopped = true;
      clearInterval(S.poll);
      window.removeEventListener("keydown", onKey, true);
    }
    if (opts.data) update(opts.data);
    else render();
    if (opts.api) { refresh(); S.poll = setInterval(tick, POLL_MS); }
    else S.poll = setInterval(() => { if (!root.isConnected) stop(); else head(); }, 5000); // "live" fades to "as of"
    return {
      update: update,
      stop: stop,
      set: (o) => { if (o) { if ("computer" in o) S.computer = o.computer; if ("reach" in o) S.reach = o.reach; } head(); },
    };
  }

  window.BrainConsole = { mount: mount };

  // ------------------------------------------------------------------------------------- the phone's page
  // brain.html: the app hands in what it opened, as for Systems and the Notes map (phone.js's KurootoView.take)
  if (document.body && document.body.classList.contains("phone-brain")) {
    const KEYS = ["bg", "fg", "accent", "lav", "pink", "peach", "sand", "rose", "bad", "panel"];
    let view = null, palette = "", had = false;
    const hex = (h) => /^#[0-9a-f]{6}$/i.test(h || "");
    function mixHex(a, b, t) {
      const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16), out = [];
      for (let s = 16; s >= 0; s -= 8) { const x = (pa >> s) & 255, y = (pb >> s) & 255; out.push(Math.round(x + (y - x) * t).toString(16).padStart(2, "0")); }
      return "#" + out.join("");
    }
    function setPalette(p) {
      const key = JSON.stringify(p || {});
      if (key === palette || !p) return;
      palette = key;
      const r = document.documentElement.style;
      for (const k of KEYS) if (hex(p[k])) r.setProperty(`--${k}`, p[k]);
      if (hex(p.fg) && hex(p.bg)) { r.setProperty("--dim", mixHex(p.fg, p.bg, 0.45)); r.setProperty("--line", mixHex(p.fg, p.bg, 0.82)); }
      if (hex(p.panel) && hex(p.fg)) r.setProperty("--raised", mixHex(p.panel, p.fg, 0.08));
      if (hex(p.accent)) r.setProperty("--accent-text", p.accent);
    }
    function take(text) {
      let d;
      try { d = JSON.parse(text); } catch (err) { return false; }
      setPalette(d.palette);
      if (!view) view = mount(document.getElementById("brain"), { mode: "phone" });
      view.set({ computer: d.computer || "", reach: d.reach !== false });
      const snap = d.snap && typeof d.snap === "object" ? d.snap : null;
      if (snap) { had = true; view.update(snap); }
      else if (d.off) { had = false; view.update({ off: true, why: "Turned off on your computer: on its dashboard, Phone → Show on the phone." }); } // nothing of it stays
      else if (had) return true; // nothing new: the last copy stays
      else view.update({ off: true, why: d.reach === false ? "Can't reach your call line, and there's no copy on this phone yet." : "Nothing here yet. Your computer sends the Brain while you watch it, when it's on and Brain is on." });
      return true;
    }
    window.KurootoView = { take: take };
  }
})();
