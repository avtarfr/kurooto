// A small QR code maker for the Tell Kurooto link (shortcut.js): byte mode, error correction level M, versions 1 to
// 20 (up to 331 bytes), as an SVG. No library and nothing fetched: the link holds a token, so it's drawn here, on the
// phone. The steps are ISO/IEC 18004's (as in Project Nayuki's QR Code generator); tests/unit/test_shortcut.py checks
// the result module by module against segno, which the dashboard uses for its pairing QR.
(function (root) {
  // level M, per version (index 0 unused): error correction codewords per block, and the number of blocks
  var ECC_PER_BLOCK = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26];
  var BLOCKS = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16];
  var MAX_VERSION = 20;

  function rawModules(ver) {
    var n = (16 * ver + 128) * ver + 64;
    if (ver >= 2) {
      var align = Math.floor(ver / 7) + 2;
      n -= (25 * align - 10) * align - 55;
      if (ver >= 7) n -= 36;
    }
    return n;
  }
  function dataCodewords(ver) { return Math.floor(rawModules(ver) / 8) - ECC_PER_BLOCK[ver] * BLOCKS[ver]; }

  // GF(256) with the polynomial 0x11D
  function mul(x, y) {
    var z = 0;
    for (var i = 7; i >= 0; i--) {
      z = (z << 1) ^ ((z >>> 7) * 0x11d);
      z ^= ((y >>> i) & 1) * x;
    }
    return z & 0xff;
  }
  function divisor(degree) {
    var r = [];
    for (var i = 0; i < degree - 1; i++) r.push(0);
    r.push(1);
    var root = 1;
    for (i = 0; i < degree; i++) {
      for (var j = 0; j < r.length; j++) {
        r[j] = mul(r[j], root);
        if (j + 1 < r.length) r[j] ^= r[j + 1];
      }
      root = mul(root, 2);
    }
    return r;
  }
  function remainder(data, div) {
    var r = div.map(function () { return 0; });
    data.forEach(function (b) {
      var f = b ^ r.shift();
      r.push(0);
      div.forEach(function (c, i) { r[i] ^= mul(c, f); });
    });
    return r;
  }

  function utf8(text) {
    var s = unescape(encodeURIComponent(text)), out = [];
    for (var i = 0; i < s.length; i++) out.push(s.charCodeAt(i));
    return out;
  }

  // text -> {size, dark(x, y)}; mask 0-7, or the one with the lowest penalty
  function make(text, mask) {
    var bytes = utf8(String(text)), ver;
    for (ver = 1; ver <= MAX_VERSION; ver++) if (4 + (ver <= 9 ? 8 : 16) + 8 * bytes.length <= dataCodewords(ver) * 8) break;
    if (ver > MAX_VERSION) throw new Error('too long for a QR code here');
    var bits = [];
    var put = function (v, n) { for (var i = n - 1; i >= 0; i--) bits.push((v >>> i) & 1); };
    put(4, 4);
    put(bytes.length, ver <= 9 ? 8 : 16);
    bytes.forEach(function (b) { put(b, 8); });
    var cap = dataCodewords(ver) * 8;
    put(0, Math.min(4, cap - bits.length));
    put(0, (8 - (bits.length % 8)) % 8);
    for (var pad = 0xec; bits.length < cap; pad ^= 0xec ^ 0x11) put(pad, 8);
    var data = [];
    for (var i = 0; i < bits.length; i += 8) {
      var v = 0;
      for (var j = 0; j < 8; j++) v = (v << 1) | bits[i + j];
      data.push(v);
    }

    // error correction, blocks interleaved
    var nb = BLOCKS[ver], el = ECC_PER_BLOCK[ver], raw = Math.floor(rawModules(ver) / 8);
    var nShort = nb - (raw % nb), shortLen = Math.floor(raw / nb), div = divisor(el), blocks = [], k = 0;
    for (i = 0; i < nb; i++) {
      var dat = data.slice(k, k + shortLen - el + (i < nShort ? 0 : 1));
      k += dat.length;
      var ecc = remainder(dat, div);
      if (i < nShort) dat.push(0);
      blocks.push(dat.concat(ecc));
    }
    var all = [];
    for (i = 0; i < blocks[0].length; i++) {
      for (j = 0; j < blocks.length; j++) if (i !== shortLen - el || j >= nShort) all.push(blocks[j][i]);
    }

    var size = ver * 4 + 17, m = [], fn = [];
    for (i = 0; i < size; i++) { m.push(new Array(size).fill(false)); fn.push(new Array(size).fill(false)); }
    var set = function (x, y, d) { m[y][x] = d; fn[y][x] = true; };
    for (i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }
    [[3, 3], [size - 4, 3], [3, size - 4]].forEach(function (c) {
      for (var dy = -4; dy <= 4; dy++) {
        for (var dx = -4; dx <= 4; dx++) {
          var d = Math.max(Math.abs(dx), Math.abs(dy)), x = c[0] + dx, y = c[1] + dy;
          if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, d !== 2 && d !== 4);
        }
      }
    });
    var pos = [];
    if (ver > 1) {
      var na = Math.floor(ver / 7) + 2, step = Math.floor((ver * 8 + na * 3 + 5) / (na * 4 - 4)) * 2;
      for (var p = size - 7; pos.length < na - 1; p -= step) pos.unshift(p);
      pos.unshift(6);
    }
    for (i = 0; i < pos.length; i++) {
      for (j = 0; j < pos.length; j++) {
        if ((i === 0 && j === 0) || (i === 0 && j === pos.length - 1) || (i === pos.length - 1 && j === 0)) continue;
        for (var ay = -2; ay <= 2; ay++) for (var ax = -2; ax <= 2; ax++) set(pos[i] + ax, pos[j] + ay, Math.max(Math.abs(ax), Math.abs(ay)) !== 1);
      }
    }
    var format = function (mk) {
      var d = (0 << 3) | mk, r = d; // level M is 0b00
      for (var t = 0; t < 10; t++) r = (r << 1) ^ ((r >>> 9) * 0x537);
      var b = ((d << 10) | r) ^ 0x5412, bit = function (n) { return ((b >>> n) & 1) === 1; };
      for (t = 0; t <= 5; t++) set(8, t, bit(t));
      set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
      for (t = 9; t < 15; t++) set(14 - t, 8, bit(t));
      for (t = 0; t < 8; t++) set(size - 1 - t, 8, bit(t));
      for (t = 8; t < 15; t++) set(8, size - 15 + t, bit(t));
      set(8, size - 8, true);
    };
    format(0);
    if (ver >= 7) {
      var r = ver;
      for (i = 0; i < 12; i++) r = (r << 1) ^ ((r >>> 11) * 0x1f25);
      var vb = (ver << 12) | r;
      for (i = 0; i < 18; i++) {
        var on = ((vb >>> i) & 1) === 1, a = size - 11 + (i % 3), c = Math.floor(i / 3);
        set(a, c, on); set(c, a, on);
      }
    }
    var n = 0;
    for (var right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (var vert = 0; vert < size; vert++) {
        for (j = 0; j < 2; j++) {
          var x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
          if (!fn[y][x] && n < all.length * 8) { m[y][x] = ((all[n >>> 3] >>> (7 - (n & 7))) & 1) === 1; n++; }
        }
      }
    }
    var flip = function (mk) {
      for (var y = 0; y < size; y++) {
        for (var x = 0; x < size; x++) {
          var inv = [(x + y) % 2, y % 2, x % 3, (x + y) % 3, (Math.floor(x / 3) + Math.floor(y / 2)) % 2,
            (x * y) % 2 + (x * y) % 3, ((x * y) % 2 + (x * y) % 3) % 2, ((x + y) % 2 + (x * y) % 3) % 2][mk] === 0;
          if (inv && !fn[y][x]) m[y][x] = !m[y][x];
        }
      }
    };
    if (mask === undefined || mask === null) {
      var best = 0, low = Infinity;
      for (var t = 0; t < 8; t++) {
        flip(t); format(t);
        var s = penalty(m, size);
        if (s < low) { low = s; best = t; }
        flip(t);
      }
      mask = best;
    }
    flip(mask);
    format(mask);
    return { version: ver, mask: mask, size: size, dark: function (x, y) { return m[y][x]; } };
  }

  // ISO 18004's four penalty rules, to pick the mask
  function penalty(m, size) {
    var score = 0, x, y, dark = 0;
    var line = function (get) {
      var s = 0, run = 1, str = '';
      for (var i = 0; i < size; i++) {
        var v = get(i);
        str += v ? '1' : '0';
        if (i > 0 && v === get(i - 1)) { run++; } else { if (run >= 5) s += run - 2; run = 1; }
      }
      if (run >= 5) s += run - 2;
      var re = /(?=(10111010000|00001011101))/g;
      while (re.exec(str)) { s += 40; re.lastIndex++; }
      return s;
    };
    for (y = 0; y < size; y++) score += line(function (i) { return m[y][i]; });
    for (x = 0; x < size; x++) score += line(function (i) { return m[i][x]; });
    for (y = 0; y < size - 1; y++) {
      for (x = 0; x < size - 1; x++) if (m[y][x] === m[y][x + 1] && m[y][x] === m[y + 1][x] && m[y][x] === m[y + 1][x + 1]) score += 3;
    }
    for (y = 0; y < size; y++) for (x = 0; x < size; x++) if (m[y][x]) dark++;
    return score + Math.floor(Math.abs(dark * 20 - size * size * 10) / (size * size)) * 10;
  }

  // the code as an SVG (black on white, with the 4-module quiet zone scanners want)
  function svg(text) {
    var q = make(text), d = '';
    for (var y = 0; y < q.size; y++) for (var x = 0; x < q.size; x++) if (q.dark(x, y)) d += 'M' + (x + 4) + ' ' + (y + 4) + 'h1v1h-1z';
    var w = q.size + 8;
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + w + '" shape-rendering="crispEdges" role="img" aria-label="QR code">' +
      '<rect width="' + w + '" height="' + w + '" fill="#fff"/><path d="' + d + '" fill="#000"/></svg>';
  }

  root.KurootoQR = { make: make, svg: svg };
})(typeof window !== 'undefined' ? window : globalThis);
