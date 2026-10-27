import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("invalid login shows a Persian error and does not store a token", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill("ali@example.com")
  await page.getByLabel(/رمز عبور/).fill("wrong-password")
  await page.getByRole("button", { name: "ورود" }).click()
  await expect(page.getByRole("alert")).toContainText(
    "ایمیل یا رمز عبور نادرست است.",
  )
  await expect(page).toHaveURL(/\/login$/)
  const authCookies = (await page.context().cookies()).filter(
    (cookie) => cookie.name === "gym_access_token",
  )
  expect(authCookies).toHaveLength(0)
})

test("unauthenticated users are redirected to login", async ({ page }) => {
  await page.goto("/athletes")
  await expect(page).toHaveURL(/\/login$/)
  await expect(
    page.getByRole("heading", { name: "ورود به آسکورا" }),
  ).toBeVisible()
})

test("invitation and password recovery pages validate input", async ({
  page,
}) => {
  await page.goto("/accept-invitation")
  await expect(page.getByRole("alert")).toContainText(
    "این دعوت‌نامه معتبر نیست یا منقضی شده است.",
  )
  await page.goto("/recover-password")
  await page.getByLabel(/ایمیل/).fill("not-an-email")
  await page.getByRole("button", { name: "ارسال پیوند بازیابی" }).click()
  await expect(page.getByRole("alert")).toContainText("ایمیل معتبر وارد کنید.")
})
