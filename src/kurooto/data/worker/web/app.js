// The phone side of a call: mic → Gemini Live (direct, short-lived token) → speaker.
// Tool calls go to your call line (/tool), which passes them to your computer; finished background tasks and
// approval questions are polled from /tasks and spoken into the call. Bundled to public/app.js when deploying.
// When Live won't start, or drops and won't come back (web/fallback.js): Live again with the next model, then turn
// by turn with this phone's own speech recognition and voice, then the same call as text on Telegram.
import { GoogleGenAI } from '@google/genai';
import { BACKOFF_MS, MID_CALL_RETRIES, STARTUP_MS, START_TIMEOUT_MS, closeError, connectError, rotate, speechKind, spoken } from './fallback.js';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const purpose = params.get('p') || '';
const since = params.get('s') || '';
// How this call listens (calls.voice_mode): 'live' (Gemini Live), 'phone' (this phone's own speech, turn by turn) or
// 'auto' (Live, and this phone's speech when Live fails). A ring's link says; otherwise the call line's /status.
const MODES = ['live', 'phone', 'auto'];
let voiceMode = MODES.includes(params.get('v')) ? params.get('v') : '';
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

let session = null, handle = null, ending = false;
let startedOffline = false; // the call began while the computer was off
let live = false; // a call got through (its end is reported, even with nothing said)
// how the call is going: '' (not yet), 'live' (Gemini Live), 'turns' (turn by turn), 'text' (moved to Telegram)
let mode = '';
let models = [], curModel = '', attempt = 0, announced = false, liveAt = 0, heard = false, midRetries = 0, goingAway = false;
let callUp = false; // the Android app was told a call is on
let nonBlocking = true; // this session's tools don't wait (some Live models don't take that)
let micStream, inCtx, outCtx, worklet, muted = false, wakeLock = null, pollTimer = null;
let playAt = 0; const playing = new Set();
let lineMe = null, lineAi = null;
const transcript = []; // [{who, text}] sent to your computer when the call ends (kept there, never synced)
function note(who, text) { const last = transcript[transcript.length - 1]; if (last && last.who === who) last.text += text; else transcript.push({ who, text }); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
// The same, but a refusal comes back as {ok: false, status, body} (the token's answer says why Live refused).
async function post(pathname, payload) {
  let r;
  try {
    r = await fetch(pathname, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-call-secret': secret }, body: JSON.stringify(payload) });
  } catch { return { ok: false, status: 0, body: {}, unreachable: true }; }
  return { ok: r.ok, status: r.status, body: await r.json().catch(() => ({})) };
}
// What the call page saw, for your computer's count of Live failures (`kurooto doctor`). Never in the way.
function report(what, fields) { api('/call-report', { what, ...fields }).catch(() => {}); }

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

// ---------- session (Gemini Live) ----------
// One try at a Live session: a token for `model` from the call line, then the socket. Resolves {ok: true} once Google
// has set the session up; otherwise {ok: false, retry, badModel, line, text} (line: the call line itself said no).
async function tryLive(want, n, resume = false) {
  if (!resume) attempt = n;
  const r = await post('/token', resume ? { resume: true, model: want } : { purpose, since, model: want, announce: !announced });
  if (Array.isArray(r.body.models) && r.body.models.length) models = r.body.models;
  if (r.unreachable) return { ok: false, line: true, text: 'the call line is unreachable right now (is this phone online?)' };
  if (!r.ok) {
    if (!r.body.live) return { ok: false, line: true, text: r.body.error || `HTTP ${r.status}` };
    return { ok: false, retry: !!r.body.retry, badModel: !!r.body.bad_model, code: r.body.code, model: r.body.model, text: r.body.error };
  }
  if (!resume) { announced = true; if (!session) startedOffline = !!r.body.offline; }
  try {
    await openSession(r.body, resume);
  } catch (e) {
    const c = (e && e.live) || connectError(e);
    report('failed', { model: r.body.model, code: c.code, stage: 'connect' });
    return { ok: false, ...c, model: r.body.model };
  }
  curModel = r.body.model;
  return { ok: true, model: r.body.model };
}

// The socket. The SDK's connect only resolves once Google has set the session up, and never if it closes first
// (how a 503 arrives), so a close or START_TIMEOUT_MS without setup counts as a failed start.
function openSession(t, resume) {
  return new Promise((resolve, reject) => {
    let done = false, s = null;
    const finish = (ok, v) => { if (done) return false; done = true; clearTimeout(timer); (ok ? resolve : reject)(v); return true; };
    const timer = setTimeout(() => finish(false, { live: { retry: true, code: 0, text: 'the voice service did not answer in time' } }), START_TIMEOUT_MS);
    const client = new GoogleGenAI({ apiKey: t.token, httpOptions: { apiVersion: 'v1alpha' } });
    client.live.connect({
      model: t.model,
      config: { ...t.config, sessionResumption: resume && handle ? { handle } : {} },
      callbacks: {
        onopen: () => {},
        onmessage: (m) => { if (s && s === session) onMessage(m); },
        onerror: (e) => console.warn('live error', e),
        onclose: (e) => {
          const c = closeError(e && e.code, e && e.reason);
          if (!finish(false, { live: c }) && s && s === session) onLiveClose(c);
        },
      },
    }).then((x) => {
      if (!finish(true, x)) { try { x.close(); } catch { /* closed */ } return; } // too late: it timed out meanwhile
      s = x; session = x; liveAt = performance.now(); heard = false;
      nonBlocking = ((t.config.tools || [])[0] || { functionDeclarations: [] }).functionDeclarations.some((d) => d.behavior === 'NON_BLOCKING');
      liveUp(resume);
    }).catch((e) => finish(false, { live: connectError(e) }));
  });
}

function liveUp(resumed) {
  status(startedOffline ? 'Connected (your computer is off: some things wait for it)' : 'Connected', 'live');
  if (purpose && !resumed) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text: '[The call just connected. Speak first.]' }] }], turnComplete: true });
  callIsOn();
}

