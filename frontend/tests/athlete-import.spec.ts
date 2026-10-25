import { randomUUID } from "node:crypto"
import { API_URL } from "./credentials"
import { expect, test } from "./fixtures/athlete-data"

async function expectPageFits(page: import("@playwright/test").Page) {
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fits).toBe(true)
}

test("manager imports athletes from CSV after previewing rows", async ({
  page,
  athleteData,
  request,
}) => {
  await page.goto("/athletes")
  await page.getByRole("button", { name: "ورود گروهی", exact: true }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByRole("heading", { name: "ورود گروهی ورزشکاران" }),
  ).toBeVisible()
  await expectPageFits(page)

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("button", { name: "دانلود CSV" }).click(),
  ])
  expect(download.suggestedFilename()).toBe("athlete-import-template.csv")

  const fileInput = dialog.getByLabel("فایل ورودی")
  await expect(fileInput).toHaveAttribute("aria-label", "فایل ورودی")

  const email = `${athleteData.marker}-import-${randomUUID()}@example.com`
  athleteData.trackEmail(email)
  const csv = [
    "email,full_name,phone,coach_email,training_goal,height_cm,weight_kg,training_days_count",
    `${email},ورزشکار ورود آزمایشی,09120000009,,قدرت,180,80,3`,
    "bad-email,ردیف نامعتبر,,,,,,",
  ].join("\n")
  await fileInput.setInputFiles({
    name: "athletes.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv, "utf8"),
  })

  await dialog.getByRole("button", { name: /ارسال دعوت‌نامه/ }).click()
  await page
    .getByRole("option", { name: "رمز عبور اولیه", exact: true })
    .click()
  await dialog
    .getByRole("textbox", { name: "رمز عبور اولیه" })
    .fill("BulkPass123!")

  // Preview without a coach: the dialog offers to recover in place.
  await dialog.getByRole("button", { name: "بررسی و پیش‌نمایش" }).click()
  await expect(dialog.getByText("مربی پیش‌فرض انتخاب نشده است")).toBeVisible()
  const coach = dialog.getByRole("combobox", { name: /مربی پیش‌فرض/ })
  await coach.click()
  await coach.fill("رضا")
  const coachOption = page.getByRole("option", {
    name: "رضا مربی",
    exact: true,
  })
  await expect(coachOption).toBeVisible()
  await expect
    .poll(() =>
      coachOption.evaluate((element) => {
        const popover = element.closest(".m3-select-popover")
        return popover ? Number(getComputedStyle(popover).opacity) : 0
      }),
    )
    .toBe(1)
  await coachOption.click()
  await expect(dialog.getByText(/آماده ورود: ۱/)).toBeVisible()
  await expect(dialog.getByText(/خطا: ۱/)).toBeVisible()
  await expect(dialog.getByText("ایمیل معتبر نیست.")).toBeVisible()
  await expectPageFits(page)
  await dialog.getByRole("button", { name: /ورود .* ورزشکار/ }).click()

  await expect(
    dialog.getByRole("heading", { name: "ورود انجام شد" }),
  ).toBeVisible()
  await expect(dialog.getByText(/ایجادشده: ۱/)).toBeVisible()
  await expect(dialog.getByText(/ناموفق: ۱/)).toBeVisible()
  await dialog.getByRole("button", { name: "پایان" }).click()

  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(email)
  await expect(page.locator(".m3-entity-card")).toHaveCount(1)

  const created = await request.get(
    `${API_URL}/api/v1/athletes?q=${encodeURIComponent(email)}`,
    { headers: athleteData.headers },
  )
  expect(created.ok()).toBeTruthy()
  const athlete = (await created.json()).data[0]
  expect(athlete.email).toBe(email)

  await page.getByRole("button", { name: "ورود گروهی", exact: true }).click()
  const reopened = page.getByRole("dialog")
  await expect(reopened).toBeVisible()
  await expect(reopened.locator(".m3-import-file__name")).toHaveCount(0)
  await expect(reopened.getByText(/آماده ورود:/)).toHaveCount(0)
  await expect(
    reopened.getByRole("button", { name: "بررسی و پیش‌نمایش" }),
  ).toBeDisabled()
  await expect(
    reopened.getByRole("textbox", { name: "رمز عبور اولیه" }),
  ).toHaveCount(0)
  await expectPageFits(page)
  await reopened.getByRole("button", { name: "انصراف", exact: true }).click()
  await expect(reopened).toHaveCount(0)
})
