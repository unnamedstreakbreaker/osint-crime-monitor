// Service worker: makes the board installable and usable offline.
// Pages and data: network first (always fresh when online), saved copy when offline.
// Icons, manifest and fonts: cache first (they rarely change).
const VERSION = "__VERSION__";
const CACHE = "crime-board-" + VERSION;
const CORE = ["./", "index.html", "te.html", "manifest.webmanifest", "manifest.te.webmanifest",
              "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "favicon-32.png",
              "status.json", "outlook.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.all(CORE.map((u) => c.add(u).catch(() => null))))   // one missing file must not block install
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("crime-board-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const bare = (url) => { const u = new URL(url); return u.origin + u.pathname; };   // drop ?t=… and #…

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const isFont = /(^|\.)fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (url.origin !== self.location.origin && !isFont) return;

  if (isFont || /\.(png|webmanifest)$/.test(url.pathname)) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }))
    );
    return;
  }

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(bare(req.url), copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(bare(req.url)).then((hit) =>
          hit || (req.mode === "navigate" ? caches.match(url.pathname.endsWith("te.html") ? "te.html" : "index.html") : undefined)
        ).then((hit) => hit || new Response("Offline and not saved yet.", {status: 503}))
      )
  );
});