function retrying() { status('Reconnecting…'); say('reconnecting…', 'sys'); }

// The Live part of a call: a start that fails is tried again (BACKOFF_MS, the next model each time); when it can't,
// the call goes on turn by turn, or on Telegram.
async function startLive(from = 0, why = '') {
  const r = from < BACKOFF_MS.length ? await rotate(tryLive, { models: () => models, from, sleep, onRetry: retrying }) : { ok: false, text: why };
  if (ending || mode !== 'live') return;
  if (r.ok) { if (r.attempt > 0) report('recovered', { model: r.model, attempt: r.attempt + 1 }); return; }
  if (r.line) { status(`Couldn't start: ${r.text}`, 'err'); return hangup(false); }
  fallBack('live', r.text);
}

// A session that closed. Going away (its time is up) resumes; closing before anything was said means it never really
// started (the next model is tried); a drop mid-call is tried again once, then the call goes on turn by turn.
function onLiveClose(c) {
  session = null;
  if (ending || mode !== 'live') return;
  if (goingAway) { goingAway = false; return reopen('', false); }
  const early = !heard && performance.now() - liveAt < STARTUP_MS;
  report('failed', { model: curModel, code: c.code, stage: early ? 'start' : 'call' });
  if (early) return startLive(attempt + 1, c.text);
  reopen(c.text, true);
}

async function reopen(why, isError) {
  if (isError && midRetries >= MID_CALL_RETRIES) return fallBack('live', why);
  if (isError) midRetries++;
  retrying();
  if (isError) await sleep(BACKOFF_MS[1]);
  if (ending || mode !== 'live') return;
  const r = await tryLive(curModel, attempt, true);
  if (ending || mode !== 'live' || r.ok) return;
  if (r.line) { status(`Call dropped (${r.text}). Tap Call to try again.`, 'err'); return hangup(false); }
  if (midRetries < MID_CALL_RETRIES) return reopen(r.text, true); // a resume that failed counts as the drop's retry
  fallBack('live', r.text);
}

