// The call page (web/app.js) when Gemini Live won't take the call, run in Node: the page bundled with a fake Live API
// (tests/js/fake-genai.mjs), a stub page, a stub call line (fetch) and stub speech (the browser's Web Speech, or the
// Android app's bridge). Run by tests/unit/test_livefallback.py:
//   node tests/js/callpage.mjs <the page bundled with @google/genai aliased to fake-genai.mjs>
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const bundle = pathToFileURL(process.argv[2]).href;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, ms = 8000, what = 'it') {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = fn(); if (v) return v; await sleep(10); }
  throw new Error(`timed out waiting for ${what}`);
}

const LIVE_DOWN = { error: "the voice service didn't start the call: The service is currently unavailable.", live: true, retry: true, code: 503, status: 'UNAVAILABLE', models: ['live-a', 'live-b'] };
let n = 0;

// A fresh page: stub DOM, call line, speech. Returns what it saw.
async function page({ search, app = null, speech = true, voice = 'auto', tokens = () => null, heard = [] }) {
  const els = {};
  const el = (id) => ({ id, textContent: '', hidden: false, className: '', disabled: false, dataset: {}, style: {}, value: '1', children: [], append(c) { this.children.push(c); }, scrollIntoView() {} });
  const seen = { calls: [], spoken: [], els };
  globalThis.__live = { steps: [], connects: [], sessions: [] };
  globalThis.document = { getElementById: (id) => (els[id] ||= el(id)), createElement: () => el(''), addEventListener() {}, visibilityState: 'visible', title: '' };
  globalThis.location = { hash: '#d1.test', search, pathname: '/' };
  globalThis.history = { replaceState() {} };
  globalThis.localStorage = { getItem: () => null, setItem() {} };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { language: 'en-GB', mediaDevices: { getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }) } } });
  globalThis.window = globalThis;
  globalThis.AudioWorkletNode = class { constructor() { this.port = {}; } };
  globalThis.AudioContext = class { constructor() { this.audioWorklet = { addModule: async () => {} }; this.currentTime = 0; } createMediaStreamSource() { return { connect() {} }; } close() {} };
  globalThis.KurootoApp = app;
  let turns = 0;
  globalThis.fetch = async (path, opts) => {
    const body = opts && opts.body ? JSON.parse(opts.body) : undefined;
    seen.calls.push([path, body]);
    let status = 200, out = { ok: true };
    if (path === '/status') out = { computer: 'online', assistant: 'Kurooto', owner: 'Sam', voice };
    else if (path === '/token') {
      const t = tokens(body);
      if (t) [status, out] = t;
      else out = { token: 'auth_tokens/x', model: body.model || 'live-a', models: ['live-a', 'live-b'], config: {}, offline: false };
    } else if (path === '/turn') out = { reply: `**Answer ${++turns}.**`, via: 'computer' };
    else if (path === '/text-call') out = { ok: true, id: 'abc', where: 'telegram' };
    else if (path === '/tasks') out = { finished: [], approvals: [], computer: 'online' };
    return { ok: status < 400, status, json: async () => out };
  };
  // the browser's speech: what's "heard", one entry per listen ({error} for a failure); nothing left: silence
  globalThis.webkitSpeechRecognition = speech ? class {
    start() {
      setTimeout(() => {
        const h = heard.length ? heard.shift() : { error: 'no-speech' };
        if (h.error) this.onerror({ error: h.error });
        else { const r = [{ transcript: h }]; r.isFinal = true; this.onresult({ resultIndex: 0, results: [r] }); }
        this.onend();
      }, 5);
    }
    stop() {}
  } : undefined;
  globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
  globalThis.speechSynthesis = { speak: (u) => { seen.spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 1); }, cancel() {} };
  await import(`${bundle}?page=${++n}`);
  seen.paths = () => seen.calls.map((c) => c[0]);
  seen.bodies = (p) => seen.calls.filter((c) => c[0] === p).map((c) => c[1]);
  return seen;
}
const reports = (s) => s.bodies('/call-report');

