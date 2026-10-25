import { expect, test as setup } from "@playwright/test"

import { ADMIN_EMAIL, DEMO_PASSWORD } from "./credentials"

const authFile = "playwright/.auth/admin.json"

setup("authenticate gym admin", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(ADMIN_EMAIL)
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL(/\/gyms\/[^/]+$/)
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await page.context().storageState({ path: authFile })
})
