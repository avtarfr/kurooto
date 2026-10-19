// The phone side of a call: mic → Gemini Live (direct, short-lived token) → speaker.
// Tool calls go to your call line (/tool), which passes them to your computer; finished background tasks and
// approval questions are polled from /tasks and spoken into the call. Bundled to public/app.js when deploying.
import { GoogleGenAI } from '@google/genai';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const purpose = params.get('p') || '';
const since = params.get('s') || '';
const store = { get: (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };
// The key: a call link's ticket (in the #fragment, never sent to the server as part of the URL), or this
// device's own key once it's paired (kept in this browser or app only).
let secret = location.hash.slice(1) || store.get('kurootoDevice');
history.replaceState(null, '', location.pathname + location.search);
const App = window.KurootoApp || null; // the Android app's bridge, when the page runs inside it
let me = 'You', ai = 'Kurooto';

if (purpose) { $('reason').textContent = purpose; $('call').textContent = 'Answer'; }
if (!secret) {
  status('This page needs a call link or a paired phone. Ask your bot for /call, or pair this phone from your computer.', 'err');
  $('call').disabled = true;
}

let session = null, model = '', config = null, handle = null, ending = false, retries = 0;
let startedOffline = false; // the call began while the computer was off
let live = false; // a call got through (its end is reported, even with nothing said)
let micStream, inCtx, outCtx, worklet, muted = false, wakeLock = null, pollTimer = null;
let playAt = 0; const playing = new Set();
let lineMe = null, lineAi = null;
const transcript = []; // [{who, text}] sent to your computer when the call ends (kept there, never synced)
function note(who, text) { const last = transcript[transcript.length - 1]; if (last && last.who === who) last.text += text; else transcript.push({ who, text }); }

function status(text, cls = '') { const s = $('status'); s.textContent = text; s.className = cls; }
function say(text, cls) { const d = document.createElement('div'); d.className = `m ${cls}`; d.textContent = text; $('log').append(d); d.scrollIntoView({ block: 'end' }); return d; }

async function api(pathname, payload) {
  let r;
  try {
    r = await fetch(pathname, {
      method: payload === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json', 'x-call-secret': secret },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
  } catch { throw new Error('the call line is unreachable right now (is this phone online?)'); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
  return r.json();
}

// ---------- audio ----------
const b64 = (buf) => { let s = ''; const u = new Uint8Array(buf); for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); };

async function startAudio() {
  if (!navigator.mediaDevices || !window.AudioWorkletNode) throw new Error('this browser is too old for calls (it needs microphone and audio worklet support)');
  micStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  inCtx = new AudioContext({ sampleRate: 16000 });
  outCtx = new AudioContext({ sampleRate: 24000 });
  await inCtx.audioWorklet.addModule('/worklet.js');
  worklet = new AudioWorkletNode(inCtx, 'pcm-capture');
  worklet.port.onmessage = (e) => {
    if (!session || muted) return;
    session.sendRealtimeInput({ audio: { data: b64(gate(e.data)), mimeType: 'audio/pcm;rate=16000' } });
  };
  inCtx.createMediaStreamSource(micStream).connect(worklet);
}

// Noise gate: learns the background level (fan, room) and sends digital silence until the frame is clearly
// louder, with a short hold so word endings aren't cut. While the assistant talks it needs a louder voice
// still, so its own voice coming back from the speaker doesn't interrupt it.
// sensitivity: 1 = default; higher = needs a louder voice (stored per phone).
let noiseFloor = 0.01, openUntil = 0, talkTail = 0, interruptUntil = 0, dropAudio = false;
const halfDuplex = () => !(App && App.isEarpiece && App.isEarpiece());
function interrupt() {
  stopPlayback();
  dropAudio = true; // ignore the rest of this answer until Gemini notices you're talking
  interruptUntil = performance.now() + 4000;
  openUntil = interruptUntil;
  $('int').hidden = true;
}
let sensitivity = Number(store.get('callGate')) || 1;
function gate(buf) {
  const pcm = new Int16Array(buf);
  let sum = 0;
  for (let i = 0; i < pcm.length; i++) { const v = pcm[i] / 0x8000; sum += v * v; }
  const rms = Math.sqrt(sum / pcm.length);
  const now = performance.now();
  const talking = playing.size > 0 || now < talkTail;
  // Half duplex on the loudspeaker: its own voice is louder than any gate, so the mic sends silence while the
  // assistant talks (Interrupt to cut in). In the Android app on the earpiece there's little echo: full duplex.
  if (talking && halfDuplex() && now > interruptUntil) { meter(rms, 1, false); return new Int16Array(pcm.length).buffer; }
  const threshold = Math.max(0.012, noiseFloor * 3.2) * sensitivity * (talking ? 2.5 : 1);
  if (rms > threshold) openUntil = now + 450;
  else noiseFloor = noiseFloor * 0.97 + Math.min(rms, noiseFloor * 2) * 0.03; // learn the quiet background
  meter(rms, threshold, now < openUntil);
  if (now < openUntil) return buf;
  return new Int16Array(pcm.length).buffer; // silence keeps Gemini's turn detection working
}
let lastMeter = 0;
function meter(rms, threshold, open) {
  const now = performance.now();
  if (now - lastMeter < 150) return;
  lastMeter = now;
  const el = $('level');
  el.style.width = `${Math.min(100, (rms / (threshold * 2)) * 100)}%`;
  el.style.background = open ? 'var(--ok)' : 'var(--dim)';
}
function setSensitivity(v) {
  sensitivity = v;
  store.set('callGate', String(v));
  $('gateval').textContent = v === 1 ? 'normal' : v > 1 ? `stricter ×${v}` : `looser ×${v}`;
}

function play(base64) {
  if (dropAudio) return;
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const pcm = new Int16Array(bytes.buffer, 0, bytes.byteLength >> 1);
  const buf = outCtx.createBuffer(1, pcm.length, 24000);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
  const src = outCtx.createBufferSource();
  src.buffer = buf; src.connect(outCtx.destination);
  playAt = Math.max(playAt, outCtx.currentTime + 0.03);
  src.start(playAt); playAt += buf.duration;
  playing.add(src);
  if (halfDuplex()) $('int').hidden = false;
  src.onended = () => { playing.delete(src); if (!playing.size) { talkTail = performance.now() + 500; $('int').hidden = true; } };
}
// Earpiece vs loudspeaker. A web page usually can't pick the earpiece; the Android app can (natively).
async function toggleOutput() {
  if (App) {
    const sp = App.toggleSpeaker();
    $('out').textContent = sp ? 'Earpiece' : 'Speaker';
    return status(sp ? 'Speaker' : 'Earpiece', 'live');
  }
  try {
    if (!outCtx || !outCtx.setSinkId) return status("This browser can't switch outputs. Use earphones for privacy.", 'err');
    if (outCtx.sinkId) { await outCtx.setSinkId(''); $('out').textContent = 'Earpiece'; return status('Speaker', 'live'); }
    let dev = null;
    if (navigator.mediaDevices.selectAudioOutput) { try { dev = await navigator.mediaDevices.selectAudioOutput(); } catch { /* cancelled */ } }
    const outs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audiooutput');
    dev = dev || outs.find((d) => /earpiece|receiver|handset|phone/i.test(d.label));
    if (!dev) return status('No earpiece offered by this browser. Use earphones.', 'err');
    await outCtx.setSinkId(dev.deviceId);
    $('out').textContent = 'Speaker'; status(`Playing on: ${dev.label || 'selected output'}`, 'live');
  } catch (e) { status(`Couldn't switch output: ${e.message}`, 'err'); }
}

function stopPlayback() { for (const s of playing) { try { s.stop(); } catch { /* done */ } } playing.clear(); playAt = 0; }

// ---------- session ----------
async function connect() {
  const t = await api('/token', { purpose: handle ? '' : purpose, since: handle ? '' : since });
  model = t.model; config = t.config;
  if (!handle) startedOffline = !!t.offline;
  const client = new GoogleGenAI({ apiKey: t.token, httpOptions: { apiVersion: 'v1alpha' } });
  session = await client.live.connect({
    model,
    config: { ...config, sessionResumption: handle ? { handle } : {} },
    callbacks: {
      onopen: () => { status(startedOffline ? 'Connected (your computer is off: some things wait for it)' : 'Connected', 'live'); retries = 0; },
      onmessage: onMessage,
      onerror: (e) => console.warn('live error', e),
      onclose: (e) => { session = null; if (!ending) reconnect(`closed ${(e && e.code) || ''} ${(e && e.reason) || ''}`.trim()); },
    },
  });
  if (purpose && !handle) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text: '[The call just connected. Speak first.]' }] }], turnComplete: true });
}

