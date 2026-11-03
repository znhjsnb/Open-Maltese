/* Network-first shell; generated data has its own content-addressed shard cache. */
const CACHE = 'open-malti-shell-v2';
const SHELL = ['./','./index.html','./styles.css','./app.js','./worker.js','./db.js','./audio.js'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) { const copy = response.clone(); event.waitUntil(caches.open(CACHE).then(c => c.put(event.request,copy))); }
    return response;
  }).catch(async () => (await caches.match(event.request)) || Response.error()));
});
