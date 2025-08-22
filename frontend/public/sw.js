/* MoodMusic SW v2 */
const STATIC_CACHE = 'mm-static-v2';
const RUNTIME_CACHE = 'mm-runtime-v1';

const STATIC_ASSETS = [
  '/',               // shell
  '/index.html',     // explícito para fallback
  '/manifest.json',

  // 👇 Asegurate de que EXISTAN en public/icons/
  '/icons/MM192x192.png',
  '/icons/MM256x256.png',
  '/icons/MM384x384.png',
  '/icons/MM512x512.png'
];

// ---- helpers
const isHttp = (url) => url.protocol === 'http:' || url.protocol === 'https:';
const sameOrigin = (url) => url.origin === self.location.origin;

// Install: precache estático
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: limpiar versiones viejas
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => ![STATIC_CACHE, RUNTIME_CACHE].includes(k))
            .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // ❌ No cachear esquemas no http/https (ej: chrome-extension)
  if (!isHttp(url)) return;

  // Navegación: app shell
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(STATIC_CACHE);
      const cached = await cache.match('/index.html');
      try {
        const fresh = await fetch('/index.html', { cache: 'no-store' });
        // Sólo cacheamos si ok
        if (fresh.ok) cache.put('/index.html', fresh.clone());
        return fresh;
      } catch {
        return cached || Response.error();
      }
    })());
    return;
  }

  // Estáticos propios (icons/ y manifest)
  if (sameOrigin(url) && (url.pathname.startsWith('/icons/') || url.pathname === '/manifest.json')) {
    event.respondWith(
      caches.match(req).then(cached => cached || fetch(req).then(res => {
        if (req.method === 'GET' && res.ok) {
          caches.open(STATIC_CACHE).then(c => c.put(req, res.clone()));
        }
        return res;
      }))
    );
    return;
  }

  // Runtime cache para otras requests (APIs, etc.)
  event.respondWith((async () => {
    const cache = await caches.open(RUNTIME_CACHE);
    const cached = await cache.match(req);

    try {
      const fresh = await fetch(req);
      // Cachear sólo GET y respuestas ok
      if (req.method === 'GET' && fresh.ok) {
        cache.put(req, fresh.clone());
      }
      return fresh;
    } catch {
      if (cached) return cached;
      throw new Error('Network error and no cache');
    }
  })());
});