async function reconnect(why) {
  if (ending) return;
  if (retries++ >= 4) { status(`Call dropped (${why}). Tap Call to try again.`, 'err'); return hangup(false); }
  status('Reconnecting…');
  await new Promise((r) => setTimeout(r, 600 * retries));
  try { await connect(); } catch (e) { reconnect(e.message); }
}

function onMessage(m) {
  if (m.sessionResumptionUpdate && m.sessionResumptionUpdate.resumable && m.sessionResumptionUpdate.newHandle) handle = m.sessionResumptionUpdate.newHandle;
  if (m.goAway) { const s = session; session = null; if (s) s.close(); return; } // onclose → reconnect with the handle
  const sc = m.serverContent;
  if (sc) {
    if (sc.interrupted) { stopPlayback(); dropAudio = false; }
    if (sc.turnComplete || sc.generationComplete) dropAudio = false;
    for (const p of (sc.modelTurn && sc.modelTurn.parts) || []) if (p.inlineData && p.inlineData.data) play(p.inlineData.data);
    if (sc.inputTranscription && sc.inputTranscription.text) { lineAi = null; lineMe = lineMe || say('', 'me'); lineMe.textContent += sc.inputTranscription.text; note(me, sc.inputTranscription.text); }
    if (sc.outputTranscription && sc.outputTranscription.text) { lineMe = null; lineAi = lineAi || say('', 'ai'); lineAi.textContent += sc.outputTranscription.text; note(ai, sc.outputTranscription.text); }
    if (sc.turnComplete) { lineMe = null; lineAi = null; }
  }
  if (m.toolCall) for (const fc of m.toolCall.functionCalls || []) runTool(fc);
}