function closeLive() {
  const s = session;
  session = null; handle = null;
  try { if (s) s.close(); } catch { /* closed */ }
  stopPlayback();
  if (micStream) micStream.getTracks().forEach((t) => t.stop());
  micStream = null;
  try { if (inCtx) inCtx.close(); } catch { /* closed */ }
  inCtx = null;
  $('int').hidden = true; $('gatebox').hidden = true;
}

function onMessage(m) {
  if (m.sessionResumptionUpdate && m.sessionResumptionUpdate.resumable && m.sessionResumptionUpdate.newHandle) handle = m.sessionResumptionUpdate.newHandle;
  if (m.goAway) { goingAway = true; if (session) session.close(); return; } // its time is up: onclose resumes with the handle
  const sc = m.serverContent;
  if (sc || m.toolCall) heard = true;
  if (sc) {
    if (sc.interrupted) { stopPlayback(); dropAudio = false; }
    if (sc.turnComplete || sc.generationComplete) dropAudio = false;
    if (sc.turnComplete) midRetries = 0; // it works again: a later drop gets its own retry
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
  if (session) session.sendToolResponse({ functionResponses: [{ id: fc.id, name: fc.name, response: nonBlocking ? { result, scheduling: 'WHEN_IDLE' } : { result } }] });
}
function toolLabel(fc) {
  const a = fc.args || {};
  return { search_notes: `searching notes: ${a.query || ''}`, read_note: `reading ${a.slug || 'a note'}`, run_task: 'started a task on your computer',
    schedule_call: `scheduling a call: ${a.when || ''}`, set_alarm: `setting the alarm: ${a.time || ''}` }[fc.name] || fc.name.replace(/_/g, ' ');
}

// Something for the AI to hear (a finished task, an approval, the computer coming back): into the Live session, or
// the next turn of a turn-by-turn call.
function tell(text) {
  if (mode === 'live' && session) session.sendClientContent({ turns: [{ role: 'user', parts: [{ text }] }], turnComplete: true });
  else if (mode === 'turns') { system.push(text); wake(); }
}

async function poll() {
  if (!session && mode !== 'turns') return;
  try {
    const { finished, approvals, computer } = await api('/tasks');
    if (startedOffline && computer === 'online') {
      startedOffline = false;
      say('your computer is back online', 'sys');
      tell('[The computer is back online: notes, tasks and everything else now work normally, and anything saved earlier is being done now. Say so briefly.]');
    }
    for (const t of finished || []) {
      say(`task ${t.status}`, 'sys');
      tell(`[Task finished] (${t.status}) Request: ${t.request}\nResult: ${t.result}`);
    }
    for (const a of approvals || []) tell(`[Approval needed] id=${a.id}: ${a.question} (answer with answer_approval)`);
  } catch { /* next round */ }
}

// ---------- turn by turn: this phone's own speech recognition and voice ----------
let speech = null; // {listen, stop, speak, hush}
const said = []; // [{role, text}] for the text AI: what was said, and notes like "[Task finished]"
const system = []; // notes waiting for the next turn
let wake = () => {}, tapped = null, listened = false; // listened: this phone's recognizer has worked

// The Android app's recognizer and voice, through its bridge; it calls back on window.kurootoSpeech.
function appSpeech() {
  let heardCb = null, spokenCb = {}, n = 0;
  window.kurootoSpeech = {
    partial: (t) => { const l = $('heard'); l.hidden = false; l.textContent = t; },
    heard: (t) => { const f = heardCb; heardCb = null; if (f) f.ok(t || ''); },
    failed: (code) => { const f = heardCb; heardCb = null; if (f) (['no-speech', 'no-match', 'stopped'].includes(code) ? f.ok('') : f.err(code)); },
    spoken: (id) => { const f = spokenCb[id]; delete spokenCb[id]; if (f) f(); },
  };
  if (App.prepareSpeech) App.prepareSpeech();
  return {
    listen: () => new Promise((ok, err) => { heardCb = { ok, err }; App.listen(navigator.language || ''); }),
    stop: () => { if (App.stopListening) App.stopListening(); },
    speak: (text) => new Promise((done) => { const id = String(++n); spokenCb[id] = done; App.speak(text, id); setTimeout(() => { if (spokenCb[id]) { delete spokenCb[id]; done(); } }, 2000 + text.length * 120); }),
    hush: () => { if (App.stopSpeaking) App.stopSpeaking(); for (const k of Object.keys(spokenCb)) { const f = spokenCb[k]; delete spokenCb[k]; f(); } },
  };
}

// The browser's Web Speech API (Chrome; Safari asks to allow dictation). Without speechSynthesis, answers are shown.
function webSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null;
  return {
    listen: () => new Promise((ok, err) => {
      rec = new SR();
      rec.lang = navigator.language || 'en-US'; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
      let final = '', failed = '';
      rec.onresult = (e) => {
        let part = '';
        for (let i = e.resultIndex; i < e.results.length; i++) { if (e.results[i].isFinal) final += e.results[i][0].transcript; else part += e.results[i][0].transcript; }
        const l = $('heard'); l.hidden = false; l.textContent = final + part;
      };
      rec.onerror = (e) => { failed = e.error || 'error'; };
      rec.onend = () => { rec = null; if (failed && !['no-speech', 'aborted'].includes(failed)) err(failed); else ok(final.trim()); };
      try { rec.start(); } catch (e) { err('busy'); }
    }),
    stop: () => { try { if (rec) rec.stop(); } catch { /* ended */ } },
    speak: (text) => new Promise((done) => {
      if (!window.speechSynthesis) return done();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = navigator.language || 'en-US';
      u.onend = done; u.onerror = done;
      setTimeout(done, 3000 + text.length * 120); // some browsers never say they're done with a long answer
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    }),
    hush: () => { try { if (window.speechSynthesis) speechSynthesis.cancel(); } catch { /* none */ } },
  };
}

