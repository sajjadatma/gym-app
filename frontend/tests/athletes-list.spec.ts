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
  const selectAll = page.getByRole("checkbox", { name: "انتخاب همه" })
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
  await expect(page).toHaveURL(/\/athletes\/[^/]+$/)
})
