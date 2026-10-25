import { expect, test } from "@playwright/test"

import { openAthlete } from "./utils/athletes"

test("Select opens a listbox, supports keyboard selection and Escape", async ({
  page,
}) => {
  await page.goto("/members")
  await page.getByRole("button", { name: "افزودن عضو" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()

  const activation = dialog.getByRole("button", { name: /روش فعال‌سازی/ })
  await activation.click()
  await expect(page.getByRole("listbox")).toBeVisible()

  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("Enter")
  await expect(activation).toContainText("رمز عبور اولیه")
  await expect(page.getByRole("listbox")).toBeHidden()

  await activation.click()
  await expect(page.getByRole("listbox")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("listbox")).toBeHidden()
  await expect(activation).toBeFocused()
})

test("searchable ComboBox filters long lists, handles no results and stays in the viewport", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  const dialog = page.getByRole("dialog")
  const coach = dialog.getByRole("combobox", { name: /مربی مسئول/ })

  await coach.click()
  await coach.fill("رضا")
  await expect(page.getByRole("option", { name: /رضا/ })).toBeVisible()
  const popupBox = await page.getByRole("listbox").boundingBox()
  const viewport = page.viewportSize()
  expect(popupBox).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(popupBox!.x).toBeGreaterThanOrEqual(0)
  expect(popupBox!.y).toBeGreaterThanOrEqual(0)
  expect(popupBox!.x + popupBox!.width).toBeLessThanOrEqual(viewport!.width + 1)
  expect(popupBox!.y + popupBox!.height).toBeLessThanOrEqual(
    viewport!.height + 1,
  )

  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("Enter")
  await expect(coach).toHaveValue(/رضا/)

  await coach.fill("zzz-no-match")
  await expect(page.getByText("نتیجه‌ای یافت نشد")).toBeVisible()
})

test("required ComboBox exposes required state and keeps the form open on validation", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  const dialog = page.getByRole("dialog")
  const coach = dialog.getByRole("combobox", { name: /مربی مسئول/ })
  await expect(coach).toHaveAttribute("required", "")
  await dialog.getByLabel(/ایمیل/).fill("required-check@example.com")
  await dialog.getByRole("button", { name: "افزودن", exact: true }).click()
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByText("برای ساخت ورزشکار، انتخاب مربی مسئول الزامی است."),
  ).toBeVisible()
})

