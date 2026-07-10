// 살롱 컨시어지 PWA — 최소 오프라인 셸 캐시
const CACHE = 'concierge-app-v2';
const ASSETS = ['./index.html', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  // 데이터(JSON)는 항상 네트워크 우선, 셸은 캐시 우선
  if (e.request.url.indexOf('/data/') !== -1) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).catch(() => caches.match('./index.html'))));
});
