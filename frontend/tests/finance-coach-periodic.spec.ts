import { expect, type Locator, type Page, test } from "@playwright/test"

async function choose(
  page: Page,
  container: Locator,
  label: string,
  option: string,
) {
  await container
    .getByRole("button", { name: new RegExp(label) })
    .first()
    .click()
  await page.getByRole("option", { name: option }).first().click()
}

test("admin accrues a fixed periodic coach expense without a sale", async ({
  page,
}) => {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  await page.goto(`/gyms/${gymId}/finance`)
  await page.getByRole("tab", { name: "قرارداد مربیان" }).click()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  const dialog = page.getByRole("dialog")
  await choose(page, dialog, "مربی", /رضا مربی/)
  await choose(page, dialog, "دوره حقوق ثابت", "ماهانه")
  await dialog.getByLabel(/^مبلغ حقوق ثابت/).fill("10000")
  await dialog.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("قرارداد ثبت شد.")).toBeVisible()
  await page
    .getByRole("button", { name: "ثبت هزینه دوره‌ای", exact: true })
    .first()
    .click()
  const accrue = page.getByRole("dialog")
  const next = new Date()
  next.setMonth(next.getMonth() + 1)
  await accrue
    .getByLabel(/^دوره/)
    .fill(
      `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`,
    )
  await accrue.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("هزینه دوره‌ای ثبت شد.")).toBeVisible()
})