function talkButton(state) {
  const b = $('talk');
  b.hidden = false;
  b.dataset.state = state;
  b.textContent = { tap: 'Talk', listening: 'Listening… (tap when done)', thinking: 'Thinking…', speaking: 'Speaking… (tap to skip)' }[state];
  b.disabled = state === 'thinking';
  if (state !== 'listening') $('heard').hidden = true;
}

// Live couldn't take the call: turn by turn if this phone can listen (and calls may use it), else Telegram.
function fallBack(why, detail) {
  if (ending || mode === 'turns' || mode === 'text') return;
  closeLive();
  const kind = voiceMode === 'live' ? '' : speechKind(window, App);
  const textWhy = why === 'mic' ? 'no_mic' : voiceMode === 'live' ? 'live' : 'no_speech';
  report('fallback', { layer: kind ? 'turns' : 'telegram', why: kind ? why : textWhy });
  if (detail) say(`voice service: ${detail}`, 'sys');
  if (kind) return startTurns(kind, false);
  startText(textWhy);
}

// Turn by turn: chosen (calls.voice_mode "phone") or because Live failed. The screen stays on meanwhile: phones stop
// listening when it goes off.
async function startTurns(kind, chosen) {
  mode = 'turns';
  live = true;
  speech = kind === 'app' ? appSpeech() : webSpeech();
  said.splice(0, said.length, ...transcript.map((l) => ({ role: l.who === ai ? 'model' : 'user', text: l.text })));
  $('mode').hidden = false; $('mute').hidden = true; $('gatebox').hidden = true;
  if (!App) $('out').hidden = true; // the browser reads answers aloud where it likes; the app can still switch
  if (App && App.turnMode) { try { $('out').textContent = App.turnMode() ? 'Earpiece' : 'Speaker'; } catch { /* older app */ } }
  callIsOn();
  status(chosen ? 'Turn by turn.' : 'The live voice is down, so this call goes turn by turn.', 'live');
  if (!chosen) await speech.speak(purpose ? "The live voice isn't working, so we'll take turns." : "The live voice isn't working, so we'll take turns. Go ahead.");
  else if (!purpose) await speech.speak('Go ahead.');
  if (purpose && !said.some((h) => h.role === 'model')) system.push('[The call just connected. Speak first: greet them and get straight to the reason.]');
  turnLoop();
}

