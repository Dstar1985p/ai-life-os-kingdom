/* Kingdom AI Service Worker — v1.0 */
const CACHE_NAME = 'kingdom-v1';
const STATIC_ASSETS = ['/', '/manifest.json', '/icon-192.svg', '/icon-512.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* Network-first for API calls, cache-first for static assets */
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/agents') ||
      url.pathname.startsWith('/opportunities') || url.pathname.startsWith('/images')) {
    // Network-first: always fresh data
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }

  // Cache-first for static shell
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
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
      icon: '/icon-192.svg',
      badge: '/icon-192.svg',
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
