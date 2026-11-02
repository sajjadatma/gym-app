import { expect, test } from "@playwright/test"

// The CI docker stack starts from a fresh seeded database, so the posting
// branch below always runs there. Against a reused local database the gym may
// already have an opening balance, in which case the test still asserts the
// posted state that the feature produces.
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
  const posted = page.getByText("موجودی افتتاحیه ثبت شده است.", {
    exact: false,
  })
  // The workspace loads its journal before deciding whether an opening can be
  // posted, so wait for either stable state instead of sampling too early.
  await expect(postButton.or(posted).first()).toBeVisible()
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

  // The gym has an active opening journal with its balanced lines.
  await expect(
    page.getByText("موجودی افتتاحیه ثبت شده است.", { exact: false }).first(),
  ).toBeVisible()
  await expect(page.getByText("سند ۱").first()).toBeVisible()
  await expect(page.getByText("نقد و بانک").first()).toBeVisible()
})
