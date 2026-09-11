const APP_CACHE = 'evolars-angola-shell-v1';
const COURSES_CACHE = 'evolars-angola-courses-v1';

const PRECACHE_URLS = [
  '/slides',
  '/slides/all',
  '/slides/offline',
  '/site.webmanifest',
  '/web/static/lib/pdfjs/build/pdf.js',
  '/web/static/lib/pdfjs/build/pdf.worker.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn('[SW] Falha no pré-cache parcial:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== APP_CACHE && key !== COURSES_CACHE)
            .map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignorar requisições não GET ou requisições internas do backend
  if (request.method !== 'GET' || url.pathname.startsWith('/web/session') || url.pathname.startsWith('/web/database')) {
    return;
  }

  // 1. PDFs e Conteúdos de Cursos: Cache-First
  if (url.pathname.includes('/binary_content') || url.pathname.endsWith('.pdf') || url.pathname.includes('/slide/')) {
    event.respondWith(
      caches.open(COURSES_CACHE).then((cache) => {
        return cache.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          return fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              cache.put(request, networkResponse.clone());
            }
            return networkResponse;
          });
        });
      })
    );
    return;
  }

  // 2. Navegação de páginas: Network-First com fallback para cache
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          const cloned = networkResponse.clone();
          caches.open(APP_CACHE).then((cache) => cache.put(request, cloned));
          return networkResponse;
        })
        .catch(() => {
          return caches.match(request).then((cached) => {
            return cached || caches.match('/slides/offline') || caches.match('/slides');
          });
        })
    );
    return;
  }

  // 3. Demais recursos estáticos: Stale-While-Revalidate
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          caches.open(APP_CACHE).then((cache) => cache.put(request, networkResponse.clone()));
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
