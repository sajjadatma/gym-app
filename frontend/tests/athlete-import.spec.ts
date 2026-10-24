import { expect, test } from "@playwright/test"

import { API_URL } from "./credentials"

test("manager imports athletes from CSV after previewing rows", async ({
  page,
  request,
}) => {
  await page.goto("/athletes")
  await page.getByRole("button", { name: "ورود گروهی" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByRole("heading", { name: "ورود گروهی ورزشکاران" }),
  ).toBeVisible()

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("button", { name: "دانلود CSV" }).click(),
  ])
  expect(download.suggestedFilename()).toBe("athlete-import-template.csv")

  const email = `import-e2e-${Date.now()}@example.com`
  const csv = [
    "email,full_name,phone,coach_email,training_goal,height_cm,weight_kg,training_days_count",
    `${email},ورزشکار ورود آزمایشی,09120000009,,قدرت,180,80,3`,
    "bad-email,ردیف نامعتبر,,,,,,",
  ].join("\n")
  await dialog.locator('input[type="file"]').setInputFiles({
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
  await page.getByRole("option", { name: "رضا مربی", exact: true }).click()
  await expect(dialog.getByText(/آماده ورود: ۱/)).toBeVisible()
  await expect(dialog.getByText(/خطا: ۱/)).toBeVisible()
  await expect(dialog.getByText("ایمیل معتبر نیست.")).toBeVisible()
  await dialog.getByRole("button", { name: /ورود .* ورزشکار/ }).click()

  await expect(
    dialog.getByRole("heading", { name: "ورود انجام شد" }),
  ).toBeVisible()
  await expect(dialog.getByText(/ایجادشده: ۱/)).toBeVisible()
  await dialog.getByRole("button", { name: "پایان" }).click()

  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(email)
  await expect(page.locator(".m3-entity-card")).toHaveCount(1)

  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }
  const created = await request.get(
    `${API_URL}/api/v1/athletes?q=${encodeURIComponent(email)}`,
    { headers },
  )
  expect(created.ok()).toBeTruthy()
  const athlete = (await created.json()).data[0]
  expect(athlete.email).toBe(email)
  const archived = await request.post(
    `${API_URL}/api/v1/athletes/${athlete.user_id}/archive`,
    { headers },
  )
  expect(archived.ok()).toBeTruthy()
})
