import { expect, test } from "@playwright/test"

test("gym admin posts and reviews the opening balance journal", async ({
  page,
}) => {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()

  await page.goto(`/gyms/${gymId}/finance`)
  await expect(page.getByRole("heading", { name: "مالی باشگاه" })).toBeVisible()

  const postButton = page.getByRole("button", {
    name: "ثبت موجودی افتتاحیه",
    exact: true,
  })
  if (await postButton.isVisible().catch(() => false)) {
    await postButton.click()
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    const amounts = dialog.locator('input[inputmode="decimal"]')
    await amounts.nth(0).fill("۱۰۰۰")
    await amounts.nth(1).fill("۱۰۰۰")
    await dialog.getByRole("button", { name: "ذخیره", exact: true }).click()
    await expect(dialog).toBeHidden()
  }

  // The posted journal is visible with its balanced lines.
  await expect(page.getByText("سند ۱").first()).toBeVisible()
  await expect(page.getByText("نقد و بانک").first()).toBeVisible()
})
