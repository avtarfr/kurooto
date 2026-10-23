// The chat with Kurooto for the iPhone Home Screen app (or any paired browser), like the Android app's: what you type
// goes through your call line to your computer and is handled like a Telegram message; Kurooto's answers come back
// here. Messages go over HTTPS with this device's key, each with a random nonce and the time, so it's used once.
// With your computer off, what you send waits on your call line ("Waiting for your computer") until it's back.
// This page keeps its own copy of the chat (the call line keeps the last 50 messages, 3 days) and asks for what's
// new when it opens, every few seconds while it's open, and after a notification.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var get = function (k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } };
  var set = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } };
  var key = get('kurootoDevice');
  var store = { seq: 0, msgs: [] };
  try { store = JSON.parse(get('kurootoChat') || 'null') || store; } catch (e) { /* a fresh copy */ }
  var replyTo = '', computer = '', busy = false;

  function hex(n) {
    var b = new Uint8Array(n);
    crypto.getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function msg(text, bad) { var m = $('msg'); m.hidden = !text; m.textContent = text || ''; m.className = 'card' + (bad ? ' err' : ''); }
  function save() { store.msgs = store.msgs.slice(-200); set('kurootoChat', JSON.stringify(store)); }

  function call(path, body) {
    return fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: { 'content-type': 'application/json', 'x-call-secret': key },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return [r.status, j]; }); });
  }

  // a message from the call line (or an answer): added, or put in place of the copy kept while it was sent
  function merge(m) {
    for (var i = 0; i < store.msgs.length; i++) {
      if (store.msgs[i].id === m.id) { store.msgs[i] = Object.assign({}, store.msgs[i], m, { state: '' }); return; }
    }
    store.msgs.push(m);
  }

  function render() {
    var log = $('log'), near = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
    log.textContent = '';
    store.msgs.forEach(function (m) { log.appendChild(bubble(m)); });
    $('status').textContent = computer === 'offline' ? 'Your computer is off: what you send waits on your call line and goes to it when it\'s back.'
      : store.msgs.length ? '' : 'Type to your assistant as you would on Telegram: commands, reminders, questions for your AI. /help lists what works.';
    $('replying').textContent = replyTo ? 'Replying to: ' + replyText() + ' (tap to cancel)' : '';
    if (near) log.scrollTop = log.scrollHeight;
  }
  function replyText() {
    var m = store.msgs.filter(function (x) { return x.id === replyTo; })[0];
    var t = m ? m.text : '';
    return t.length > 60 ? t.slice(0, 59) + '…' : t;
  }

  function bubble(m) {
    var mine = m.from === 'you', b = el('div', 'm' + (mine ? ' me' : ''));
    if (m.title && !mine) b.appendChild(el('b', '', m.title + '\n'));
    b.appendChild(document.createTextNode(m.text || ''));
    if (mine && m.state) b.appendChild(el('div', 'status' + (m.state === 'failed' ? ' err' : ''), m.state === 'sending' ? 'Sending…' : m.state === 'waiting' ? 'Waiting for your computer' : 'Not sent' + (m.note ? ': ' + m.note : '') + ' (tap to try again)'));
    if (mine && m.state === 'failed') b.onclick = function () { send(m.text, m.re || '', m.id); };
    var row = el('div', 'choices');
    (mine ? [] : m.buttons || []).forEach(function (x, i) {
      if (x.url && String(x.url).indexOf('https://') === 0) {
        var a = el('a', 'button quiet', x.label);
        a.href = x.url;
        a.target = '_blank';
        a.rel = 'noopener';
        row.appendChild(a);
      } else {
        var btn = el('button', 'quiet', x.label);
        btn.onclick = function () { tap(m, i, btn); };
        row.appendChild(btn);
      }
    });
    if (!mine && m.reply) {
      var r = el('button', 'quiet', 'Reply');
      r.onclick = function () { replyTo = m.id; render(); $('typed').focus(); };
      row.appendChild(r);
    }
    if (row.childNodes.length) b.appendChild(row);
    return b;
  }

  function send(text, to, id) {
    id = id || hex(8);
    merge({ id: id, from: 'you', text: text, re: to, at: Math.floor(Date.now() / 1000), state: 'sending' });
    save();
    render();
    var body = { id: id, ts: Date.now(), n: hex(16), text: text };
    if (to) body.to = to;
    call('/chat', body).then(function (res) {
      var j = res[1], mine = store.msgs.filter(function (x) { return x.id === id; })[0];
      if (res[0] === 200 && j.queued) { mine.state = 'waiting'; computer = 'offline'; }
      else if (res[0] === 200) { mine.state = ''; (j.said || []).forEach(merge); }
      else { mine.state = 'failed'; mine.note = j.note || j.error || ''; }
      save();
      render();
      if (res[0] === 401) msg('This phone was unpaired. Pair it again from your computer.', true);
    }).catch(function () {
      var mine = store.msgs.filter(function (x) { return x.id === id; })[0];
      mine.state = 'failed';
      mine.note = 'couldn\'t reach your call line';
      save();
      render();
    });
  }

  function tap(m, i, btn) {
    btn.disabled = true;
    call('/chat', { id: hex(8), ts: Date.now(), n: hex(16), button: i, msg: m.id }).then(function (res) {
      btn.disabled = false;
      var j = res[1];
      msg(res[0] === 200 ? (j.queued ? 'Tapped. It waits on your call line for your computer.' : '') : (j.note || j.error || 'That didn\'t go through.'), res[0] !== 200);
      sync();
    }).catch(function () { btn.disabled = false; msg('Couldn\'t reach your call line. Is this phone online?', true); });
  }

  function sync() {
    if (busy || !key) return;
    busy = true;
    call('/chat?after=' + (store.seq || 0)).then(function (res) {
      busy = false;
      if (res[0] === 401) { msg('This phone was unpaired. Pair it again from your computer.', true); return; }
      if (res[0] !== 200) return;
      var j = res[1];
      if (j.assistant) { $('who').textContent = j.assistant; $('typed').placeholder = 'Message ' + j.assistant; }
      computer = j.computer || '';
      if (j.seq < store.seq) store.seq = 0; // the call line was set up again: start over from what it has
      (j.msgs || []).forEach(merge);
      store.seq = Math.max(store.seq, j.seq || 0);
      var waiting = (j.waiting || []).map(function (w) { return w.oid; });
      store.msgs.forEach(function (m) { if (m.state === 'waiting' && waiting.indexOf(m.id) < 0) m.state = ''; });
      save();
      render();
    }).catch(function () { busy = false; });
  }

  if (!key) { msg('This phone isn\'t paired yet. On your computer: Kurooto → Phone → Pair a phone.', true); return; }
  $('send').onclick = function () {
    var t = $('typed').value.trim();
    if (!t) return;
    $('typed').value = '';
    var to = replyTo;
    replyTo = '';
    send(t.slice(0, 4000), to);
  };
  $('replying').onclick = function () { replyTo = ''; render(); };
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') sync(); });
  setInterval(function () { if (document.visibilityState === 'visible') sync(); }, 5000);
  render();
  sync();
})();
