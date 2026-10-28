const BUILD_ID = "__FORMYAR_BUILD_ID__"
const CACHE_NAME = `formyar-shell-${BUILD_ID}`
const CACHE_PREFIX = "formyar-shell-"
const PRECACHE = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  __FORMYAR_PRECACHE_ASSETS__,
]

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)),
  )
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener("fetch", (event) => {
  const request = event.request
  if (request.method !== "GET") return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/docs"))
    return

  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request)
          if (
            response.ok &&
            response.headers
              .get("content-type")
              ?.toLowerCase()
              .includes("text/html")
          ) {
            const copy = response.clone()
            event.waitUntil(
              caches.open(CACHE_NAME).then((cache) => cache.put("/", copy)),
            )
          }
          return response
        } catch {
          const cache = await caches.open(CACHE_NAME)
          return (await cache.match("/")) ?? Response.error()
        }
      })(),
    )
    return
  }

  if (
    url.pathname.startsWith("/assets/") ||
    url.pathname.startsWith("/icons/")
  ) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME)
        const cached = await cache.match(request)
        if (cached) return cached
        try {
          const response = await fetch(request)
          if (response.ok) {
            const copy = response.clone()
            event.waitUntil(cache.put(request, copy))
          }
          return response
        } catch {
          return Response.error()
        }
      })(),
    )
  }
})
