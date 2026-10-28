import { expect, test } from "@playwright/test"

import { openAthlete } from "./utils/athletes"

test("admin dashboard and gym switching", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await expect(page.getByText("باشگاه آرام").first()).toBeVisible()

  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: /باشگاه پویا/ }).click()
  await expect(page.getByText("باشگاه پویا").first()).toBeVisible()

  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: /باشگاه آرام/ }).click()
  await expect(page.getByText("باشگاه آرام").first()).toBeVisible()

  await expect(page.locator(".m3-account-trigger")).toBeVisible()
  await expect(page.getByRole("button", { name: "تیم باشگاه" })).toBeVisible()
})

test("athlete list, detail and editable active program builder", async ({
  page,
}) => {
  await page.goto("/")
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes\/?$/)
  await expect(page.getByRole("heading", { name: "ورزشکاران" })).toBeVisible()

  await openAthlete(page, "نیما ورزشکار")
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/athletes\/[^/]+$/)
  await expect(
    page.getByRole("heading", { name: "نیما ورزشکار" }),
  ).toBeVisible()

  await page.getByRole("tab", { name: /برنامه‌ها/ }).click()
  await page
    .locator(".m3-version-row")
    .filter({ hasText: "برنامه قدرتی ۸ هفته‌ای" })
    .getByRole("button", { name: "ویرایش", exact: true })
    .click()
  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  await expect(
    page.getByText(
      "برنامه فعال است. تغییرات پس از ذخیره برای ورزشکار نمایش داده می‌شوند.",
    ),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "برنامه قدرتی ۸ هفته‌ای" }),
  ).toBeVisible()
  await expect(page.getByRole("combobox").first()).toBeEnabled()
  await expect(
    page.getByRole("button", { name: "انتخاب تاریخ" }).first(),
  ).toBeEnabled()
})

test("add-athlete validation keeps the form and shows a Persian error", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await dialog.getByRole("button", { name: "افزودن" }).click()
  await expect(dialog.getByText("ایمیل معتبر وارد کنید.")).toBeVisible()
  await dialog.getByLabel(/ایمیل/).fill("new-athlete@example.com")
  await expect(dialog.getByLabel(/ایمیل/)).toHaveValue(
    "new-athlete@example.com",
  )
  await dialog.getByRole("button", { name: "انصراف" }).click()
})

test("language switch updates direction and translations", async ({ page }) => {
  await page.goto("/")
  await page
    .locator(".m3-topbar__actions")
    .getByRole("button", { name: "حساب کاربری" })
    .click()
  await page.getByRole("button", { name: "English" }).click()
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr")
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "Athletes" }),
  ).toBeVisible()

  await page
    .locator(".m3-topbar__actions")
    .getByRole("button", { name: "Account" })
    .click()
  await page.getByRole("button", { name: "فارسی" }).click()
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
})

test("templates and exercise library render", async ({ page }) => {
  await page.goto("/exercises")
  await expect(
    page.getByRole("heading", { name: "کتابخانه حرکات" }),
  ).toBeVisible()
  await expect(page.getByText("پرس سینه هالتر").first()).toBeVisible()
  await page.goto("/templates")
  await expect(
    page.getByRole("heading", { name: "قالب‌های تمرینی" }),
  ).toBeVisible()
  await expect(page.getByText("قالب قدرت تمام‌بدن").first()).toBeVisible()
})

test("owner can open gym details and sees ownership transfer", async ({
  page,
}) => {
  await page.goto("/gyms")
  await expect(page.getByRole("heading", { name: "باشگاه‌ها" })).toBeVisible()
  await page
    .locator(".m3-entity-card")
    .filter({ hasText: "باشگاه آرام" })
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await page.getByRole("button", { name: "تنظیمات باشگاه" }).click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/settings$/)
  await expect(page.getByRole("heading", { name: "باشگاه آرام" })).toBeVisible()
  await expect(
    page.getByRole("button", { name: "انتقال مالکیت" }),
  ).toBeVisible()
  await expect(
    page.getByText("باشگاه آرام · مدیران و مربیان این باشگاه"),
  ).toHaveCount(0)
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "تیم باشگاه" })
    .click()
  await expect(page.getByRole("heading", { name: "تیم باشگاه" })).toBeVisible()
  await expect(page.getByText("reza@example.com")).toBeVisible()
})

test("club users keep their club context on the clubs page", async ({
  page,
}) => {
  await page.goto("/gyms")
  await expect(page.locator(".m3-topbar__gym")).toContainText("باشگاه آرام")
  await expect(page.getByRole("button", { name: "تغییر باشگاه" })).toBeVisible()
})

test("mobile admin keeps gym context and current role available", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")
  await expect(page.getByRole("button", { name: "تغییر باشگاه" })).toBeVisible()
  await expect(page.locator(".m3-account-trigger")).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
  await page.locator(".m3-account-trigger").click()
  const sheet = page.locator(".m3-account-sheet")
  await expect(sheet).toBeVisible()
  await expect(sheet.locator(".m3-account__role")).toHaveText("حالت مدیریت")
  await expect(sheet.getByRole("button", { name: "حالت مربیگری" })).toHaveCount(
    0,
  )
  await expect(
    page.locator(".m3-mobile-nav").getByRole("button", { name: "تیم باشگاه" }),
  ).toBeVisible()
})

test("club users reach club settings from the workspace", async ({ page }) => {
  await page.goto("/gyms")
  await page
    .locator(".m3-entity-card")
    .filter({ hasText: "باشگاه آرام" })
    .click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await page.getByRole("button", { name: "تنظیمات باشگاه" }).click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/settings$/)
  await expect(page.getByRole("heading", { name: "باشگاه آرام" })).toBeVisible()
  await page.locator(".m3-back-button").first().click()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
})

test("club users do not get global people management", async ({ page }) => {
  await page.goto("/")
  await expect(
    page.locator(".m3-nav-rail").getByRole("button", { name: "مربیان" }),
  ).toHaveCount(0)
  await page.goto("/coaches")
  await expect(page).toHaveURL(/\/gyms\/[^/]+\/members$/)
})
