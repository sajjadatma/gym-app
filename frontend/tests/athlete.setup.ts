import { expect, test as setup } from "@playwright/test"

import { ATHLETE_EMAIL, DEMO_PASSWORD } from "./credentials"

const authFile = "playwright/.auth/athlete.json"

setup("authenticate athlete", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(ATHLETE_EMAIL)
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL(/\/gyms\/[^/]+$/)
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await page.context().storageState({ path: authFile })
})
