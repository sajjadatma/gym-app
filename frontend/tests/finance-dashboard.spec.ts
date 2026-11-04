import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

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

test("gym admin dashboard summary cards follow the configured display unit", async ({
  page,
  request,
}) => {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()

  const login = await request.post(`${API_URL}/api/v1/login/access-token`, {
    form: { username: "ali@example.com", password: DEMO_PASSWORD },
  })
  expect(login.ok()).toBeTruthy()
  const token = (await login.json()).access_token as string
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }
  const toman = await request.patch(`${API_URL}/api/v1/finance/settings`, {
    headers,
    data: { display_unit: "TOMAN" },
  })
  expect(toman.ok()).toBeTruthy()
  try {
    await page.goto(`/gyms/${gymId}/finance`)
    const card = page
      .locator(".m3-card--outlined")
      .filter({ hasText: "جریان نقدی خالص" })
      .first()
    await expect(card).toBeVisible()
    await expect(card).toContainText("تومان")
    await expect(card).not.toContainText("ریال")
  } finally {
    const rial = await request.patch(`${API_URL}/api/v1/finance/settings`, {
      headers,
      data: { display_unit: "RIAL" },
    })
    expect(rial.ok()).toBeTruthy()
  }
})
