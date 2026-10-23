// Kurooto's service worker: turns a push (it carries nothing) into a notification. It asks the call line what's
// ringing or waiting, with this device's key: a call opens the call page, a question or message opens the inbox, and
// a chat message from Kurooto opens the chat (/talk; the newest few come with /pending as "chat").
function idb(mode, fn) {
  return new Promise(function (resolve) {
    try {
      var open = indexedDB.open('kurooto', 1);
      open.onupgradeneeded = function () { open.result.createObjectStore('kv'); };
      open.onsuccess = function () { fn(open.result.transaction('kv', mode).objectStore('kv'), resolve); };
      open.onerror = function () { resolve(''); };
    } catch (e) { resolve(''); }
  });
}
function idbGet(key) {
  return idb('readonly', function (s, done) { var r = s.get(key); r.onsuccess = function () { done(r.result || ''); }; r.onerror = function () { done(''); }; });
}
function idbPut(key, value) {
  return idb('readwrite', function (s, done) { var r = s.put(value, key); r.onsuccess = function () { done(true); }; r.onerror = function () { done(false); }; });
}

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });

// Notifications for things answered elsewhere (or expired) go away.
function tidy(items) {
  if (!self.registration.getNotifications) return Promise.resolve();
  var open = items.map(function (i) { return 'kurooto-' + i.id; });
  return self.registration.getNotifications().then(function (ns) {
    ns.forEach(function (n) { if (n.tag && n.tag !== 'kurooto-call' && n.tag !== 'kurooto' && open.indexOf(n.tag) < 0) n.close(); });
  }).catch(function () {});
}

// The newest thing this phone hasn't been shown yet: a question or message, else a chat message.
function showItem(items, name, chat) {
  return idbGet('seen').then(function (raw) {
    var seen = [];
    try { seen = JSON.parse(raw || '[]'); } catch (e) { seen = []; }
    var fresh = items.filter(function (i) { return seen.indexOf(i.id) < 0; });
    if (!fresh.length) fresh = (chat || []).filter(function (m) { return seen.indexOf(m.id) < 0; }).map(function (m) { return { id: m.id, title: m.title, text: m.text, kind: 'chat' }; });
    var it = fresh[fresh.length - 1];
    if (!it) return self.registration.showNotification(name, { body: 'Something new is waiting for you. Tap to see it.', data: { link: '/inbox' }, tag: 'kurooto' });
    var more = fresh.length > 1 ? ' (+' + (fresh.length - 1) + ' more)' : '';
    return idbPut('seen', JSON.stringify(seen.concat([it.id]).slice(-100))).then(function () {
      return self.registration.showNotification(it.title || name, {
        body: String(it.text || '').slice(0, 300) + more, data: { link: it.kind === 'chat' ? '/talk' : '/inbox#' + it.id }, tag: 'kurooto-' + it.id,
        requireInteraction: it.kind === 'question' || it.kind === 'approval',
      });
    });
  });
}

self.addEventListener('push', function (event) {
  event.waitUntil(idbGet('device').then(function (key) {
    return fetch('/pending', { headers: { 'x-call-secret': key } }).then(function (r) { return r.json(); });
  }).then(function (j) {
    var ring = (j.rings || [])[0];
    var items = j.items || [];
    var name = j.assistant || 'Kurooto'; // your assistant's current name (it can be renamed on your computer)
    return Promise.all([tidy(items), j.assistant ? idbPut('assistant', j.assistant) : null]).then(function () {
      if (ring) {
        return self.registration.showNotification(ring.alarm ? 'Wake-up call' : name + ' is calling', {
          body: ring.reason || 'Tap to answer', data: { link: ring.link }, tag: 'kurooto-call', renotify: true, requireInteraction: true,
        });
      }
      return showItem(items, name, j.chat);
    });
  }).catch(function () {
    // iOS drops the subscription if a push shows nothing, so always show something
    return idbGet('assistant').then(function (name) {
      return self.registration.showNotification(name || 'Kurooto', { body: 'Something came in. Tap to see it.', data: { link: '/inbox' }, tag: 'kurooto' });
    });
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var link = (event.notification.data && event.notification.data.link) || '/';
  event.waitUntil(self.clients.openWindow(link));
});
