import { expect, test } from "@playwright/test"

test("athlete list switches to a selectable table and remembers the view", async ({
  page,
}) => {
  await page.goto("/athletes")

  // Cards are the default view.
  await expect(page.locator(".m3-entity-card").first()).toBeVisible()

  // Search has an empty-result state and a clear action.
  const search = page.getByLabel("جستجوی نام، ایمیل یا تلفن")
  await search.fill("zzz-no-such-athlete")
  await expect(page.getByText("نتیجه‌ای یافت نشد")).toBeVisible()
  await page
    .locator(".m3-empty")
    .getByRole("button", { name: "پاک‌کردن جستجو" })
    .click()
  await expect(page.locator(".m3-entity-card").first()).toBeVisible()

  await page.getByRole("button", { name: "جدول", exact: true }).click()
  const table = page.locator(".m3-data-table")
  await expect(table).toBeVisible()
  const rows = table.locator("tbody tr")
  await expect(rows.first()).toBeVisible()
  const firstRow = rows.first()

  // Single selection shows the future bulk-actions bar.
  await firstRow.locator('input[type="checkbox"]').check()
  await expect(
    page.getByRole("status").filter({ hasText: "انتخاب‌شده" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "لغو انتخاب" }).click()
  await expect(firstRow.locator('input[type="checkbox"]')).not.toBeChecked()

  // Header checkbox selects every visible row.
  const selectAll = page.getByRole("checkbox", { name: "انتخاب این صفحه" })
  await selectAll.check()
  await expect(firstRow.locator('input[type="checkbox"]')).toBeChecked()

  // The chosen view survives a reload.
  await page.reload()
  await expect(page.locator(".m3-data-table")).toBeVisible()

  // The athlete name opens the profile.
  await page
    .locator(".m3-data-table tbody tr .m3-data-table__identity")
    .first()
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes\/[^/]+$/)
})

test("coach picker searches on the server and loads more", async ({ page }) => {
  const coaches = Array.from({ length: 25 }, (_, index) => ({
    user_id: `coach-${index}`,
    email: `coach-${index}@example.com`,
    full_name: `مربی تست ${String(index).padStart(2, "0")}`,
  }))
  await page.route(/\/api\/v1\/gyms\/[^/]+\/coaches(\?.*)?$/, async (route) => {
    const url = new URL(route.request().url())
    const search = url.searchParams.get("q") ?? ""
    const offset = Number(url.searchParams.get("offset") ?? 0)
    const limit = Number(url.searchParams.get("limit") ?? 10)
    const matching = coaches.filter(
      (coach) =>
        !search ||
        coach.full_name.includes(search) ||
        coach.email.includes(search),
    )
    await route.fulfill({
      json: {
        data: matching.slice(offset, offset + limit),
        count: matching.length,
      },
    })
  })

  await page.goto("/athletes")
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes$/)
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  const dialog = page.getByRole("dialog")
  const picker = dialog.getByRole("combobox", { name: "مربی" })
  await picker.click()
  await expect(page.getByRole("option")).toHaveCount(20)

  await page.getByRole("button", { name: "نمایش بیشتر" }).click()
  await expect(page.getByRole("option")).toHaveCount(25)

  await picker.fill("مربی تست 24")
  await expect(page.getByRole("option")).toHaveCount(1)
  await expect(page.getByRole("option", { name: "مربی تست 24" })).toBeVisible()
})