async function runTool(fc) {
  say(toolLabel(fc), 'sys');
  let result;
  try { result = (await api('/tool', { name: fc.name, args: fc.args || {} })).result; } catch (e) { result = `Tool failed: ${e.message}`; }
  if (session) session.sendToolResponse({ functionResponses: [{ id: fc.id, name: fc.name, response: { result, scheduling: 'WHEN_IDLE' } }] });
}
function toolLabel(fc) {
  const a = fc.args || {};
  return { search_notes: `searching notes: ${a.query || ''}`, read_note: `reading ${a.slug || 'a note'}`, run_task: 'started a task on your computer',
    schedule_call: `scheduling a call: ${a.when || ''}`, set_alarm: `setting the alarm: ${a.time || ''}` }[fc.name] || fc.name.replace(/_/g, ' ');
}

async function poll() {
  if (!session) return;
  try {
    const { finished, approvals, computer } = await api('/tasks');
    if (startedOffline && computer === 'online') {
      startedOffline = false;
      say('your computer is back online', 'sys');
      if (session) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text: '[The computer is back online: notes, tasks and everything else now work normally, and anything saved earlier is being done now. Say so briefly.]' }] }], turnComplete: true });
    }
    for (const t of finished || []) {
      say(`task ${t.status}`, 'sys');
      if (session) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text: `[Task finished] (${t.status}) Request: ${t.request}\nResult: ${t.result}` }] }], turnComplete: true });
    }
    for (const a of approvals || []) {
      if (session) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text: `[Approval needed] id=${a.id}: ${a.question} (answer with answer_approval)` }] }], turnComplete: true });
    }
  } catch { /* next round */ }
}