async function turnLoop() {
  let quiet = 0;
  while (mode === 'turns' && !ending) {
    if (system.length) { await answer(system.shift(), true); continue; }
    if (quiet >= 2) { // nothing heard twice: wait for a tap
      talkButton('tap');
      status('Tap Talk to speak.', 'live');
      await new Promise((r) => { tapped = r; wake = r; });
      tapped = null; wake = () => {}; quiet = 0;
      if (system.length) continue;
    }
    if (mode !== 'turns' || ending) break;
    talkButton('listening');
    let text;
    try {
      text = speech ? await speech.listen() : '';
      listened = true;
    } catch (code) {
      if (mode !== 'turns' || ending) break;
      if (!listened && ['not-allowed', 'service-not-allowed', 'audio-capture', 'permission', 'audio', 'unavailable', 'language', 'language-not-supported'].includes(String(code))) {
        return startText(['not-allowed', 'audio-capture', 'permission', 'audio'].includes(String(code)) ? 'no_mic' : 'no_speech');
      }
      say(`speech recognition: ${code}`, 'sys');
      quiet = 2;
      continue;
    }
    if (mode !== 'turns' || ending) break;
    if (!text) { quiet++; continue; }
    quiet = 0;
    await answer(text, false);
  }
}

// One turn: what they said (or a note) to the text AI, its answer shown and read aloud.
async function answer(text, isNote) {
  if (!isNote) { say(text, 'me'); note(me, text); }
  said.push({ role: 'user', text });
  talkButton('thinking');
  status('Thinking…', 'live');
  let r;
  try {
    r = await api('/turn', { history: said.slice(-40), purpose, since, announce: !announced });
    announced = true;
  } catch (e) {
    if (mode !== 'turns') return;
    say(`no answer: ${e.message}`, 'sys');
    talkButton('speaking');
    if (speech) await speech.speak("Sorry, I couldn't get an answer just now. Try again.");
    return;
  }
  if (mode !== 'turns' || ending) return;
  const reply = spoken(r.reply);
  if (r.offline) startedOffline = true; // told when the computer is back (poll)
  said.push({ role: 'model', text: reply });
  say(reply, 'ai'); note(ai, reply);
  let where = '';
  try { where = App && App.speechWhere ? App.speechWhere() : ''; } catch { /* an older app */ }
  status(`Turn by turn${where === 'on-device' ? ': your speech is recognised on this phone' : ''}${r.via === 'line' ? ' (answered on your call line)' : ''}.`, 'live');
  talkButton('speaking');
  if (speech) await speech.speak(reply);
}

// ---------- text on Telegram ----------
async function startText(why) {
  if (ending || mode === 'text') return;
  mode = 'text';
  closeLive();
  if (speech) { speech.stop(); speech.hush(); }
  $('talk').hidden = true; $('mode').hidden = true;
  status('Moving this call to Telegram…');
  const r = await post('/text-call', { purpose, since, why, lines: transcript.slice(-200), announce: !announced });
  if (!r.ok) {
    status(`Couldn't move the call to Telegram either: ${r.body.error || (r.unreachable ? 'the call line is unreachable' : `HTTP ${r.status}`)}`, 'err');
    return hangup(false);
  }
  announced = true;
  live = true;
  transcript.splice(0); // they're on Telegram now, and the call's journal is written from there
  const msg = r.body.queued
    ? 'Your computer is off, so this call goes on as messages on Telegram as soon as it\'s back.'
    : 'This call goes on as messages on Telegram. Answer there.';
  say(msg, 'sys');
  status(msg, 'live');
  if (App && App.speak) { try { App.speak(msg, 'bye'); } catch { /* no voice */ } } else if (window.speechSynthesis) { try { speechSynthesis.speak(new SpeechSynthesisUtterance(msg)); } catch { /* no voice */ } }
  setTimeout(() => { if (mode === 'text') hangup(false); }, 6000);
}