// ---- 1. Live: a 1011 "unavailable" close at the start, then the next model gets through after about a second
{
  const s = await page({ search: '?p=Evening%20debrief&s=123' });
  __live.steps.push({ close: [1011, 'The service is currently unavailable.'] }, { ok: true });
  const t0 = Date.now();
  s.els.call.onclick();
  await until(() => s.els.status.textContent === 'Connected', 8000, 'connected');
  assert.ok(Date.now() - t0 >= 900, 'waited about a second before trying again');
  assert.deepEqual(s.bodies('/token').map((b) => b.model), ['', 'live-b']);
  assert.deepEqual(s.bodies('/token').map((b) => b.announce), [true, false]); // the call is announced once
  assert.deepEqual(__live.connects.map((c) => c.model), ['live-a', 'live-b']);
  await until(() => reports(s).some((r) => r.what === 'recovered'), 2000, 'the report');
  assert.deepEqual(reports(s).map((r) => [r.what, r.code || r.attempt]), [['failed', 1011], ['recovered', 2]]);
  assert.ok(s.els.log.children.some((c) => c.textContent === 'reconnecting…'));
  assert.equal(__live.sessions[0].sent[0].turns[0].parts[0].text, '[The call just connected. Speak first.]');
  s.els.call.onclick(); // hang up
  await until(() => s.bodies('/transcript').length, 2000, 'the end of the call');
  assert.equal(s.bodies('/transcript')[0].layer, 'live');
}

