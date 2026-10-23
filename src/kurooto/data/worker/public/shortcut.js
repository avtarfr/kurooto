// Tell Kurooto (0.6.0): the recipe for an iPhone Shortcut that sends what you say to Kurooto, with this phone's own
// link filled in. Apple doesn't let a web page make a Shortcut file, so it's five steps by hand. The link
// (<call line>/tell/tk1.<id>.<secret>) is made by the call line for this paired phone (POST /shortcut/new; one per
// phone, a new one replaces the old) and kept only here, in this app's storage; the call line keeps its hash. It
// can send a chat message as this phone and nothing else. Revoke it here (New link, Remove) or on your computer
// (dashboard → Phone). Used by settings.html, and by pair.html right after an iPhone pairs.
(function () {
  var box = document.getElementById('shortcut');
  if (!box) return;
  var get = function (k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } };
  var set = function (k, v) { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e) { /* private mode */ } };
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function rich(tag, parts) { // ["plain", ["b", "bold"], ["code", "x"]] -> an element, no HTML parsing
    var e = el(tag);
    parts.forEach(function (p) { e.appendChild(typeof p === 'string' ? document.createTextNode(p) : el(p[0], '', p[1])); });
    return e;
  }

  function call(path) {
    return fetch(path, { method: path === '/shortcut' ? 'GET' : 'POST', headers: { 'content-type': 'application/json', 'x-call-secret': get('kurootoDevice') }, body: path === '/shortcut' ? undefined : '{}' })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return [r.status, j]; }); });
  }

  function say(text, bad) {
    var p = box.querySelector('.status') || box.appendChild(el('p', 'status'));
    p.className = 'status' + (bad ? ' err' : ' ok');
    p.textContent = text || '';
  }

  function make() {
    say('Making your link…');
    return call('/shortcut/new').then(function (res) {
      if (res[0] === 200 && res[1].url) { set('kurootoTell', res[1].url); render(res[1].url); return; }
      if (res[0] === 401) { render(''); say('This phone isn\'t paired (any more). Pair it again from your computer.', true); return; }
      render(''); say(res[1].error || 'Couldn\'t make the link. Try again.', true);
    }).catch(function () { render(''); say('Couldn\'t reach your call line. Is this phone online?', true); });
  }

  function remove() {
    if (!confirm('Remove the link? Your Tell Kurooto Shortcut stops working.')) return;
    call('/shortcut/off').then(function () { set('kurootoTell', ''); render(''); say('Removed. The Shortcut no longer works.'); })
      .catch(function () { say('Couldn\'t reach your call line. Is this phone online?', true); });
  }

  function copy(text, button) {
    var done = function () { button.textContent = 'Copied'; setTimeout(function () { button.textContent = 'Copy the link'; }, 2000); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { pick(); });
    else pick();
    function pick() { var f = box.querySelector('.link'); f.focus(); f.select(); f.setSelectionRange(0, text.length); try { document.execCommand('copy'); done(); } catch (e) { /* selected: Copy from the menu */ } }
  }

  function render(url) {
    box.textContent = '';
    box.appendChild(el('h2', '', 'Tell Kurooto: Siri and Back Tap'));
    box.appendChild(el('p', '', 'A Shortcut that sends what you say to Kurooto, like typing it in the chat, and reads you the answer. Say "Hey Siri, Tell Kurooto", or tap the back of your iPhone.'));
    if (!url) {
      var b = el('button', '', 'Make my Shortcut link');
      b.onclick = make;
      box.appendChild(b);
      return;
    }
    var link = el('input', 'link');
    link.readOnly = true;
    link.value = url;
    link.setAttribute('aria-label', 'Your Shortcut link');
    link.onfocus = function () { link.select(); };
    box.appendChild(link);
    var cp = el('button', '', 'Copy the link');
    cp.onclick = function () { copy(url, cp); };
    box.appendChild(cp);
    var qr = el('div', 'qr');
    try { qr.innerHTML = window.KurootoQR.svg(url); } catch (e) { qr.hidden = true; }
    box.appendChild(qr);
    box.appendChild(el('p', 'small', 'The same link as a QR code, to build the Shortcut on another Apple device (an iPad or Mac signed in to your Apple ID gets it too).'));
    var ol = el('ol');
    ol.appendChild(rich('li', ['Open the ', ['b', 'Shortcuts'], ' app, tap ', ['b', '+'], ' and name the new shortcut ', ['b', 'Tell Kurooto'], ' (tap its name at the top, then Rename). The name is what you say to Siri.']));
    ol.appendChild(rich('li', ['Add the action ', ['b', 'Dictate Text'], ' (type "dictate" in the search box).']));
    ol.appendChild(rich('li', ['Add ', ['b', 'Get Contents of URL'], ' and paste your link where it says URL. Tap the arrow to show more: Method ', ['b', 'POST'], ', Request Body ', ['b', 'JSON'], ', Add new field → ', ['b', 'Text'], ', key ', ['code', 'text'], ', and for its value pick ', ['b', 'Dictated Text'], '.']));
    ol.appendChild(rich('li', ['Add ', ['b', 'Speak Text'], ' (or Show Result) with ', ['b', 'Contents of URL'], ', so you hear the answer.']));
    ol.appendChild(rich('li', ['Tap ', ['b', 'Done'], ', run it once and say something. When it asks to connect to your call line, tap ', ['b', 'Always Allow'], '.']));
    box.appendChild(ol);
    box.appendChild(rich('p', [['b', 'Siri: '], 'say "Hey Siri, Tell Kurooto", then what you want ("remind me at 9 to call the bank").']));
    box.appendChild(rich('p', [['b', 'Back Tap: '], 'Settings → Accessibility → Touch → Back Tap → Double Tap (or Triple Tap) → Tell Kurooto. On an iPhone with an Action button: Settings → Action Button → Shortcut → Tell Kurooto.']));
    box.appendChild(el('p', '', 'Kurooto\'s first answer is read out ("On it." for longer jobs); the full answer comes in the chat. With your computer off, your message waits on your call line.'));
    box.appendChild(el('p', 'small', 'Keep the link to yourself: anyone who has it can send Kurooto messages as this phone (only messages: it opens nothing else). To stop it, make a new link here or remove it, or revoke it on your computer (dashboard → Phone).'));
    var row = el('div', 'row');
    var again = el('button', 'quiet', 'New link');
    again.onclick = function () { if (confirm('Make a new link? The old one stops working: paste the new one into your Shortcut.')) make(); };
    var off = el('button', 'quiet', 'Remove');
    off.onclick = remove;
    row.appendChild(again);
    row.appendChild(off);
    box.appendChild(row);
  }

  // what the call line knows (it may have been revoked on the computer); make one if this phone has none yet and the
  // page asks for it (data-auto: right after pairing an iPhone)
  function load() {
    if (!get('kurootoDevice')) { render(''); say('Pair this phone first: on your computer, Kurooto → Phone → Pair a phone.', true); return; }
    var kept = get('kurootoTell');
    call('/shortcut').then(function (res) {
      var s = res[0] === 200 ? res[1].shortcut : null;
      if (s && kept && kept.indexOf('/tell/tk1.' + s.id + '.') > 0) { render(kept); return; }
      if (kept) set('kurootoTell', '');
      if (res[0] === 200 && box.hasAttribute('data-auto') && !s) { make(); return; }
      render('');
      if (s) say('This phone has a Shortcut link made elsewhere (or this app\'s storage was cleared). Make a new link to see it here; the old one stops working.');
      else if (kept) say('Your old link was revoked. Make a new one and paste it into your Shortcut.', true);
      else if (res[0] !== 200) say(res[1].error || 'Couldn\'t ask your call line.', true);
    }).catch(function () { render(kept); if (!kept) say('Couldn\'t reach your call line. Is this phone online?', true); });
  }

  window.KurootoShortcut = { load: load };
  if (!box.hidden) load();
})();
