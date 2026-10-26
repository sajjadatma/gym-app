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
  const editedCoachName = `${coachName} ویرایش‌شده`
  const editedCoachPhone = "09125550011"
  const secondCoachName = `مربی دوم سراسری ${stamp}`
  const secondCoachEmail = `global-coach-two-${stamp}@example.com`
  const athleteName = `ورزشکار سراسری ${stamp}`
  const athleteEmail = `global-athlete-${stamp}@example.com`
  const athletePhone = "09127778899"
  const editedAthleteName = `${athleteName} ویرایش‌شده`
  const editedAthletePhone = "09127770011"

  await loginAsSuperuser(page)
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "مربیان" }),
  ).toBeVisible()
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  await expect(page).toHaveURL(/\/coaches$/)
  await page.getByRole("button", { name: "جدول" }).click()

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
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(coachEmail)
  await expect(page.getByText(coachEmail)).toBeVisible()
  await expect(page.locator("tr", { hasText: coachEmail })).toContainText(
    "باشگاه آرام",
  )

  const coachRow = page.locator("tr", { hasText: coachEmail })
  await coachRow.getByRole("button", { name: "ویرایش", exact: true }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByLabel("نام و نام خانوادگی").fill(editedCoachName)
  await dialog.getByLabel("شماره تلفن").fill(editedCoachPhone)
  await dialog.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(coachRow).toContainText(editedCoachName)
  await expect(coachRow).toContainText(editedCoachPhone)

  await page.getByRole("button", { name: "افزودن مربی" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByLabel("نام و نام خانوادگی").fill(secondCoachName)
  await dialog.getByLabel("ایمیل").fill(secondCoachEmail)
  await dialog.getByLabel("شماره تلفن").fill("09125550022")
  await dialog.getByRole("button", { name: "ایجاد" }).click()
  const secondCoachResult = page.getByRole("dialog", {
    name: "مربی ساخته شد.",
  })
  await expect(secondCoachResult).toBeVisible()
  await secondCoachResult.getByRole("button", { name: "بستن" }).last().click()
  await page.waitForTimeout(300)

  await coachRow.getByRole("button", { name: "آرشیو" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "آرشیو" }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.locator(".m3-tabs").getByRole("button", { name: "آرشیو" }).click()
  const archivedCoach = page.locator("tr", { hasText: coachEmail })
  await expect(archivedCoach.locator(".m3-status")).toHaveText("آرشیو")
  await archivedCoach.getByRole("button", { name: "بازیابی" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "بازیابی" })
    .click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.locator(".m3-tabs").getByRole("button", { name: "فعال" }).click()
  await expect(
    page.locator("tr", { hasText: coachEmail }).locator(".m3-status"),
  ).toHaveText("فعال")

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/athletes$/)
  await page.getByRole("button", { name: "جدول" }).click()
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByRole("button", { name: /مربی/ }).click()
  await page.getByRole("option", { name: editedCoachName }).click()
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
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(athleteEmail)
  const athleteRow = page.locator("tr", { hasText: athleteEmail })
  await expect(athleteRow).toContainText("باشگاه آرام")
  await expect(athleteRow).toContainText(athletePhone)
  await athleteRow.getByRole("button", { name: "ویرایش", exact: true }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByLabel("نام و نام خانوادگی").fill(editedAthleteName)
  await dialog.getByLabel("شماره تلفن").fill(editedAthletePhone)
  await dialog.getByRole("button", { name: /مربی/ }).click()
  await page.getByRole("option", { name: secondCoachName }).click()
  await dialog.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(athleteRow).toContainText(editedAthleteName)
  await expect(athleteRow).toContainText(editedAthletePhone)
  await expect(athleteRow).toContainText(secondCoachName)
  await athleteRow.getByRole("button", { name: "آرشیو" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "آرشیو" }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await page.locator(".m3-tabs").getByRole("button", { name: "آرشیو" }).click()
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
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(coachEmail)
  await coachRow.getByRole("button", { name: "حذف از باشگاه" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "حذف از باشگاه" })
    .click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator(".m3-scrim")).toHaveCount(0)
  await expect(page.getByText(coachEmail)).toHaveCount(0)
})

test("superuser transfers a coach and athlete between clubs", async ({
  page,
}) => {
  const stamp = Date.now()
  const coachName = `مربی انتقالی ${stamp}`
  const coachEmail = `transfer-coach-${stamp}@example.com`
  const athleteName = `ورزشکار انتقالی ${stamp}`
  const athleteEmail = `transfer-athlete-${stamp}@example.com`
  const destinationClub = "باشگاه پویا"
  const destinationCoach = "سارا مربی"

  await loginAsSuperuser(page)
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  await page.getByRole("button", { name: "جدول" }).click()

  await page.getByRole("button", { name: "افزودن مربی" }).click()
  let dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByLabel("نام و نام خانوادگی").fill(coachName)
  await dialog.getByLabel("ایمیل").fill(coachEmail)
  await dialog.getByLabel("شماره تلفن").fill("09125557711")
  await dialog.getByRole("button", { name: "ایجاد" }).click()
  const coachResult = page.getByRole("dialog", { name: "مربی ساخته شد." })
  await expect(coachResult).toBeVisible()
  await coachResult.getByRole("button", { name: "بستن" }).last().click()
  await expect(page.locator(".m3-scrim")).toHaveCount(0)

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await page.getByRole("button", { name: "جدول" }).click()
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: "باشگاه آرام" }).click()
  await dialog.getByRole("button", { name: /مربی/ }).click()
  await page.getByRole("option", { name: coachName }).click()
  await dialog.getByLabel("نام و نام خانوادگی").fill(athleteName)
  await dialog.getByLabel("ایمیل").fill(athleteEmail)
  await dialog.getByLabel("شماره تلفن").fill("09125557722")
  await dialog.getByRole("button", { name: "ایجاد" }).click()
  const athleteResult = page.getByRole("dialog", {
    name: "ورزشکار ساخته شد.",
  })
  await expect(athleteResult).toBeVisible()
  await athleteResult.getByRole("button", { name: "بستن" }).last().click()
  await expect(page.locator(".m3-scrim")).toHaveCount(0)

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(coachEmail)
  const coachRow = page.locator("tr", { hasText: coachEmail })
  await coachRow.getByRole("button", { name: "انتقال باشگاه" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: destinationClub }).click()
  await dialog.getByRole("button", { name: "انتقال", exact: true }).click()
  await expect(dialog.getByText(/ابتدا ورزشکاران این مربی/)).toBeVisible()
  await dialog.getByRole("button", { name: "انصراف" }).click()
  await expect(dialog).toHaveCount(0)

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(athleteEmail)
  const athleteRow = page.locator("tr", { hasText: athleteEmail })
  await expect(athleteRow).toContainText("باشگاه آرام")
  await athleteRow.getByRole("button", { name: "انتقال باشگاه" }).click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: destinationClub }).click()
  await dialog.getByRole("button", { name: /مربی/ }).click()
  await page.getByRole("option", { name: destinationCoach }).click()
  await dialog.getByRole("button", { name: "انتقال", exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(athleteRow).toContainText(destinationClub)
  await expect(athleteRow).toContainText(destinationCoach)

  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "مربیان" })
    .click()
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(coachEmail)
  const transferredCoachRow = page.locator("tr", { hasText: coachEmail })
  await transferredCoachRow
    .getByRole("button", { name: "انتقال باشگاه" })
    .click()
  dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: /باشگاه/ }).click()
  await page.getByRole("option", { name: destinationClub }).click()
  await dialog.getByRole("button", { name: "انتقال", exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(transferredCoachRow).toContainText(destinationClub)
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

test("global athlete list paginates and changes page size", async ({
  page,
}) => {
  const rows = Array.from({ length: 23 }, (_, index) => ({
    user_id: `athlete-${index}`,
    gym_id: "gym-1",
    gym_name: "باشگاه آرام",
    email: `athlete-${index}@example.com`,
    full_name: `ورزشکار ${index}`,
    phone: "09120000000",
    is_archived: false,
    coach_user_id: null,
    coach_name: "رضا مربی",
    created_at: new Date().toISOString(),
  }))
  await page.route(/\/api\/v1\/superuser\/athletes(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      const url = new URL(route.request().url())
      const offset = Number(url.searchParams.get("offset") ?? 0)
      const limit = Number(url.searchParams.get("limit") ?? 10)
      const archived = url.searchParams.get("is_archived")
      const matching = archived === "true" ? [] : rows
      await route.fulfill({
        json: {
          data: matching.slice(offset, offset + limit),
          count: matching.length,
        },
      })
      return
    }
    await route.continue()
  })

  await loginAsSuperuser(page)
  await page.goto("/athletes")
  const pager = page.locator(".m3-pagination")
  await expect(pager).toBeVisible()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۱ از ۳")
  await expect(page.locator(".m3-entity-card")).toHaveCount(10)

  await pager.getByRole("button", { name: "بعدی" }).click()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۲ از ۳")
  await pager.getByRole("button", { name: "بعدی" }).click()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۳ از ۳")
  await expect(page.locator(".m3-entity-card")).toHaveCount(3)

  await pager.getByRole("button", { name: /تعداد در صفحه/ }).click()
  await page.getByRole("option", { name: "۲۵" }).click()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۱ از ۱")
  await expect(page.locator(".m3-entity-card")).toHaveCount(23)
})

test("global list state is restored from the URL and Back works", async ({
  page,
}) => {
  const rows = Array.from({ length: 30 }, (_, index) => ({
    user_id: `url-athlete-${index}`,
    gym_id: "gym-1",
    gym_name: "باشگاه آرام",
    email: `url-athlete-${index}@example.com`,
    full_name: `ورزشکار آدرس ${index}`,
    phone: "09120000000",
    is_archived: false,
    coach_user_id: null,
    coach_name: "رضا مربی",
    created_at: new Date().toISOString(),
  }))
  const requests: string[] = []
  await page.route(/\/api\/v1\/superuser\/athletes(\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }
    const url = new URL(route.request().url())
    requests.push(url.search)
    const offset = Number(url.searchParams.get("offset") ?? 0)
    const limit = Number(url.searchParams.get("limit") ?? 10)
    const archived = url.searchParams.get("is_archived")
    const matching = archived === "true" ? [] : rows
    await route.fulfill({
      json: {
        data: matching.slice(offset, offset + limit),
        count: matching.length,
      },
    })
  })

  await loginAsSuperuser(page)
  await page.goto("/athletes")
  const pager = page.locator(".m3-pagination")
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۱ از ۳")

  await pager.getByRole("button", { name: "بعدی" }).click()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۲ از ۳")
  await expect(page.locator(".m3-entity-card")).toHaveCount(10)
  expect(requests.at(-1)).toContain("offset=10")
  expect(requests.at(-1)).toContain("limit=10")

  await page.goBack()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۱ از ۳")
  await page.goForward()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۲ از ۳")

  await page.reload()
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۲ از ۳")

  await page.goto("/athletes?page=abc&size=999")
  await expect(pager.locator(".m3-pagination__page")).toHaveText("صفحه ۱ از ۳")
  expect(requests.at(-1)).toContain("offset=0")
  expect(requests.at(-1)).toContain("limit=10")
})
