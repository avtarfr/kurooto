// The proposals page: every change the AI proposed (core/proposals.py), with the whole diff, Apply / Change / Discard,
// and Undo for ones you applied. Nothing on this page leaves the computer.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();
const when = (t) => new Date(t * 1000).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const count = (c) => c.status === "deleted" ? "deleted" : c.binary ? "binary" : `${c.status === "added" ? "new, " : ""}+${c.added} −${c.removed}`;

function diffHtml(text) {
  return text.split("\n").map((ln) => {
    const k = ln.startsWith("diff ") ? "file" : ln.startsWith("@@") ? "hunk" : ln.startsWith("+++") || ln.startsWith("---") ? "file"
      : ln.startsWith("+") ? "add" : ln.startsWith("-") ? "del" : "";
    return `<span class="${k}">${esc(ln) || " "}</span>`;
  }).join("");
}

function card(p, diff) {
  const open = p.status === "waiting";
  const ck = p.checks;
  const checks = ck ? (ck.ran ? (ck.ok ? `Checks passed in ${ck.seconds} s.` : `Checks failed (${esc(ck.why || "exit " + ck.code)}).`) : `Checks didn't run: ${esc(ck.why)}.`) : "";
  return `<div class="box" data-id="${esc(p.id)}">
    <h2>${esc(p.title)}</h2>
    <div class="meta">${esc(p.label)} · ${p.kind === "git" ? "git: one commit on your branch" : "files"} · ${when(p.created)}${p.rev ? ` · version ${p.rev + 1}` : ""}${open ? "" : ` · ${esc(p.status)}`}</div>
    ${p.deletes && p.deletes.length ? `<div class="dels">It deletes ${p.deletes.length} file${p.deletes.length > 1 ? "s" : ""}: ${p.deletes.map(esc).join(", ")}</div>` : ""}
    ${p.summary ? `<div class="sum">${esc(p.summary)}</div>` : ""}
    <ul class="files">${(p.files || []).map((c) => `<li>${esc(c.path)} (${count(c)})</li>`).join("")}</ul>
    ${checks ? `<div class="meta">${checks}</div>` : ""}
    ${p.blocked && p.blocked.length ? `<div class="warn">Refused while it worked (outside its scratch folder): ${p.blocked.map(esc).join(", ")}</div>` : ""}
    ${p.outside && p.outside.length ? `<div class="warn">Changed in the original while it worked (not part of this proposal): ${p.outside.map(esc).join(", ")}</div>` : ""}
    ${open ? `<div class="acts"><button class="primary" data-act="apply">Apply</button><button data-act="discard">Discard</button>
      <textarea placeholder="What should change? Then Change." data-text></textarea><button data-act="change">Change</button></div>` : ""}
    ${p.status === "applied" ? `<div class="acts"><button data-act="undo">Undo</button></div>` : ""}
    ${diff !== undefined ? `<pre class="diff">${diffHtml(diff)}</pre>` : `<button data-diff>Show the diff</button>`}
  </div>`;
}

function projects(list) {
  if (!list) return;  // Help with your project is off
  $("#ask").hidden = false;
  const on = list.filter((p) => p.help);
  $("#ask-project").innerHTML = on.map((p) => `<option>${esc(p.name)}</option>`).join("");
  $("#ask-off").textContent = on.length ? "" : "No project lets the AI help yet: /project help on <name> in the chat.";
}

async function show() {
  const v = await api("proposals");
  projects(v.projects);
  const waiting = v.proposals.filter((p) => p.status === "waiting" || p.status === "changing");
  const rest = v.proposals.filter((p) => !(p.status === "waiting" || p.status === "changing"));
  const full = await Promise.all(waiting.map((p) => api(`proposals/${p.id}`)));
  $("#list").innerHTML = waiting.length ? full.map((x) => card(x.proposal, x.proposal.diff)).join("") : `<p class="empty">Nothing waits for your OK.</p>`;
  $("#done").innerHTML = rest.length ? rest.map((p) => card(p)).join("") : `<p class="empty">None.</p>`;
}

document.addEventListener("click", async (e) => {
  const t = e.target;
  if (t.id === "ask-go") {
    const r = await api("projects/help", { name: $("#ask-project").value, what: $("#ask-what").value });
    $("#said").textContent = r.message || r.error || "";
    if (r.ok) $("#ask-what").value = "";
    return;
  }
  const box = t.closest("[data-id]");
  if (!box) return;
  const id = box.dataset.id;
  if (t.dataset.diff !== undefined) {
    const x = await api(`proposals/${id}`);
    t.outerHTML = `<pre class="diff">${diffHtml(x.proposal.diff || "")}</pre>`;
    return;
  }
  const act = t.dataset.act;
  if (!act) return;
  const text = box.querySelector("[data-text]")?.value || "";
  if (act === "change" && !text.trim()) { $("#said").textContent = "Say what should change first."; return; }
  t.disabled = true;
  const r = await api("proposals/act", { id, act, text });
  $("#said").textContent = r.message || r.error || "";
  show();
});
show();
