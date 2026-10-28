import { expect, test } from "@playwright/test"

test("PWA manifest and install assets are available", async ({
  page,
  request,
}) => {
  await page.goto("/login")
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    "href",
    "/manifest.webmanifest",
  )
  const manifestResponse = await request.get("/manifest.webmanifest")
  expect(manifestResponse.ok()).toBeTruthy()
  const manifest = await manifestResponse.json()
  expect(manifest.display).toBe("standalone")
  expect(manifest.lang).toBe("fa")
  expect(manifest.dir).toBe("rtl")
  expect(
    manifest.icons.some((icon: { sizes: string }) => icon.sizes === "192x192"),
  ).toBe(true)
  expect(
    manifest.icons.some((icon: { sizes: string }) => icon.sizes === "512x512"),
  ).toBe(true)
  for (const icon of manifest.icons) {
    const iconResponse = await request.get(icon.src)
    expect(iconResponse.ok()).toBeTruthy()
  }
  const swResponse = await request.get("/sw.js")
  expect(swResponse.ok()).toBeTruthy()
  expect(await swResponse.text()).toContain('addEventListener("fetch"')

  if (process.env.PWA_PROD === "1") {
    await page.goto("/")
    await page.waitForFunction(async () => {
      const registration = await navigator.serviceWorker.getRegistration()
      return Boolean(registration)
    })
    const registered = await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.getRegistration()
      return Boolean(registration)
    })
    expect(registered).toBe(true)
  }
})

test("production worker controls a warmed shell without caching private API data", async ({
  browser,
}) => {
  test.skip(process.env.PWA_PROD !== "1", "production build only")
  const origin = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8000"
  const context = await browser.newContext()
  const page = await context.newPage()
  try {
    await page.goto(`${origin}/manifest.webmanifest`)
    await page.evaluate(async () => {
      const cache = await caches.open("unrelated-cache")
      await cache.put("/sentinel", new Response("keep"))
    })

    await page.goto(`${origin}/login`)
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready
      if (!navigator.serviceWorker.controller) {
        await new Promise<void>((resolve) => {
          navigator.serviceWorker.addEventListener(
            "controllerchange",
            () => resolve(),
            { once: true },
          )
        })
      }
    })
    await page.reload()
    await page.waitForFunction(() =>
      Boolean(navigator.serviceWorker.controller),
    )

    const keys = await page.evaluate(async () => caches.keys())
    const shellKey = keys.find((key) => key.startsWith("formyar-shell-"))
    expect(shellKey).toBeTruthy()
    expect(keys).toContain("unrelated-cache")
    const buildId = shellKey!.replace("formyar-shell-", "")
    const workerText = await (
      await context.request.get(`${origin}/sw.js`)
    ).text()
    expect(workerText).toContain(`const BUILD_ID = "${buildId}"`)

    await page.waitForFunction(async () => {
      const keys = await caches.keys()
      const key = keys.find((value) => value.startsWith("formyar-shell-"))
      if (!key) return false
      const cache = await caches.open(key)
      return Boolean(await cache.match("/"))
    })

    await context.setOffline(true)
    await page.reload()
    await expect(
      page.getByRole("button", { name: "ورود", exact: true }),
    ).toBeVisible()
    await context.setOffline(false)

    const cachedApiRequests = await page.evaluate(async () => {
      const keys = await caches.keys()
      const urls: string[] = []
      for (const key of keys) {
        const cache = await caches.open(key)
        for (const request of await cache.keys()) urls.push(request.url)
      }
      return urls.filter((url) => url.includes("/api/"))
    })
    expect(cachedApiRequests).toEqual([])
  } finally {
    await context.close()
  }
})

test("missing hashed assets never fall back to the HTML shell", async ({
  request,
}) => {
  test.skip(process.env.PWA_PROD !== "1", "production build only")
  const response = await request.get("/assets/definitely-missing.js")
  expect(response.status()).toBe(404)
  expect(response.headers()["content-type"] ?? "").not.toContain("text/html")
})
