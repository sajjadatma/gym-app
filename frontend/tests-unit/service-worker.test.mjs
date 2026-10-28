import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import path from "node:path"
import test from "node:test"
import vm from "node:vm"

const TOKEN = "__FORMYAR_BUILD_ID__"
const BUILD_ID = "abc123def4567890"
const CACHE_NAME = `formyar-shell-${BUILD_ID}`
const workerPath = path.resolve(import.meta.dirname, "../public/sw.js")

class FakeCache {
  entries = new Map()
  putCalls = 0
  deleteCalls = 0
  addAllCalls = []
  async put(request, response) {
    this.putCalls += 1
    this.entries.set(
      typeof request === "string" ? request : request.url,
      response,
    )
  }
  async match(request) {
    const response = this.entries.get(
      typeof request === "string" ? request : request.url,
    )
    return response?.clone()
  }
  async delete(request) {
    this.deleteCalls += 1
    this.entries.delete(typeof request === "string" ? request : request.url)
  }
  async addAll(requests) {
    this.addAllCalls.push([...requests])
  }
}

class FakeCacheStorage {
  caches = new Map()
  deleted = []
  constructor(seed = {}) {
    for (const [name, cache] of Object.entries(seed))
      this.caches.set(name, cache)
  }
  async open(name) {
    if (!this.caches.has(name)) this.caches.set(name, new FakeCache())
    return this.caches.get(name)
  }
  async keys() {
    return [...this.caches.keys()]
  }
  async delete(name) {
    this.deleted.push(name)
    return this.caches.delete(name)
  }
}

async function loadWorker({
  storage = new FakeCacheStorage(),
  replies = [],
  fetchImpl,
} = {}) {
  const source = (await readFile(workerPath, "utf8"))
    .split(TOKEN)
    .join(BUILD_ID)
    .split("__FORMYAR_PRECACHE_ASSETS__")
    .join('"/assets/app.js",\n  "/assets/app.css",')
  const listeners = {}
  let claimCalls = 0
  let skipWaitingCalls = 0
  const fetches = [...replies]
  const self = {
    location: { origin: "http://localhost" },
    addEventListener: (type, handler) => {
      listeners[type] = handler
    },
    skipWaiting: () => {
      skipWaitingCalls += 1
    },
    clients: {
      claim: async () => {
        claimCalls += 1
      },
    },
  }
  const fetch = async (input, init) => {
    if (fetchImpl) return fetchImpl(input, init)
    if (fetches.length) {
      const reply = fetches.shift()
      if (reply instanceof Error) throw reply
      return reply
    }
    const url = typeof input === "string" ? input : input.url
    const isAsset = url.includes("/assets/")
    return new Response(isAsset ? "asset" : "<!doctype html>", {
      status: 200,
      headers: {
        "content-type": isAsset ? "text/javascript" : "text/html",
      },
    })
  }
  const context = vm.createContext({
    self,
    caches: storage,
    fetch,
    Response,
    URL,
    console,
  })
  vm.runInContext(source, context)
  return {
    listeners,
    storage,
    get claimCalls() {
      return claimCalls
    },
    get skipWaitingCalls() {
      return skipWaitingCalls
    },
  }
}

function eventFor(request) {
  let responsePromise
  const waits = []
  return {
    request,
    waitUntil: (promise) => waits.push(promise),
    respondWith: (promise) => {
      responsePromise = promise
    },
    async response() {
      return await responsePromise
    },
    async drain() {
      await Promise.all(waits)
    },
  }
}

test("install precaches the complete build without taking over open tabs", async () => {
  const storage = new FakeCacheStorage()
  const worker = await loadWorker({ storage })
  const event = eventFor({})
  worker.listeners.install(event)
  await event.drain()
  const cache = await storage.open(CACHE_NAME)
  assert.ok(cache.entries.has("/"))
  assert.ok(cache.entries.has("/assets/app.js"))
  assert.ok(cache.entries.has("/assets/app.css"))
  assert.equal(cache.putCalls, 6)
  assert.equal(worker.skipWaitingCalls, 0)
})

test("install fails instead of caching an HTML fallback as a build asset", async () => {
  const worker = await loadWorker({
    fetchImpl: async (input) => {
      const url = typeof input === "string" ? input : input.url
      const isAsset = url.includes("/assets/")
      return new Response(isAsset ? "<!doctype html>" : "shell", {
        status: 200,
        headers: { "content-type": "text/html" },
      })
    },
  })
  const event = eventFor({})
  worker.listeners.install(event)
  await assert.rejects(() => event.drain(), /Precache returned HTML/)
})