// ---------- buttons ----------
function callIsOn() {
  live = true;
  if (!pollTimer) pollTimer = setInterval(poll, 4000);
  if (App && !callUp) { callUp = true; App.callStarted(); if (mode === 'live') $('out').textContent = 'Speaker'; }
}

async function start() {
  ending = false; mode = 'live'; announced = false; attempt = 0; midRetries = 0; goingAway = false; listened = false;
  system.length = 0;
  $('call').textContent = 'Hang up'; $('call').className = 'end'; $('call').disabled = false; $('mute').hidden = false; $('out').hidden = false;
  status('Connecting…');
  try { wakeLock = navigator.wakeLock ? await navigator.wakeLock.request('screen') : null; } catch { /* optional */ }
  if (!voiceMode) await Promise.race([statusDone, sleep(3000)]);
  const kind = speechKind(window, App);
  if (voiceMode === 'phone' && kind) return startTurns(kind, true); // no Live at all; without speech here, Live
  try {
    await startAudio();
  } catch (e) {
    if (ending) return;
    say(`microphone: ${e.message}`, 'sys');
    return fallBack('mic', '');
  }
  if (ending) return;
  startLive(0);
}

function hangup(user = true) {
  // always sent, even with nothing said: it also tells your computer the call is over ("on a call" ends)
  if (live || transcript.length) api('/transcript', { lines: transcript.splice(0), purpose, since, ended: true, layer: mode }).catch(() => {});
  ending = true;
  live = false;
  mode = '';
  clearInterval(pollTimer); pollTimer = null;
  closeLive();
  if (speech) { speech.stop(); speech.hush(); speech = null; }
  if (tapped) tapped();
  if (outCtx) outCtx.close();
  outCtx = null;
  if (wakeLock && wakeLock.release) wakeLock.release();
  wakeLock = null;
  $('call').textContent = 'Call'; $('call').className = ''; $('call').disabled = !secret; $('mute').hidden = true; $('out').hidden = true; $('int').hidden = true;
  $('talk').hidden = true; $('heard').hidden = true; $('mode').hidden = true; $('gatebox').hidden = false;
  if (user) status('Call ended');
  if (App) { callUp = false; App.callEnded(); }
}

$('talk').onclick = () => {
  const st = $('talk').dataset.state;
  if (st === 'tap' && tapped) tapped();
  else if (st === 'listening' && speech) speech.stop();
  else if (st === 'speaking' && speech) speech.hush();
};
$('call').onclick = () => ($('call').className === 'end' ? hangup() : start());
$('out').onclick = toggleOutput;
$('int').onclick = interrupt;
$('gate').oninput = (e) => setSensitivity(Number(e.target.value));
$('gate').value = String(sensitivity); setSensitivity(sensitivity);
$('mute').onclick = () => { muted = !muted; $('mute').textContent = muted ? 'Unmute' : 'Mute'; };
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && (session || mode === 'turns') && !wakeLock && navigator.wakeLock) try { wakeLock = await navigator.wakeLock.request('screen'); } catch { /* optional */ }
});

// Who's who, and whether the computer is on (also checks the key early, so a bad link says so before you tap).
let statusDone = Promise.resolve();
if (secret) {
  statusDone = api('/status').then((s) => {
    if (!voiceMode && MODES.includes(s.voice)) voiceMode = s.voice;
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
