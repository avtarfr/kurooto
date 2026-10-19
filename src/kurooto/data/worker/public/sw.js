// Kurooto's service worker: turns a call push (no payload) into a notification. It asks the call line what's
// ringing with this device's key, and opens the call when you tap it.
function idbGet(key) {
  return new Promise(function (resolve) {
    try {
      var open = indexedDB.open('kurooto', 1);
      open.onupgradeneeded = function () { open.result.createObjectStore('kv'); };
      open.onsuccess = function () { var r = open.result.transaction('kv').objectStore('kv').get(key); r.onsuccess = function () { resolve(r.result || ''); }; r.onerror = function () { resolve(''); }; };
      open.onerror = function () { resolve(''); };
    } catch (e) { resolve(''); }
  });
}

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });

self.addEventListener('push', function (event) {
  event.waitUntil(idbGet('device').then(function (key) {
    return fetch('/pending', { headers: { 'x-call-secret': key } }).then(function (r) { return r.json(); });
  }).then(function (j) {
    var ring = (j.rings || [])[0];
    if (!ring) return self.registration.showNotification('Kurooto', { body: 'A call came in. Tap to call back.', data: { link: '/' }, tag: 'kurooto-call' });
    return self.registration.showNotification(ring.alarm ? 'Wake-up call' : 'Kurooto is calling', {
      body: ring.reason || 'Tap to answer', data: { link: ring.link }, tag: 'kurooto-call', renotify: true, requireInteraction: true,
    });
  }).catch(function () {
    // iOS drops the subscription if a push shows nothing, so always show something
    return self.registration.showNotification('Kurooto', { body: 'A call came in. Tap to call back.', data: { link: '/' }, tag: 'kurooto-call' });
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var link = (event.notification.data && event.notification.data.link) || '/';
  event.waitUntil(self.clients.openWindow(link));
});
