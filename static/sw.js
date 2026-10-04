// Prayash: online-first, with a generic offline page and public assets only.
const STATIC_CACHE = "prayash-static-v2";
const OFFLINE_PAGE = "/static/offline.html";
const PUBLIC_ASSETS = new Map([
  ["/static/styles.css", ["text/css"]],
  ["/static/script.js", ["text/javascript", "application/javascript"]],
  ["/static/manifest.json", ["application/json", "application/manifest+json"]],
  ["/static/icons/icon-192x192.png", ["image/png"]],
  ["/static/icons/icon-512x512.png", ["image/png"]],
  [OFFLINE_PAGE, ["text/html"]],
]);

// Only installation writes to Cache Storage. Fetch these fixed public files
// without cookies, redirects, or HTTP-cache reuse; never store page/API fetches.
self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const assets = await Promise.all(Array.from(PUBLIC_ASSETS, async ([path, types]) => {
      const url = new URL(path, self.location.origin).href;
      const response = await fetch(url, {
        credentials: "omit", cache: "no-store", redirect: "error",
      });
      const type = (response.headers.get("Content-Type") || "").split(";")[0].trim();
      const policy = response.headers.get("Cache-Control") || "";
      const vary = response.headers.get("Vary") || "";
      // Flask adds Vary: Cookie even to public files. These fixed requests
      // omit credentials, so that header does not make them user-specific.
      if (response.status !== 200 || response.type !== "basic" ||
          response.redirected || response.url !== url || !types.includes(type) ||
          /(?:private|no-store)/i.test(policy) || /(?:\*|authorization)/i.test(vary)) {
        throw new Error(`Unsafe or unavailable PWA asset: ${path}`);
      }
      return [path, response];
    }));
    const cache = await caches.open(STATIC_CACHE);
    await Promise.all(assets.map(([path, response]) => cache.put(path, response)));
    // Normal updates wait for the existing user-controlled Refresh action.
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => /^prayash-(?:static|dynamic)-v\d+$/.test(name) && name !== STATIC_CACHE)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    event.waitUntil(self.skipWaiting());
  }
});

async function offlinePage() {
  const page = await caches.open(STATIC_CACHE)
    .then((cache) => cache.match(OFFLINE_PAGE)).catch(() => null);
  // Storage may have been evicted after installation. Still return no user data.
  return page || new Response(
    '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Offline - Prayash</title><h1>You are offline</h1><p>Reconnect to use Prayash.</p><a href="">Retry</a></html>',
    { status: 503, headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src \'none\'; base-uri \'none\'; frame-ancestors \'none\'",
    } }
  );
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  // APIs (even direct navigations), streams, foreign origins, and mutations
  // bypass the worker entirely. Their errors must never become offline HTML.
  if (request.method !== "GET" || url.origin !== self.location.origin ||
      url.pathname === "/api" || url.pathname.startsWith("/api/") ||
      (request.headers.get("Accept") || "").includes("text/event-stream")) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request, { cache: "no-store" }).catch(offlinePage));
    return;
  }

  // An exact allowlist, with only the existing public asset-version parameter.
  // Runtime responses are NEVER cached, including redirects and error bodies.
  if (!PUBLIC_ASSETS.has(url.pathname) ||
      (url.search && !/^\?v=[a-zA-Z0-9_-]{1,64}$/.test(url.search))) return;
  event.respondWith(fetch(request).catch(async () => {
    const cache = await caches.open(STATIC_CACHE);
    return (await cache.match(url.pathname)) || Response.error();
  }));
});
