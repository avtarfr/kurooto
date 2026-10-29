// Kurooto Worker: your own call line on Cloudflare's free plan, deployed for you by Kurooto (Phone calls setup).
//   - Serves the call page, the phone pairing page and the installable web app (public/).
//   - Your computer keeps one outbound WebSocket to the Durable Object "Line" (no open ports; works behind any
//     router or campus network). While it's connected, tool calls, finished tasks, transcripts and shared files
//     are passed to it.
//   - Calls: Gemini Live tokens are minted here with your Gemini key, so the audio goes between your phone and
//     Google directly. What the call knows and can do (its instructions and tools) is pushed by your computer.
//   - Ringing: your computer (or the cron below, when it's off) rings your paired devices: the Android app through
//     its own WebSocket to this line (0.7.0) and through ntfy (encrypted with NTFY_KEY, which your devices, your
//     computer and this Worker hold: ntfy can't read it), the web app through Web Push (no payload; it asks this
//     Worker what's ringing). Not while you're on a call: those calls ring when it ends.
//   - The Android app's own connection (0.7.0): each paired Android phone keeps one WebSocket to /phone, accepted with
//     the hibernation API, so an idle one costs nothing (its "ping" is answered by the runtime without waking this
//     object). Everything this line sends the Android app (rings, messages, chat, Today nudges...) goes down it first,
//     sealed exactly as on ntfy, with a message id ("mid") the phone uses to drop a second copy; the last ones are
//     kept a few hours so a phone that reconnects gets what it missed. ntfy is only the fallback: for a phone not
//     heard from lately (or one with an app from before 0.7.0), and a second path for rings.
//   - Messages: questions and approvals (and other kinds, if you choose) reach your phones the same way; this keeps
//     what's still open (the inbox) for the web app to list. Answers come back through /answer to your computer
//     (the Android app's are sealed with the ntfy key, which keeps them from ntfy but not from this Worker: it holds
//     NTFY_KEY), or wait here till it's back.
//   - Chat (0.5.16): what you type in the phone app goes through /chat to your computer like a Telegram message;
//     its answers come back the way messages do (chat-say), and this keeps the chat's last 50 messages (3 days at
//     most) so a phone can catch up with the computer off. 0.8.10: separate chats ("sessions"): every message
//     carries its `session` (none: "main", Kurooto's own); the last 50 of each are kept here (under "chat" for main,
//     "chat:<id>" for the others) with the list of chats your computer pushed ("chat-sessions"), so a phone can
//     catch up with the computer off (GET /chat?sessions=1; without it, only main, as older app versions expect).
//     A change to a message (edited, deleted, pinned) keeps its place and gets a new seq. "chat-status" (working /
//     idle) only goes to the phones connected straight to this line: not kept, no notification. A sealed message
//     marked `live` (the being's requests) never waits in the outbox: with the computer off it's refused at once.
//   - Tell Kurooto (0.6.0): a paired phone can make one Shortcut link for itself ("tk1.<id>.<secret>", only its hash
//     kept here). The iPhone Shortcut posts what you said to /tell/<token>; it goes on as a chat message from that
//     phone, and nothing else: the link opens no other door here. Your computer lists them and can revoke one;
//     unpairing the phone ends its link too.
//   - Files for the chat (0.5.18): where Telegram would get a document, your computer can leave a sealed copy here
//     for a day ("file-put"; AES-256-GCM with a key made on your computer that's only in the link's #fragment, so
//     what's kept here can't be opened without the link); /file is the page that fetches it (/sealed/<id>) and opens
//     it in the phone's browser. At most FILE_MAX each and FILES_BYTES in all.
//   - While your computer is off: answers come from the brief it last pushed, notes from the index it pushed (and,
//     with Notes sync, whole notes from your private GitHub repo); anything that needs the computer is queued.
//     What you do on a paired phone meanwhile (answers, chat messages and button taps, shared files) waits here
//     too (the phone outbox: at most 100 things and 20 MB), in order; your computer takes it one item at a time
//     when it's back ("outbox"), and the phone hears when each went through.
//   - Going offline: when your computer's link has been gone for a while (it's asleep, crashed or lost its network)
//     the cron says so for it, once, outside the night hours it pushed: on the phone app, and on Telegram if you
//     allowed this line to keep your bot's token (pushed over the link, kept in this object's storage, deleted when
//     you turn it off). A clean stop says "bye" first, so nothing is said twice.
//   - Reminders with the lid shut (only with that feature on): your computer hands over the next day's reminders and
//     the morning's first class and what's due, each as a time plus copies sealed for your Android phones with keys
//     only those phones hold ("s1"; this Worker can't open them). Whichever side is awake at an item's time says it:
//     your computer claims it then, or the cron sends it to the phones. One answer per item, so nothing comes twice.
//   - The app's Today screen (0.6.0): your computer hands over the day's list (classes, what's due, the alarm...)
//     sealed for each Android phone with that phone's own key ("s1", as above: this Worker can't open it), one copy
//     per phone ("today-put"); a phone fetches its own from /today, with when it came, so it shows with the computer
//     off. A changed list nudges the phones ("today" on ntfy).
//   - Systems and the Notes map on the Android app (0.7.0, only with calls.views on): your computer seals each
//     snapshot once with a fresh key and that key for each Android phone with the phone's own key ("v1": this Worker
//     can open neither), and hands it over in parts ("view-put"); this keeps only the newest of each, and a phone
//     fetches its own from /view. Systems is sent only while a phone watches it: the app says so every ~20 s
//     (/view/watch), which this passes to your computer. Turned off, your computer says "off" and the copies go.
//     The Brain (0.8.10, kind "brain") goes the same way, also only while watched (/view/watch?kind=brain).
//   - When Gemini Live won't take a call (web/fallback.js): the call page asks for a token for the next Live model
//     (the list your computer pushed), then goes turn by turn (/turn: each turn to your computer's AI, or to a Gemini
//     text model with your key here while the computer is off, with the same instructions and tools), then to
//     Telegram (/text-call, through your computer). Live failures and fallbacks are reported to your computer
//     (/call-report) for `kurooto doctor`.
// Vars: OWNER_ID, TZ, PUBLIC_URL, VERSION, LIVE_MODEL, NTFY_SERVER, NOTES_REPO (optional), GEMINI_BASE_URL and
// TELEGRAM_API (tests).
// Secrets: CALL_SECRET, CONNECTOR_SECRET, GEMINI_API_KEY, NTFY_TOPIC, NTFY_KEY, VAPID_JWK, VAPID_PUBLIC, NTFY_TOKEN
// (empty unless you gave one: an ntfy account's token) and GITHUB_TOKEN (optional: read-only access to the notes repo).
import { GoogleGenAI } from '@google/genai';
import { cleanHistory, cleanLines, googleError, spoken } from '../web/fallback.js';

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-headers': 'content-type, x-call-secret',
  'access-control-allow-methods': 'GET, POST',
};
const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...CORS },
});
const passOn = async (r) => new Response(await r.text(), { status: r.status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...CORS } });

function same(a, b) {
  const x = new TextEncoder().encode(String(a || '')), y = new TextEncoder().encode(String(b || ''));
  if (!x.length || x.length !== y.length) return false;
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x[i] ^ y[i];
  return d === 0;
}
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
const randomHex = (n) => hex(crypto.getRandomValues(new Uint8Array(n)));
const sha256 = async (s) => hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)));
function b64url(bytes) {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
const unb64 = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4)), (c) => c.charCodeAt(0));

// "k1." tokens: AES-256-GCM, nonce || ciphertext+tag, base64url. Same format on the computer and in the Android app.
export async function sealK1(keyB64, text) {
  const key = await crypto.subtle.importKey('raw', unb64(keyB64), 'AES-GCM', false, ['encrypt']);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, new TextEncoder().encode(text)));
  const all = new Uint8Array(12 + ct.length);
  all.set(nonce);
  all.set(ct, 12);
  return 'k1.' + b64url(all);
}
export async function openK1(keyB64, token) {
  if (!keyB64 || !String(token).startsWith('k1.')) return null;
  try {
    const raw = unb64(token.slice(3));
    const key = await crypto.subtle.importKey('raw', unb64(keyB64), 'AES-GCM', false, ['decrypt']);
    return new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, key, raw.slice(12)));
  } catch { return null; }
}

// A call link made on your computer (Telegram /call): "t1.<expires ms>.<HMAC-SHA256(CALL_SECRET, 't1.<expires ms>')>".
export async function signedTicketOk(secret, t) {
  const m = /^t1\.(\d{13})\.([0-9a-f]{64})$/.exec(String(t || ''));
  if (!m || Number(m[1]) < Date.now() || !secret) return false;
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return same(hex(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(`t1.${m[1]}`))), m[2]);
}

// Web Push without a payload (RFC 8292 VAPID): the service worker then asks /pending what's ringing.
async function webPush(env, sub) {
  const ep = new URL(sub.endpoint);
  const key = await crypto.subtle.importKey('jwk', JSON.parse(env.VAPID_JWK), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const enc = (o) => b64url(new TextEncoder().encode(JSON.stringify(o)));
  const unsigned = `${enc({ typ: 'JWT', alg: 'ES256' })}.${enc({ aud: ep.origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: env.PUBLIC_URL })}`;
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, new TextEncoder().encode(unsigned)));
  const r = await fetch(sub.endpoint, {
    method: 'POST',
    headers: { authorization: `vapid t=${unsigned}.${b64url(sig)}, k=${env.VAPID_PUBLIC}`, ttl: '120', urgency: 'high', 'content-length': '0' },
  });
  return r.status;
}

// A message already sealed for the Android app (k1), to ntfy: the fallback since 0.7.0 (Line.toPhones). ntfy limits
// each internet address, and a free ntfy account is counted by address too; NTFY_TOKEN only helps with a paid
// account. A token ntfy refuses falls back to publishing without one.
async function publish(env, message, priority = 3) {
  if (!env.NTFY_TOPIC || !message) return false;
  const body = JSON.stringify({ topic: env.NTFY_TOPIC, message, priority, tags: ['k1'] });
  for (const token of env.NTFY_TOKEN ? [env.NTFY_TOKEN, ''] : ['']) {
    const headers = { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) };
    const r = await fetch((env.NTFY_SERVER || 'https://ntfy.sh').replace(/\/+$/, '') + '/', { method: 'POST', headers, body });
    if (!(token && (r.status === 401 || r.status === 403))) return r.ok;
  }
  return false;
}

// Web Push to every device that has it on; drops subscriptions the push service says are gone.
async function pushAll(env, devices) {
  let web = 0, changed = false;
  const errors = [];
  for (const d of Object.values(devices)) {
    if (!d.push) continue;
    const status = await webPush(env, d.push).catch((e) => { errors.push(String(e?.message || e).slice(0, 120)); return 0; });
    if (status === 404 || status === 410) { d.push = null; changed = true; } else if (status >= 200 && status < 300) web++;
    else if (status) errors.push(`push answered ${status}`);
  }
  return { web, changed, errors };
}

// An inbox item as the Android app gets it (ntfy messages must stay under 4 KB once sealed).
function phoneMessage(it) {
  const m = {
    title: String(it.title || 'Kurooto').slice(0, 120), message: String(it.text || ''), priority: ['question', 'approval'].includes(it.kind) ? 4 : 3,
    tags: ['msg', `kind-${String(it.kind || 'info').replace(/[^a-z]/g, '')}`], time: Math.floor(Date.now() / 1000),
    id: it.id, kind: it.kind, reply: !!it.reply, later: !!it.later,
    choices: (it.choices || []).slice(0, 8).map((c) => String(c).slice(0, 60)),
    buttons: (it.buttons || []).slice(0, 4).map((b) => (b.url ? { label: String(b.label).slice(0, 40), url: String(b.url) } : { label: String(b.label).slice(0, 40) })),
  };
  const size = () => new TextEncoder().encode(JSON.stringify(m)).length;
  while (size() > 2800 && m.message.length > 80) m.message = m.message.slice(0, Math.floor(m.message.length * 0.8)) + '…';
  return m;
}

// A chat message from Kurooto as the Android app gets it (it fetches the whole chat from /chat when it's opened).
// A change to one (0.8.10: edited, deleted, pinned) is tagged "chat-update" instead, which older apps ignore.
function chatMessage(m, update = false) {
  const out = {
    title: String(m.title || 'Kurooto').slice(0, 120), message: m.text, priority: 3, tags: ['stop', update ? 'chat-update' : 'chat'],
    time: Math.floor(Date.now() / 1000), id: m.id, seq: m.seq, re: m.re || '', reply: !!m.reply, buttons: m.buttons,
    session: m.session || 'main', from: m.from,
  };
  for (const k of ['file', 'quote', 'edited', 'deleted', 'pinned']) if (m[k] !== undefined) out[k] = m[k];
  const size = () => new TextEncoder().encode(JSON.stringify(out)).length;
  while (size() > 2800 && out.message.length > 80) out.message = out.message.slice(0, Math.floor(out.message.length * 0.8)) + '…';
  return out;
}

// Telegram, for "your computer is offline" (only with the token your computer pushed after you allowed it).
async function sendTelegram(env, tg, text) {
  if (!tg || !tg.token || !tg.chat) return false;
  const base = (env.TELEGRAM_API || 'https://api.telegram.org').replace(/\/+$/, '');
  const r = await fetch(`${base}/bot${tg.token}/sendMessage`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: tg.chat, text: String(text).slice(0, 4000), link_preview_options: { is_disabled: true } }),
  });
  return r.ok;
}

