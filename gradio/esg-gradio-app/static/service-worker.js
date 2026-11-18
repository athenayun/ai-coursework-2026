const CACHE = 'open-data-static-v1';
const ASSETS = ['/offline.html', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', event => {
  const req = event.request;
  // Never cache API responses, downloaded CSVs, or dynamic Gradio traffic.
  if (req.method !== 'GET') return;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match('/offline.html')));
  } else if (ASSETS.includes(new URL(req.url).pathname)) {
    event.respondWith(caches.match(req).then(cached => cached || fetch(req)));
  }
});
