// Confidential mail summarised on this computer (the mail digest's local mode): read-only, plus Add / Not needed for
// the dates the local model found. Nothing on this page leaves the computer.
"use strict";
const TOKEN = document.querySelector('meta[name="kurooto-token"]').content;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const api = async (path, body) => (await fetch(`/api/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Kurooto": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();

async function show(day) {
  const v = await api(`mail/confidential${day ? `?day=${encodeURIComponent(day)}` : ""}`);
  $("#days").innerHTML = v.days.map((d) => `<button data-day="${esc(d)}" class="${d === v.day ? "on" : ""}">${esc(d)}</button>`).join("");
  const text = $("#text");
  text.textContent = v.text || "Nothing summarised yet.";
  text.className = v.text ? "" : "empty";
  $("#offers").innerHTML = v.offers.length
    ? v.offers.map((o) => `<div class="offer"><span>${esc(o.title)} · ${esc(new Date(o.due).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}</span>
        <button class="primary" data-add="${esc(o.id)}">Add to Deadlines</button><button data-no="${esc(o.id)}">Not needed</button></div>`).join("")
    : `<p class="empty">None waiting.</p>`;
}
document.addEventListener("click", async (e) => {
  const t = e.target;
  if (t.dataset.day) show(t.dataset.day);
  if (t.dataset.add || t.dataset.no) {
    const r = await api("mail/confidential/settle", { id: t.dataset.add || t.dataset.no, add: Boolean(t.dataset.add) });
    $("#said").textContent = r.message || "";
    show(document.querySelector(".days button.on")?.dataset.day);
  }
});
show();
