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
  ).toHaveCount(0)

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

test("the global athletes route lists athletes when no club is active", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.goto("/athletes")
  await expect(page).toHaveURL((url) => url.pathname === "/athletes")
  await expect(page.getByRole("heading", { name: "ورزشکاران" })).toBeVisible()
})

test("superuser inside a club hides the clubs nav and can return to the global dashboard", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "باشگاه‌ها" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "باشگاه‌ها" }),
  ).toHaveCount(0)

  const topbarBack = () =>
    page.locator(".m3-topbar").getByRole("button", { name: "داشبورد سراسری" })

  await expect(topbarBack()).toBeVisible()
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes$/)
  await expect(topbarBack()).toBeVisible()

  await topbarBack().click()
  await expect(page).toHaveURL((url) => url.pathname === "/")
  await expect(page.locator(".m3-topbar__gym")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "ورود به باشگاه" }).first(),
  ).toBeVisible()
})

test("global coaches and athletes pages manage people across clubs", async ({
  page,
}) => {
  const stamp = Date.now()
  const coachName = `مربی سراسری ${stamp}`
  const coachEmail = `global-coach-${stamp}@example.com`
  const coachPhone = "09125554433"
  const athleteName = `ورزشکار سراسری ${stamp}`
  const athleteEmail = `global-athlete-${stamp}@example.com`
  const athletePhone = "09127778899"

  await loginAsSuperuser(page)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "مربیان" }),
  ).toBeVisible()
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  await expect(page).toHaveURL(/\/coaches$/)

  await page.getByRole("button", { name: "افزودن مربی" }).click()
  let dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByLabel("نام و نام خانوادگی").fill(coachName)
  await dialog.getByLabel("ایمیل").fill(coachEmail)
  await dialog.getByLabel("شماره تلفن").fill(coachPhone)
  await dialog.getByRole("button", { name: "ایجاد" }).click()
  const coachResult = page.getByRole("dialog", { name: "مربی ساخته شد." })
  await expect(coachResult).toBeVisible()
  await coachResult.getByRole("button", { name: "بستن" }).last().click()
  await expect(coachResult).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await page.waitForTimeout(300)
  await expect(page.getByText(coachEmail)).toBeVisible()
  await expect(page.locator("tr", { hasText: coachEmail })).toContainText(
    "باشگاه آرام",
  )

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/athletes$/)
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByRole("button", { name: /مربی/ }).click()
  await page.getByRole("option", { name: coachName }).click()
  await dialog.getByLabel("نام و نام خانوادگی").fill(athleteName)
  await dialog.getByLabel("ایمیل").fill(athleteEmail)
  await dialog.getByLabel("شماره تلفن").fill(athletePhone)
  await dialog.getByRole("button", { name: "ایجاد" }).click()
  const athleteResult = page.getByRole("dialog", {
    name: "ورزشکار ساخته شد.",
  })
  await expect(athleteResult).toBeVisible()
  await athleteResult.getByRole("button", { name: "بستن" }).last().click()
  await expect(athleteResult).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await page.waitForTimeout(300)
  const athleteRow = page.locator("tr", { hasText: athleteEmail })
  await expect(athleteRow).toContainText("باشگاه آرام")
  await expect(athleteRow).toContainText(athletePhone)
  await athleteRow.getByRole("button", { name: "آرشیو" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "آرشیو" }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await page.getByRole("button", { name: "نمایش آرشیوشده‌ها" }).click()
  const archivedRow = page.locator("tr", { hasText: athleteEmail })
  await expect(archivedRow.locator(".m3-status")).toHaveText("آرشیو")
  await archivedRow.getByRole("button", { name: "حذف" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "حذف" }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await expect(page.getByText(athleteEmail)).toHaveCount(0)

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  const coachRow = page.locator("tr", { hasText: coachEmail })
  await coachRow.getByRole("button", { name: "حذف" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "حذف" }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await expect(page.getByText(coachEmail)).toHaveCount(0)
})

test("global people navigation disappears inside a club", async ({ page }) => {
  await loginAsSuperuser(page)
  await page.getByRole("button", { name: "ورود به باشگاه" }).first().click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "مربیان" }),
  ).toHaveCount(0)
  await page.goto("/coaches")
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/members$/)
})
