/* AI Time Keeper — service worker
   শুধু অ্যাপ-আইকন/ম্যানিফেস্ট/CDN ক্যাশ হয় — HTML বা /api/ কখনো নয়,
   যাতে আপডেট আর ডেটা সবসময় টাটকা থাকে। */
const CACHE = 'atk-shell-v1';
const ASSETS = ['/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png', '/manifest.webmanifest'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  const u = new URL(e.request.url);
  if (u.origin !== location.origin) {
    // CDN (Chart.js) — cache-first, নেট না থাকলেও চার্ট চলবে
    if (u.hostname.includes('jsdelivr') || u.hostname.includes('cdn.sheetjs')) {
      e.respondWith(caches.match(e.request).then(function (r) {
        return r || fetch(e.request).then(function (r2) {
          const cl = r2.clone();
          caches.open(CACHE).then(function (c) { c.put(e.request, cl); });
          return r2;
        });
      }).catch(function () { return caches.match(e.request); }));
    }
    return;
  }
  if (u.pathname.startsWith('/api/')) return;   // ডেটা সবসময় লাইভ
  if (ASSETS.indexOf(u.pathname) !== -1) {
    e.respondWith(caches.match(e.request).then(function (r) { return r || fetch(e.request); }));
  }
});
