// A file your computer left on your call line for the chat (where Telegram would get a document). The link's #fragment
// holds its id, the key and its name; the fragment never leaves this phone, so the call line only ever has the
// sealed bytes ("f1": AES-256-GCM, nonce || ciphertext+tag). Opened here: saved, and shown when it's text.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var h = new URLSearchParams(location.hash.slice(1));
  var id = (h.get('i') || '').replace(/[^0-9a-f]/g, ''), key = h.get('k') || '', name = (h.get('n') || 'file').replace(/[\\/]/g, '-');

  function msg(text, bad) { var m = $('msg'); m.hidden = !text; m.textContent = text || ''; m.className = 'card' + (bad ? ' err' : ''); }
  function unb64(s) {
    var b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
    var out = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
    return out;
  }
  var TEXT = /\.(md|txt|csv|json|log|py|tex|html?)$/i;
  var TYPES = { pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', md: 'text/markdown', txt: 'text/plain', zip: 'application/zip' };

  $('name').textContent = name;
  document.title = name;
  if (id.length !== 32 || !key) { msg('This link is incomplete. Open it from the chat again.', true); return; }
  msg('Opening…');
  fetch('/sealed/' + id).then(function (r) {
    if (!r.ok) return r.json().catch(function () { return {}; }).then(function (j) { throw new Error(j.note || 'This file is gone.'); });
    return r.arrayBuffer();
  }).then(function (buf) {
    var raw = new Uint8Array(buf);
    return crypto.subtle.importKey('raw', unb64(key), 'AES-GCM', false, ['decrypt']).then(function (k) {
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, k, raw.slice(12));
    }).catch(function () { throw new Error('This link doesn\'t open the file (it was cut short?). Open it from the chat again.'); });
  }).then(function (plain) {
    msg('');
    var ext = (name.split('.').pop() || '').toLowerCase();
    var blob = new Blob([plain], { type: TYPES[ext] || 'application/octet-stream' });
    var save = $('save');
    save.href = URL.createObjectURL(blob);
    save.download = name;
    save.textContent = 'Save ' + name + ' (' + Math.max(1, Math.round(plain.byteLength / 1024)) + ' KB)';
    save.hidden = false;
    if (TEXT.test(name) && plain.byteLength < 2 * 1024 * 1024) {
      $('text').textContent = new TextDecoder().decode(plain);
      $('text').hidden = false;
    }
  }).catch(function (e) { msg(e.message || 'Couldn\'t reach your call line. Is this phone online?', true); });
})();
