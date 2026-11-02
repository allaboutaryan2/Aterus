'use strict';
// Cache only the public application shell. API responses, credentials, terminal
// transcripts and project files never enter Cache Storage.
const CACHE = 'aterus-shell-v4';
const PUBLIC = ['/', '/app.js', '/style.css', '/pwa.js', '/pwa.css', '/connect-phone.js', '/connect-phone.css', '/manifest.webmanifest', '/icon.svg', '/icon-180.png', '/icon-192.png', '/icon-512.png', '/vendor/xterm.js', '/vendor/xterm.css'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('aterus-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.search || !PUBLIC.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(url.pathname, copy)));
    }
    return response;
  }).catch(async () => {
    const cached = await caches.match(url.pathname);
    return cached || Response.error();
  }));
});

self.addEventListener('message', event => { if(event.data?.type === 'ATERUS_ACTIVATE_UPDATE') self.skipWaiting(); });
