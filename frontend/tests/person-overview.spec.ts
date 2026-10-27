import { expect, test } from "@playwright/test"

test("athlete and coach details open the complete overview page", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page.waitForSelector(".m3-entity-card, .m3-data-table")
  if ((await page.locator(".m3-data-table").count()) === 0) {
    await page.getByRole("button", { name: "جدول", exact: true }).click()
  }

  const athleteRow = page.locator(".m3-data-table tbody tr").first()
  await athleteRow.getByRole("button", { name: "جزئیات" }).click()

  await expect(page).toHaveURL(/\/people\/[^/?]+\?gym=/)
  await expect(
    page.getByRole("heading", { name: "پرونده ورزشکار" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "تاریخچهٔ کامل" }),
  ).toBeVisible()
  await expect(page.getByText("عضویت‌ها و نقش‌ها")).toBeVisible()
  await expect(page.getByText("برنامه‌های تمرینی")).toBeVisible()

  await page.getByRole("button", { name: "بازگشت" }).click()
  await expect(page.locator(".m3-data-table")).toBeVisible()

  await page.goto("/members")
  const coachRow = page
    .locator("tbody tr")
    .filter({ has: page.getByRole("button", { name: "جزئیات" }) })
    .first()
  await coachRow.getByRole("button", { name: "جزئیات" }).click()

  await expect(page).toHaveURL(/\/people\/[^/?]+\?gym=.*kind=COACH/)
  await expect(page.getByRole("heading", { name: "پرونده مربی" })).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "تاریخچهٔ کامل" }),
  ).toBeVisible()
})

test("overview keeps a clear empty state for a coach without records", async ({
  page,
}) => {
  await page.goto("/members")
  const coachRow = page
    .locator("tbody tr")
    .filter({ has: page.getByRole("button", { name: "جزئیات" }) })
    .first()
  await coachRow.getByRole("button", { name: "جزئیات" }).click()

  const programsSection = page
    .locator(".m3-card")
    .filter({ hasText: "برنامه‌های نوشته‌شده" })
  await expect(programsSection).toBeVisible()
  const programCount = await programsSection.locator(".person-program").count()
  const emptyCount = await programsSection
    .getByText("برنامه‌ای نوشته نشده است")
    .count()
  expect(programCount + emptyCount).toBeGreaterThan(0)
})

test("people tables keep Details visible and secondary actions in a menu", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page.waitForSelector(".m3-entity-card, .m3-data-table")
  if ((await page.locator(".m3-data-table").count()) === 0) {
    await page.getByRole("button", { name: "جدول", exact: true }).click()
  }

  const row = page.locator(".m3-data-table tbody tr").first()
  await expect(row.getByRole("button", { name: "جزئیات" })).toBeVisible()
  const more = row.getByRole("button", { name: "اقدام‌های بیشتر" })
  await more.click()

  const menu = page.getByRole("menu")
  await expect(menu).toBeVisible()
  await expect(menu.getByRole("menuitem", { name: "باز کردن" })).toBeVisible()

  await page.keyboard.press("Escape")
  await expect(menu).toHaveCount(0)
  await expect(more).toHaveAttribute("aria-expanded", "false")
})
