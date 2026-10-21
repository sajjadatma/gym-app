import { expect, test } from "@playwright/test"

test("admin dashboard, gym switching and coach mode", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await expect(page.getByText("باشگاه آرام").first()).toBeVisible()

  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: /باشگاه پویا/ }).click()
  await expect(page.getByText("باشگاه پویا").first()).toBeVisible()

  await page.getByRole("button", { name: "تغییر باشگاه" }).click()
  await page.getByRole("menuitem", { name: /باشگاه آرام/ }).click()
  await expect(page.getByText("باشگاه آرام").first()).toBeVisible()

  await page.getByRole("button", { name: "تغییر نقش" }).click()
  await page.getByRole("menuitem", { name: "حالت مربیگری" }).click()
  await expect(page.getByRole("button", { name: "تیم باشگاه" })).toHaveCount(0)
  await page.getByRole("button", { name: "تغییر نقش" }).click()
  await page.getByRole("menuitem", { name: "حالت مدیریت" }).click()
  await expect(page.getByRole("button", { name: "تیم باشگاه" })).toBeVisible()
})

test("athlete list, detail and read-only program builder", async ({ page }) => {
  await page.goto("/")
  await page
    .locator(".m3-nav-rail")
    .getByRole("button", { name: "ورزشکاران" })
    .click()
  await expect(page).toHaveURL(/\/athletes\/?$/)
  await expect(page.getByRole("heading", { name: "ورزشکاران" })).toBeVisible()

  await page.getByRole("button", { name: /نیما ورزشکار/ }).click()
  await expect(page).toHaveURL(/\/athletes\/[^/]+$/)
  await expect(
    page.getByRole("heading", { name: "نیما ورزشکار" }),
  ).toBeVisible()

  await page.getByRole("tab", { name: /برنامه‌ها/ }).click()
  await page.getByRole("button", { name: "باز کردن" }).first().click()
  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  await expect(
    page.getByText("این برنامه منتشرشده و فعال است و قابل ویرایش نیست."),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "برنامه قدرتی ۸ هفته‌ای" }),
  ).toBeVisible()
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

test("mobile admin keeps gym and role context available", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")
  await expect(page.getByRole("button", { name: "تغییر باشگاه" })).toBeVisible()
  await expect(page.getByRole("button", { name: "تغییر نقش" })).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
  await page.getByRole("button", { name: "تغییر نقش" }).click()
  await page.getByRole("menuitem", { name: "حالت مربیگری" }).click()
  await expect(page.locator(".m3-mobile-nav")).toBeVisible()
  await expect(
    page.locator(".m3-mobile-nav").getByRole("button", { name: "تیم باشگاه" }),
  ).toHaveCount(0)
  await page.getByRole("button", { name: "تغییر نقش" }).click()
  await page.getByRole("menuitem", { name: "حالت مدیریت" }).click()
  await expect(
    page.locator(".m3-mobile-nav").getByRole("button", { name: "تیم باشگاه" }),
  ).toBeVisible()
})
