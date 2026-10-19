// The Worker's k1 and t1 code against the shared test vectors (tests/fixtures/call-vectors.json).
// Run by tests/unit/test_calls.py: node tests/js/vectors.mjs <worker.js> <vectors.json>
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const [, , workerPath, vectorsPath] = process.argv;
const { openK1, sealK1, signedTicketOk } = await import(pathToFileURL(workerPath).href);
const v = JSON.parse(fs.readFileSync(vectorsPath, 'utf8'));

assert.equal(await openK1(v.k1.key, v.k1.sealed), v.k1.plain);
assert.equal(await openK1(v.k1.key, v.k1.sealed.slice(0, -2) + 'AA'), null); // tampered
const again = await sealK1(v.k1.key, v.k1.plain);
assert.equal(await openK1(v.k1.key, again), v.k1.plain);
const realNow = Date.now;
Date.now = () => v.t1.now_ms;
assert.equal(await signedTicketOk(v.t1.secret, v.t1.ticket), true);
assert.equal(await signedTicketOk('another-secret', v.t1.ticket), false);
Date.now = () => v.t1.now_ms + 3 * 3600e3;
assert.equal(await signedTicketOk(v.t1.secret, v.t1.ticket), false); // expired
Date.now = realNow;
console.log('vectors ok');
