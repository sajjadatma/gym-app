import { API_URL } from "./credentials"
import { expect, test } from "./fixtures/athlete-data"

test("admin builds, saves and publishes a program through the UI", async ({
  page,
  athleteData,
}) => {
  const athlete = await athleteData.create({
    name: "ورزشکار آزمون رابط",
  })
  const athleteId = athlete.athleteId

  await page.goto(`/athletes/${athleteId}`)
  await page.getByRole("button", { name: "ساخت برنامه" }).click()
  const createDialog = page.getByRole("dialog")
  await createDialog.getByLabel(/عنوان برنامه/).fill("عنوان لغوشده")
  await createDialog.getByLabel(/هدف/).fill("هدف لغوشده")
  await createDialog
    .getByRole("button", { name: "انصراف", exact: true })
    .click()
  await page.getByRole("button", { name: "ساخت برنامه", exact: true }).click()
  await expect(createDialog.getByLabel(/عنوان برنامه/)).toHaveValue("")
  await expect(createDialog.getByLabel(/هدف/)).toHaveValue("")
  await createDialog.getByLabel(/عنوان برنامه/).fill("برنامه آزمون رابط")
  await createDialog.getByRole("button", { name: "ایجاد" }).click()

  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  await expect(
    page.getByRole("heading", { name: "برنامه آزمون رابط" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "افزودن روز" }).click()
  const versionId = new URL(page.url()).pathname.split("/")[2]
  await page.getByRole("checkbox", { name: "سینه", exact: true }).check()
  await page.getByRole("checkbox", { name: "بازو", exact: true }).check()
  const addExercise = page.locator(".m3-builder-add-exercise")
  const exerciseSearch = addExercise.getByRole("combobox")
  await exerciseSearch.click()
  await exerciseSearch.fill("پرس سینه هالتر")
  await expect(exerciseSearch).toHaveAttribute("aria-expanded", "true")
  await expect(
    page.getByRole("option", { name: "پرس سینه هالتر · سینه" }),
  ).toBeVisible()
  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("Enter")
  await expect(exerciseSearch).toHaveValue(/پرس سینه هالتر/)
  await addExercise.getByRole("button", { name: "افزودن", exact: true }).click()
  await expect(
    page.locator(".m3-set-editor input[type=number]").first(),
  ).toHaveValue("8")

  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click()
  await expect(page.getByText("برنامه ذخیره شد.")).toBeVisible()

  await page.getByRole("button", { name: "انتشار برنامه" }).click()
  const publishDialog = page.getByRole("dialog")
  await expect(publishDialog).toBeVisible()
  await publishDialog.getByRole("button", { name: "انتشار برنامه" }).click()
  await expect(page).toHaveURL(new RegExp(`/athletes/${athleteId}$`))
  await expect(page.getByText("برنامه آزمون رابط").first()).toBeVisible()

  await page.goto(`/programs/${versionId}/edit`)
  await expect(
    page.getByRole("checkbox", { name: "سینه", exact: true }),
  ).toBeChecked()
  await expect(
    page.getByRole("checkbox", { name: "بازو", exact: true }),
  ).toBeChecked()
  await page.getByLabel(/عنوان برنامه/).fill("برنامه ویرایش‌شده فعال")
  await page.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("برنامه ذخیره شد.")).toBeVisible()
  await page.reload()
  await expect(page.getByLabel(/عنوان برنامه/)).toHaveValue(
    "برنامه ویرایش‌شده فعال",
  )
  await expect(
    page.getByRole("button", { name: "انتشار برنامه", exact: true }),
  ).toHaveCount(0)
  await page.goto(`/print/${versionId}`)
  await expect(page.locator(".m3-print-day__title")).toContainText(
    "سینه / بازو",
  )

  await page.goto(`/athletes/${athleteId}`)
  const backButton = page.locator(".m3-back-button").first()
  await expect(backButton).toBeVisible()
  await expect(backButton.locator("svg")).toHaveCount(1)
  await expect(
    page.getByRole("button", { name: "ساخت نسخه جدید", exact: true }),
  ).toHaveCount(0)
  const tabsFit = await page
    .locator(".m3-tabs")
    .evaluate((el) => el.scrollWidth <= el.clientWidth + 1)
  expect(tabsFit).toBe(true)
  await page.getByRole("tab", { name: /برنامه‌ها/ }).click()

  const versionRow = page
    .locator(".m3-version-row")
    .filter({ hasText: "برنامه ویرایش‌شده فعال" })
  await expect(versionRow).toHaveCount(1)
  await versionRow.getByRole("button", { name: "حذف", exact: true }).click()
  const deleteDialog = page.getByRole("dialog")
  await expect(deleteDialog).toBeVisible()
  await expect(deleteDialog).toContainText("حذف نسخه برنامه")
  await deleteDialog.getByRole("button", { name: "حذف", exact: true }).click()
  await expect(page.getByText("نسخه برنامه حذف شد.")).toBeVisible()
  await expect(versionRow).toHaveCount(0)
  await page.reload()
  await page.getByRole("tab", { name: /برنامه‌ها/ }).click()
  await expect(
    page.locator(".m3-version-row").filter({
      hasText: "برنامه ویرایش‌شده فعال",
    }),
  ).toHaveCount(0)
})

test("numbered day builder caps program days to the athlete's training-day count", async ({
  page,
  athleteData,
  request,
}) => {
  const athlete = await athleteData.create({
    name: "ورزشکار روزهای تمرین",
  })
  const athleteId = athlete.athleteId

  await request.patch(`${API_URL}/api/v1/athletes/${athleteId}`, {
    headers: athleteData.headers,
    data: { training_days_count: 2 },
  })

  await page.goto(`/athletes/${athleteId}`)
  await page.getByRole("button", { name: "ساخت برنامه", exact: true }).click()
  const createDialog = page.getByRole("dialog")
  await createDialog.getByLabel(/عنوان برنامه/).fill("برنامه دو روزه")
  await createDialog.getByRole("button", { name: "ایجاد" }).click()

  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  await expect(
    page.getByRole("heading", { name: "برنامه دو روزه" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
  await expect(page.getByRole("tab")).toHaveCount(1)
  await expect(page.getByRole("tab").first()).toContainText("روز 1")
  await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
  await expect(page.getByRole("tab")).toHaveCount(2)
  await expect(page.getByRole("tab").last()).toContainText("روز 2")
  await expect(
    page.getByRole("button", { name: "افزودن روز", exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "کپی روز", exact: true }),
  ).toBeDisabled()

  // Only one day's editor is visible at a time.
  await expect(page.locator(".m3-day")).toHaveCount(1)

  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click()
  await expect(page.getByText("برنامه ذخیره شد.")).toBeVisible()
})
