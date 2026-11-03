import { expect, type Page, test } from "@playwright/test"

const SUPERUSER_EMAIL = process.env.PLAYWRIGHT_SUPERUSER_EMAIL
const SUPERUSER_PASSWORD = process.env.PLAYWRIGHT_SUPERUSER_PASSWORD

test.skip(
  !SUPERUSER_EMAIL || !SUPERUSER_PASSWORD,
  "PLAYWRIGHT_SUPERUSER_EMAIL/PASSWORD not configured",
)

async function loginAsSuperuser(page: Page) {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(SUPERUSER_EMAIL!)
  await page.getByLabel(/رمز عبور/).fill(SUPERUSER_PASSWORD!)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL("**/")
}

test("superuser opens platform finance and sees separate cash and accrual views", async ({
  page,
}) => {
  await loginAsSuperuser(page)
  await page.goto("/platform/finance")
  await expect(page.getByRole("heading", { name: "مالی پلتفرم" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "پلن‌ها" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "قراردادها" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "صورتحساب‌ها" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "مطالبات" })).toBeVisible()
  await expect(page.getByText("MRR")).toBeVisible()
  await expect(page.getByText("وجه جمع‌آوری‌شده")).toBeVisible()
  await expect(page.getByText("درآمد شناسایی‌شده")).toBeVisible()
  await page.getByRole("tab", { name: "مطالبات" }).click()
  await expect(page.getByText("یادآوری‌ها")).toBeVisible()
  await expect(page.getByText(/یادآوری فقط درون‌برنامه‌ای/)).toBeVisible()
})