test("activation removes only obsolete FormYar caches", async () => {
  const storage = new FakeCacheStorage({
    "formyar-shell-v1": new FakeCache(),
    [CACHE_NAME]: new FakeCache(),
    "unrelated-cache": new FakeCache(),
  })
  const worker = await loadWorker({ storage })
  const event = eventFor({})
  worker.listeners.activate(event)
  await event.drain()
  assert.deepEqual(storage.deleted, ["formyar-shell-v1"])
  assert.equal(worker.claimCalls, 1)
  assert.equal(worker.skipWaitingCalls, 0)
})

test("navigation bypasses the HTTP cache instead of trusting stale HTML", async () => {
  let navigationInit
  const worker = await loadWorker({
    fetchImpl: async (_input, init) => {
      navigationInit = init
      return new Response("fresh shell", {
        status: 200,
        headers: { "content-type": "text/html" },
      })
    },
  })
  const event = eventFor({
    method: "GET",
    url: "http://localhost/login",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "fresh shell")
  assert.equal(navigationInit.cache, "no-store")
})

test("navigation keeps the installed shell and never replaces it with a newer build", async () => {
  const storage = new FakeCacheStorage({ [CACHE_NAME]: new FakeCache() })
  const cache = await storage.open(CACHE_NAME)
  await cache.put("/", new Response("old shell"))
  const worker = await loadWorker({
    storage,
    replies: [
      new Response("new shell", {
        status: 200,
        headers: { "content-type": "text/html; charset=utf-8" },
      }),
      new Response("server error", {
        status: 500,
        headers: { "content-type": "text/html" },
      }),
      new Error("offline"),
    ],
  })

  let event = eventFor({
    method: "GET",
    url: "http://localhost/login",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "new shell")
  await event.drain()
  assert.equal(await (await cache.match("/")).text(), "old shell")

  event = eventFor({
    method: "GET",
    url: "http://localhost/login",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "server error")
  await event.drain()
  assert.equal(await (await cache.match("/")).text(), "old shell")

  event = eventFor({
    method: "GET",
    url: "http://localhost/athletes",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "old shell")
})

test("HTML fallbacks are never cached or served for asset URLs", async () => {
  const storage = new FakeCacheStorage({ [CACHE_NAME]: new FakeCache() })
  const worker = await loadWorker({
    storage,
    replies: [
      new Response("<!doctype html>", {
        status: 200,
        headers: { "content-type": "text/html" },
      }),
    ],
  })
  const event = eventFor({
    method: "GET",
    url: "http://localhost/assets/index.css",
  })
  worker.listeners.fetch(event)
  const response = await event.response()
  assert.equal(response.status, 404)
  assert.equal(
    response.headers.get("content-type"),
    "text/plain; charset=utf-8",
  )
  await event.drain()
  const cache = await storage.open(CACHE_NAME)
  assert.equal(cache.putCalls, 0)
})

test("a cached HTML fallback is evicted before fetching the real asset", async () => {
  const storage = new FakeCacheStorage({ [CACHE_NAME]: new FakeCache() })
  const cache = await storage.open(CACHE_NAME)
  const url = "http://localhost/assets/index.css"
  await cache.put(
    url,
    new Response("<!doctype html>", {
      status: 200,
      headers: { "content-type": "text/html" },
    }),
  )
  const worker = await loadWorker({
    storage,
    replies: [
      new Response("real css", {
        status: 200,
        headers: { "content-type": "text/css" },
      }),
    ],
  })
  const event = eventFor({ method: "GET", url })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "real css")
  await event.drain()
  assert.equal(cache.deleteCalls, 1)
  const cached = await cache.match(url)
  assert.equal(cached.headers.get("content-type"), "text/css")
})

test("only successful static responses enter this build cache and APIs are untouched", async () => {
  const storage = new FakeCacheStorage({ [CACHE_NAME]: new FakeCache() })
  const worker = await loadWorker({
    storage,
    replies: [
      new Response("asset", { status: 200 }),
      new Response("missing", { status: 404 }),
    ],
  })

  let event = eventFor({ method: "GET", url: "http://localhost/assets/app.js" })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "asset")
  await event.drain()
  const cache = await storage.open(CACHE_NAME)
  assert.equal(cache.putCalls, 1)

  event = eventFor({ method: "GET", url: "http://localhost/assets/missing.js" })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "missing")
  await event.drain()
  assert.equal(cache.putCalls, 1)

  event = eventFor({ method: "GET", url: "http://localhost/api/v1/athletes" })
  worker.listeners.fetch(event)
  assert.equal(await event.response(), undefined)
  assert.equal(cache.putCalls, 1)
})

test("missing offline shell returns a network error response", async () => {
  const worker = await loadWorker({ replies: [new Error("offline")] })
  const event = eventFor({
    method: "GET",
    url: "http://localhost/login",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal((await event.response()).type, "error")
})
