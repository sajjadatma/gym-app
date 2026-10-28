import type { Locator, Page } from "@playwright/test"

import { API_URL } from "./credentials"
import { expect, test } from "./fixtures/athlete-data"

async function chooseRowAction(page: Page, row: Locator, name: string) {
  await row.getByRole("button", { name: "اقدام‌های بیشتر" }).click()
  await page.getByRole("menu").getByRole("menuitem", { name }).click()
}

async function expectPageFits(page: Page) {
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fits).toBe(true)
}

test("archived athletes can be restored or permanently deleted", async ({
  page,
  athleteData,
  request,
}) => {
  const restoreTarget = await athleteData.create({
    name: "ورزشکار بازیابی آزمون",
    archived: true,
  })
  const deleteTarget = await athleteData.create({
    name: "ورزشکار حذف آزمون",
    archived: true,
  })

  await page.goto("/athletes/archived")
  await expect(
    page.getByRole("heading", { name: "ورزشکاران آرشیوشده" }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "آرشیو" })).toHaveClass(
    /is-active/,
  )
  await expectPageFits(page)

  const restoreRow = page
    .locator(".m3-archive-table tbody tr")
    .filter({ hasText: restoreTarget.email })
  await chooseRowAction(page, restoreRow, "بازیابی")
  await expect(page.getByText("ورزشکار بازیابی شد.")).toBeVisible()
  await expect(restoreRow).toHaveCount(0)

  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(restoreTarget.email)
  await page.goto("/athletes")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(restoreTarget.email)
  await expect(page.locator(".m3-entity-card")).toHaveCount(1)

  await page.goto("/athletes/archived")
  const deleteRow = page
    .locator(".m3-archive-table tbody tr")
    .filter({ hasText: deleteTarget.email })
  const moreButton = deleteRow.getByRole("button", {
    name: "اقدام‌های بیشتر",
  })
  await moreButton.scrollIntoViewIfNeeded()
  await expect(moreButton).toBeVisible()

  let deleteCalls = 0
  await page.route("**/api/v1/athletes/*", async (route) => {
    if (
      route.request().method() === "DELETE" &&
      new URL(route.request().url()).pathname.endsWith(
        `/athletes/${deleteTarget.athleteId}`,
      )
    ) {
      deleteCalls += 1
    }
    await route.continue()
  })

  await chooseRowAction(page, deleteRow, "حذف")
  const dialog = page.getByRole("dialog")
  await expect(dialog).toContainText("حذف دائمی ورزشکار")
  await expectPageFits(page)
  const submit = dialog.getByRole("button", { name: "حذف دائمی" })
  await expect(submit).toBeDisabled()

  await page.keyboard.press("Escape")
  await expect(dialog).toHaveCount(0)
  expect(deleteCalls).toBe(0)

  await chooseRowAction(page, deleteRow, "حذف")
  await expect(dialog).toBeVisible()
  await expect(submit).toBeDisabled()
  const confirmation = dialog.getByLabel(/برای تأیید، ایمیل/)
  await confirmation.fill("wrong@example.com")
  await expect(submit).toBeDisabled()
  await confirmation.fill(deleteTarget.email)
  await expect(submit).toBeEnabled()
  await submit.click()
  await expect(page.getByText("ورزشکار حذف شد.")).toBeVisible()
  await expect(deleteRow).toHaveCount(0)
  expect(deleteCalls).toBe(1)

  const missing = await request.get(
    `${API_URL}/api/v1/athletes/${deleteTarget.athleteId}`,
    { headers: deleteTarget.headers },
  )
  expect(missing.status()).toBe(404)
})

test("archived athletes can be restored in bulk", async ({
  page,
  athleteData,
}) => {
  const marker = `بازیابی گروهی ${Date.now()}`
  const first = await athleteData.create({
    name: `${marker} ۱`,
    archived: true,
  })
  const second = await athleteData.create({
    name: `${marker} ۲`,
    archived: true,
  })

  await page.goto("/athletes/archived")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(marker)
  const rows = page.locator(".m3-archive-table tbody tr")
  await expect(rows).toHaveCount(2)
  await page.getByRole("checkbox", { name: "انتخاب این صفحه" }).check()
  await expect(page.locator(".m3-selection-bar__count")).toHaveText(
    /۲ انتخاب‌شده/,
  )
  await page.getByRole("button", { name: "بازیابی انتخاب‌شده‌ها" }).click()
  await expect(page.getByText(/۲ ورزشکار بازیابی شد/)).toBeVisible()
  await expect(rows).toHaveCount(0)

  for (const target of [first, second]) {
    const response = await page.request.get(
      `${API_URL}/api/v1/athletes/${target.athleteId}`,
      { headers: target.headers },
    )
    expect(response.status()).toBe(200)
  }
})

test("archive is available on cards and as a table bulk action", async ({
  page,
  athleteData,
}) => {
  const cardTarget = await athleteData.create({
    name: "آرشیو کارت آزمون",
  })
  await page.goto("/athletes")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(cardTarget.email)
  const card = page.locator(".m3-entity-card").first()
  await expect(card).toBeVisible()
  await chooseRowAction(page, card, "آرشیو ورزشکار")
  const cardDialog = page.getByRole("dialog")
  await expect(cardDialog).toContainText("آرشیو ورزشکار")
  await cardDialog.getByRole("button", { name: "آرشیو", exact: true }).click()
  await expect(page.getByText("ورزشکار آرشیو شد.")).toBeVisible()
  await expect(page.locator(".m3-entity-card")).toHaveCount(0)

  const marker = `آرشیو گروهی جدول ${Date.now()}`
  await athleteData.create({ name: `${marker} ۱` })
  await athleteData.create({ name: `${marker} ۲` })
  await page.goto("/athletes")
  await page.getByRole("button", { name: "جدول", exact: true }).click()
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(marker)
  const rows = page.locator(".m3-data-table tbody tr")
  await expect(rows).toHaveCount(2)
  await page.getByRole("checkbox", { name: "انتخاب این صفحه" }).check()
  await page.getByRole("button", { name: "آرشیو انتخاب‌شده‌ها" }).click()
  const bulkDialog = page.getByRole("dialog")
  await expect(bulkDialog).toContainText("آرشیو ۲ ورزشکار")
  await bulkDialog.getByRole("button", { name: "آرشیو", exact: true }).click()
  await expect(page.getByText(/۲ ورزشکار آرشیو شد/)).toBeVisible()
  await expect(rows).toHaveCount(0)
})
