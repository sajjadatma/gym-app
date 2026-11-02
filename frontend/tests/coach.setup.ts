import { expect, test as setup } from "@playwright/test"

import { DEMO_PASSWORD } from "./credentials"

const authFile = "playwright/.auth/coach.json"

setup("authenticate coach", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill("reza@example.com")
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL(/\/gyms\/[^/]+$/)
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await page.context().storageState({ path: authFile })
})
