// The Chat page (0.8.14, look.chat_page; web/chat_api.py): the phone app's chat on the dashboard. The same chats and
// messages as the app, newest at the bottom, Kurooto's buttons under its messages, files as links, the app's "Waiting
// for you" questions with their answers, and a box to write in the open chat. A tap or a message here goes the same
// way as one in the app, so a question settles everywhere and the chat's AI context carries. Loaded on demand by
// home.js (renderChat), which calls CHATPAGE.mount(body, api, opts) and hands every {t: "chat"} live message to
// CHATPAGE.live(m). Nothing here is fetched from the internet; the links in messages open like any other link.
"use strict";
(function () {
  const S = { body: null, api: null, opts: {}, list: null, sid: "main", msgs: [], reply: null, note: "", busy: false, timer: 0, readAt: "" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  // .cp .log undoes style.css's .log (a 180 px box): the messages fill the page, the box to write in at its foot
  const CSS = `.cp{display:grid;grid-template-columns:minmax(180px,240px) minmax(0,1fr);gap:14px;height:100%;min-height:420px}
  body:not(.dense) .cp{height:72vh}
  .cp .ss{display:flex;flex-direction:column;gap:2px;overflow:auto;border-right:1px solid var(--rule,var(--line));padding-right:10px}
  .cp .ss button.s{display:flex;flex-direction:column;align-items:stretch;text-align:left;width:100%;padding:6px 8px;border:1px solid transparent;background:none;color:inherit;border-radius:6px;cursor:pointer;font:inherit}
  .cp .ss button.s.on{background:var(--raised,var(--panel));border-color:var(--rule,var(--line))}
  .cp .ss .top{display:flex;gap:6px;align-items:baseline}.cp .ss .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
  .cp .ss .ln{color:var(--dim);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .cp .ss .un{background:var(--accent);color:var(--accent-contrast);border-radius:9px;padding:0 6px;font-size:11px;font-weight:600}
  .cp .ss .wk{color:var(--accent-text);font-size:11px}.cp .ss .new{margin-top:6px}
  .cp .th{display:flex;flex-direction:column;min-width:0;min-height:0}
  .cp .hd{display:flex;gap:8px;align-items:center;padding-bottom:6px;border-bottom:1px solid var(--rule,var(--line))}
  .cp .hd b{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cp .hd .d{font-size:12px}
  .cp .wt{border:1px solid var(--rule,var(--line));border-radius:8px;padding:6px 10px;margin:8px 0 0;max-height:34%;overflow:auto}
  .cp .wt h4{margin:0 0 4px}.cp .wi{padding:6px 0;border-top:1px solid var(--rule,var(--line))}.cp .wi:first-of-type{border-top:0}
  .cp .wi .tx{white-space:pre-wrap;overflow-wrap:anywhere}
  .cp .log{flex:1;overflow:auto;padding:10px 2px;display:flex;flex-direction:column;gap:8px;min-height:0;max-height:none;margin:0}
  .cp .day{align-self:center;color:var(--dim);font-size:11px;margin:6px 0 0}
  .cp .m{max-width:78%;align-self:flex-start;background:var(--raised,var(--panel));border:1px solid var(--rule,var(--line));border-radius:10px;padding:7px 10px}
  .cp .m.you{align-self:flex-end;background:color-mix(in srgb,var(--accent) 16%,var(--panel))}
  .cp .m .tt{font-weight:600;margin-bottom:2px}.cp .m .tx{white-space:pre-wrap;overflow-wrap:anywhere}
  .cp .m .tx code{font-family:var(--code,var(--mono));font-size:.92em;background:color-mix(in srgb,var(--fg) 8%,transparent);padding:0 3px;border-radius:3px}
  .cp .m .q{border-left:2px solid var(--lav);padding-left:6px;color:var(--dim);font-size:12px;margin-bottom:4px;white-space:pre-wrap;overflow-wrap:anywhere}
  .cp .m .meta{color:var(--dim);font-size:11px;margin-top:3px;display:flex;gap:8px;align-items:center}
  .cp .m .meta button{border:0;background:none;color:var(--dim);padding:0;font-size:11px;cursor:pointer;text-decoration:underline}
  .cp .m .bt{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.cp .m .bt a{padding:5px 12px;border:1px solid var(--rule,var(--line));border-radius:6px;font-size:13px}
  .cp .m .fl{margin-top:4px}.cp .m.gone .tx{color:var(--dim);font-style:italic}
  .cp .in{border-top:1px solid var(--rule,var(--line));padding-top:8px}
  .cp .in .re{font-size:12px;color:var(--dim);margin-bottom:4px;display:flex;gap:8px}.cp .in .re span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .cp .in form{display:flex;gap:8px;align-items:flex-end}.cp .in textarea{flex:1;resize:none;min-height:2.4em;max-height:9em;font:inherit;padding:6px 8px;background:var(--panel);color:var(--fg);border:1px solid var(--rule,var(--line))}
  .cp .say{min-height:1.3em;font-size:12px;color:var(--dim)}.cp .say.bad{color:var(--bad)}
  @media (max-width:720px){.cp{grid-template-columns:1fr;height:auto}.cp .ss{border-right:0;max-height:30vh}.cp .log{max-height:60vh}}`;

  // ------------------------------------------------------------------------------------------- helpers
  const here = () => S.body && S.body.isConnected && S.body.querySelector(".cp");
  const hhmm = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const dayOf = (t) => new Date(t * 1000).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  const size = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n || 0} B`);
  const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");
  // what Kurooto writes, safely: escaped first, then `code`, *bold* / **bold** and web links (links.js opens them)
  function rich(text) {
    let h = esc(text);
    h = h.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    h = h.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*(\S(?:[^*\n]*\S)?)\*(?=[\s).,;:!?]|$)/g, "$1<b>$2</b>");
    return h.replace(/https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)]/g, (u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  }
  const session = () => ((S.list && S.list.sessions) || []).find((r) => r.id === S.sid);
  const say = (text, bad) => { S.note = text || ""; const el = S.body && S.body.querySelector(".cp .say"); if (el) { el.textContent = S.note; el.classList.toggle("bad", !!bad); } };

  // ---------------------------------------------------------------------------------------------- load
  function mount(body, api, opts) {
    S.body = body; S.api = api; S.opts = opts || {}; S.reply = null; S.note = "";
    try { S.sid = localStorage.getItem("kurooto.chat.session") || "main"; } catch { S.sid = "main"; }
    if (!document.getElementById("chat-css")) { const st = document.createElement("style"); st.id = "chat-css"; st.textContent = CSS; document.head.appendChild(st); }
    body.onclick = click; body.onsubmit = submit; body.onchange = null;
    body.innerHTML = '<p class="d">Loading the chat…</p>';
    load(true);
  }
  async function load(thread) {
    let r; try { r = await S.api("chat"); } catch { if (S.body) S.body.innerHTML = '<p class="d">The chat could not load.</p>'; return; }
    if (!S.body || !S.body.isConnected) return;
    if (!r || r.on === false || r.off || r.ok === false) { S.list = null; S.body.innerHTML = `<div class="cp-off"><p>${esc((r && r.note) || "The chat isn't available.")}</p>${r && r.on === false && S.opts.open ? '<p><a href="#" data-page="features">Features</a></p>' : ""}</div>`; return; }
    S.list = r;
    if (!session()) S.sid = "main";
    if (thread) await openThread(S.sid, false);
    render(); markRead();
  }
  async function openThread(sid, draw = true) {
    S.sid = sid; S.reply = null;
    try { localStorage.setItem("kurooto.chat.session", sid); } catch { /* fine */ }
    let r; try { r = await S.api(`chat/thread?session=${encodeURIComponent(sid)}`); } catch { r = null; }
    S.msgs = (r && r.msgs) || [];
    if (draw) render();
    markRead();
  }
  // the newest message here counts as read, as when the app shows the chat; the app keeps its own badge (its marks)
  function markRead() {
    const s = session(), lastMsg = S.msgs[S.msgs.length - 1];
    if (!s || !lastMsg || document.hidden || !here()) return;
    if (s.read === lastMsg.id || S.readAt === `${S.sid}:${lastMsg.id}`) return;
    S.readAt = `${S.sid}:${lastMsg.id}`; s.read = lastMsg.id; s.unread = 0;
    S.api("chat/op", { op: "read", session: S.sid, upto: lastMsg.id }).catch(() => {});
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && here()) markRead(); });

  // -------------------------------------------------------------------------------------------- render
  function sessionsHtml() {
    const L = S.list, working = new Set(L.working || []);
    const rows = L.sessions.map((r) => `<button class="s${r.id === S.sid ? " on" : ""}" data-s="${esc(r.id)}"><span class="top"><span class="nm">${esc(r.title || "New chat")}</span>${working.has(r.id) ? '<span class="wk">working</span>' : ""}${r.unread ? `<span class="un" title="unread">${r.unread > 99 ? "99+" : r.unread}</span>` : ""}</span><span class="ln">${esc(r.last || "")}</span></button>`).join("");
    const canNew = L.switches && L.switches.chat_sessions !== false;
    return `<nav class="ss" aria-label="chats">${rows}${canNew ? '<button class="new" data-new="1">+ new chat</button>' : ""}</nav>`;
  }
  function waitingHtml() {
    const items = (S.list && S.list.waiting) || [];
    if (!items.length) return "";
    const one = (it) => {
      const bits = [];
      for (const c of it.choices || []) bits.push(`<button data-ans="${esc(it.id)}" data-v="${esc(c)}">${esc(c)}</button>`);
      (it.buttons || []).forEach((b, i) => bits.push(b.url ? `<a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.label)}</a>` : `<button data-wbtn="${esc(it.id)}" data-n="${i}">${esc(b.label)}</button>`));
      if (it.reply) bits.push(`<button data-wreply="${esc(it.id)}">answer…</button>`);
      if (it.later) bits.push(`<button data-ans="${esc(it.id)}" data-v="later">later</button>`);
      if (!it.qid) bits.push(`<button data-dismiss="${esc(it.id)}" title="take it off the list, here and on your phones">dismiss</button>`);
      return `<div class="wi"><div class="tx">${it.title ? `<b>${esc(it.title)}</b>\n` : ""}${rich(it.text)}</div><div class="bt">${bits.join(" ")}</div></div>`;
    };
    return `<section class="wt" aria-label="waiting for you"><h4>Waiting for you</h4>${items.map(one).join("")}</section>`;
  }
  function msgHtml(m) {
    const you = m.from === "you", gone = !!m.deleted;
    let h = `<div class="m${you ? " you" : ""}${gone ? " gone" : ""}" data-id="${esc(m.id)}">`;
    if (m.quote && !gone) h += `<div class="q">${esc((m.quote.from === "you" ? "you: " : "") + (m.quote.text || ""))}</div>`;
    if (m.title && !gone) h += `<div class="tt">${esc(m.title)}</div>`;
    h += `<div class="tx">${gone ? "deleted" : rich(m.text || "")}</div>`;
    if (m.file && !gone) {
      const f = m.file, label = `${esc(f.name)} <span class="d">${size(f.size)}</span>`;
      h += `<div class="fl">file: ${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : `${label} <span class="d">(on this computer)</span>`}</div>`;
    }
    if ((m.buttons || []).length && !gone) {
      h += `<div class="bt">${m.buttons.map((b, i) => (b.url ? `<a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.label)}</a>` : `<button data-btn="${esc(m.id)}" data-n="${i}">${esc(b.label)}</button>`)).join("")}</div>`;
    }
    const marks = [hhmm(m.at || 0)];
    if (m.edited && !gone) marks.push("edited");
    if (m.pinned) marks.push("pinned");
    h += `<div class="meta"><span>${marks.join(" · ")}</span>${gone ? "" : `<button data-reply="${esc(m.id)}">reply</button>`}</div></div>`;
    return h;
  }
  function threadHtml() {
    let h = "", day = "";
    for (const m of S.msgs) {
      const d = dayOf(m.at || 0);
      if (d !== day) { day = d; h += `<div class="day">${esc(d)}</div>`; }
      h += msgHtml(m);
    }
    return h || `<p class="d">Nothing here yet. ${S.sid === "main" ? "Kurooto's own messages land here; write below to start." : "Write below to start this chat."}</p>`;
  }
  function render() {
    if (!S.body || !S.body.isConnected || !S.list) return;
    const old = S.body.querySelector(".cp .log"), atEnd = !old || old.scrollHeight - old.scrollTop - old.clientHeight < 40;
    const ta = S.body.querySelector(".cp textarea"), draft = ta ? ta.value : "", focused = ta && document.activeElement === ta;
    const s = session() || { id: "main", title: S.list.name };
    const own = s.id !== "main" && S.list.switches && S.list.switches.chat_sessions !== false;
    const tools = own ? `<button data-rename="1">rename</button><button data-pin="1">${s.pinned ? "unpin" : "pin"}</button><button data-del="1">delete</button>` : "";
    const re = S.reply ? S.msgs.find((m) => m.id === S.reply) : null;
    S.body.innerHTML = `<div class="cp">${sessionsHtml()}<div class="th"><div class="hd"><b>${esc(s.title || "New chat")}</b><span class="d">the same chat as the phone app</span>${tools}</div>${waitingHtml()}
      <div class="log" aria-live="polite">${threadHtml()}</div>
      <div class="in">${re ? `<div class="re"><span>replying to: ${esc((re.text || "").slice(0, 120))}</span><button data-noreply="1">cancel</button></div>` : ""}
      <form><textarea rows="2" aria-label="Write to ${esc(S.list.name)}" placeholder="Write to ${esc(S.list.name)}: Enter sends, Shift+Enter a new line"></textarea><button class="primary" type="submit">Send</button></form><div class="say"></div></div></div></div>`;
    const log = S.body.querySelector(".cp .log");
    if (atEnd || !old) log.scrollTop = log.scrollHeight;
    const nta = S.body.querySelector(".cp textarea");
    nta.value = draft; if (focused || re) nta.focus({ preventScroll: true });
    nta.addEventListener("keydown", keys);
    say(S.note);
  }

  // -------------------------------------------------------------------------------------------- acting
  function keys(e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); e.target.form.requestSubmit(); }
    else if (e.key === "Escape" && S.reply) { e.preventDefault(); S.reply = null; render(); }
  }
  async function submit(e) {
    e.preventDefault();
    const ta = S.body.querySelector(".cp textarea"); const text = ta.value.trim(); if (!text || S.busy) return;
    S.busy = true; say("Sending…");
    let r; try { r = await S.api("chat/send", { session: S.sid, text, reply: S.reply || "" }); } catch { r = { ok: false, note: "This page lost Kurooto. Is it running?" }; }
    S.busy = false;
    if (!r.ok) { say(r.note || "That didn't go.", true); return; }
    ta.value = ""; S.reply = null; S.note = "";
    for (const m of r.said || []) upsert(m);
    render();
  }
  function upsert(m) {
    if (!m || !m.id || (m.session || "main") !== S.sid) return false;
    const i = S.msgs.findIndex((x) => x.id === m.id);
    if (i >= 0) S.msgs[i] = m; else S.msgs.push(m);
    return true;
  }
  async function click(e) {
    const t = e.target.closest("button, a[data-page]"); if (!t || !S.body.contains(t)) return;
    const d = t.dataset;
    if (d.page) { e.preventDefault(); if (S.opts.open) S.opts.open(d.page); return; }
    if (d.s) { if (d.s !== S.sid) { S.note = ""; await openThread(d.s); } return; }
    if (d.reply) { S.reply = d.reply; render(); return; }
    if (d.noreply) { S.reply = null; render(); return; }
    if (d.btn) { t.disabled = true; const r = await S.api("chat/button", { msg: d.btn, n: Number(d.n) }); say(r.note || (r.ok ? "" : "That button is out of date."), !r.ok); return; }
    if (d.ans || d.wbtn || d.dismiss) {
      const item = d.ans || d.wbtn || d.dismiss;
      const body = d.ans ? { item, answer: d.v } : d.wbtn ? { item, button: Number(d.n) } : { item, dismiss: true };
      t.disabled = true; const r = await S.api("chat/answer", body); say(r.note || "", !r.ok); load(false); return;
    }
    if (d.wreply) {
      const text = prompt("Your answer:"); if (!text || !text.trim()) return;
      const r = await S.api("chat/answer", { item: d.wreply, answer: text.trim() }); say(r.note || "", !r.ok); load(false); return;
    }
    if (d.new) {
      const sid = newId(), r = await S.api("chat/op", { op: "session.new", session: sid });
      if (!r.ok) { say(r.note || "No new chat.", true); return; }
      S.list.sessions = r.sessions || S.list.sessions; await openThread(sid); S.body.querySelector(".cp textarea").focus(); return;
    }
    if (d.rename) { const s = session(), v = prompt("Name this chat:", (s && s.title) || ""); if (!v || !v.trim()) return; const r = await S.api("chat/op", { op: "session.rename", session: S.sid, title: v.trim() }); say(r.note || "", !r.ok); return; }
    if (d.pin) { const s = session(); const r = await S.api("chat/op", { op: "session.pin", session: S.sid, on: !(s && s.pinned) }); say(r.note || "", !r.ok); return; }
    if (d.del) {
      const s = session(); if (!confirm(`Delete the chat "${(s && s.title) || "New chat"}"? It goes from your phones too, with its messages and the AI's memory of it.`)) return;
      const r = await S.api("chat/op", { op: "session.delete", session: S.sid }); if (!r.ok) { say(r.note || "", true); return; }
      S.sid = "main"; await load(true);
    }
  }

  // ---------------------------------------------------------------------------------------------- live
  // {t: "chat", kind: "msg"} adds or changes a message (the open chat shows it now; the list follows), "sessions" and
  // "waiting" ask for the list again, "status" is a chat's "working"/"idle"
  function live(m) {
    if (!here()) return;
    if (m.kind === "msg" && m.msg) {
      if (upsert(m.msg)) { render(); markRead(); }
      soon();
    } else if (m.kind === "status" && S.list) {
      const w = new Set(S.list.working || []); if (m.state === "working") w.add(m.session); else w.delete(m.session);
      S.list.working = [...w]; render();
    } else soon();
  }
  function soon() {
    clearTimeout(S.timer);
    S.timer = setTimeout(async () => {
      if (!here()) return;
      const had = S.sid; await load(false);
      if (S.sid !== had) { await openThread(S.sid, false); render(); } // the open chat was deleted somewhere else
    }, 300);
  }

  window.CHATPAGE = { mount, live };
})();
