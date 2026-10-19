// The phone's inbox (the iPhone Home Screen app, or any paired browser): what Kurooto asked you that's still open,
// with buttons to answer. Answers are single use (a random nonce and the time) and go to your computer through
// your call line, or wait there until the computer is back on.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var key = '';
  try { key = localStorage.getItem('kurootoDevice') || ''; } catch (e) { key = ''; }

  function msg(text, bad) { var m = $('msg'); m.hidden = !text; m.textContent = text || ''; m.className = 'card' + (bad ? ' err' : ''); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function nonce() {
    var b = new Uint8Array(16);
    crypto.getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  function call(path, body) {
    return fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: { 'content-type': 'application/json', 'x-call-secret': key },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return [r.status, j]; }); });
  }

  function send(it, card, fields) {
    var buttons = card.querySelectorAll('button, textarea');
    for (var i = 0; i < buttons.length; i++) buttons[i].disabled = true;
    var status = card.querySelector('.status');
    status.className = 'status';
    status.textContent = 'Sending…';
    var body = { item: it.id, ts: Date.now(), n: nonce() };
    for (var k in fields) body[k] = fields[k];
    call('/answer', body).then(function (res) {
      var j = res[1];
      if (res[0] >= 200 && res[0] < 300) {
        status.className = 'status ok';
        status.textContent = j.note || 'Sent.';
        setTimeout(load, 2500);
      } else {
        status.className = 'status err';
        status.textContent = j.note || j.error || 'That didn\'t go through.';
        if (res[0] !== 410) for (var i = 0; i < buttons.length; i++) buttons[i].disabled = false;
      }
    }).catch(function () {
      status.className = 'status err';
      status.textContent = 'Couldn\'t reach your call line. Is this phone online?';
      for (var i = 0; i < buttons.length; i++) buttons[i].disabled = false;
    });
  }

  function button(label, cls, onclick) { var b = el('button', cls, label); b.onclick = onclick; return b; }

  var name = 'Kurooto'; // your assistant's name, as your computer last said

  function card(it) {
    var c = el('section', 'card');
    c.id = it.id;
    c.appendChild(el('h2', '', it.title || name));
    c.appendChild(el('p', 'text', it.text || ''));
    var choices = el('div', 'choices');
    (it.choices || []).forEach(function (ch) {
      choices.appendChild(button(ch, '', function () { send(it, c, { answer: ch }); }));
    });
    (it.buttons || []).forEach(function (b, i) {
      if (b.url && String(b.url).indexOf('https://') === 0) {
        var a = el('a', 'button quiet', b.label);
        a.href = b.url;
        a.target = '_blank';
        a.rel = 'noopener';
        choices.appendChild(a);
      } else {
        choices.appendChild(button(b.label, 'quiet', function () { send(it, c, { button: i }); }));
      }
    });
    if (choices.childNodes.length) c.appendChild(choices);
    if (it.reply) {
      var box = el('textarea');
      box.rows = 3;
      box.placeholder = (it.choices || []).length ? 'Or type an answer' : 'Your answer';
      c.appendChild(box);
      c.appendChild(button('Send', '', function () {
        if (box.value.trim()) send(it, c, { answer: box.value.trim() });
      }));
    }
    var more = el('div', 'choices');
    if (it.later) more.appendChild(button('Later', 'quiet', function () { send(it, c, { answer: 'later' }); }));
    if (!it.qid) more.appendChild(button('Dismiss', 'quiet', function () { send(it, c, { dismiss: true }); }));
    c.appendChild(more);
    c.appendChild(el('p', 'status', ''));
    return c;
  }

  function load() {
    if (!key) {
      msg('This phone isn\'t paired yet. On your computer: Kurooto → Phone → Pair a phone, or send /phone to your bot.', true);
      return;
    }
    call('/pending').then(function (res) {
      if (res[0] === 401) { msg('This phone was unpaired. Pair it again from your computer.', true); return; }
      if (res[0] !== 200) { msg(res[1].error || 'Couldn\'t load what\'s waiting.', true); return; }
      msg('');
      if (res[1].assistant) { name = res[1].assistant; $('who').textContent = name; }
      var list = $('list');
      list.textContent = '';
      (res[1].rings || []).forEach(function (r) {
        var c = el('section', 'card');
        c.appendChild(el('h2', '', r.alarm ? 'Wake-up call' : name + ' is calling'));
        c.appendChild(el('p', 'text', r.reason || ''));
        var a = el('a', 'button', 'Answer');
        a.href = r.link;
        c.appendChild(a);
        list.appendChild(c);
      });
      var items = (res[1].items || []).slice().reverse(); // newest first
      items.forEach(function (it) { list.appendChild(card(it)); });
      $('empty').hidden = list.childNodes.length > 0;
      var want = location.hash.slice(1);
      if (want && $(want)) $(want).scrollIntoView({ block: 'start' });
    }).catch(function () { msg('Couldn\'t reach your call line. Is this phone online?', true); });
  }

  $('reload').onclick = load;
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') load(); });
  load();
})();
