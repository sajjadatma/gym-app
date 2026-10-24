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
  async addAll() {}
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
} = {}) {
  const source = (await readFile(workerPath, "utf8"))
    .split(TOKEN)
    .join(BUILD_ID)
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
  const fetch = async () => {
    const reply = fetches.shift()
    if (reply instanceof Error) throw reply
    return reply
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

test("navigation caches only successful HTML shells and keeps the last good shell offline", async () => {
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
  assert.equal(await (await cache.match("/")).text(), "new shell")

  event = eventFor({
    method: "GET",
    url: "http://localhost/login",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "server error")
  await event.drain()
  assert.equal(await (await cache.match("/")).text(), "new shell")

  event = eventFor({
    method: "GET",
    url: "http://localhost/athletes",
    mode: "navigate",
  })
  worker.listeners.fetch(event)
  assert.equal(await (await event.response()).text(), "new shell")
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
