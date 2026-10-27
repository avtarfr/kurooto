/* The being's memory: a 3D force layout of your notes, off the page's thread (being.js starts it as a worker).
   Linked notes pull together (a link through a "Seen in" or a reading list half as hard; each note's springs scaled by one
   over the root of its links, so a hub can't overshoot), every note keeps its distance from the notes near it, wide
   enough that each one shows on its own (a grid, at most 40 neighbours each, so it stays cheap), and each neighbourhood
   is held near its own centre. In: {p, li, lw, hood, ctr, iters}; out: {p, done} every few steps, the last done. */
"use strict";
const SK = .1; // the springs' strength (stable to at least 2.5x this on a 3,400-note graph)
onmessage = (e) => {
  const { p, li, lw, hood, ctr, iters } = e.data, N = hood.length;
  // a note's springs together pull no harder than a few links would: a hub with hundreds of links would overshoot
  const deg = new Float32Array(N); for (let l = 0; l < li.length; l++) deg[li[l]]++;
  const ks = deg.map((d) => 1 / Math.sqrt(Math.max(1, d)));
  const v = new Float32Array(N * 3), H = .1, inv = 1 / H, cells = new Map(), key = (x, y, z) => ((x + 512) * 1024 + (y + 512)) * 1024 + (z + 512);
  for (let it = 0; it < iters; it++) {
    const cool = 1 - (it / iters) * .9;
    cells.clear();
    for (let i = 0; i < N; i++) { const k = key(Math.floor(p[i * 3] * inv), Math.floor(p[i * 3 + 1] * inv), Math.floor(p[i * 3 + 2] * inv)); let c = cells.get(k); if (!c) cells.set(k, (c = [])); c.push(i); }
    for (let i = 0; i < N; i++) {
      const x = p[i * 3], y = p[i * 3 + 1], z = p[i * 3 + 2], cx = Math.floor(x * inv), cy = Math.floor(y * inv), cz = Math.floor(z * inv);
      for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const list = cells.get(key(cx + a, cy + b, cz + c)); if (!list) continue;
        for (let q = 0, seen = 0; q < list.length && seen < 40; q++) {
          const j = list[q]; if (j <= i) continue;
          const dx = x - p[j * 3], dy = y - p[j * 3 + 1], dz = z - p[j * 3 + 2], r2 = dx * dx + dy * dy + dz * dz;
          if (r2 >= H * H || r2 < 1e-10) continue; seen++;
          const r = Math.sqrt(r2), f = .007 * (1 - r / H) / r;
          v[i * 3] += dx * f; v[i * 3 + 1] += dy * f; v[i * 3 + 2] += dz * f; v[j * 3] -= dx * f; v[j * 3 + 1] -= dy * f; v[j * 3 + 2] -= dz * f;
        }
      }
    }
    for (let l = 0; l < li.length; l += 2) {
      const i = li[l], j = li[l + 1], dx = p[j * 3] - p[i * 3], dy = p[j * 3 + 1] - p[i * 3 + 1], dz = p[j * 3 + 2] - p[i * 3 + 2];
      const r = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-5, f = lw[l >> 1] * SK * (r - .06) / r, fi = f * ks[i], fj = f * ks[j];
      v[i * 3] += dx * fi; v[i * 3 + 1] += dy * fi; v[i * 3 + 2] += dz * fi; v[j * 3] -= dx * fj; v[j * 3 + 1] -= dy * fj; v[j * 3 + 2] -= dz * fj;
    }
    for (let i = 0; i < N; i++) { const h = hood[i] * 3; for (let d = 0; d < 3; d++) { const q = i * 3 + d; v[q] = (v[q] + (ctr[h + d] - p[q]) * .01) * .6; p[q] += v[q] * cool; } }
    if (it % 12 === 11 && it < iters - 1) postMessage({ p: p.slice(), done: false });
  }
  postMessage({ p, done: true });
};
