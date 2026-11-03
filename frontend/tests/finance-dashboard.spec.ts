import { expect, test } from "@playwright/test"

test("gym admin sees separate cashflow and accrual metrics and owner platform billing", async ({
  page,
}) => {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  await page.goto(`/gyms/${gymId}/finance`)
  await expect(page.getByText("داشبورد مالی")).toBeVisible()
  await expect(page.getByText("جریان نقدی خالص")).toBeVisible()
  await expect(page.getByText("درآمد شناسایی‌شده")).toBeVisible()
  await expect(page.getByText("سود عملیاتی تقریبی")).toBeVisible()
  await page.getByRole("tab", { name: "مالی پلتفرم" }).click()
  await expect(page.getByText("صورتحساب‌ها")).toBeVisible()
  await expect(page.getByText("مطالبات")).toBeVisible()
  await expect(page.getByRole("button", { name: "ثبت پرداخت" })).toHaveCount(0)
})
