import { expect, test } from "@playwright/test"

const ADMIN_EMAIL = "ali@example.com"
const ADMIN_PASSWORD = "DemoPass123!"
const SUPERUSER_EMAIL = "finance-sandbox-admin@example.com"
const SUPERUSER_PASSWORD = "SandboxAdmin123!"

async function archiveGymOverrides(
  request: import("@playwright/test").APIRequestContext,
) {
  const login = await request.post("/api/v1/login/access-token", {
    form: { username: SUPERUSER_EMAIL, password: SUPERUSER_PASSWORD },
  })
  if (!login.ok()) return
  const token = (await login.json()).access_token as string
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.get("/api/v1/finance/platform-contracts", {
    headers,
    params: { scope: "GYM" },
  })
  if (!list.ok()) return
  for (const contract of (await list.json()) as Array<{
    id: string
    status: string
  }>) {
    if (contract.status === "ACTIVE") {
      await request.post(
        `/api/v1/finance/platform-contracts/${contract.id}/archive`,
        { headers },
      )
    }
  }
}

async function login(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(email)
  await page.getByLabel(/رمز عبور/).fill(password)
  await page.getByRole("button", { name: "ورود" }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

test("gym admin completes contract, sale, payment, settlement and report journey", async ({
  page,
}) => {
  await page.context().clearCookies()
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)

  await page.getByRole("button", { name: "مالی" }).first().click()
  await expect(
    page.getByRole("heading", { name: "نمای کلی مالی باشگاه" }),
  ).toBeVisible()
  await expect(
    page.getByText("محیط آزمایشی — پول واقعی جابه‌جا نمی‌شود"),
  ).toBeVisible()

  await page.getByRole("link", { name: "قراردادها و درصدها" }).click()
  await expect(
    page.getByRole("heading", { name: "قراردادهای مربی" }),
  ).toBeVisible()
  await expect(page.getByText(/درصد پلتفرم از قرارداد پلتفرم/)).toBeVisible()
  await expect(page.getByText("رضا مربی").first()).toBeVisible()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  await page.getByRole("button", { name: "انتخاب کنید مربی" }).click()
  await page.getByRole("option", { name: "رضا مربی" }).click()
  await page.getByRole("button", { name: "حق عضویت باشگاه" }).click()
  await page.getByRole("option", { name: "برنامه تغذیه" }).click()
  await expect(page.getByRole("textbox", { name: "درصد پلتفرم" })).toHaveValue(
    /۱۲/,
  )
  await page.getByRole("textbox", { name: /درصد باشگاه/ }).fill("38")
  await page.getByRole("textbox", { name: /درصد مربی/ }).fill("50")
  await expect(page.locator(".m3-dialog").getByText("۰٪")).toBeVisible()
  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click()
  await expect(page.getByText("برنامه تغذیه").last()).toBeVisible()

  await page.getByRole("link", { name: "فروش و پرداخت‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "فروش و پرداخت‌ها" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "فروش جدید" }).click()
  await page.getByLabel("توضیح فروش").fill("فروش تست مرورگر")
  await page.getByLabel("مبلغ پایه (تومان)").fill("1000000")
  await page.getByRole("button", { name: /مربی \(اختیاری\)/ }).click()
  await page.getByRole("option", { name: "رضا مربی" }).click()
  await expect(
    page.getByRole("checkbox", { name: /Value-added tax/ }),
  ).toBeChecked()
  await page.getByRole("button", { name: "محاسبه پیش‌نمایش" }).click()
  await expect(page.getByText("ورزشکار می‌پردازد")).toBeVisible()
  await expect(
    page.locator(".m3-preview").getByText("سهم پلتفرم"),
  ).toBeVisible()
  await expect(
    page.locator(".m3-preview").getByText("سهم باشگاه"),
  ).toBeVisible()
  await expect(page.locator(".m3-preview").getByText("سهم مربی")).toBeVisible()
  await page.getByRole("button", { name: "ثبت فروش" }).click()
  await expect(
    page.getByRole("heading", { name: "پرداخت آزمایشی" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "پرداخت موفق" }).click()
  await expect(page.getByText("موفق").first()).toBeVisible()
  await expect(
    page.locator(".m3-payment-result").getByText("پلتفرم", { exact: true }),
  ).toBeVisible()
  await page.getByRole("button", { name: "بستن" }).last().click()

  await page.getByRole("link", { name: "تسویه‌ها" }).click()
  await expect(page.getByRole("heading", { name: "تسویه‌ها" })).toBeVisible()
  await page.getByRole("button", { name: "درخواست تسویه" }).first().click()
  await page.getByRole("button", { name: "انتخاب کنید مربی" }).click()
  await page.getByRole("option", { name: "رضا مربی" }).click()
  await page.locator(".m3-dialog input[inputmode='numeric']").fill("500000")
  await page.getByRole("button", { name: "ثبت درخواست" }).click()
  await expect(page.getByText("در انتظار تسویه").first()).toBeVisible()
  await page.getByRole("button", { name: "تکمیل تسویه" }).first().click()
  await expect(page.getByText("تسویه‌شده").first()).toBeVisible()

  await page.getByRole("link", { name: "گزارش‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "گزارش‌های مالی" }),
  ).toBeVisible()
  await expect(page.getByText("فعالیت دوره")).toBeVisible()
  await expect(page.getByText("مانده تا تاریخ")).toBeVisible()
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "خروجی CSV" }).click()
  await download
})

test("finance screens stay RTL and do not overflow on mobile", async ({
  page,
}) => {
  await page.context().clearCookies()
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await page.getByRole("button", { name: "مالی" }).first().click()
  await expect(
    page.getByRole("heading", { name: "نمای کلی مالی باشگاه" }),
  ).toBeVisible()
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
  await page.getByRole("link", { name: "فروش و پرداخت‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "فروش و پرداخت‌ها" }),
  ).toBeVisible()
  const salesOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(salesOverflow).toBeLessThanOrEqual(1)
})

test("global administrator manages platform contracts and sees cross-gym overview", async ({
  page,
  request,
}) => {
  const contractName = `قرارداد اختصاصی تست ${Date.now()}`
  await archiveGymOverrides(request)
  await page.context().clearCookies()
  await login(page, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
  await page.getByRole("button", { name: "مالی" }).first().click()
  await expect(
    page.getByRole("heading", { name: "نمای کلی مالی سراسری" }),
  ).toBeVisible()
  await expect(page.getByText("مقایسه باشگاه‌ها")).toBeVisible()

  await page.getByRole("link", { name: "قراردادهای پلتفرم" }).click()
  await expect(
    page.getByRole("heading", { level: 1, name: "قراردادهای پلتفرم" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  await page.getByRole("textbox").first().fill(contractName)
  await page.getByRole("button", { name: /دامنه/ }).click()
  await page.getByRole("option", { name: "اختصاصی باشگاه" }).click()
  await page.getByRole("button", { name: "انتخاب کنید باشگاه" }).click()
  await page.getByRole("option", { name: "باشگاه پویا" }).click()
  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click()
  const createdRow = page.getByRole("row", { name: new RegExp(contractName) })
  await expect(createdRow).toBeVisible()
  await createdRow.getByRole("button", { name: "فعال‌سازی" }).click()
  await expect(createdRow.getByText("فعال")).toBeVisible()

  await page.getByRole("link", { name: "مالیات‌ها" }).click()
  await expect(page.getByRole("heading", { name: "مالیات‌ها" })).toBeVisible()
  await expect(page.getByText("Value-added tax")).toBeVisible()
})
