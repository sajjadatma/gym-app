import { expect, type Page, test } from "@playwright/test"

const SUPERUSER_EMAIL = process.env.PLAYWRIGHT_SUPERUSER_EMAIL
const SUPERUSER_PASSWORD = process.env.PLAYWRIGHT_SUPERUSER_PASSWORD

test.skip(
  !SUPERUSER_EMAIL || !SUPERUSER_PASSWORD,
  "PLAYWRIGHT_SUPERUSER_EMAIL/PASSWORD not configured",
)

export async function loginAsSuperuser(page: Page) {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(SUPERUSER_EMAIL!)
  await page.getByLabel(/رمز عبور/).fill(SUPERUSER_PASSWORD!)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL("**/")
}

test("superuser lands globally without a club context", async ({ page }) => {
  await loginAsSuperuser(page)
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await expect(page.locator(".m3-topbar__gym")).toHaveCount(0)
  await expect(page.locator(".m3-topbar__role")).toHaveCount(0)
  await expect(page.getByText("باشگاه آرام").first()).toBeVisible()
  await expect(
    page.getByRole("button", { name: "ورود به باشگاه" }).first(),
  ).toBeVisible()
})

test("superuser with no clubs is sent to the clubs page with a create action", async ({
  page,
}) => {
  await page.route(/\/api\/v1\/gyms\/?(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { data: [] } })
      return
    }
    await route.continue()
  })
  await loginAsSuperuser(page)
  await expect(page).toHaveURL((url) => url.pathname === "/gyms")
  await expect(
    page.getByRole("button", { name: "ایجاد باشگاه" }).first(),
  ).toBeVisible()
})
