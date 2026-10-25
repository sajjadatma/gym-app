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

test("entering a club opens its workspace and keeps the club on reload", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")
  await expect(page.locator(".m3-topbar__role").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "ورزشکاران" }),
  ).toBeVisible()

  await page.reload()
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
})

test("club settings live on their own route", async ({ page }) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await page.getByRole("button", { name: "تنظیمات باشگاه" }).click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/settings$/)
  await expect(page.getByRole("heading", { name: "باشگاه آرام" })).toBeVisible()
  await expect(
    page.getByRole("button", { name: "ویرایش", exact: true }),
  ).toBeVisible()

  await page.reload()
  await expect(page.getByRole("heading", { name: "باشگاه آرام" })).toBeVisible()
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")
})

test("all clubs leaves the club from a workspace page and returns to the global view", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes\/?$/)
  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: "همه باشگاه‌ها" }).click()
  await expect(page).toHaveURL((url) => url.pathname === "/")
  await expect(page.locator(".m3-topbar__gym")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "ورود به باشگاه" }).first(),
  ).toBeVisible()
})

test("switching clubs from the workspace changes the club and keeps a club URL", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")

  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: /باشگاه پویا/ }).click()

  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه پویا")
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await page.reload()
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه پویا")
})

test("club workspace highlights the dashboard item and keeps its URL", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  const workspace = page.url()

  await expect(
    page.locator(".m3-nav-rail__item[aria-current='page']"),
  ).toHaveText(/داشبورد/)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "باشگاه‌ها" }),
  ).not.toHaveAttribute("aria-current", "page")

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "داشبورد" })
    .click()
  await expect(page).toHaveURL(workspace)
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")
})

test("club cards on the clubs list link into the workspace", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.goto("/gyms")
  const firstCard = page.locator(".m3-entity-card").first()
  await expect(firstCard).toContainText("ورود به باشگاه")
  await expect(firstCard).not.toContainText("جزئیات باشگاه")
})

test("club-scoped deep links without a club return to the clubs list", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.goto("/athletes")
  await expect(page).toHaveURL((url) => url.pathname === "/gyms")
})
