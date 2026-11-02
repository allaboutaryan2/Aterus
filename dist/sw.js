'use strict';
const CACHE = 'aterus-portal-v1';
// Explicit public assets only. Never cache downloads, host addresses, queries,
// credentials, backend responses or traffic to a paired computer.
const SHELL = ['/', '/index.html', '/style.css', '/connect.js', '/install.js',
  '/manifest.webmanifest', '/icon.svg', '/icon-180.png', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith('aterus-portal-') && key !== CACHE)
    .map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      url.search || !SHELL.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(url.pathname, copy)));
    }
    return response;
  }).catch(async () => (await caches.match(url.pathname)) || Response.error()));
});
self.addEventListener('message', event => {
  if (event.data?.type === 'ATERUS_PORTAL_UPDATE') self.skipWaiting();
});
