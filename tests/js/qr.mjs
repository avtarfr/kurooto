// The phone's QR maker (public/qr.js), for tests/unit/test_shortcut.py: node qr.mjs <text> [mask] prints the version,
// the mask and the modules (one string of 0 and 1 per row) as JSON.
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
vm.runInThisContext(fs.readFileSync(path.join(here, '../../src/kurooto/data/worker/public/qr.js'), 'utf8'));
const [text, mask] = process.argv.slice(2);
const q = globalThis.KurootoQR.make(text, mask === undefined ? undefined : Number(mask));
const rows = [];
for (let y = 0; y < q.size; y++) {
  let r = '';
  for (let x = 0; x < q.size; x++) r += q.dark(x, y) ? '1' : '0';
  rows.push(r);
}
console.log(JSON.stringify({ version: q.version, mask: q.mask, rows, svg: globalThis.KurootoQR.svg(text).length }));
