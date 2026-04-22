/**
 * AYY-26 — Service Worker for POS terminal offline support.
 *
 * Strategy:
 * - Static assets: cache-first (cached at build time)
 * - API calls: network-first with fallback to cache
 * - Bills: stored in IndexedDB, not in cache
 */

const CACHE_NAME = 'ayy-pos-v0.1';
const OFFLINE_QUEUE_DB = 'ayy-pos-queue';
const OFFLINE_QUEUE_STORE = 'pending-bills';

// Install — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/index.html',
        '/static/js/main.js',
      ]);
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch — network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API calls: network-first
  if (url.pathname.startsWith('/till/') || url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => {
          // Network-first failed, try cache
          return caches.match(event.request);
        })
    );
    return;
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

// Background sync for pending bills
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-pending-bills') {
    event.waitUntil(syncPendingBills());
  }
});

async function syncPendingBills() {
  // This is handled by the main thread via the database,
  // but we set up the sync here for the background sync API.
  const clients = await self.clients.matchAll();
  clients.forEach((client) => {
    client.postMessage({ type: 'SYNC_AVAILABLE' });
  });
}
