/* Kingdom AI Service Worker — v1.2 */
const CACHE_NAME = 'kingdom-v3';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  // Delete ALL old caches on activate
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

/* Network-first for everything — always serve fresh content */
self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

/* Push notification handler */
self.addEventListener('push', (e) => {
  if (!e.data) return;
  let data;
  try { data = e.data.json(); } catch { data = { title: 'Kingdom', body: e.data.text() }; }

  e.waitUntil(
    self.registration.showNotification(data.title || 'Kingdom AI', {
      body: data.body || 'New update from your Kingdom',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: data.tag || 'kingdom-general',
      renotify: true,
      data: { url: data.url || '/' },
      actions: data.actions || [],
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const target = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      const existing = wins.find((w) => w.url.includes(self.location.origin));
      if (existing) {
        existing.focus();
        existing.navigate(target);
      } else {
        clients.openWindow(target);
      }
    })
  );
});
