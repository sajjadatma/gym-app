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
