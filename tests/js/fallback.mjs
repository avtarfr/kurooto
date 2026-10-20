// web/fallback.js (shared by the call page and the call line): reading Google's errors, the Live retries with model
// rotation, which speech a phone has, and answers made fit to read aloud.
// Run by tests/unit/test_livefallback.py: node tests/js/fallback.mjs <fallback.js>
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const f = await import(pathToFileURL(process.argv[2]).href);

// ---- Google's errors: the one from today, as the SDK throws it
const today = new Error('{"error":{"code":503,"message":"The service is currently unavailable.","status":"UNAVAILABLE"}}');
let g = f.googleError(today);
assert.equal(g.code, 503); assert.equal(g.status, 'UNAVAILABLE'); assert.equal(g.retry, true);
assert.equal(g.text, 'The service is currently unavailable.');
g = f.googleError(Object.assign(new Error('got status: 429 Too Many Requests. {"error":{"code":429,"status":"RESOURCE_EXHAUSTED","message":"quota"}}'), { status: 429 }));
assert.equal(g.retry, true); assert.equal(g.status, 'RESOURCE_EXHAUSTED');
g = f.googleError(new Error('{"error":{"code":403,"message":"API key not valid","status":"PERMISSION_DENIED"}}'));
assert.equal(g.retry, false); assert.equal(g.badModel, false);
g = f.googleError(new Error('{"error":{"code":404,"message":"models/gemini-x is not found for API version v1alpha","status":"NOT_FOUND"}}'));
assert.equal(g.retry, false); assert.equal(g.badModel, true);
assert.equal(f.googleError(new Error('fetch failed: 502 Bad Gateway')).retry, true);

// ---- a Live socket closing
assert.equal(f.closeError(1011, 'The service is currently unavailable.').retry, true);
assert.equal(f.closeError(1013, '').retry, true);
assert.equal(f.closeError(1006, '').retry, true);
assert.equal(f.closeError(1008, 'Request contains an invalid argument.').retry, false);
assert.equal(f.closeError(1007, 'models/gemini-old is not found').badModel, true);
assert.equal(f.connectError(new TypeError('Failed to fetch')).retry, true);

// ---- rotation: 503, then the next model works (after ~1 s); the waits are 1 s and 3 s
const sleeps = [], retries = [];
const sleep = async (ms) => { sleeps.push(ms); };
let tried = [];
let r = await f.rotate(async (model, n) => { tried.push(model); return n === 0 ? { ok: false, retry: true, code: 503 } : { ok: true }; },
  { models: () => ['live-a', 'live-b'], sleep, onRetry: (n, m) => retries.push([n, m]) });
assert.equal(r.ok, true); assert.equal(r.model, 'live-b'); assert.equal(r.attempt, 1);
assert.deepEqual(tried, ['live-a', 'live-b']); assert.deepEqual(sleeps, [1000]); assert.deepEqual(retries, [[1, 'live-b']]);

// every try fails: three tries (now, +1 s, +3 s), round the list, then it gives up with the last error
tried = []; sleeps.length = 0;
r = await f.rotate(async (model) => { tried.push(model); return { ok: false, retry: true, code: 503, text: 'unavailable' }; },
  { models: () => ['live-a', 'live-b'], sleep });
assert.equal(r.ok, false); assert.equal(r.code, 503); assert.deepEqual(tried, ['live-a', 'live-b', 'live-a']); assert.deepEqual(sleeps, [1000, 3000]);

// the model list arrives with the first answer (the first try names none: the call line picks)
let list = [];
tried = [];
r = await f.rotate(async (model) => { tried.push(model); list = ['live-a', 'live-b']; return { ok: false, retry: true }; }, { models: () => list, sleep });
assert.deepEqual(tried, ['', 'live-b', 'live-a']);

// one model only: tried again, the same one
tried = [];
await f.rotate(async (model) => { tried.push(model); return { ok: false, retry: true }; }, { models: () => ['only'], sleep });
assert.deepEqual(tried, ['only', 'only', 'only']);

// what another try won't fix stops at once: the call line itself, a wrong key
for (const fail of [{ line: true, text: 'wrong or missing key' }, { retry: false, code: 403 }]) {
  tried = [];
  r = await f.rotate(async (model) => { tried.push(model); return { ok: false, ...fail }; }, { models: () => ['a', 'b'], sleep });
  assert.equal(tried.length, 1); assert.equal(r.ok, false);
}
// a model that doesn't exist moves on to the next (but not round to itself)
tried = [];
r = await f.rotate(async (model) => { tried.push(model); return model === 'gone' ? { ok: false, badModel: true } : { ok: true }; }, { models: () => ['gone', 'fine'], sleep });
assert.equal(r.ok, true); assert.deepEqual(tried, ['gone', 'fine']);
// a session that never really started picks up where the tries left off
tried = [];
r = await f.rotate(async (model, n) => { tried.push(n); return { ok: false, retry: true }; }, { models: () => ['a', 'b'], from: 2, sleep });
assert.deepEqual(tried, [2]);

// ---- which speech: the app's own inside the app (never the web view's), the browser's elsewhere
assert.equal(f.speechKind({ webkitSpeechRecognition: function () {} }, null), 'web');
assert.equal(f.speechKind({}, null), '');
assert.equal(f.speechKind({ webkitSpeechRecognition: function () {} }, { canListen: () => true }), 'app');
assert.equal(f.speechKind({ webkitSpeechRecognition: function () {} }, { canListen: () => false }), '');
assert.equal(f.speechKind({ webkitSpeechRecognition: function () {} }, { callStarted() {} }), ''); // an older app
assert.equal(f.speechKind({}, { canListen: () => { throw new Error('gone'); } }), '');

// ---- answers read aloud
assert.equal(f.spoken('**Done.** See [your note](https://x.y/z).\n- one\n- two'), 'Done. See your note. one two');
assert.equal(f.spoken('# Plan\n```js\ncode()\n```\nAll set.'), 'Plan All set.');
const long = f.spoken('A sentence here. '.repeat(200), 100);
assert.ok(long.length <= 100 && long.endsWith('.'));

// ---- what a turn and a handover carry
assert.deepEqual(f.cleanHistory([{ role: 'model', text: ' hi ' }, { role: 'system', text: 'x' }, { text: '' }, null]),
  [{ role: 'model', text: 'hi' }, { role: 'user', text: 'x' }]);
assert.equal(f.cleanHistory(Array.from({ length: 100 }, (_, i) => ({ role: 'user', text: String(i) }))).length, 60);
assert.deepEqual(f.cleanLines([{ who: 'Sam', text: 'yes' }, { who: 'Kurooto' }]), [{ who: 'Sam', text: 'yes' }]);

console.log('fallback ok');
