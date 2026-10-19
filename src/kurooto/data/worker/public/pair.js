// Pairing: trade the one-time code from your computer (QR or the link your bot sent) for this device's own key.
// Android gets the native app (it rings like a call); iPhone and others use this site as a home-screen app with
// call notifications (Web Push).
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var q = new URLSearchParams(location.search), h = new URLSearchParams(location.hash.slice(1));
  var code = (q.get('c') || h.get('c') || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  if (location.hash) history.replaceState(null, '', location.pathname + (code ? '?c=' + code : ''));
  var ua = navigator.userAgent;
  var ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var android = /Android/.test(ua);
  var standalone = navigator.standalone === true || (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
  var get = function (k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } };
  var set = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } };

  function msg(text, bad) { var m = $('msg'); m.hidden = false; m.textContent = text; m.className = 'card' + (bad ? ' err' : ''); }
  function show(id) { ['android', 'ios', 'web', 'done'].forEach(function (s) { $(s).hidden = s !== id; }); }

  // the service worker reads the device key from IndexedDB (it can't see localStorage)
  function idbPut(key, value) {
    return new Promise(function (resolve) {
      try {
        var open = indexedDB.open('kurooto', 1);
        open.onupgradeneeded = function () { open.result.createObjectStore('kv'); };
        open.onsuccess = function () { var tx = open.result.transaction('kv', 'readwrite'); tx.objectStore('kv').put(value, key); tx.oncomplete = function () { resolve(true); }; tx.onerror = function () { resolve(false); }; };
        open.onerror = function () { resolve(false); };
      } catch (e) { resolve(false); }
    });
  }

  function claim() {
    if (!code) { msg('This link has no pairing code. On your computer, open Kurooto → Phone → Pair a phone.', true); return; }
    $('claim').disabled = true;
    fetch('/pair/claim', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ code: code, kind: 'web', name: ios ? 'iPhone' : android ? 'Android browser' : 'Browser' }) })
      .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
      .then(function (res) {
        $('claim').disabled = false;
        if (!res[0]) { msg(res[1].error || 'Pairing failed.', true); return; }
        set('kurootoDevice', res[1].device);
        if (res[1].vapid) set('kurootoVapid', res[1].vapid);
        idbPut('device', res[1].device);
        $('msg').hidden = true;
        show('done');
      })
      .catch(function () { $('claim').disabled = false; msg('Couldn\'t reach the call line. Is this phone online?', true); });
  }

  function b64urlToBytes(s) {
    var b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
    var out = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
    return out;
  }

  function notifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      msg(ios ? 'Notifications need the Home Screen app on iOS 16.4 or newer: add this page to your Home Screen and open it from there.' : 'This browser can\'t show call notifications.', true);
      return;
    }
    Notification.requestPermission().then(function (p) {
      if (p !== 'granted') { msg('Notifications are off for this site. Turn them on in Settings to get calls.', true); return; }
      return navigator.serviceWorker.register('/sw.js').then(function () { return navigator.serviceWorker.ready; }).then(function (reg) {
        return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64urlToBytes(get('kurootoVapid')) });
      }).then(function (sub) {
        return fetch('/push/subscribe', { method: 'POST', headers: { 'content-type': 'application/json', 'x-call-secret': get('kurootoDevice') }, body: JSON.stringify({ subscription: sub.toJSON() }) });
      }).then(function (r) {
        if (r.ok) { $('notify').hidden = true; $('donetext').textContent = 'Paired, with call notifications on. Keep Kurooto on your Home Screen; calls arrive as notifications you tap to answer.'; }
        else msg('Couldn\'t turn notifications on (the call line said no). Pair again from your computer.', true);
      });
    }).catch(function (e) { msg('Couldn\'t turn notifications on: ' + e.message, true); });
  }

  $('claim').onclick = claim;
  $('notify').onclick = notifications;
  $('useweb').onclick = function (e) { e.preventDefault(); show('web'); };

  if (get('kurootoDevice') && !code) { show('done'); return; }
  if (android) {
    var back = location.origin + '/pair#c=' + code;
    $('openapp').href = 'intent://pair?c=' + code + '&u=' + encodeURIComponent(location.origin) +
      '#Intent;scheme=kurooto;package=io.github.avtarfr.kurooto;S.browser_fallback_url=' + encodeURIComponent(back) + ';end';
    fetch('/kurooto.apk', { method: 'HEAD' }).then(function (r) { if (!r.ok) { $('apk').hidden = true; } }).catch(function () {});
    show('android');
  } else if (ios && !standalone) {
    // When added to the Home Screen, the app opens /pair?c=… (from this manifest) and pairs itself there.
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/manifest.webmanifest?c=' + code;
    document.head.appendChild(link);
    show('ios');
  } else if (get('kurootoDevice')) {
    show('done');
  } else {
    show('web');
    if (standalone && code) claim();
  }
})();