// ---------- buttons ----------
async function start() {
  ending = false; $('call').disabled = true; status('Connecting…');
  try {
    await startAudio();
    await connect();
    try { wakeLock = navigator.wakeLock ? await navigator.wakeLock.request('screen') : null; } catch { /* optional */ }
    pollTimer = setInterval(poll, 4000);
    live = true;
    $('call').textContent = 'Hang up'; $('call').className = 'end'; $('call').disabled = false; $('mute').hidden = false; $('out').hidden = false;
    if (App) { App.callStarted(); $('out').textContent = 'Speaker'; }
  } catch (e) {
    status(`Couldn't start: ${e.message}`, 'err');
    hangup(false);
  }
}

function hangup(user = true) {
  // always sent, even with nothing said: it also tells your computer the call is over ("on a call" ends)
  if (live || transcript.length) api('/transcript', { lines: transcript.splice(0), purpose, since, ended: true }).catch(() => {});
  ending = true;
  live = false;
  clearInterval(pollTimer);
  try { if (session) session.close(); } catch { /* closed */ }
  session = null; handle = null;
  stopPlayback();
  if (micStream) micStream.getTracks().forEach((t) => t.stop());
  if (inCtx) inCtx.close();
  if (outCtx) outCtx.close();
  if (wakeLock && wakeLock.release) wakeLock.release();
  wakeLock = null;
  $('call').textContent = 'Call'; $('call').className = ''; $('call').disabled = !secret; $('mute').hidden = true; $('out').hidden = true; $('int').hidden = true;
  if (user) status('Call ended');
  if (App) App.callEnded();
}

$('call').onclick = () => (session || $('call').className === 'end' ? hangup() : start());
$('out').onclick = toggleOutput;
$('int').onclick = interrupt;
$('gate').oninput = (e) => setSensitivity(Number(e.target.value));
$('gate').value = String(sensitivity); setSensitivity(sensitivity);
$('mute').onclick = () => { muted = !muted; $('mute').textContent = muted ? 'Unmute' : 'Mute'; };
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && session && !wakeLock && navigator.wakeLock) try { wakeLock = await navigator.wakeLock.request('screen'); } catch { /* optional */ }
});

// Who's who, and whether the computer is on (also checks the key early, so a bad link says so before you tap).
if (secret) {
  api('/status').then((s) => {
    if (s.assistant) { ai = s.assistant; $('who').textContent = s.assistant; document.title = s.assistant; }
    if (s.owner) me = s.owner;
    if (!purpose) status(s.computer === 'online' ? 'Ready' : 'Ready (your computer is off: calls still work, some things wait for it)');
  }).catch((e) => { status(`This link doesn't work: ${e.message}. Ask your bot for /call again.`, 'err'); $('call').disabled = true; });
}
if ('serviceWorker' in navigator && !App && store.get('kurootoDevice')) navigator.serviceWorker.register('/sw.js').catch(() => {});
// A paired phone (not a one-off call link): what's waiting for you (questions, approvals, messages).
if (!App && store.get('kurootoDevice') && secret === store.get('kurootoDevice')) {
  $('inbox').hidden = false;
  api('/pending').then((j) => { const n = (j.items || []).length; if (n) $('inbox').textContent = `Waiting for you (${n})`; }).catch(() => {});
}

// Opened from the Android app after you tapped Answer (or Call): start right away.
if (App && params.get('auto') === '1' && secret) start();
