// The morning page: today's plan from the daily note, and the day around it. Opened by the alarm; read-only.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();

// Just enough Markdown for a plan: headings, lists, tasks, bold, links shown as their text.
function inline(s) {
  return esc(s)
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2").replace(/\[\[([^\]]+)\]\]/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
}
function markdown(text) {
  const out = []; let list = false;
  const close = () => { if (list) { out.push("</ul>"); list = false; } };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) { close(); out.push(`<h${m[1].length <= 2 ? 3 : 4}>${inline(m[2])}</h${m[1].length <= 2 ? 3 : 4}>`); }
    else if ((m = line.match(/^\s*(?:[-*]|\d+[.)])\s+(\[( |x|X)\]\s+)?(.*)$/))) {
      if (!list) { out.push("<ul>"); list = true; }
      const done = m[2] && m[2].toLowerCase() === "x";
      out.push(`<li${done ? ' class="done"' : ""}>${m[1] ? (done ? "☑ " : "☐ ") : ""}${inline(m[3])}</li>`);
    } else if (!line.trim()) close();
    else { close(); out.push(`<p>${inline(line)}</p>`); }
  }
  close();
  return out.join("");
}

function section(title, rows) {
  if (!rows || !rows.length) return "";
  return `<section class="box"><h2>${esc(title)}</h2><ul>${rows.join("")}</ul></section>`;
}

async function load() {
  let d;
  try { d = await api("morning"); } catch { $("#plan").innerHTML = '<p class="empty">Kurooto isn\'t answering right now.</p>'; return; }
  const hour = new Date().getHours();
  const hi = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  $("#hello").textContent = d.name ? `${hi}, ${d.name}` : hi;
  $("#date").textContent = d.day || "";
  $("#plan").innerHTML = d.plan ? markdown(d.plan) : '<p class="empty">No plan in today\'s note yet. With Chat on and the alarm set, one is drafted 20 minutes before it rings.</p>';
  if (d.note_exists) {
    const b = $("#open-note"); b.classList.remove("hidden");
    b.onclick = () => api("open-note", { id: d.note }).catch(() => {});
  }
  const side = [
    section("Classes", (d.classes || []).map((c) => `<li class="${c.skipping ? "off" : ""}"><span class="t">${esc(c.time)}</span>${esc(c.name)}${c.skipping ? " (skipping)" : ""}</li>`)),
    section("Calendar", (d.calendar || []).map((e) => `<li>${esc(e)}</li>`)),
    section("Due soon", (d.due || []).map((x) => `<li>${esc(x.title)} <span class="t">${esc(x.when)}</span></li>`)),
    section("Time to start", (d.start || []).map((x) => `<li>${esc(x.title)} <span class="t">${esc(x.when)}</span></li>`)),
    section("Check-ins", (d.checkins || []).map((c) => `<li class="${c.status === "skipped" ? "off" : ""}"><span class="t">${esc(c.time)}</span>${esc(c.name)} (${esc(c.status)})</li>`)),
    section("Open questions", (d.questions || []).map((q) => `<li>${esc(q)}</li>`)),
    section("So far", [d.alarm ? `<li>Next alarm: ${esc(d.alarm)}</li>` : "", d.study_h ? `<li>Studied today: ${esc(d.study_h)} h</li>` : ""].filter(Boolean)),
  ].join("");
  $("#side").innerHTML = side || '<section class="box"><p class="empty">Nothing else on today.</p></section>';
}
load();
setInterval(load, 5 * 60 * 1000);
