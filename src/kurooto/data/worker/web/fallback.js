// When Google's live voice (Gemini Live) won't take a call, the call still happens, one of three ways, tried in order:
//   1. Live again: a start that fails with "unavailable" or "too many requests" (503, 429, UNAVAILABLE, a socket
//      closed by the service) is tried again after about 1 s, then 3 s, each time with the next Live model in
//      calls.live_models. A drop in the middle of a call is tried again once.
//   2. Turn by turn: the phone's own speech recognition and voice (the Android app's, or the browser's Web Speech),
//      each turn answered by the text AI with the same instructions and tools (your computer, or Gemini on your call
//      line while the computer is off).
//   3. Text on Telegram: no speech recognition or no microphone, so the same conversation goes on as messages.
// Shared by the call page (web/app.js) and your call line (src/worker.js); tests in tests/js/fallback.mjs.

export const BACKOFF_MS = [0, 1000, 3000]; // attempt n waits this long first
export const STARTUP_MS = 8000; // a session that closes this soon, before anything was said, never started
export const START_TIMEOUT_MS = 12000; // a session that isn't set up by then counts as failed
export const MID_CALL_RETRIES = 1; // a drop in the middle of a call is tried again this many times
const TRANSIENT = /UNAVAILABLE|RESOURCE_EXHAUSTED|INTERNAL|DEADLINE_EXCEEDED|ABORTED/;
const BUSY_TEXT = /unavailable|overload|try again|temporar|503|429|quota|exhausted|rate.?limit|deadline|internal error/i;
const MODEL_TEXT = /\bmodels?\b.*\b(not found|not supported|unsupported|does not exist|is not available)|NOT_FOUND/i;

function clip(s, n) {
  s = String(s || '');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

// What Google answered when a request failed (the token, a text turn): {code, status, retry, badModel, text}.
// The SDK puts Google's JSON ({"error":{"code":503,"message":...,"status":"UNAVAILABLE"}}) in the error's message.
export function googleError(e) {
  const msg = String((e && e.message) || e || '');
  let code = Number(e && e.status) || 0, status = '', text = '';
  const at = msg.indexOf('{');
  if (at >= 0) {
    try {
      const j = JSON.parse(msg.slice(at));
      const err = j.error || j;
      code = code || Number(err.code) || 0;
      status = String(err.status || '');
      text = String(err.message || '');
    } catch { /* not JSON */ }
  }
  if (!status) status = (/\b(UNAVAILABLE|RESOURCE_EXHAUSTED|INTERNAL|DEADLINE_EXCEEDED|NOT_FOUND|PERMISSION_DENIED|INVALID_ARGUMENT|UNAUTHENTICATED)\b/.exec(msg) || [])[1] || '';
  if (!code) code = Number((/\b(4\d\d|5\d\d)\b/.exec(msg) || [])[1]) || 0;
  const retry = code === 429 || (code >= 500 && code < 600) || TRANSIENT.test(status);
  const badModel = !retry && (code === 404 || status === 'NOT_FOUND' || MODEL_TEXT.test(text || msg));
  return { code, status, retry, badModel, text: clip(text || msg || 'no answer', 200) };
}

// A Live socket that closed: 1011 (the service's own error, how "unavailable" arrives), 1013 (try again later) and
// 1006 (the connection broke) pass soon; a reason that says the service is busy does too.
export function closeError(code, reason) {
  code = Number(code) || 0;
  const text = String(reason || '');
  const retry = [1006, 1011, 1013, 1014].includes(code) || BUSY_TEXT.test(text);
  const badModel = !retry && MODEL_TEXT.test(text);
  return { code, status: '', retry, badModel, text: clip(text || (code ? `closed (${code})` : 'closed'), 200) };
}

// A connect that threw before any socket closed (the SDK, the network).
export function connectError(e) {
  const g = googleError(e);
  return g.code || g.status ? g : { ...g, retry: true };
}

// Try a Live start, up to BACKOFF_MS.length times from attempt `from`: attempt n waits BACKOFF_MS[n] and uses the
// n-th model (round the list). tryModel(model, n) -> {ok} or {ok: false, retry, badModel, line, text}. It stops
// early on what another try won't fix: the call line itself refused or can't be reached (line), or Google refused
// for good (a wrong key); a model that doesn't exist only moves on when there's another.
export async function rotate(tryModel, { models = () => [], from = 0, plan = BACKOFF_MS, sleep, onRetry } = {}) {
  let last = { ok: false, text: 'not tried' };
  for (let i = from; i < plan.length; i++) {
    const list = models() || [];
    const model = list.length ? list[i % list.length] : '';
    if (i > 0) {
      if (onRetry) onRetry(i, model);
      if (plan[i] && sleep) await sleep(plan[i]);
    }
    const r = (await tryModel(model, i)) || { ok: false, text: 'no answer' };
    if (r.ok) return { ...r, model: r.model || model, attempt: i };
    last = { ...r, ok: false, model: r.model || model, attempt: i };
    if (r.line || r.stop) break;
    if (!r.retry && !(r.badModel && list.length > 1)) break;
  }
  return last;
}

// Which speech the phone has for a call turn by turn: 'app' (the Android app's recognizer and voice), 'web' (the
// browser's Web Speech API) or '' (none: the call goes to Telegram). Inside the Android app only its own counts:
// the app's web view has no working Web Speech.
export function speechKind(win, app) {
  if (app) {
    try { return typeof app.canListen === 'function' && app.canListen() ? 'app' : ''; } catch { return ''; }
  }
  return win && (win.SpeechRecognition || win.webkitSpeechRecognition) ? 'web' : '';
}

// An answer as it's read aloud: no markdown, links as their words, at most `n` characters.
export function spoken(text, n = 1200) {
  let s = String(text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^\s{0,3}(#{1,6}|[-*+]|\d+[.)])\s+/gm, '')
    .replace(/[*_`~|>#]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (s.length > n) {
    const cut = s.slice(0, n);
    const end = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('? '), cut.lastIndexOf('! '));
    s = end > n / 2 ? cut.slice(0, end + 1) : cut + '…';
  }
  return s;
}

// A call's turns so far, as sent with each turn: [{role: 'user' | 'model', text}], the newest last.
export function cleanHistory(h, max = 60, chars = 2000) {
  return (Array.isArray(h) ? h : [])
    .filter((x) => x && typeof x.text === 'string' && x.text.trim())
    .slice(-max)
    .map((x) => ({ role: x.role === 'model' ? 'model' : 'user', text: x.text.trim().slice(0, chars) }));
}

// A transcript ({who, text} per line), as handed to Telegram when a call moves there.
export function cleanLines(lines, max = 200, chars = 4000) {
  return (Array.isArray(lines) ? lines : [])
    .filter((x) => x && typeof x.text === 'string' && x.text.trim())
    .slice(-max)
    .map((x) => ({ who: String(x.who || '').slice(0, 60), text: x.text.trim().slice(0, chars) }));
}