// ---- 2. Live down (503 three times: now, +1 s, +3 s, round the models), so the call goes turn by turn
{
  const s = await page({ search: '?p=Evening%20debrief&s=123', tokens: () => [503, LIVE_DOWN], heard: ['Fine, thanks'] });
  const t0 = Date.now();
  s.els.call.onclick();
  await until(() => s.bodies('/turn').length >= 2, 12000, 'two turns');
  assert.ok(Date.now() - t0 >= 3900, 'waited 1 s and 3 s');
  assert.deepEqual(s.bodies('/token').map((b) => b.model), ['', 'live-b', 'live-a']);
  assert.equal(__live.connects.length, 0);
  assert.deepEqual(reports(s).at(-1), { what: 'fallback', layer: 'turns', why: 'live' });
  assert.equal(s.spoken[0], "The live voice isn't working, so we'll take turns.");
  const [first, second] = s.bodies('/turn');
  assert.equal(first.announce, true); assert.equal(second.announce, false);
  assert.match(first.history[0].text, /^\[The call just connected\. Speak first/);
  assert.deepEqual(second.history.slice(1), [{ role: 'model', text: 'Answer 1.' }, { role: 'user', text: 'Fine, thanks' }]);
  await until(() => s.spoken.includes('Answer 2.'), 2000, 'the answer read aloud');
  assert.equal(s.spoken[1], 'Answer 1.'); // markdown taken out before it's read
  await until(() => s.els.talk.dataset.state === 'tap', 4000, 'Talk after two silences');
  s.els.call.onclick();
  await until(() => s.bodies('/transcript').length, 2000, 'the end');
  const end = s.bodies('/transcript')[0];
  assert.equal(end.layer, 'turns');
  assert.deepEqual(end.lines.map((l) => [l.who, l.text]), [['Kurooto', 'Answer 1.'], ['Sam', 'Fine, thanks'], ['Kurooto', 'Answer 2.']]);
}

// ---- 3. Live refused and no speech recognition here: the call moves to Telegram
{
  const s = await page({ search: '?p=Quiz&s=7', speech: false, tokens: () => [503, { ...LIVE_DOWN, retry: false, code: 403 }] });
  s.els.call.onclick();
  await until(() => s.bodies('/text-call').length, 4000, 'the handover');
  assert.equal(s.bodies('/token').length, 1); // a refusal another try won't fix: no retries
  const h = s.bodies('/text-call')[0];
  assert.equal(h.why, 'no_speech'); assert.equal(h.purpose, 'Quiz'); assert.equal(h.since, '7'); assert.equal(h.announce, true);
  assert.deepEqual(reports(s).at(-1), { what: 'fallback', layer: 'telegram', why: 'no_speech' });
  await until(() => /Telegram/.test(s.els.status.textContent), 2000, 'the status');
  s.els.call.onclick();
}

// ---- 4. speech recognition refused before anything worked: Telegram too
{
  const s = await page({ search: '?p=Quiz&s=8', tokens: () => [503, LIVE_DOWN], heard: [{ error: 'not-allowed' }] });
  s.els.call.onclick();
  await until(() => s.bodies('/text-call').length, 12000, 'the handover');
  assert.equal(s.bodies('/text-call')[0].why, 'no_mic');
  s.els.call.onclick();
}

// ---- 5. a drop in the middle of a call: tried again once (resuming), then turn by turn with what was said so far
{
  const s = await page({ search: '?p=Evening%20debrief&s=9', heard: ['Yes'] });
  __live.steps.push({ ok: true, say: 'How was your day?', dropAfter: 30 }, { close: [1011, 'The service is currently unavailable.'] });
  s.els.call.onclick();
  await until(() => s.bodies('/turn').length, 8000, 'turn by turn');
  const tokens = s.bodies('/token');
  assert.equal(tokens.length, 2); assert.equal(tokens[1].resume, true); assert.equal(tokens[1].model, 'live-a');
  assert.deepEqual(reports(s).map((r) => [r.what, r.stage || r.layer]), [['failed', 'call'], ['failed', 'connect'], ['fallback', 'turns']]);
  const first = s.bodies('/turn')[0];
  assert.deepEqual(first.history[0], { role: 'model', text: 'How was your day?' }); // carried over, not asked again
  assert.equal(first.history.length, 2); // and no "speak first": it had already spoken
  s.els.call.onclick();
}

// ---- 6. calls.voice_mode "phone" in the Android app: no Live at all; the app's recognizer and voice, screen on
{
  const app = {
    log: [],
    canListen() { return true; },
    speechWhere() { return 'on-device'; },
    prepareSpeech() { this.log.push('prepare'); },
    turnMode() { this.log.push('turnMode'); return true; },
    listen(lang) { this.log.push(`listen ${lang}`); setTimeout(() => window.kurootoSpeech.heard('I am up'), 5); },
    stopListening() {},
    speak(text, id) { this.log.push(`say ${text}`); setTimeout(() => window.kurootoSpeech.spoken(id), 1); },
    stopSpeaking() {},
    callStarted() { this.log.push('started'); },
    callEnded() { this.log.push('ended'); },
    isEarpiece: () => false,
    toggleSpeaker: () => true,
  };
  const s = await page({ search: '?p=Wake-up%20call&s=10&v=phone&auto=1', app });
  await until(() => s.bodies('/turn').length >= 2, 4000, 'two turns');
  assert.equal(s.bodies('/token').length, 0); // Live isn't used
  assert.deepEqual(app.log.slice(0, 3), ['prepare', 'turnMode', 'started']);
  assert.ok(app.log.includes('say Answer 1.') && app.log.includes('listen en-GB'));
  assert.equal(s.bodies('/turn')[1].history.at(-1).text, 'I am up');
  await until(() => /recognised on this phone/.test(s.els.status.textContent), 2000, 'the on-device note');
  s.els.call.onclick();
  await until(() => app.log.includes('ended'), 2000, 'the app told');
}

// ---- 7. "phone" asked for, but this browser can't listen: Live as usual
{
  const s = await page({ search: '?s=11', speech: false, voice: 'phone' });
  s.els.call.onclick();
  await until(() => s.els.status.textContent === 'Connected', 4000, 'Live');
  s.els.call.onclick();
}

console.log('callpage ok');
process.exit(0);