// 22:10 today, "Mon 22:10" another day, in your time zone.
function clockTime(ms, tz) {
  const d = new Date(ms);
  const day = (x) => x.toLocaleDateString('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' });
  const t = d.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false });
  return day(d) === day(new Date()) ? t : `${d.toLocaleDateString('en-GB', { timeZone: tz, weekday: 'short' })} ${t}`;
}

async function githubNote(env, slug) {
  if (!env.GITHUB_TOKEN || !env.NOTES_REPO) return null;
  const p = String(slug).replace(/^\/+|\.md$/g, '') + '.md';
  if (p.split('/').some((s) => s === '..' || s === '')) return null;
  const r = await fetch(`https://api.github.com/repos/${env.NOTES_REPO}/contents/${p.split('/').map(encodeURIComponent).join('/')}`, {
    headers: { authorization: `Bearer ${env.GITHUB_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'kurooto-worker' },
  });
  return r.ok ? await r.text() : null;
}

const MAX_DEVICES = 10;
// a Tell Kurooto link (one per paired phone): "tk1.<8 hex id>.<32 hex secret>", in the Shortcut's URL
const TELL_TOKEN = /^tk1\.([0-9a-f]{8})\.([0-9a-f]{32})$/;
const TELL_TEXT = 4000;
const RING_S = 60, ALARM_RING_S = 300;
// the Android app's own connection (0.7.0): a phone heard from (its "ping", about every minute while it's awake and
// every few minutes asleep) this recently counts as connected, and gets no ntfy copy of anything but a ring; what
// was sent to the phones is kept this many messages and this long, for a phone that reconnects (one that never
// connected, or whose place in it is gone, gets the last PHONE_NEW_MS of it)
const PHONE_FRESH_MS = 6 * 60e3, PHONE_LOG_MAX = 60, PHONE_LOG_MS = 6 * 3600e3, PHONE_NEW_MS = 10 * 60e3;
const SEND_MAX = 8000; // what your computer hands over at /send (a message for the phones), at most
const ON_CALL_MS = 90e3; // a live call checks in every few seconds (/tasks); this long after the last one it's over
const ITEM_ID = /^[0-9a-f]{16}$/;
// the phone outbox: what a paired phone sent while your computer was off (kept in the queue, in order, each body
// under its own key); at most this many things and bytes of shared files, a file going in parts of PART bytes
const PHONE_KINDS = ['answer', 'chat', 'upload'];
const OUTBOX_MAX = 100, OUTBOX_BYTES = 20 * 1024 * 1024, PART = 512 * 1024, QUEUE_MAX = 200;
const OUTBOX_FULL = 'Your call line is holding as much as it can for your computer. Wait till it is back on, or use Telegram.';
// the chat: messages kept, for how long, longest text kept
const CHAT_MAX = 50, CHAT_KEEP_S = 3 * 86400, CHAT_TEXT = 6000, DONE_KEEP_MS = 86400e3;
// the chats (0.8.10): an id, the most kept, how long a "working" status counts without an "idle"
const SESSION_ID = /^[0-9a-f]{16}$/, SESSIONS_MAX = 100, STATUS_MS = 3 * 3600e3;
const OFF_NOW = "Your computer is off, try again when it's on.";
// what a plain (iPhone app) chat message may carry, besides its id
const CHAT_FIELDS = ['text', 'to', 'button', 'msg', 'ts', 'n', 'session', 'reply', 'file', 'voice', 'op', 'args', 'title', 'target', 'on', 'upto', 'key', 'value'];
// files for the chat (sealed on your computer): the id, a part's most, a file's most, all of them at once
const FILE_ID = /^[0-9a-f]{32}$/;
const FILE_PART = 400 * 1024, FILE_MAX = 10 * 1024 * 1024 + 64, FILES_BYTES = 30 * 1024 * 1024;
// sealed reminders: at most this many held; a failed send is tried again each minute this many times; a send in
// progress counts as sent this long; answers are kept this long
const SEALED_MAX = 40, SEALED_TRIES = 5, SEALED_BUSY_MS = 120e3, SEALED_KEEP_MS = 3 * 86400e3;
const SEAL_TOKEN = /^s1\.B[A-Za-z0-9_-]{86}\.[A-Za-z0-9_-]{40,2210}$/; // at most 2300 in all: fits ntfy sealed again
const SEAL_KEY = /^B[A-Za-z0-9_-]{86}$/; // a phone's P-256 public key, 65 bytes uncompressed, base64url
const TODAY_TOKEN = /^s1\.B[A-Za-z0-9_-]{86}\.[A-Za-z0-9_-]{40,110000}$/; // the Today list sealed for one phone
// the phone's views (0.7.0): which, a part's most (bytes), the most parts, a view's key sealed for one phone; a
// phone's "watching Systems" reaches your computer at most this often
const VIEW_KINDS = ['notes', 'systems', 'brain']; // brain (0.8.10): the Brain console's copy, sent while watched
const VIEW_PART = 96 * 1024, VIEW_PARTS = 24;
const VIEW_KEY = /^s1\.B[A-Za-z0-9_-]{86}\.[A-Za-z0-9_-]{40,600}$/;
const WATCH_MS = 5e3;
// calls when Gemini Live won't (web/fallback.js): Live model ids; rounds of tool calls in one text turn; what a text
// turn is told when your computer didn't push its own wording
const MODEL_ID = /^[A-Za-z0-9][\w.-]{0,79}$/;
const VOICE_MODES = ['live', 'phone', 'auto']; // calls.voice_mode: Gemini Live, the phone's own speech, or Live first
const TURN_TOOL_ROUNDS = 4;
const TURNS_TEXT = 'This call goes turn by turn: their phone turns what they say into text and reads your answers aloud. Keep each answer to one to three short spoken sentences: no lists, markdown, emojis or stage directions.';

export class Line {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.store = state.storage;
    this.pending = new Map();
    this.chatStatus = {}; // the chats an AI request is working for (chat-status): kept in memory only
    // The computer's heartbeat: "ping" is answered "pong" by the runtime without waking this object.
    this.state.setWebSocketAutoResponse(new WebSocketRequestResponsePair('ping', 'pong'));
  }

  // Online = a socket heard from (heartbeat or any message) in the last 90 s. A socket can look open here long
  // after the computer's network went away; that one doesn't count.
  online() {
    const now = Date.now();
    return this.computers().some((ws) => {
      const beat = this.state.getWebSocketAutoResponseTimestamp(ws)?.getTime() || 0;
      const seen = ws.deserializeAttachment()?.at || 0;
      return now - Math.max(beat, seen) < 90e3;
    });
  }

  // When the computer was last heard from, by the sockets still here (0 if none).
  lastSeen() {
    let seen = 0;
    for (const ws of this.computers()) {
      const beat = this.state.getWebSocketAutoResponseTimestamp(ws)?.getTime() || 0;
      seen = Math.max(seen, beat, ws.deserializeAttachment()?.at || 0);
    }
    return seen;
  }

  tell(msg) {
    if (!this.online()) return false;
    try { this.computers()[0].send(JSON.stringify(msg)); return true; } catch { return false; }
  }

  // The sockets here are your computer's (its connector: attachment {at}) and, since 0.7.0, the Android phones'
  // (tagged "phone" and "dev:<id>", attachment {kind: 'phone', dev, at}). A socket from before 0.7.0 is the computer's.
  computers() {
    return this.state.getWebSockets().filter((ws) => ws.deserializeAttachment()?.kind !== 'phone');
  }

  // When each Android phone was last heard from on its own connection: {device id: ms}.
  phonesHeard() {
    const out = {};
    for (const ws of this.state.getWebSockets('phone')) {
      const a = ws.deserializeAttachment() || {};
      if (!a.dev) continue;
      const beat = this.state.getWebSocketAutoResponseTimestamp(ws)?.getTime() || 0;
      out[a.dev] = Math.max(out[a.dev] || 0, beat, a.at || 0);
    }
    return out;
  }

  // What waits for the computer, oldest first. Each item has a sequence number; a body given separately (a phone's)
  // is kept under its own key. Past QUEUE_MAX the oldest of the line's own items go, never a phone's.
  async queueList() {
    const q = (await this.store.get('queue')) || [];
    if (q.some((x) => !x.seq)) { // kept by a line from before 0.5.16
      let seq = (await this.store.get('qseq')) || 0;
      for (const x of q) if (!x.seq) x.seq = ++seq;
      await this.store.put('qseq', seq);
      await this.store.put('queue', q);
    }
    return q;
  }

  async queue(item, body) {
    const q = await this.queueList();
    const seq = ((await this.store.get('qseq')) || 0) + 1;
    await this.store.put('qseq', seq);
    const e = { ...item, seq, at: new Date().toISOString() };
    if (body !== undefined) { e.bkey = `q:${seq}`; await this.store.put(e.bkey, body); }
    q.push(e);
    while (q.length > QUEUE_MAX) {
      const i = q.findIndex((x) => !PHONE_KINDS.includes(x.kind));
      if (i < 0) break;
      const [gone] = q.splice(i, 1);
      if (gone.bkey) await this.store.delete(gone.bkey);
    }
    await this.store.put('queue', q);
    this.tell({ type: 'outbox' }); // the computer looked away a moment (or is taking the rest): it takes this too
    return q.length;
  }

  // Something the computer should hear about: now if it's connected, else when it's back.
  async event(msg) {
    if (!this.tell({ type: 'event', ...msg })) await this.queue({ kind: 'event', ...msg });
  }

  // `kurooto rotate` (a lost phone, a backup that got out) deployed this line with a new CALL_SECRET: the phones
  // paired before, the call links made here and open pairing codes stop working. The first run only notes it.
  async fresh() {
    const gen = (await sha256(`gen:${this.env.CALL_SECRET || ''}`)).slice(0, 16);
    if (this.gen === gen) return;
    const was = await this.store.get('gen');
    if (was && was !== gen) {
      await this.store.delete(['devices', 'tickets', 'paircodes', 'pairfail', 'tells']);
      await this.viewsDrop(); // sealed for phones that aren't paired any more
    }
    if (was !== gen) await this.store.put('gen', gen);
    this.gen = gen;
  }

  async fetch(req) {
    await this.fresh();
    const url = new URL(req.url);
    const p = url.pathname;
    if (p === '/connect') return this.connect(req);
    if (p === '/send' && req.method === 'POST') return this.send(req); // your computer, without its WebSocket
    if (p === '/tick') return json(await this.tick());
    if (p === '/pair/claim' && req.method === 'POST') return this.claim(req);
    if (p.startsWith('/sealed/') && req.method === 'GET') return this.fileGet(p.slice(8)); // the key is in the link
    if (p.startsWith('/tell/tk1.')) return this.tellSend(req, p.slice(6)); // a Shortcut: its token is its only key
    const who = await this.auth(req.headers.get('x-call-secret'));
    // a refused request's body is read first: answering before it has all arrived trips up the local dev server
    const refuse = async (error, status) => { try { await req.arrayBuffer(); } catch { /* none */ } return json({ error }, status); };
    if (!who) return refuse('wrong or missing key', 401);
    try {
      if (p === '/status') {
        const brief = await this.store.get('brief');
        return json({ computer: this.online() ? 'online' : 'offline', brief_at: brief?.at || null, ...((await this.store.get('names')) || {}), device: who.kind === 'device' ? who.id : null, voice: await this.voice('outgoing') });
      }
      if (p === '/token' && req.method === 'POST') return this.token(req, who);
      if (p === '/turn' && req.method === 'POST') return this.turn(req, who);
      if (p === '/text-call' && req.method === 'POST') return this.textCall(req, who);
      if (p === '/call-report' && req.method === 'POST') return this.report(req);
      if (p === '/tool' && req.method === 'POST') return this.tool(req);
      if (p === '/tasks') return this.tasks(req);
      if (p === '/transcript' && req.method === 'POST') return this.transcript(req);
      if (p === '/upload' && req.method === 'POST') return this.upload(req, url, who);
      if (who.kind !== 'device') return refuse('that needs a paired device', 403);
      if (p === '/phone') return this.phoneConnect(req, who, url);
      if (p === '/pending') return json({ rings: await this.ringing(who.id), items: await this.openItems(), chat: (await this.chatLog()).msgs.filter((m) => m.from === 'kurooto').slice(-5), assistant: ((await this.store.get('names')) || {}).assistant || '' });
      if (p === '/answer' && req.method === 'POST') return this.answer(req, who);
      if (p === '/chat' && req.method === 'POST') return this.chat(req, who);
      if (p === '/chat') {
        const after = Number(url.searchParams.get('after')) || 0, log = await this.chatLog();
        const assistant = ((await this.store.get('names')) || {}).assistant || '';
        if (url.searchParams.get('sessions') !== '1') return json({ seq: log.seq, msgs: log.msgs.filter((m) => m.seq > after), ...(await this.outboxFor(who.id)), assistant });
        return json({ ...(await this.chatAll(after)), ...(await this.outboxFor(who.id)), assistant }); // 0.8.10: every chat
      }
      if (p === '/outbox') return json(await this.outboxFor(who.id));
      if (p === '/today') { // this phone's sealed copy of the Today list (null until your computer sent one for it)
        const t = (await this.store.get('today')) || null;
        const mine = !!t && (t.devs || []).includes(who.id);
        return json({ today: mine ? (await this.store.get(`today:${who.id}`)) || null : null, at: mine ? t.at : null, off: !!t?.off, computer: this.online() ? 'online' : 'offline' });
      }
      if (p === '/view') { // this phone's copy of Systems or the Notes map: its sealed key and the sealed snapshot
        const kind = url.searchParams.get('kind') || '';
        if (!VIEW_KINDS.includes(kind)) return json({ error: 'which view?' }, 400);
        const views = (await this.store.get('views')) || {};
        const v = views[kind], key = v && v.keys ? v.keys[who.id] : null;
        return json({ view: key ? { rev: v.rev, at: v.at, key, data: await this.viewData(kind, v) } : null, off: !!views.off, computer: this.online() ? 'online' : 'offline' });
      }
      if (p === '/view/watch' && req.method === 'POST') { // the app has Systems (or ?kind=brain, the Brain) open: your computer sends it live
        try { await req.arrayBuffer(); } catch { /* no body */ }
        const watchKind = url.searchParams.get('kind') === 'brain' ? 'brain' : 'systems';
        const views = (await this.store.get('views')) || {};
        if (((await this.store.get('devices')) || {})[who.id]?.kind !== 'android') return json({ error: 'only the Android app shows these' }, 403);
        if (views.off) return json({ ok: false, off: true, computer: this.online() ? 'online' : 'offline' });
        this.watched = this.watched || {};
        let told = false;
        const watchKey = watchKind === 'systems' ? who.id : `${who.id}:${watchKind}`;
        if (Date.now() - (this.watched[watchKey] || 0) >= WATCH_MS) {
          told = this.tell({ type: 'event', name: 'views_watch', device: who.id, kind: watchKind }); // never queued: live or nothing
          if (told) this.watched[watchKey] = Date.now();
        }
        return json({ ok: true, told, computer: this.online() ? 'online' : 'offline' });
      }
      if (p === '/upcoming') { // bedside mode (Android, 0.6.0): the calls due in the next day, from the schedule pushed
        const now = Math.floor(Date.now() / 1000), names = (await this.store.get('names')) || {};
        const calls = ((await this.store.get('schedule')) || []).filter((c) => c.at >= now - 60).slice(0, 8)
          .map((c) => ({ at: c.at, reason: String(c.reason || '').slice(0, 200), alarm: !!c.alarm }));
        return json({ calls, waiting: (await this.openItems()).length, computer: this.online() ? 'online' : 'offline', assistant: names.assistant || '' });
      }
      if (p === '/shortcut/new' && req.method === 'POST') return this.tellNew(req, who);
      if (p === '/shortcut/off' && req.method === 'POST') return json({ ok: await this.tellDrop((t) => t.device === who.id) });
      if (p === '/shortcut') {
        const mine = Object.entries((await this.store.get('tells')) || {}).find(([, t]) => t.device === who.id);
        return json({ shortcut: mine ? { id: mine[0], created: mine[1].created, used: mine[1].used || null } : null });
      }
      if (p === '/app-call' && req.method === 'POST') return json({ link: `${this.env.PUBLIC_URL}/?v=${await this.voice('outgoing')}#${await this.mintTicket(2)}`, computer: this.online() ? 'online' : 'offline' });
      if (p === '/ring-reply' && req.method === 'POST') {
        const { since = '', action = '' } = await req.json();
        if (!['later', 'skip', 'decline', 'answer'].includes(action)) return json({ error: 'unknown action' }, 400);
        await this.endRing(String(since));
        await this.event({ name: 'ring_reply', since: String(since), action, device: who.id });
        return json({ ok: true });
      }
      if (p === '/push/subscribe' && req.method === 'POST') {
        const { subscription } = await req.json();
        const local = /^http:\/\/(127\.0\.0\.1|localhost)[:/]/.test(this.env.PUBLIC_URL || ''); // wrangler dev in tests
        if (!subscription?.endpoint || !(/^https:\/\//.test(subscription.endpoint) || (local && /^http:\/\/127\.0\.0\.1[:/]/.test(subscription.endpoint)))) return json({ error: 'no subscription' }, 400);
        const devices = (await this.store.get('devices')) || {};
        if (!devices[who.id]) return json({ error: 'unknown device' }, 403);
        devices[who.id].push = { endpoint: subscription.endpoint };
        await this.store.put('devices', devices);
        return json({ ok: true });
      }
      if (p === '/device/key' && req.method === 'POST') { // the Android app's public key for sealed reminders
        const { pub = '' } = await req.json().catch(() => ({}));
        if (!SEAL_KEY.test(String(pub))) return json({ error: 'not a key' }, 400);
        const devices = (await this.store.get('devices')) || {};
        if (devices[who.id]?.kind !== 'android') return json({ error: 'only the Android app has a key' }, 403);
        const changed = devices[who.id].seal !== pub;
        devices[who.id].seal = String(pub);
        await this.store.put('devices', devices);
        if (changed) await this.event({ name: 'device_key', id: who.id });
        return json({ ok: true });
      }
      return json({ error: 'not found' }, 404);
    } catch (e) {
      return json({ error: String(e?.message || e).slice(0, 300) }, 500);
    }
  }

  // ------------------------------------------------------------------------------------------------ auth
  // A paired device ("d1.<id>.<secret>"), a call link from this Worker (random, 2 h) or from your computer (t1).
  async auth(key) {
    key = String(key || '');
    const d = /^d1\.([0-9a-f]{8})\.([0-9a-f]{64})$/.exec(key);
    if (d) {
      const dev = ((await this.store.get('devices')) || {})[d[1]];
      return dev && same(dev.hash, await sha256(d[2])) ? { kind: 'device', id: d[1] } : null;
    }
    if (await signedTicketOk(this.env.CALL_SECRET, key)) return { kind: 'ticket' };
    const t = (await this.store.get('tickets')) || {};
    return Object.entries(t).some(([k, exp]) => same(k, key) && exp > Date.now()) ? { kind: 'ticket' } : null;
  }

  async mintTicket(hours) {
    const ticket = randomHex(16);
    const t = (await this.store.get('tickets')) || {};
    for (const [k, exp] of Object.entries(t)) if (exp < Date.now()) delete t[k];
    t[ticket] = Date.now() + hours * 3600e3;
    await this.store.put('tickets', t);
    return ticket;
  }

  // --------------------------------------------------------------------------------------------- pairing
  // Your computer makes a one-time code (QR or the link Telegram sends you); the phone trades it for its own key.
  async claim(req) {
    const now = Date.now();
    const fail = (await this.store.get('pairfail')) || { n: 0, since: now };
    if (now - fail.since > 3600e3) Object.assign(fail, { n: 0, since: now });
    if (fail.n >= 30) return json({ error: 'too many wrong codes; make a new one on your computer' }, 429);
    const { code = '', name = '', kind = 'web' } = await req.json().catch(() => ({}));
    const codes = (await this.store.get('paircodes')) || {};
    const h = await sha256(String(code).trim().toUpperCase());
    const hit = codes[h];
    for (const [k, c] of Object.entries(codes)) if (c.exp < now) delete codes[k];
    if (!hit || hit.exp < now) {
      fail.n += 1;
      await this.store.put('pairfail', fail);
      await this.store.put('paircodes', codes);
      return json({ error: 'that code is wrong or has expired; make a new one on your computer' }, 401);
    }
    delete codes[h];
    await this.store.put('paircodes', codes);
    const devices = (await this.store.get('devices')) || {};
    if (Object.keys(devices).length >= MAX_DEVICES) return json({ error: `at most ${MAX_DEVICES} devices; remove one on your computer first` }, 409);
    const id = randomHex(4), secret = randomHex(32);
    const k = kind === 'android' ? 'android' : 'web';
    devices[id] = { name: String(name).slice(0, 60) || (k === 'android' ? 'Android phone' : 'Phone'), kind: k, hash: await sha256(secret), created: new Date().toISOString(), push: null };
    await this.store.put('devices', devices);
    await this.event({ name: 'device_paired', id, device_name: devices[id].name, kind: k });
    const names = (await this.store.get('names')) || {};
    return json({
      device: `d1.${id}.${secret}`, id, url: this.env.PUBLIC_URL, ...names,
      ntfy: k === 'android' ? { server: this.env.NTFY_SERVER || 'https://ntfy.sh', topic: this.env.NTFY_TOPIC, key: this.env.NTFY_KEY } : null,
      vapid: this.env.VAPID_PUBLIC || null,
    });
  }

  // ---------------------------------------------------------------------------------------- the computer
  connect(req) {
    if (req.headers.get('upgrade') !== 'websocket') return new Response('expected a websocket', { status: 426 });
    if (!same(req.headers.get('x-connector-secret'), this.env.CONNECTOR_SECRET)) return new Response('no', { status: 401 });
    for (const old of this.computers()) { try { old.close(1000, 'replaced'); } catch { /* gone */ } }
    const pair = new WebSocketPair();
    this.state.acceptWebSocket(pair[1], ['computer']);
    pair[1].serializeAttachment({ at: Date.now() });
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  async webSocketMessage(ws, data) {
    const was = ws.deserializeAttachment() || {};
    if (was.kind === 'phone') { // a phone only pings (answered without waking this); anything else just says it's there
      ws.serializeAttachment({ ...was, at: Date.now() });
      return;
    }
    ws.serializeAttachment({ at: Date.now() });
    let m;
    try { m = JSON.parse(data); } catch { return; }
    if (m.type === 'reply') {
      const r = this.pending.get(m.id);
      if (r) { this.pending.delete(m.id); r(m); }
    } else if (m.type === 'state') {
      for (const k of ['brief', 'config', 'texts', 'offline', 'schedule', 'names', 'live']) {
        if (m[k] !== undefined) await this.store.put(k, k === 'brief' ? { ...m.brief, at: new Date().toISOString() } : m[k]);
      }
      if (m.presence !== undefined) await this.setPresence(m.presence);
      if (m.inbox && Array.isArray(m.inbox.items)) await this.setInbox(m.inbox.items, Number(m.inbox.rev) || 0);
      if (m.sealed_on === false) await this.store.delete('sealed'); // reminders with the lid shut is off: drop them
      if (((await this.store.get('queue')) || []).length) ws.send(JSON.stringify({ type: 'outbox' })); // missed a nudge?
    } else if (m.type === 'index') {
      await this.store.put(`index:${m.part || 0}`, m.items || []);
      if ((m.part || 0) === 0) await this.store.put('index:parts', m.parts || 1);
    } else if (m.type === 'hello') {
      const q = await this.queueList();
      const away = (await this.store.get('away')) || null; // what this line told you while the computer was gone
      const told = away && away.told ? { since: away.since, told: away.told, channels: away.channels || [] } : null;
      if (m.pull) { // it takes what waited one item at a time ("outbox"), each dropped here once it's done
        ws.send(JSON.stringify({ type: 'welcome', version: this.env.VERSION || '', queue: [], outbox: q.length, away: told }));
      } else { // a computer from before 0.5.16: everything at once, what it can't take (chat, files) left out
        const all = [];
        for (const x of q) {
          if (x.kind === 'answer' && x.bkey) all.push({ ...x, body: await this.store.get(x.bkey) });
          else if (!PHONE_KINDS.includes(x.kind)) all.push(x);
          if (x.bkey) await this.store.delete(x.bkey);
        }
        ws.send(JSON.stringify({ type: 'welcome', version: this.env.VERSION || '', queue: all, away: told }));
        if (q.length) await this.store.put('queue', []);
      }
      if (away && !away.told) await this.store.delete('away'); // back before anything was said: nothing to say
      await this.store.put('seen', Date.now());
    } else if (m.type === 'admin') {
      let result;
      try { result = await this.admin(m); } catch (e) { result = { error: String(e?.message || e) }; }
      try { ws.send(JSON.stringify({ type: 'admin-reply', id: m.id, result })); } catch { /* gone */ }
    }
  }

  async webSocketClose(ws) { // the computer (or a phone) reconnects by itself
    if (ws?.deserializeAttachment()?.kind !== 'phone') await this.store.put('seen', Date.now());
  }

  async webSocketError(ws) { if (ws?.deserializeAttachment()?.kind !== 'phone') await this.store.put('seen', Date.now()); }

  async admin(m) {
    if (m.op === 'ring') return this.ring(m);
    if (m.op === 'stop-ring') { await this.endRing(String(m.since || '')); return { ok: true }; }
    if (m.op === 'pair-code') {
      const codes = (await this.store.get('paircodes')) || {};
      for (const [k, c] of Object.entries(codes)) if (c.exp < Date.now()) delete codes[k];
      codes[await sha256(String(m.code).trim().toUpperCase())] = { exp: Date.now() + Math.min(Number(m.minutes) || 15, 60) * 60e3 };
      await this.store.put('paircodes', codes);
      await this.store.put('pairfail', { n: 0, since: Date.now() });
      return { ok: true };
    }
    if (m.op === 'devices') {
      const d = (await this.store.get('devices')) || {};
      const heard = this.phonesHeard(), fresh = Date.now() - PHONE_FRESH_MS;
      return { devices: Object.entries(d).map(([id, v]) => ({
        id, name: v.name, kind: v.kind, created: v.created, push: !!v.push, seal: v.seal || '',
        ...(v.kind === 'android' ? { connected: (heard[id] || 0) > fresh, heard: heard[id] ? new Date(heard[id]).toISOString() : null } : {}),
      })) };
    }
    if (m.op === 'revoke') { // `device`: m.id is the admin request's own (a line before 0.6.0 read m.id: never found)
      const dev = String(m.device || '');
      const d = (await this.store.get('devices')) || {};
      const had = !!d[dev];
      delete d[dev];
      await this.store.put('devices', d);
      for (const ws of this.state.getWebSockets(`dev:${dev}`)) { try { ws.close(1008, 'unpaired'); } catch { /* gone */ } }
      await this.store.delete(`today:${dev}`); // its Today copy goes with it
      const views = await this.store.get('views'); // and its keys to the views
      if (views) { for (const k of VIEW_KINDS) if (views[k]?.keys) delete views[k].keys[dev]; await this.store.put('views', views); }
      await this.tellDrop((t) => t.device === dev); // its Tell Kurooto link goes with it
      return { ok: had };
    }
    if (m.op === 'tells') {
      const d = (await this.store.get('devices')) || {};
      const t = (await this.store.get('tells')) || {};
      return { tells: Object.entries(t).map(([id, v]) => ({ id, device: v.device, device_name: d[v.device]?.name || '', created: v.created, used: v.used || null })) };
    }
    if (m.op === 'tell-revoke') return { ok: await this.tellDrop((_t, id) => id === String(m.tid || '')) };
    if (m.op === 'ticket') return { ticket: await this.mintTicket(Math.min(Number(m.hours) || 2, 24)) };
    if (m.op === 'bye') return this.bye(m);
    if (m.op === 'notify') return this.notify(m.item || {}, Number(m.rev) || 0, m.assistant);
    if (m.op === 'notify-clear') {
      const inbox = (await this.store.get('inbox')) || { rev: 0, items: [] };
      const ids = (m.ids || []).map(String);
      await this.setInbox(inbox.items.filter((i) => !ids.includes(i.id)), Math.max(inbox.rev, Number(m.rev) || 0), ids);
      return { ok: true };
    }
    if (m.op === 'sealed-put') return this.sealedPut(Array.isArray(m.items) ? m.items : [], Number(m.rev) || 0);
    if (m.op === 'sealed-claim') return this.sealedClaim((Array.isArray(m.ids) ? m.ids : []).map(String));
    if (m.op === 'outbox') return this.outbox(m.done);
    if (m.op === 'chat-say') return this.chatSay(m.msg || {}, m.assistant, !!m.update);
    if (m.op === 'chat-sessions') return this.chatSessionsPut(m);
    if (m.op === 'chat-status') return this.chatStatusPut(m);
    if (m.op === 'file-put') return this.filePut(m);
    if (m.op === 'today-put') return this.todayPut(m);
    if (m.op === 'view-put') return this.viewPut(m);
    return { error: 'unknown op' };
  }

  // Ask the computer (relay). 503 when it's not connected; the caller then answers from what it has.
  async relay(method, path, body, body_b64) {
    const sockets = this.computers();
    if (!sockets.length || !this.online()) return { status: 503, body: JSON.stringify({ offline: true }) };
    const id = crypto.randomUUID();
    const reply = new Promise((resolve) => {
      this.pending.set(id, resolve);
      setTimeout(() => { if (this.pending.delete(id)) resolve({ status: 504, body: JSON.stringify({ error: 'your computer did not answer in time' }) }); }, 55000);
    });
    sockets[0].send(JSON.stringify({ type: 'request', id, method, path, body, body_b64 }));
    const r = await reply;
    return { status: r.status || 200, body: r.body };
  }

  // ---------------------------------------------------------------------------------------------- calls
  // The Live models to try, in order: the one in the call setup, then the others your computer pushed.
  async liveModels(tpl) {
    const live = (await this.store.get('live')) || {};
    const list = [tpl?._model || this.env.LIVE_MODEL || 'gemini-3.8-live', ...(Array.isArray(live.models) ? live.models : [])];
    return [...new Set(list.map(String).filter((m) => MODEL_ID.test(m)))].slice(0, 6);
  }

  // The call's instructions, the same for Live and for turn-by-turn calls: the time, whether the computer is off,
  // and why the call was placed.
  async instructions(tpl, purpose, online) {
    const texts = (await this.store.get('texts')) || {};
    const brief = await this.store.get('brief');
    const when = new Date().toLocaleString('en-GB', { timeZone: this.env.TZ || 'UTC', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    let si = String(tpl.systemInstruction || '').replace('%%NOW%%', when);
    if (!online && texts.offline) si += '\n' + texts.offline.replace('%%BRIEF_AT%%', brief?.at ? brief.at.slice(0, 16).replace('T', ' ') + ' UTC' : 'unknown');
    if (purpose && texts.purpose) si += '\n' + texts.purpose.replace('%%REASON%%', String(purpose).slice(0, 300));
    return si;
  }

  // A call got through (Live, turn by turn or on Telegram): the ring stops and your computer hears it was answered.
  async started(purpose, since, who, online, layer) {
    if (since) await this.endRing(String(since));
    await this.event({ name: 'call_started', purpose: String(purpose).slice(0, 120), since: String(since), via: who.kind, offline: !online, layer });
  }

  ai(apiVersion = 'v1alpha') { // v1alpha for Live tokens; text turns use the default (v1beta)
    return new GoogleGenAI({ apiKey: this.env.GEMINI_API_KEY, httpOptions: { ...(apiVersion ? { apiVersion } : {}), ...(this.env.GEMINI_BASE_URL ? { baseUrl: this.env.GEMINI_BASE_URL } : {}) } });
  }

  // A Live token for one call (`model`: one of liveModels, else the first). announce: false for another try at the
  // same call (it was announced already); resume: picking up a session that dropped. When Google refuses (503
  // UNAVAILABLE, 429...) the answer says so (live, retry), and your computer counts it.
  async token(req, who) {
    const { purpose = '', since = '', model: want = '', announce = true, resume = false } = await req.json().catch(() => ({}));
    const tpl = await this.store.get('config');
    if (!tpl) return json({ error: 'your computer has never connected to this call line, so calls are not set up yet' }, 503);
    const online = this.online();
    const models = await this.liveModels(tpl);
    const model = models.includes(String(want)) ? String(want) : models[0];
    const config = JSON.parse(JSON.stringify(tpl));
    for (const k of Object.keys(config)) if (k.startsWith('_')) delete config[k];
    config.systemInstruction = await this.instructions(tpl, resume ? '' : purpose, online);
    // what this model's session drops or changes (your computer works it out: calls/fallback.py live_profile)
    const prof = (((await this.store.get('live')) || {}).profiles || {})[model] || {};
    if (prof.non_blocking === false) for (const t of config.tools || []) for (const d of t.functionDeclarations || []) delete d.behavior;
    if (typeof prof.voice === 'string') {
      if (prof.voice) config.speechConfig = { voiceConfig: { prebuiltVoiceConfig: { voiceName: prof.voice } } };
      else delete config.speechConfig;
    }
    let token;
    try {
      token = await this.ai().authTokens.create({ config: {
        uses: 1,
        expireTime: new Date(Date.now() + 30 * 60e3).toISOString(),
        newSessionExpireTime: new Date(Date.now() + 2 * 60e3).toISOString(),
        liveConnectConstraints: { model, config },
        httpOptions: { apiVersion: 'v1alpha' },
      } });
    } catch (e) {
      const g = googleError(e);
      await this.event({ name: 'live_failed', model, code: g.code, status: g.status, stage: 'token' });
      // a model other than the first that refuses the session may just not take it: the next one is tried
      const badModel = g.badModel || (!g.retry && g.code === 400 && model !== models[0]);
      return json({ error: `the voice service didn't start the call: ${g.text}`, live: true, retry: g.retry, bad_model: badModel, code: g.code, status: g.status, model, models }, 503);
    }
    await this.store.put('oncall', Date.now());
    if (announce && !resume) await this.started(purpose, since, who, online, 'live');
    else if (since) await this.endRing(String(since));
    return json({ token: token.name, model, models, config, offline: !online });
  }

  // One turn of a turn-by-turn call: your computer's AI answers when it's online (the same AI and tools as your
  // messages); otherwise, or when it couldn't, a Gemini text model with your key answers here, with the call's
  // instructions and tools (the tools as on any call: your computer's, or what it last sent).
  async turn(req, who) {
    const b = await req.json().catch(() => ({}));
    const history = cleanHistory(b.history);
    if (!history.length) return json({ error: 'nothing to answer' }, 400);
    const purpose = String(b.purpose || '').slice(0, 300), since = String(b.since || '');
    const tpl = await this.store.get('config');
    if (!tpl) return json({ error: 'your computer has never connected to this call line, so calls are not set up yet' }, 503);
    const online = this.online();
    await this.store.put('oncall', Date.now());
    if (b.announce) await this.started(purpose, since, who, online, 'turns');
    if (online) {
      const r = await this.relay('POST', '/turn', JSON.stringify({ history, purpose, since }));
      if (r.status === 200) {
        try { const j = JSON.parse(r.body || '{}'); if (j.reply) return json({ reply: spoken(j.reply), via: 'computer' }); } catch { /* below */ }
      }
    }
    try {
      return json({ reply: await this.textTurn(tpl, history, purpose, online), via: 'line', offline: !online });
    } catch (e) {
      const g = googleError(e);
      return json({ error: `no answer from Gemini: ${g.text}`, code: g.code }, 502);
    }
  }

  async textTurn(tpl, history, purpose, online) {
    const texts = (await this.store.get('texts')) || {};
    const live = (await this.store.get('live')) || {};
    const systemInstruction = (await this.instructions(tpl, purpose, online)) + '\n' + (texts.turns || TURNS_TEXT);
    const decls = (((tpl.tools || [])[0] || {}).functionDeclarations || []).map(({ behavior, ...d }) => d); // NON_BLOCKING is Live's
    const tools = decls.length ? [{ functionDeclarations: decls }] : undefined;
    const contents = history.map((h) => ({ role: h.role, parts: [{ text: h.text }] }));
    const model = MODEL_ID.test(String(live.text_model || '')) ? String(live.text_model) : 'gemini-flash-latest';
    const ai = this.ai('');
    for (let round = 0; ; round++) {
      const last = round >= TURN_TOOL_ROUNDS;
      const r = await ai.models.generateContent({ model, contents, config: { systemInstruction, tools, ...(tools && last ? { toolConfig: { functionCallingConfig: { mode: 'NONE' } } } : {}) } });
      const calls = (r.functionCalls || []).slice(0, 8);
      if (!calls.length || last) return spoken(r.text || '') || "Sorry, I didn't get that. Could you say it again?";
      contents.push(r.candidates[0].content);
      const parts = [];
      for (const fc of calls) parts.push({ functionResponse: { id: fc.id, name: fc.name, response: { result: await this.runTool(String(fc.name || ''), fc.args || {}) } } });
      contents.push({ role: 'user', parts });
    }
  }

  // A tool for a turn answered here: your computer's when it's online, else what it last sent (offlineTool).
  async runTool(name, args) {
    if (this.online()) {
      const r = await this.relay('POST', '/tool', JSON.stringify({ name, args }));
      if (r.status === 200) { try { return JSON.parse(r.body || '{}').result; } catch { return 'That tool gave no answer.'; } }
      if (r.status !== 503) return 'That tool failed on their computer.';
    }
    return this.offlineTool(name, args);
  }

  // The call goes on as text on Telegram: your computer starts the conversation now, or as soon as it's back.
  async textCall(req, who) {
    const b = await req.json().catch(() => ({}));
    const body = { purpose: String(b.purpose || '').slice(0, 300), since: String(b.since || ''), why: String(b.why || '').replace(/[^\w-]/g, '').slice(0, 20), lines: cleanLines(b.lines) };
    const online = this.online();
    if (b.announce) await this.started(body.purpose, body.since, who, online, 'telegram');
    if (online) {
      const r = await this.relay('POST', '/textcall', JSON.stringify(body));
      if (r.status === 200) return new Response(r.body, { status: 200, headers: { 'content-type': 'application/json', ...CORS } });
    }
    await this.queue({ kind: 'event', name: 'text_call', ...body });
    return json({ ok: true, queued: true });
  }

  // What the call page saw: a Live start or session that failed, a retry that worked, a fallback (for `kurooto doctor`).
  async report(req) {
    const b = await req.json().catch(() => ({}));
    const name = { failed: 'live_failed', recovered: 'live_recovered', fallback: 'call_fallback' }[String(b.what || '')];
    if (!name) return json({ error: 'unknown report' }, 400);
    const ev = { name };
    if (MODEL_ID.test(String(b.model || ''))) ev.model = String(b.model);
    for (const k of ['code', 'attempt']) if (Number.isFinite(Number(b[k]))) ev[k] = Number(b[k]);
    for (const k of ['stage', 'layer', 'why', 'status']) if (b[k]) ev[k] = String(b[k]).replace(/[^\w .:-]/g, '').slice(0, 80);
    await this.event(ev);
    return json({ ok: true });
  }

  async tool(req) {
    const body = await req.text();
    if (this.online()) {
      const r = await this.relay('POST', '/tool', body);
      if (r.status !== 503) return new Response(r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    const { name = '', args = {}, since = '' } = JSON.parse(body || '{}');
    return json({ result: await this.offlineTool(String(name), args || {}, String(since || '').slice(0, 20)) });
  }

  async offlineTool(name, args, since = '') {
    const brief = (await this.store.get('brief')) || {};
    const off = (await this.store.get('offline')) || {};
    const texts = (await this.store.get('texts')) || {};
    if ((off.brief || {})[name]) return { ...(brief[off.brief[name]] ?? { note: 'nothing saved for this' }), note: 'from what your computer last sent; it is offline now' };
    if (name === 'search_notes' && off.notes) {
      const hits = await this.search(String(args.query || ''));
      return hits.length ? { note: 'computer offline: keyword search over note titles, headings and summaries; read_note for the full text', hits } : 'Nothing in the notes index matches (keyword search only while the computer is off). Try other words.';
    }
    if (name === 'read_note' && off.notes) {
      const text = await githubNote(this.env, args.slug || '');
      if (text) return text.length > 6000 ? text.slice(0, 6000) + '\n[…]' : text;
      return this.env.GITHUB_TOKEN ? `No note "${args.slug}" in the notes repo.` : (texts.no_notes || 'Your computer is off, so whole notes can\'t be read right now.');
    }
    if ((off.queue || []).includes(name)) {
      await this.queue({ kind: 'tool', name, args, since }); // the call's own look back gets it, not the next call's
      return texts.queued || 'Saved. Your computer is off; it will do this as soon as it is back online.';
    }
    return texts.needs_computer || 'That needs your computer, which is off right now.';
  }

  async search(query) {
    const words = query.toLowerCase().split(/\W+/).filter((w) => w.length > 2);
    const parts = (await this.store.get('index:parts')) || 0;
    const scored = [];
    for (let i = 0; i < parts; i++) {
      for (const n of (await this.store.get(`index:${i}`)) || []) {
        const hay = { t: (n.t || '').toLowerCase(), a: (n.a || '').toLowerCase(), h: (n.h || '').toLowerCase(), m: (n.m || '').toLowerCase(), s: (n.s || '').toLowerCase() };
        let sc = 0;
        for (const w of words) sc += (hay.t.includes(w) ? 5 : 0) + (hay.a.includes(w) ? 4 : 0) + (hay.s.includes(w) ? 3 : 0) + (hay.h.includes(w) ? 2 : 0) + (hay.m.includes(w) ? 1 : 0);
        if (sc > 0) scored.push([sc, n]);
      }
    }
    return scored.sort((a, b) => b[0] - a[0]).slice(0, 6).map(([sc, n]) => ({ slug: n.s, title: n.t, headings: n.h, summary: n.m, score: sc }));
  }

  async tasks(req) {
    await this.store.put('oncall', Date.now()); // the call page asks every few seconds while a call is live
    if (this.online()) {
      const r = await this.relay('GET', '/tasks', '');
      if (r.status !== 503) return new Response(r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    return json({ finished: [], running: 0, approvals: [], computer: 'offline' });
  }

  async transcript(req) {
    await this.store.delete('oncall'); // the call page sends this when the call ends
    const body = (await req.text()).slice(0, 3_000_000);
    if (this.online()) {
      const r = await this.relay('POST', '/transcript', body);
      if (r.status !== 503) return new Response(r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    await this.queue({ kind: 'transcript', body: body.slice(0, 200_000) });
    return json({ ok: true, queued: true });
  }

  // A part of a shared file: to your computer now; from a paired phone while it's off, kept in the outbox (a whole
  // file must fit when its first part comes).
  async upload(req, url, who) {
    const offline = () => json({ error: 'your computer is offline: share it again later, or send it to your Telegram bot' }, 503);
    if (!this.online() && who.kind !== 'device') { try { await req.arrayBuffer(); } catch { /* none */ } return offline(); }
    const buf = new Uint8Array(await req.arrayBuffer());
    if (buf.length > 600 * 1024) return json({ error: 'send files in parts of at most 512 KB' }, 413);
    let s = '';
    for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    if (this.online() && (who.kind !== 'device' || !(await this.outboxBusy()))) { // a phone's waits behind what it sent before
      const r = await this.relay('POST', '/upload' + url.search, '', btoa(s));
      if (r.status !== 503 || who.kind !== 'device') return new Response(r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    const id = String(url.searchParams.get('id') || '').replace(/[^\w-]/g, '').slice(0, 40);
    if (who.kind !== 'device' || !id) return offline();
    const part = Number(url.searchParams.get('part')) || 0, parts = Math.max(1, Number(url.searchParams.get('parts')) || 1);
    const ok = await this.outboxPut('upload', who, id, btoa(s), { bytes: buf.length, need: part === 0 ? parts * PART : 0, search: url.search, last: part >= parts - 1 });
    if (!ok) return json({ error: 'full', note: OUTBOX_FULL }, 507);
    const texts = (await this.store.get('texts')) || {};
    return json({ ok: true, queued: true, part, note: texts.outbox_queued || 'Saved on your call line. It goes to your computer when it is back on.' });
  }

  // ------------------------------------------------------------------------------------------- ringing
  // How a call listens: what your computer said for this call, else its default ("live", "phone" or "auto").
  async voice(which = 'voice', given = '') {
    if (VOICE_MODES.includes(given)) return given;
    const v = ((await this.store.get('live')) || {})[which];
    return VOICE_MODES.includes(v) ? v : 'auto';
  }

  async ring({ reason = '', alarm = false, since = '', key = '', assistant = '', voice = '' }) {
    since = String(since || Math.floor(Date.now() / 1000));
    const ticket = await this.mintTicket(alarm ? 3 : 2);
    const link = `${this.env.PUBLIC_URL}/?p=${encodeURIComponent(String(reason).slice(0, 300))}&s=${encodeURIComponent(since)}&v=${await this.voice('voice', voice)}#${ticket}`;
    const rings = ((await this.store.get('rings')) || []).filter((r) => r.until > Date.now() && r.since !== since);
    rings.push({ since, reason: String(reason).slice(0, 300), link, alarm: !!alarm, key, until: Date.now() + (alarm ? ALARM_RING_S : RING_S) * 1000 });
    await this.store.put('rings', rings.slice(-10));
    const devices = (await this.store.get('devices')) || {};
    const list = Object.entries(devices);
    let android = false;
    if (list.some(([, d]) => d.kind === 'android')) {
      android = await this.toPhones({ title: alarm ? 'Wake-up call' : 'Incoming call', message: String(reason).slice(0, 300), priority: 5,
        tags: ['call', `since-${since}`].concat(alarm ? ['alarm'] : []), click: link, time: Math.floor(Date.now() / 1000) }, assistant).catch(() => false);
    }
    const { web, changed, errors } = await pushAll(this.env, devices);
    if (changed) await this.store.put('devices', devices);
    return { since, link, android, web, devices: list.length, phones: list.filter(([, d]) => d.kind === 'android').length, errors };
  }

  async endRing(since) {
    if (!since) return;
    const rings = (await this.store.get('rings')) || [];
    const left = rings.filter((r) => r.since !== since && r.until > Date.now());
    if (left.length !== rings.length) {
      await this.store.put('rings', left);
      await this.toPhones({ title: 'stop', message: '', tags: ['stop', `since-${since}`], time: Math.floor(Date.now() / 1000) }).catch(() => false);
    }
  }

  async ringing() {
    const now = Date.now();
    return ((await this.store.get('rings')) || []).filter((r) => r.until > now).map(({ since, reason, link, alarm }) => ({ since, reason, link, alarm }));
  }

  // --------------------------------------------------------------------------------------------- messages
  // Every sealed message to the Android app carries your assistant's current name, so renaming it on your computer
  // reaches the app without pairing again. Your computer sends the name with each ring and message; the state push
  // keeps it fresh for calls this Worker places itself.
  //
  // 0.7.0: sealed once, with a message id ("mid"), kept for phones that reconnect, sent down every Android phone's own
  // connection, and to ntfy only when a paired Android phone wasn't heard from lately (PHONE_FRESH_MS: asleep, out of
  // reach, or an app from before 0.7.0) or it's a ring (a second path; the phone keeps the first copy). True when an
  // Android phone has it (connected) or ntfy took it.
  async toPhones(fields, assistant = '') {
    const names = (await this.store.get('names')) || {};
    const name = String(assistant || '').slice(0, 60);
    if (name && name !== names.assistant) await this.store.put('names', { ...names, assistant: name });
    const current = name || names.assistant || '';
    const devices = (await this.store.get('devices')) || {};
    const android = Object.entries(devices).filter(([, d]) => d.kind === 'android').map(([id]) => id);
    if (!this.env.NTFY_KEY || !android.length) return false;
    const k1 = await sealK1(this.env.NTFY_KEY, JSON.stringify({ ...fields, ...(current ? { assistant: current } : {}), mid: randomHex(8) }));
    const seq = await this.phoneLogPut(k1);
    for (const ws of this.state.getWebSockets('phone')) { try { ws.send(JSON.stringify({ seq, k1 })); } catch { /* gone */ } }
    const heard = this.phonesHeard(), cut = Date.now() - PHONE_FRESH_MS;
    const up = android.filter((id) => (heard[id] || 0) > cut).length;
    const ring = Array.isArray(fields.tags) && fields.tags.includes('call');
    const viaNtfy = ring || up < android.length ? await publish(this.env, k1, fields.priority || 3).catch(() => false) : false;
    return up > 0 || viaNtfy;
  }

  // What went to the Android phones lately, for one that reconnects: {seq, items: [{seq, t, k1}]}.
  async phoneLog() {
    const log = (await this.store.get('plog')) || { seq: 0, items: [] };
    const cut = Date.now() - PHONE_LOG_MS;
    return { seq: log.seq, items: log.items.filter((x) => x.t > cut) };
  }

  async phoneLogPut(k1) {
    const log = await this.phoneLog();
    const seq = log.seq + 1;
    await this.store.put('plog', { seq, items: log.items.concat([{ seq, t: Date.now(), k1 }]).slice(-PHONE_LOG_MAX) });
    return seq;
  }

  // An Android phone's own connection (0.7.0): one per phone (a new one replaces the old), hibernatable. It first
  // hears {"type": "hello", seq}, then what it missed: every message after `after` (the last seq it had), or the
  // last PHONE_NEW_MS of them when it has none or this line's count started again. Then each message as it's sent,
  // {seq, k1}. It sends "ping" now and then; the runtime answers "pong" without waking this object.
  async phoneConnect(req, who, url) {
    if (req.headers.get('upgrade') !== 'websocket') return json({ error: 'expected a websocket' }, 426);
    const devices = (await this.store.get('devices')) || {};
    if (devices[who.id]?.kind !== 'android') return json({ error: 'only the Android app has its own connection' }, 403);
    for (const old of this.state.getWebSockets(`dev:${who.id}`)) { try { old.close(1000, 'replaced'); } catch { /* gone */ } }
    const pair = new WebSocketPair();
    this.state.acceptWebSocket(pair[1], ['phone', `dev:${who.id}`]);
    pair[1].serializeAttachment({ kind: 'phone', dev: who.id, at: Date.now() });
    const log = await this.phoneLog();
    const after = Number(url.searchParams.get('after')) || 0;
    const known = after > 0 && after <= log.seq, cut = Date.now() - PHONE_NEW_MS;
    pair[1].send(JSON.stringify({ type: 'hello', seq: log.seq, version: this.env.VERSION || '' }));
    for (const x of log.items) if (known ? x.seq > after : x.t > cut) pair[1].send(JSON.stringify({ seq: x.seq, k1: x.k1 }));
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  // Your computer hands over a message for the Android phones over HTTPS (0.7.0: when its WebSocket is down, it used
  // to publish to ntfy itself, from an address it shares). {fields, assistant}; checked with the connector secret.
  async send(req) {
    const raw = await req.text().catch(() => '');
    if (!same(req.headers.get('x-connector-secret'), this.env.CONNECTOR_SECRET)) return json({ error: 'no' }, 401);
    if (raw.length > SEND_MAX) return json({ error: 'too long' }, 413);
    let b;
    try { b = JSON.parse(raw || '{}'); } catch { return json({ error: 'not JSON' }, 400); }
    if (!b.fields || typeof b.fields !== 'object' || Array.isArray(b.fields)) return json({ error: 'no message' }, 400);
    const devices = (await this.store.get('devices')) || {};
    const phones = Object.values(devices).filter((d) => d.kind === 'android').length;
    if (!phones) return json({ ok: true, android: false, phones: 0 });
    return json({ ok: true, android: await this.toPhones(b.fields, b.assistant).catch(() => false), phones });
  }

  // The inbox: what your computer sent your phones that's still open. Its revision only goes up, so an older
  // snapshot never overwrites a newer one. Items that go (answered, expired) are cleared from Android phones.
  async setInbox(items, rev, cleared = []) {
    const cur = (await this.store.get('inbox')) || { rev: 0, items: [] };
    if (rev < cur.rev) return false;
    const keep = items.filter((i) => i && ITEM_ID.test(String(i.id))).slice(-40);
    const gone = cur.items.map((i) => i.id).filter((id) => !keep.some((i) => i.id === id)).concat(cleared);
    await this.store.put('inbox', { rev, items: keep });
    if (gone.length) await this.clearPhones([...new Set(gone)]);
    return true;
  }

  async openItems() {
    const now = Date.now() / 1000;
    return (((await this.store.get('inbox')) || {}).items || []).filter((i) => (i.until || 0) > now);
  }

  async clearPhones(ids) {
    const devices = (await this.store.get('devices')) || {};
    if (!Object.values(devices).some((d) => d.kind === 'android')) return false;
    // "stop" too, so an older app that doesn't know "clear" ignores it instead of showing it
    return this.toPhones({ title: 'stop', message: '', tags: ['stop', 'clear'], ids: ids.slice(0, 40), time: Math.floor(Date.now() / 1000) }).catch(() => false);
  }

  async notify(item, rev, assistant = '') {
    if (!ITEM_ID.test(String(item.id))) return { error: 'bad item' };
    const cur = (await this.store.get('inbox')) || { rev: 0, items: [] };
    await this.store.put('inbox', { rev: Math.max(cur.rev, rev), items: cur.items.filter((i) => i.id !== item.id).concat([item]).slice(-40) });
    const devices = (await this.store.get('devices')) || {};
    const list = Object.values(devices);
    let android = false;
    if (list.some((d) => d.kind === 'android')) android = await this.toPhones(phoneMessage(item), assistant).catch(() => false);
    const { web, changed, errors } = await pushAll(this.env, devices);
    if (changed) await this.store.put('devices', devices);
    return { android, web, devices: list.length, errors };
  }

  // An answer from a phone: to your computer now, or kept until it's back. The Android app's answer is sealed
  // ("k1"); the web app's is plain JSON over HTTPS. Your computer checks it's fresh and used only once.
  async answer(req, who) {
    const raw = await req.text();
    if (raw.length > 16000) return json({ error: 'too long' }, 413);
    let b;
    try { b = JSON.parse(raw || '{}'); } catch { return json({ error: 'not JSON' }, 400); }
    const item = String(b.item || '');
    if (!ITEM_ID.test(item)) return json({ error: 'no item' }, 400);
    const body = { device: who.id, at: Date.now(), item };
    if (b.k1) body.k1 = String(b.k1);
    else for (const k of ['answer', 'button', 'dismiss', 'ts', 'n']) if (b[k] !== undefined) body[k] = b[k];
    const inbox = (await this.store.get('inbox')) || { rev: 0, items: [] };
    await this.store.put('inbox', { rev: inbox.rev, items: inbox.items.filter((i) => i.id !== item) });
    if (this.online() && !(await this.outboxBusy())) { // behind what this or another phone sent before, if any
      const r = await this.relay('POST', '/answer', JSON.stringify(body));
      if (r.status !== 503) return new Response(r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    if (!(await this.outboxPut('answer', who, item, body))) return json({ error: 'full', note: OUTBOX_FULL }, 507);
    const texts = (await this.store.get('texts')) || {};
    return json({ ok: true, queued: true, note: texts.answer_queued || 'Saved. Your computer gets it when it is back on.' });
  }

  // ------------------------------------------------------------------------------------------- the chat
  // A message typed in the phone app (or a button tapped under one of Kurooto's): to your computer now, or kept in
  // the outbox till it's back. Like an answer: the Android app's is sealed ("k1"), the web app's plain JSON.
  async chat(req, who) {
    const raw = await req.text();
    if (raw.length > 16000) return json({ error: 'too long' }, 413);
    let b;
    try { b = JSON.parse(raw || '{}'); } catch { return json({ error: 'not JSON' }, 400); }
    const id = String(b.id || '');
    if (!ITEM_ID.test(id)) return json({ error: 'no id' }, 400);
    const body = { device: who.id, at: Date.now(), id };
    if (b.k1) body.k1 = String(b.k1);
    else for (const k of CHAT_FIELDS) if (b[k] !== undefined) body[k] = b[k];
    // `live` (the being's requests, 0.8.10): now or not at all, ahead of what waits in the outbox
    if (this.online() && (b.live || !(await this.outboxBusy()))) {
      const r = await this.relay('POST', '/chat', JSON.stringify(body));
      if (r.status !== 503 || b.live) return new Response(r.status === 503 ? JSON.stringify({ ok: false, offline: true, note: OFF_NOW }) : r.body, { status: r.status, headers: { 'content-type': 'application/json', ...CORS } });
    }
    if (b.live) return json({ ok: false, offline: true, note: OFF_NOW }, 503);
    if (!(await this.outboxPut('chat', who, id, body))) return json({ error: 'full', note: OUTBOX_FULL }, 507);
    const texts = (await this.store.get('texts')) || {};
    return json({ ok: true, queued: true, note: texts.chat_queued || 'Your computer is off: this waits on your call line and goes to it when it is back.' });
  }

  // One chat's kept messages ("main": Kurooto's own, under "chat", which also holds the seq all chats share).
  async chatLog(sid = 'main') {
    const main = (await this.store.get('chat')) || { seq: 0, msgs: [] };
    const log = sid === 'main' ? main : (await this.store.get(`chat:${sid}`)) || { msgs: [] };
    const cut = Date.now() / 1000 - CHAT_KEEP_S;
    return { seq: main.seq, msgs: log.msgs.filter((m) => m.at > cut) };
  }

  async chatPut(sid, seq, msgs) {
    if (sid === 'main') return this.store.put('chat', { seq, msgs });
    const main = (await this.store.get('chat')) || { seq: 0, msgs: [] };
    await this.store.put('chat', { seq: Math.max(main.seq, seq), msgs: main.msgs });
    await this.store.put(`chat:${sid}`, { msgs });
    const idx = (await this.store.get('chatIdx')) || [];
    if (!idx.includes(sid)) await this.store.put('chatIdx', idx.concat([sid]));
  }

  // Every chat's messages after `after` (in seq order), the list of chats and the commands, and which are working.
  async chatAll(after) {
    const ids = ['main', ...((await this.store.get('chatIdx')) || [])];
    let seq = 0, msgs = [];
    for (const sid of ids) {
      const log = await this.chatLog(sid);
      seq = Math.max(seq, log.seq);
      msgs = msgs.concat(log.msgs.filter((m) => m.seq > after));
    }
    msgs.sort((a, b) => a.seq - b.seq);
    const list = (await this.store.get('chatSessions')) || { rev: 0, sessions: [], commands: [], switches: {} };
    const now = Date.now(), status = {};
    for (const [sid, st] of Object.entries(this.chatStatus)) if (now - st.t < STATUS_MS) status[sid] = { state: st.state, job: st.job };
    return { seq, msgs, sessions: list.sessions, commands: list.commands, switches: list.switches || {}, srev: list.rev, status };
  }

  // Your computer puts a message in the chat: yours (once it took it) or Kurooto's (then it goes to your phones).
  // update: a change to one already here (edited, deleted, pinned): it keeps its place, gets a new seq, and goes to
  // the phones connected straight to this line ("chat-update"; the others see it when they catch up).
  async chatSay(msg, assistant = '', update = false) {
    if (!ITEM_ID.test(String(msg.id)) || !['you', 'kurooto'].includes(msg.from)) return { error: 'bad message' };
    const sid = SESSION_ID.test(String(msg.session || '')) ? String(msg.session) : 'main';
    const log = await this.chatLog(sid);
    const had = log.msgs.find((m) => m.id === msg.id);
    if (had && !update) return { ok: true, seq: had.seq }; // said already (sent again after the link dropped)
    const m = had || {
      id: msg.id, from: msg.from,
      at: Number.isFinite(msg.at) ? Math.floor(msg.at) : Math.floor(Date.now() / 1000),
      buttons: (Array.isArray(msg.buttons) ? msg.buttons : []).slice(0, 6).map((x) => (String(x?.url || '').startsWith('https://') ? { label: String(x.label).slice(0, 40), url: String(x.url) } : { label: String(x?.label || '').slice(0, 40) })),
      reply: !!msg.reply,
    };
    m.seq = log.seq + 1;
    m.text = String(msg.text || '').slice(0, CHAT_TEXT);
    m.session = sid;
    if (msg.title) m.title = String(msg.title).slice(0, 120);
    if (ITEM_ID.test(String(msg.re || ''))) m.re = String(msg.re);
    for (const k of ['edited', 'deleted']) if (msg[k]) m[k] = true;
    if (msg.pinned !== undefined) m.pinned = !!msg.pinned;
    if (msg.deleted) { delete m.file; delete m.quote; m.buttons = []; }
    else {
      const f = msg.file;
      if (f && typeof f === 'object') m.file = { name: String(f.name || '').slice(0, 120), size: Number(f.size) || 0, mime: String(f.mime || '').slice(0, 100), ...(String(f.url || '').startsWith('http') ? { url: String(f.url).slice(0, 600) } : {}) };
      const q = msg.quote;
      if (q && typeof q === 'object' && ITEM_ID.test(String(q.id || ''))) m.quote = { id: String(q.id), from: String(q.from || '').slice(0, 10), text: String(q.text || '').slice(0, 200) };
    }
    const msgs = had ? log.msgs.map((x) => (x.id === m.id ? m : x)) : log.msgs.concat([m]).slice(-CHAT_MAX);
    await this.chatPut(sid, m.seq, msgs);
    if (!had) await this.chatTouch(sid, m);
    if (had) { await this.toLinked(chatMessage(m, true)); return { ok: true, seq: m.seq }; }
    if (m.from !== 'kurooto') return { ok: true, seq: m.seq };
    if (msg.quiet) { await this.toLinked(chatMessage(m)); return { ok: true, seq: m.seq }; } // (0.9.1) the Desk chat: kept, no notification
    const devices = (await this.store.get('devices')) || {};
    let android = false;
    if (Object.values(devices).some((d) => d.kind === 'android')) android = await this.toPhones(chatMessage(m), assistant).catch(() => false);
    const { web, changed, errors } = await pushAll(this.env, devices);
    if (changed) await this.store.put('devices', devices);
    return { ok: true, seq: m.seq, android, web, errors };
  }

  // A new message: the chat's last line and time in the kept list (your computer pushes the list only when chats
  // change, not with every message).
  async chatTouch(sid, m) {
    const list = await this.store.get('chatSessions');
    const row = list?.sessions?.find((x) => x.id === sid);
    if (!row) return;
    row.updated = m.at;
    row.last = String(m.text || m.file?.name || '').replace(/\s+/g, ' ').slice(0, 120);
    await this.store.put('chatSessions', list);
  }

  // The list of chats and the commands ("/" in the composer), from your computer after each change: kept, and the
  // phones told (quiet: a read mark, only the ones connected straight here). A chat no longer listed loses what's
  // kept of it here.
  async chatSessionsPut(m) {
    const clean = (x) => ({
      id: String(x?.id || ''), title: String(x?.title || '').slice(0, 80), created: Number(x?.created) || 0, updated: Number(x?.updated) || 0,
      pinned: !!x?.pinned, last: String(x?.last || '').slice(0, 120), read: String(x?.read || '').slice(0, 16),
    });
    const sessions = (Array.isArray(m.sessions) ? m.sessions : []).map(clean).filter((x) => x.id === 'main' || SESSION_ID.test(x.id)).slice(0, SESSIONS_MAX);
    const commands = (Array.isArray(m.commands) ? m.commands : []).slice(0, 100).map((c) => ({ name: String(c?.name || '').slice(0, 32), help: String(c?.help || '').slice(0, 100) })).filter((c) => c.name);
    const switches = {};
    for (const [k, v] of Object.entries(m.switches || {})) if (/^chat_[a-z_]{1,30}$/.test(k)) switches[k] = !!v;
    const rev = Number(m.rev) || 0;
    await this.store.put('chatSessions', { rev, sessions, commands, switches });
    const live = new Set(sessions.map((x) => x.id)), idx = (await this.store.get('chatIdx')) || [];
    const gone = idx.filter((sid) => !live.has(sid));
    for (const sid of gone) { await this.store.delete(`chat:${sid}`); delete this.chatStatus[sid]; }
    if (gone.length) await this.store.put('chatIdx', idx.filter((sid) => live.has(sid)));
    const note = { title: 'stop', message: '', tags: ['stop', 'sessions'], kind: 'sessions', srev: rev, time: Math.floor(Date.now() / 1000) };
    if (new TextEncoder().encode(JSON.stringify(sessions)).length < 2000) note.sessions = sessions; // else: GET /chat?sessions=1
    if (m.quiet) await this.toLinked(note);
    else await this.toPhones(note).catch(() => false);
    return { ok: true, rev };
  }

  // "working" / "idle" for one chat: in memory here (GET /chat?sessions=1 shows it) and to the connected phones.
  async chatStatusPut(m) {
    const sid = SESSION_ID.test(String(m.session || '')) ? String(m.session) : 'main';
    const state = m.state === 'working' ? 'working' : 'idle', job = String(m.job || '').slice(0, 40);
    if (state === 'working') this.chatStatus[sid] = { state, job, t: Date.now() };
    else delete this.chatStatus[sid];
    await this.toLinked({ title: 'stop', message: '', tags: ['stop', 'status'], kind: 'status', session: sid, state, job });
    return { ok: true };
  }

  // To the Android phones connected straight to this line only: sealed as always, not kept for a phone that
  // reconnects, never through ntfy (no seq, so the phone's count of what it got stays as it was).
  async toLinked(fields) {
    if (!this.env.NTFY_KEY) return false;
    const sockets = this.state.getWebSockets('phone');
    if (!sockets.length) return false;
    const k1 = await sealK1(this.env.NTFY_KEY, JSON.stringify({ ...fields, mid: randomHex(8) }));
    for (const ws of sockets) { try { ws.send(JSON.stringify({ k1 })); } catch { /* gone */ } }
    return true;
  }

  // ------------------------------------------------------------------------------------ files for the chat
  // A file from your computer, sealed there, in parts (`size`: all of it, said with part 0); it can be fetched once
  // every part is here, for `hours`.
  async filePut(m) {
    const id = String(m.fid || ''), part = Number(m.part), parts = Number(m.parts); // m.id is the request's
    if (!FILE_ID.test(id) || !Number.isInteger(part) || !Number.isInteger(parts) || part < 0 || part >= parts) return { error: 'bad part' };
    const data = unb64(String(m.data || '').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''));
    const files = await this.filesLive();
    if (part === 0) {
      const size = Number(m.size) || 0;
      if (size > FILE_MAX || size < data.length) return { error: 'too big', note: 'Too big for your call line.' };
      const used = Object.values(files).reduce((n, f) => n + f.size, 0);
      if (used + size > FILES_BYTES) return { error: 'full', note: 'Your call line holds as many files as it can for now; try again tomorrow.' };
      files[id] = { parts, size, got: 0, bytes: 0, exp: Date.now() + Math.min(Math.max(Number(m.hours) || 24, 1), 48) * 3600e3 };
    }
    const f = files[id];
    if (!f || f.parts !== parts || f.got !== part) return { error: 'parts in order, from part 0' };
    if (data.length > FILE_PART || f.bytes + data.length > f.size) return { error: 'too big', note: 'Too big for your call line.' };
    await this.store.put(`f:${id}:${part}`, data);
    f.got += 1;
    f.bytes += data.length;
    await this.store.put('files', files);
    return { ok: true, part, ready: f.got >= f.parts };
  }

  // The files still in date; the parts of those that aren't go.
  async filesLive() {
    const files = (await this.store.get('files')) || {};
    const now = Date.now();
    let gone = false;
    for (const [id, f] of Object.entries(files)) {
      if (f.exp > now) continue;
      for (let i = 0; i < f.parts; i++) await this.store.delete(`f:${id}:${i}`);
      delete files[id];
      gone = true;
    }
    if (gone) await this.store.put('files', files);
    return files;
  }

  async fileGet(id) {
    const f = FILE_ID.test(id) ? (await this.filesLive())[id] : null;
    if (!f || f.got < f.parts || f.bytes !== f.size) return json({ error: 'gone', note: 'This file is gone: links to files work for a day. Ask for it again.' }, 404);
    const out = new Uint8Array(f.bytes);
    let at = 0;
    for (let i = 0; i < f.parts; i++) {
      const b = await this.store.get(`f:${id}:${i}`);
      if (!b) return json({ error: 'gone' }, 404);
      out.set(b, at);
      at += b.length;
    }
    return new Response(out, { headers: { 'content-type': 'application/octet-stream', 'cache-control': 'no-store', ...CORS } });
  }

  // ----------------------------------------------------------------------------------- the Today screen
  // Your computer's newest batch replaces the last (an older one never replaces a newer): one sealed copy per Android
  // phone, kept under its own key; phones no longer in it lose theirs. changed: the list itself changed, so the
  // phones are nudged to fetch it ("stop" too, so an older app ignores it). off: calls.today was turned off.
  async todayPut(m) {
    const cur = (await this.store.get('today')) || { rev: 0, devs: [] };
    const rev = Number(m.rev) || 0;
    if (rev < cur.rev) return { ok: false, stale: true };
    const devices = (await this.store.get('devices')) || {};
    const devs = [];
    for (const [dev, tok] of Object.entries(m.seal && typeof m.seal === 'object' ? m.seal : {})) {
      if (devices[dev]?.kind !== 'android' || !TODAY_TOKEN.test(String(tok)) || devs.length >= MAX_DEVICES) continue;
      await this.store.put(`today:${dev}`, String(tok));
      devs.push(dev);
    }
    for (const dev of cur.devs || []) if (!devs.includes(dev)) await this.store.delete(`today:${dev}`);
    await this.store.put('today', { rev, devs, at: new Date().toISOString(), off: !!m.off });
    if ((m.changed || m.off) && Object.values(devices).some((d) => d.kind === 'android')) {
      await this.toPhones({ title: 'stop', message: '', tags: ['stop', 'today'], time: Math.floor(Date.now() / 1000) }).catch(() => false);
    }
    return { ok: true, held: devs.length };
  }

  // ------------------------------------------------------------------------------------- the phone's views
  // Systems or the Notes map from your computer, sealed there (v1), in parts in order from part 0 (which brings `size`
  // and `keys`: the snapshot's key sealed for each Android phone). A newer rev replaces the one being received; when
  // every part is here it replaces the kept one, whose parts go. Stored: `views` {off, notes, systems: {rev, parts,
  // size, keys, at}, pend: {<kind>: the one coming in, with got and bytes}}, each part under `v:<kind>:<rev>:<n>`.
  // off: calls.views was turned off: every copy goes.
  async viewPut(m) {
    if (m.off) {
      await this.viewsDrop();
      await this.store.put('views', { off: true });
      return { ok: true, off: true };
    }
    const kind = String(m.view || ''), rev = Number(m.rev) || 0, part = Number(m.part), parts = Number(m.parts);
    if (!VIEW_KINDS.includes(kind) || !Number.isInteger(part) || !Number.isInteger(parts) || parts < 1 || parts > VIEW_PARTS || part < 0 || part >= parts) return { error: 'bad part' };
    const data = unb64(String(m.data || '').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''));
    if (data.length > VIEW_PART) return { error: 'too big', note: 'A part is too big for your call line.' };
    const views = (await this.store.get('views')) || {};
    views.pend = views.pend || {};
    if (part === 0) {
      if (views[kind] && rev <= views[kind].rev) return { ok: false, stale: true };
      const size = Number(m.size) || 0;
      if (size < data.length || size > VIEW_PART * parts) return { error: 'bad size' };
      if (views.pend[kind]) await this.viewParts(kind, views.pend[kind], true);
      const devices = (await this.store.get('devices')) || {}, keys = {};
      for (const [dev, tok] of Object.entries(m.keys && typeof m.keys === 'object' ? m.keys : {})) {
        if (devices[dev]?.kind !== 'android' || !VIEW_KEY.test(String(tok)) || Object.keys(keys).length >= MAX_DEVICES) continue;
        keys[dev] = String(tok);
      }
      views.pend[kind] = { rev, parts, size, keys, got: 0, bytes: 0 };
    }
    const p = views.pend[kind];
    if (!p || p.rev !== rev || p.parts !== parts || p.got !== part) return { error: 'parts in order, from part 0' };
    if (p.bytes + data.length > p.size) return { error: 'too big', note: 'Bigger than it said.' };
    await this.store.put(`v:${kind}:${rev}:${part}`, data);
    p.got += 1;
    p.bytes += data.length;
    let ready = false;
    if (p.got === p.parts) {
      if (p.bytes !== p.size) { await this.viewParts(kind, p, true); delete views.pend[kind]; await this.store.put('views', views); return { error: 'short', note: 'Some of it went missing.' }; }
      if (views[kind]) await this.viewParts(kind, views[kind]);
      views[kind] = { rev, parts, size: p.size, keys: p.keys, at: new Date().toISOString() };
      delete views.pend[kind];
      views.off = false;
      ready = true;
    }
    await this.store.put('views', views);
    return { ok: true, part, ready, held: ready ? Object.keys(views[kind].keys).length : undefined };
  }

  // delete a view's parts (all of them, or for one still coming in only those that came)
  async viewParts(kind, v, partial = false) {
    const n = partial ? v.got || 0 : v.parts;
    for (let i = 0; i < n; i++) await this.store.delete(`v:${kind}:${v.rev}:${i}`);
  }

  async viewsDrop() {
    const views = (await this.store.get('views')) || {};
    for (const k of VIEW_KINDS) {
      if (views[k]) await this.viewParts(k, views[k]);
      if (views.pend && views.pend[k]) await this.viewParts(k, views.pend[k], true);
    }
    await this.store.delete('views');
  }

  // a kept view's sealed bytes, base64url
  async viewData(kind, v) {
    const out = new Uint8Array(v.size);
    let at = 0;
    for (let i = 0; i < v.parts; i++) {
      const b = await this.store.get(`v:${kind}:${v.rev}:${i}`);
      if (!b) return null;
      out.set(b, at);
      at += b.length;
    }
    return b64url(out);
  }

  // ------------------------------------------------------------------------------------- Tell Kurooto
  // A paired phone makes (or remakes) its Shortcut link; an older one of that phone's stops working.
  async tellNew(req, who) {
    try { await req.arrayBuffer(); } catch { /* no body */ }
    const devices = (await this.store.get('devices')) || {};
    if (!devices[who.id]) return json({ error: 'unknown device' }, 403);
    const t = (await this.store.get('tells')) || {};
    for (const [k, v] of Object.entries(t)) if (v.device === who.id) delete t[k];
    const id = randomHex(4), secret = randomHex(16);
    t[id] = { hash: await sha256(secret), device: who.id, created: new Date().toISOString(), used: null };
    await this.store.put('tells', t);
    await this.event({ name: 'shortcut_made', id, device: who.id, device_name: devices[who.id].name });
    return json({ ok: true, id, token: `tk1.${id}.${secret}`, url: `${this.env.PUBLIC_URL}/tell/tk1.${id}.${secret}` });
  }

  // Drop the links that match; true if any did.
  async tellDrop(match) {
    const t = (await this.store.get('tells')) || {};
    let n = 0;
    for (const [id, v] of Object.entries(t)) if (match(v, id)) { delete t[id]; n++; }
    if (n) await this.store.put('tells', t);
    return n > 0;
  }

  // What the Shortcut sends: {"text"} as JSON, a form or plain text. It goes on exactly like a chat message typed on
  // the phone the link belongs to (now, or kept in the outbox); the answer is plain text for the Shortcut to speak.
  async tellSend(req, token) {
    const text = (s, status = 200) => new Response(s, { status, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
    const raw = req.method === 'POST' ? await req.text().catch(() => '') : '';
    const m = TELL_TOKEN.exec(String(token || ''));
    const t = (await this.store.get('tells')) || {};
    const it = m && t[m[1]];
    const devices = (await this.store.get('devices')) || {};
    if (!it || !same(it.hash, await sha256(m[2])) || !devices[it.device]) return text('This Tell Kurooto link was revoked or is wrong. Make a new one in the Kurooto app on your iPhone (Settings).', 401);
    if (req.method !== 'POST') return text('This is your Tell Kurooto link. Use it in the Shortcut (method POST); see the Kurooto app\'s Settings.', 405);
    if (raw.length > 16000) return text('That was too long.', 413);
    let said = '';
    const ctype = req.headers.get('content-type') || '';
    try {
      if (ctype.includes('json')) said = JSON.parse(raw || '{}').text;
      else if (ctype.includes('form')) said = new URLSearchParams(raw).get('text');
      else said = raw;
    } catch { said = ''; }
    said = String(said || '').trim().slice(0, TELL_TEXT);
    if (!said) return text('I heard nothing to send.', 400);
    t[m[1]].used = new Date().toISOString();
    await this.store.put('tells', t);
    const id = randomHex(8);
    const body = { device: it.device, at: Date.now(), id, ts: Date.now(), n: randomHex(16), text: said, via: 'shortcut' };
    if (this.online() && !(await this.outboxBusy())) {
      const r = await this.relay('POST', '/chat', JSON.stringify(body));
      if (r.status !== 503) {
        let j = {};
        try { j = JSON.parse(r.body || '{}'); } catch { /* not JSON */ }
        const out = (j.said || []).map((x) => String(x.text || '')).filter(Boolean).join('\n\n');
        return text(out || j.note || j.error || (r.status < 300 ? 'Sent.' : 'That did not go through.'), r.status < 300 ? 200 : r.status);
      }
    }
    if (!(await this.outboxPut('chat', { id: it.device }, id, body))) return text(OUTBOX_FULL, 507);
    return text(((await this.store.get('texts')) || {}).chat_queued || 'Your computer is off: this waits on your call line and goes to it when it is back.');
  }

  // ------------------------------------------------------------------------------------- the phone outbox
  async outboxBusy() {
    return ((await this.store.get('queue')) || []).some((x) => PHONE_KINDS.includes(x.kind));
  }

  // Keep a phone's request for the computer. False when the outbox is full (OUTBOX_MAX things; OUTBOX_BYTES of
  // files, checked for a whole file when its first part comes: need).
  async outboxPut(kind, who, oid, body, { bytes = 0, need = 0, ...extra } = {}) {
    const mine = ((await this.store.get('queue')) || []).filter((x) => PHONE_KINDS.includes(x.kind));
    const used = mine.reduce((n, x) => n + (x.bytes || 0), 0);
    const things = new Set(mine.map((x) => x.oid));
    if (!things.has(oid) && things.size >= OUTBOX_MAX) return false;
    if (used + Math.max(need, bytes) > OUTBOX_BYTES + (need ? 0 : OUTBOX_BYTES)) return false; // a file's later parts were counted with its first
    await this.queue({ kind, device: who.id, oid, ...(bytes ? { bytes } : {}), ...extra }, body);
    return true;
  }

  // What this phone sent that still waits for the computer, and what went through in the last day.
  async outboxFor(device) {
    const q = (await this.store.get('queue')) || [];
    const waiting = [], seen = new Set();
    for (const x of q) {
      if (x.device !== device || !x.oid || seen.has(x.oid)) continue;
      seen.add(x.oid);
      waiting.push({ oid: x.oid, kind: x.kind, at: x.at });
    }
    const done = ((await this.store.get('odone')) || []).filter((d) => d.device === device).map(({ device: _, ...d }) => d);
    return { waiting, done, computer: this.online() ? 'online' : 'offline' };
  }

  // The computer takes what waited, oldest first: `done` is the item it just finished (dropped here, and the phone
  // that sent it is told); the answer is the next one, with its body.
  async outbox(done) {
    const q = await this.queueList();
    if (done && Number.isFinite(Number(done.seq))) {
      const i = q.findIndex((x) => x.seq === Number(done.seq));
      if (i >= 0) {
        const [it] = q.splice(i, 1);
        await this.store.put('queue', q);
        if (it.bkey) await this.store.delete(it.bkey);
        if (it.device && it.oid && (it.kind !== 'upload' || it.last)) await this.outboxDone(it, done);
      }
    }
    const next = q[0];
    if (!next) return { item: null };
    const { bkey, ...item } = next;
    if (bkey) item[next.kind === 'upload' ? 'body_b64' : 'body'] = await this.store.get(bkey);
    return { item, left: q.length };
  }

  async outboxDone(it, done) {
    const status = Number(done.status) || 0;
    const d = { oid: it.oid, kind: it.kind, ok: status >= 200 && status < 300, note: String(done.note || '').slice(0, 300), t: Date.now() };
    const all = ((await this.store.get('odone')) || []).filter((x) => x.t > Date.now() - DONE_KEEP_MS && x.oid !== it.oid);
    await this.store.put('odone', all.concat([{ ...d, device: it.device }]).slice(-100));
    const devices = (await this.store.get('devices')) || {};
    if (devices[it.device]?.kind === 'android') { // "stop" too, so an older app ignores it
      await this.toPhones({ title: 'stop', message: '', tags: ['stop', 'outbox'], dev: it.device, done: [d], time: Math.floor(Date.now() / 1000) }).catch(() => false);
    }
  }

  // ------------------------------------------------------------------------------------- going offline
  // Your computer's settings for this (pushed with its state): on, after_min, channels, hush ([from ms, to ms]: night
  // and focus, when nothing is said), text, why, back_at (when it last said it's back), tg (token and chat, or none).
  async setPresence(p) {
    const { tg, ...cfg } = p && typeof p === 'object' ? p : {};
    if (tg && tg.token && tg.chat) await this.store.put('tg', { token: String(tg.token), chat: String(tg.chat) });
    else await this.store.delete('tg');
    await this.store.put('presence', cfg);
    const away = await this.store.get('away');
    if (away && (!cfg.on || (Number(cfg.back_at) || 0) > away.since)) await this.store.delete('away'); // it said it's back
  }

  // Say it on the channels you chose (or only some of them). Returns the ones it reached.
  async sayAway(cfg, away, only = null) {
    const text = String(away.text || cfg.text || 'Kurooto has been offline since %%SINCE%% (%%WHY%%).')
      .replace('%%SINCE%%', clockTime(away.since, this.env.TZ || 'UTC'))
      .replace('%%WHY%%', away.why || cfg.why || 'asleep, off or without internet');
    const chans = (cfg.channels || []).filter((c) => !only || only.includes(c));
    const sent = [];
    if (chans.includes('telegram') && await sendTelegram(this.env, await this.store.get('tg'), text).catch(() => false)) sent.push('telegram');
    if (chans.includes('app')) {
      const s = Math.floor(Date.now() / 1000);
      const names = (await this.store.get('names')) || {};
      const r = await this.notify({ id: randomHex(8), kind: 'info', title: names.assistant || 'Kurooto', text, at: s, until: s + 12 * 3600 }, 0).catch(() => null);
      if (r && (r.android || r.web)) sent.push('app');
    }
    return sent;
  }

  // Your computer is stopping on purpose: it says so itself on what it can (told), this says it on the rest. At night
  // (hush) nothing now: the cron says it in the morning if the computer isn't back. An update's restart: nothing.
  async bye(m) {
    const cfg = (await this.store.get('presence')) || {};
    const now = Date.now();
    await this.store.put('seen', now);
    const away = { since: now, told: 0, why: String(m.why || '').slice(0, 80), text: String(m.later || '').slice(0, 600), channels: [] };
    let sent = [];
    if (!m.restart && cfg.on) {
      const told = (m.told || []).map(String);
      const rest = (cfg.channels || []).filter((c) => !told.includes(c));
      if (!m.hush && rest.length) sent = await this.sayAway(cfg, { ...away, text: String(m.text || '').slice(0, 600) }, rest);
      if (told.length || sent.length) Object.assign(away, { told: now, channels: [...told, ...sent] });
    }
    await this.store.put('away', away);
    return { ok: true, sent };
  }

  // Every minute: if the computer has been gone for after_min (and it isn't night), say so, once per time away.
  async presenceTick() {
    try {
      const cfg = (await this.store.get('presence')) || {};
      if (!cfg.on) return null;
      const now = Date.now();
      if (this.online()) { await this.store.put('seen', now); return null; }
      let away = await this.store.get('away');
      if (!away) {
        const seen = Math.max((await this.store.get('seen')) || 0, this.lastSeen());
        if (!seen) return null;
        away = { since: seen, told: 0, why: '', text: '', channels: [] };
        await this.store.put('away', away);
      }
      if (away.told || now - away.since < Math.max(0, Number(cfg.after_min ?? 10)) * 60e3) return null;
      if ((cfg.hush || []).some(([a, b]) => a <= now && now < b)) return null;
      away.channels = await this.sayAway(cfg, away);
      away.told = now;
      await this.store.put('away', away);
      return { told: away.channels };
    } catch (e) {
      return { error: String(e?.message || e).slice(0, 200) };
    }
  }

  // --------------------------------------------------------------------------- reminders with the lid shut
  // The box ('sealed'): what your computer handed over for the next day, each {id, at, until (s), seal: {device id:
  // s1 token}}. The answers ('sealdone'), one per id: {by: 'computer'} (your computer was awake and said it, or will),
  // or {by: 'line', ok} (this line sent it; while a send is under way or failed it has busy and tries). Every change
  // to them is read, changed and written with no other request in between (nothing else is awaited meanwhile).
  async sealedDone() {
    const done = (await this.store.get('sealdone')) || {};
    const cut = Date.now() - SEALED_KEEP_MS;
    for (const [k, v] of Object.entries(done)) if (!v || !(v.t > cut)) delete done[k];
    return done;
  }

  // Your computer's batch replaces the box (an older one never replaces a newer). Items already answered stay out.
  async sealedPut(items, rev) {
    const cur = (await this.store.get('sealed')) || { rev: 0, items: [] };
    if (rev < cur.rev) return { ok: false, stale: true };
    const done = await this.sealedDone();
    const keep = [], told = {};
    for (const it of items.slice(0, SEALED_MAX)) {
      if (!it || !ITEM_ID.test(String(it.id)) || !Number.isFinite(it.at) || !Number.isFinite(it.until)) continue;
      const d = done[it.id];
      if (d && (d.by === 'computer' || d.ok)) { told[it.id] = d.by; continue; }
      const seal = {};
      for (const [dev, tok] of Object.entries(it.seal || {})) if (/^[0-9a-f]{8}$/.test(dev) && SEAL_TOKEN.test(String(tok))) seal[dev] = String(tok);
      if (Object.keys(seal).length) keep.push({ id: String(it.id), at: Math.floor(it.at), until: Math.floor(it.until), seal });
    }
    while (keep.length && JSON.stringify(keep).length > 120000) keep.pop(); // one stored value; the latest go first
    await this.store.put('sealed', { rev, items: keep });
    await this.store.put('sealdone', done);
    return { ok: true, held: keep.length, done: told };
  }

  // Your computer is awake at these items' time: it says them, unless this line already has (or is sending them).
  async sealedClaim(ids) {
    const done = await this.sealedDone();
    const now = Date.now(), out = {};
    for (const id of ids.slice(0, 100)) {
      if (!ITEM_ID.test(id)) continue;
      const d = done[id];
      if (d && d.by === 'line' && (d.ok || now - (d.busy || 0) < SEALED_BUSY_MS)) { out[id] = 'line'; continue; }
      if (!d || d.by !== 'computer') done[id] = { by: 'computer', t: now }; // a send that failed: it's your computer's now
      out[id] = 'computer';
    }
    await this.store.put('sealdone', done);
    const box = (await this.store.get('sealed')) || { rev: 0, items: [] };
    const left = box.items.filter((it) => out[it.id] !== 'computer');
    if (left.length !== box.items.length) await this.store.put('sealed', { ...box, items: left });
    return { ids: out };
  }

  // Every minute, while your computer is offline: send what's due and not yet answered to the phones it was sealed
  // for. Marked as this line's before it goes out, so a claim meanwhile hears "line"; told to your computer after.
  async sealedTick() {
    if (this.online()) return null;
    const box = (await this.store.get('sealed')) || { rev: 0, items: [] };
    if (!box.items.length) return null;
    const s = Math.floor(Date.now() / 1000);
    const devices = (await this.store.get('devices')) || {};
    const sent = [];
    for (const it of box.items) {
      if (it.at > s || s >= it.until) continue;
      const done = await this.sealedDone();
      const d = done[it.id];
      if (d && (d.by !== 'line' || d.ok || Date.now() - (d.busy || 0) < SEALED_BUSY_MS || (d.tries || 0) >= SEALED_TRIES)) continue;
      const tries = (d?.tries || 0) + 1;
      done[it.id] = { by: 'line', t: Date.now(), ok: false, busy: Date.now(), tries };
      await this.store.put('sealdone', done);
      let ok = false;
      for (const [dev, sealed] of Object.entries(it.seal)) {
        if (devices[dev]?.kind !== 'android') continue; // unpaired since
        ok = (await this.toPhones({ title: 'sealed', message: '', tags: ['stop', 'sealed'], id: it.id, dev, sealed, time: s }).catch(() => false)) || ok;
      }
      const after = await this.sealedDone();
      const failed = !ok && tries >= SEALED_TRIES;
      after[it.id] = ok ? { by: 'line', t: Date.now(), ok: true } : failed ? { by: 'computer', t: Date.now(), failed: true } : { by: 'line', t: Date.now(), ok: false, busy: 0, tries };
      await this.store.put('sealdone', after);
      if (ok || failed) await this.queue({ kind: 'event', name: ok ? 'sealed_sent' : 'sealed_failed', id: it.id, at: it.at });
      if (ok) sent.push(it.id);
    }
    const done = await this.sealedDone();
    const now = await this.store.get('sealed');
    if (now) {
      const left = now.items.filter((it) => s < it.until && !(done[it.id] && (done[it.id].ok || done[it.id].by === 'computer')));
      if (left.length !== now.items.length) await this.store.put('sealed', { ...now, items: left });
    }
    return { sent };
  }

  // Every minute (cron): place the calls that fall due while the computer is off, from the schedule it pushed.
  async tick() {
    await this.filesLive(); // files for the chat whose day is up go
    const presence = await this.presenceTick();
    const sealed = await this.sealedTick().catch((e) => ({ error: String(e?.message || e).slice(0, 200) }));
    if (this.online()) return { skipped: 'computer online' };
    const now = Math.floor(Date.now() / 1000);
    const sched = (await this.store.get('schedule')) || [];
    const fired = (await this.store.get('fired')) || {};
    const held = (await this.store.get('held')) || {}; // calls that came due while you were on a call
    const onCall = Date.now() - ((await this.store.get('oncall')) || 0) < ON_CALL_MS;
    const placed = [];
    for (const it of sched) {
      const key = `${it.at}:${it.key || ''}`;
      if (fired[key] || it.at > now || (it.at < now - 180 && !(held[key] && it.at > now - 7200))) continue;
      if (onCall && !it.alarm) { held[key] = now; continue; } // it rings when the call ends
      fired[key] = now;
      await this.ring({ reason: it.reason, alarm: !!it.alarm, since: String(it.at), key: it.key || '', voice: it.voice || '' });
      await this.queue({ kind: 'event', name: 'rang_offline', key: it.key || '', at: it.at, reason: String(it.reason || '').slice(0, 200) });
      placed.push(key);
    }
    for (const [k, t] of Object.entries(fired)) if (t < now - 86400) delete fired[k];
    for (const [k, t] of Object.entries(held)) if (fired[k] || t < now - 7200) delete held[k];
    await this.store.put('fired', fired);
    await this.store.put('held', held);
    return { placed, presence, sealed };
  }
}

function manifest(url, env) {
  const code = (url.searchParams.get('c') || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 16);
  return new Response(JSON.stringify({
    name: 'Kurooto', short_name: 'Kurooto', display: 'standalone', background_color: '#0b0f0a', theme_color: '#0b0f0a',
    start_url: code ? `/pair?c=${code}` : '/', scope: '/',
    icons: [{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' }, { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }],
  }), { headers: { 'content-type': 'application/manifest+json', 'cache-control': 'no-store' } });
}

const line = (env) => env.LINE.get(env.LINE.idFromName(env.OWNER_ID || 'owner'));

export default {
  async scheduled(_event, env) {
    await line(env).fetch('https://line/tick');
  },

  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    if (url.pathname === '/health') return json({ ok: true, version: env.VERSION || '' });
    if (url.pathname === '/manifest.webmanifest') return manifest(url, env);
    if (url.pathname === '/tick') return json({ error: 'not found' }, 404); // the cron's door, not a public one
    return line(env).fetch(req);
  },
};