test("Persian date picker selects today and submits Gregorian ISO", async ({
  page,
}) => {
  await page.goto("/athletes")
  await openAthlete(page, "نیما ورزشکار")
  await expect(
    page.getByRole("heading", { name: "نیما ورزشکار" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  const dateDialog = page.getByRole("dialog")
  await expect(dateDialog.getByRole("grid")).toBeVisible()
  await expect(dateDialog.getByRole("gridcell").first()).toBeVisible()

  await dateDialog.getByRole("button", { name: "امروز" }).click()
  await expect(dateDialog).toBeHidden()

  const todayIso = await page.evaluate(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`
  })

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.method() === "PATCH" &&
        /\/api\/v1\/athletes\/[^/]+$/.test(req.url()),
    ),
    page.getByRole("button", { name: "ذخیره", exact: true }).click(),
  ])
  expect(request.postDataJSON().birth_date).toBe(todayIso)
})

test("date picker inside a dialog is not clipped", async ({ page }) => {
  await page.goto("/athletes")
  await openAthlete(page, "نیما ورزشکار")
  await page.getByRole("button", { name: "ساخت برنامه" }).click()
  const createDialog = page.locator(".m3-dialog").first()
  await expect(createDialog).toBeVisible()

  await createDialog
    .getByRole("button", { name: "انتخاب تاریخ" })
    .first()
    .click()
  const dateDialog = page.getByRole("dialog").filter({
    has: page.getByRole("grid"),
  })
  await expect(dateDialog).toBeVisible()
  const box = await dateDialog.boundingBox()
  const viewport = page.viewportSize()
  expect(box).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height + 1)

  await page.keyboard.press("Escape")
  await expect(dateDialog).toBeHidden()
  await expect(createDialog).toBeVisible()
  await createDialog.getByRole("button", { name: "انصراف" }).click()
})

test("English locale keeps Select and DatePicker usable in LTR", async ({
  page,
}) => {
  await page.goto("/")
  await page
    .locator(".m3-topbar__actions")
    .getByRole("button", { name: "حساب کاربری" })
    .click()
  await page.getByRole("button", { name: "English" }).click()
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr")

  await page.goto("/athletes")
  await page.getByRole("button", { name: "Add athlete" }).click()
  const dialog = page.getByRole("dialog")
  await expect(
    dialog.getByRole("combobox", { name: "Responsible coach" }),
  ).toBeVisible()
  await dialog.getByRole("button", { name: "Cancel" }).click()

  await openAthlete(page, "نیما ورزشکار")
  await page.getByRole("button", { name: "Select date" }).first().click()
  const dateDialog = page.getByRole("dialog")
  await expect(dateDialog.getByRole("grid")).toBeVisible()
  await expect(dateDialog.getByRole("button", { name: /year/i })).toBeVisible()
  await page.keyboard.press("Escape")
})

test("Persian leap-year date converts to the correct Gregorian ISO", async ({
  page,
}) => {
  await page.goto("/athletes")
  await openAthlete(page, "نیما ورزشکار")

  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  const dateDialog = page.getByRole("dialog")

  await dateDialog.getByRole("button", { name: "سال" }).click()
  await page.getByRole("option", { name: "۱۴۰۳", exact: true }).click()
  await dateDialog.getByRole("button", { name: "ماه" }).click()
  await page.getByRole("option", { name: "اسفند", exact: true }).click()
  await dateDialog.getByRole("button", { name: /۱۴۰۳ اسفند ۳۰/ }).click()
  await expect(dateDialog).toBeHidden()

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.method() === "PATCH" &&
        /\/api\/v1\/athletes\/[^/]+$/.test(req.url()),
    ),
    page.getByRole("button", { name: "ذخیره", exact: true }).click(),
  ])
  expect(request.postDataJSON().birth_date).toBe("2025-03-20")
})

test("date picker clear action submits a null value", async ({ page }) => {
  await page.goto("/athletes")
  await openAthlete(page, "نیما ورزشکار")

  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  let dateDialog = page.getByRole("dialog")
  await dateDialog.getByRole("button", { name: "امروز" }).click()
  await expect(dateDialog).toBeHidden()

  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  dateDialog = page.getByRole("dialog")
  await dateDialog.getByRole("button", { name: "پاک‌کردن" }).click()
  await expect(dateDialog).toBeHidden()

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.method() === "PATCH" &&
        /\/api\/v1\/athletes\/[^/]+$/.test(req.url()),
    ),
    page.getByRole("button", { name: "ذخیره", exact: true }).click(),
  ])
  expect(request.postDataJSON().birth_date).toBeNull()
})

test("Select, ComboBox and DatePicker remain usable in a mobile-sized modal", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/athletes")
  await page.getByRole("button", { name: "افزودن ورزشکار" }).click()
  const dialog = page.locator(".m3-dialog").first()

  const coach = dialog.getByRole("combobox", { name: /مربی مسئول/ })
  await coach.click()
  await coach.fill("رضا")
  await expect(page.getByRole("option", { name: /رضا/ })).toBeVisible()
  const comboList = page.locator(".m3-combobox__popover [role=listbox]")
  let box = await comboList.boundingBox()
  const viewport = page.viewportSize()
  expect(box).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height + 1)
  await page.keyboard.press("Escape")
  await expect(comboList).toBeHidden()

  const activation = dialog.getByRole("button", { name: /روش فعال‌سازی/ })
  await activation.click()
  const selectList = page.locator(
    ".m3-select-popover:not(.m3-combobox__popover) [role=listbox]",
  )
  box = await selectList.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height + 1)
  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible()
  await dialog.getByRole("button", { name: "انصراف" }).click()

  await openAthlete(page, "نیما ورزشکار")
  await page.getByRole("button", { name: "ساخت برنامه" }).click()
  const createDialog = page.locator(".m3-dialog").first()
  await createDialog
    .getByRole("button", { name: "انتخاب تاریخ" })
    .first()
    .click()
  const dateDialog = page.getByRole("dialog").filter({
    has: page.getByRole("grid"),
  })
  await expect(dateDialog).toBeVisible()
  box = await dateDialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height + 1)
  await page.keyboard.press("Escape")
  await expect(createDialog).toBeVisible()
})
