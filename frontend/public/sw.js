/**
 * Service worker: cache-first for static assets, network-first for API,
 * background sync for pending bills.
 */

const CACHE_NAME = "ayy-pos-v1";
const API_CACHE = "ayy-api-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME && k !== API_CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Cache-first for static assets
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    // Network-first for API calls
    event.respondWith(
      fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(API_CACHE).then((cache) => cache.put(event.request, clone));
        return response;
      }).catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first for everything else
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});

// Background sync for pending bills
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-pending-bills") {
    event.waitUntil(window.clients.matchAll().then((clients) => {
      return clients[0]?.postMessage({ type: "BACKGROUND_SYNC" });
    }));
  }
});
