import { expect, test } from "@playwright/test"

const ADMIN_EMAIL = "ali@example.com"
const ADMIN_PASSWORD = "DemoPass123!"
const SUPERUSER_EMAIL = "finance-sandbox-admin@example.com"
const SUPERUSER_PASSWORD = "SandboxAdmin123!"

async function login(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.context().clearCookies()
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(email)
  await page.getByLabel(/رمز عبور/).fill(password)
  await page.getByRole("button", { name: "ورود" }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

async function openSalesDialog(page: import("@playwright/test").Page) {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await page.getByRole("button", { name: "مالی", exact: true }).first().click()
  await page.getByRole("link", { name: "فروش و پرداخت‌ها" }).click()
  await page.getByRole("button", { name: "فروش جدید" }).first().click()
  await expect(page.getByRole("dialog")).toBeVisible()
}

test("Persian and Arabic-Indic sale amounts produce the same valid preview", async ({
  page,
}) => {
  await openSalesDialog(page)
  await page.getByLabel("توضیح فروش").fill("QA Persian amount")
  const amount = page.getByLabel("مبلغ پایه (تومان)")

  await amount.fill("۱۰۰۰۰۰۰")
  const persianResponse = page.waitForResponse((response) =>
    response.url().endsWith("/sales/preview"),
  )
  await page.getByRole("button", { name: "محاسبه پیش‌نمایش" }).click()
  const persian = await persianResponse
  expect(persian.status()).toBe(200)
  expect(persian.request().postDataJSON()).toMatchObject({
    base_amount_irr: 10_000_000,
  })
  await expect(page.locator(".m3-preview")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "ثبت فروش", exact: true }),
  ).toBeEnabled()

  await amount.fill("١٠٠٠٠٠٠")
  const arabicResponse = page.waitForResponse((response) =>
    response.url().endsWith("/sales/preview"),
  )
  await page.getByRole("button", { name: "محاسبه پیش‌نمایش" }).click()
  const arabic = await arabicResponse
  expect(arabic.status()).toBe(200)
  expect(arabic.request().postDataJSON()).toMatchObject({
    base_amount_irr: 10_000_000,
  })
})

test("Persian tax edit persists the new percentage and rejects invalid input", async ({
  page,
  request,
}) => {
  const loginResponse = await request.post("/api/v1/login/access-token", {
    form: { username: SUPERUSER_EMAIL, password: SUPERUSER_PASSWORD },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const token = (await loginResponse.json()).access_token as string
  const created = await request.post("/api/v1/finance/taxes", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `QA Percent ${Date.now()}`,
      calculation: "PERCENT",
      percent_bp: 1000,
      is_active: true,
    },
  })
  expect(created.ok()).toBeTruthy()
  const tax = (await created.json()) as { id: string; name: string }

  await login(page, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
  await page.goto("/finance/taxes")
  const row = page.getByRole("row", { name: new RegExp(tax.name) })
  await row.getByRole("button", { name: "ویرایش" }).click()
  const dialog = page.getByRole("dialog")
  const percent = dialog.getByLabel("درصد", { exact: true })
  await percent.fill("۲۰")
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/finance/taxes/${tax.id}`) &&
      response.request().method() === "PATCH",
  )
  await dialog.getByRole("button", { name: /ذخیره/ }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect((await response.json()).percent_bp).toBe(2000)
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(row).toContainText("۲۰٪")

  await row.getByRole("button", { name: "ویرایش" }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  const invalidPercent = dialog.getByLabel("درصد", { exact: true })
  await invalidPercent.fill("abc")
  let patched = false
  const countPatch = () => {
    patched = true
  }
  page.on("request", (request) => {
    if (
      request.url().includes(`/finance/taxes/${tax.id}`) &&
      request.method() === "PATCH"
    ) {
      countPatch()
    }
  })
  await dialog.getByRole("button", { name: /ذخیره/ }).click()
  await expect(
    page.getByRole("alert").filter({ hasText: "درصد معتبر نیست" }).first(),
  ).toBeVisible()
  expect(patched).toBe(false)

  await invalidPercent.fill("0")
  const zeroResponse = page.waitForResponse(
    (response) =>
      response.url().includes(`/finance/taxes/${tax.id}`) &&
      response.request().method() === "PATCH",
  )
  await dialog.getByRole("button", { name: /ذخیره/ }).click()
  const zero = await zeroResponse
  expect(zero.status()).toBe(200)
  expect(await zero.json()).toMatchObject({ percent_bp: 0 })
})

test("changing the category invalidates the previous preview", async ({
  page,
}) => {
  await openSalesDialog(page)
  await page.getByLabel("توضیح فروش").fill("QA stale preview")
  const previewResponse = page.waitForResponse((response) =>
    response.url().endsWith("/sales/preview"),
  )
  await page.getByRole("button", { name: "محاسبه پیش‌نمایش" }).click()
  expect((await previewResponse).status()).toBe(200)
  await expect(page.locator(".m3-preview")).toBeVisible()

  await page.getByRole("button", { name: "حق عضویت باشگاه" }).click()
  await page.getByRole("option", { name: "برنامه تغذیه" }).click()
  await expect(page.locator(".m3-preview")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "ثبت فروش", exact: true }),
  ).toBeDisabled()
})

test("a delayed preview response cannot validate a newer form", async ({
  page,
}) => {
  await openSalesDialog(page)
  await page.getByLabel("توضیح فروش").fill("QA delayed preview")
  await page.route("**/api/v1/finance/gyms/*/sales/preview", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700))
    await route.continue()
  })
  const previewResponse = page.waitForResponse((response) =>
    response.url().endsWith("/sales/preview"),
  )
  await page.getByRole("button", { name: "محاسبه پیش‌نمایش" }).click()
  await page.getByRole("button", { name: "حق عضویت باشگاه" }).click()
  await page.getByRole("option", { name: "برنامه تغذیه" }).click()
  await previewResponse
  await expect(page.locator(".m3-preview")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "ثبت فروش", exact: true }),
  ).toBeDisabled()
  await page.unroute("**/api/v1/finance/gyms/*/sales/preview")
})

test("all gym finance pages stay RTL and overflow-free at 390 and 1280", async ({
  page,
}) => {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  const gymPath = new URL(page.url()).pathname
  const paths = [
    "/finance",
    "/finance/contracts",
    "/finance/sales",
    "/finance/taxes",
    "/finance/settlements",
    "/finance/reports",
    "/coach-plan",
  ]
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    for (const suffix of paths) {
      await page.goto(gymPath + suffix)
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      )
      expect(overflow, `${width} ${suffix}`).toBeLessThanOrEqual(1)
    }
  }
  expect(errors).toEqual([])
})

test("Persian refund and settlement amounts are converted to IRR", async ({
  page,
  request,
}) => {
  const loginResponse = await request.post("/api/v1/login/access-token", {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const token = (await loginResponse.json()).access_token as string

  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  const gymPath = new URL(page.url()).pathname
  const gymId = gymPath.split("/")[2]
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId,
  }
  const description = `QA refund settlement ${Date.now()}`
  const saleResponse = await request.post(
    `/api/v1/finance/gyms/${gymId}/sales`,
    {
      headers,
      data: {
        category: "MEMBERSHIP",
        description,
        base_amount_irr: 10_000_000,
        tax_ids: [],
        coach_user_id: null,
        sold_on: new Date().toISOString().slice(0, 10),
      },
    },
  )
  expect(saleResponse.ok()).toBeTruthy()
  const sale = (await saleResponse.json()) as {
    id: string
    total_amount_irr: number
  }
  const paymentResponse = await request.post(
    `/api/v1/finance/gyms/${gymId}/sales/${sale.id}/payments`,
    {
      headers,
      data: {
        outcome: "SUCCESS",
        idempotency_key: `qa-refund-payment-${Date.now()}`,
      },
    },
  )
  expect(paymentResponse.ok()).toBeTruthy()

  await page.goto(`${gymPath}/finance/sales`)
  const saleRow = page.getByRole("row", { name: new RegExp(description) })
  await saleRow.getByRole("button", { name: "بازگشت وجه" }).click()
  const refundDialog = page.getByRole("dialog")
  await refundDialog.getByLabel("مبلغ بازگشت (تومان)").fill("۵۰۰۰۰۰")
  await refundDialog.getByLabel("دلیل").fill("بازپرداخت آزمون فارسی")
  const refundResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/refunds") &&
      response.request().method() === "POST",
  )
  await refundDialog.getByRole("button", { name: "ثبت بازگشت وجه" }).click()
  const refund = await refundResponse
  expect(refund.status()).toBe(200)
  expect(refund.request().postDataJSON()).toMatchObject({
    amount_irr: 5_000_000,
  })

  await page.goto(`${gymPath}/finance/settlements`)
  await page.getByRole("button", { name: "درخواست تسویه" }).first().click()
  const settlementDialog = page.getByRole("dialog")
  await settlementDialog.getByRole("button", { name: "سهم مربی" }).click()
  await page.getByRole("option", { name: "سهم باشگاه" }).click()
  await settlementDialog.getByLabel("مبلغ (تومان)").fill("۱۰۰۰۰۰")
  const settlementResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/settlements") &&
      response.request().method() === "POST",
  )
  await settlementDialog.getByRole("button", { name: "ثبت درخواست" }).click()
  const settlement = await settlementResponse
  expect(settlement.status()).toBe(200)
  expect(settlement.request().postDataJSON()).toMatchObject({
    amount_irr: 1_000_000,
    party: "GYM",
  })
})

test("metadata-only plan edits preserve every IRR remainder", async ({
  page,
  request,
}) => {
  const loginResponse = await request.post("/api/v1/login/access-token", {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const token = (await loginResponse.json()).access_token as string

  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  const gymPath = new URL(page.url()).pathname
  const gymId = gymPath.split("/")[2]
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId,
  }
  const coachesResponse = await request.get(
    `/api/v1/finance/gyms/${gymId}/coaches`,
    { headers },
  )
  expect(coachesResponse.ok()).toBeTruthy()
  const coach = (await coachesResponse.json())[0] as { user_id: string }
  const stamp = Date.now()
  const plans: Array<{ id: string; title: string; irr: number }> = []
  for (let remainder = 0; remainder < 10; remainder += 1) {
    const irr = 100 + remainder
    const title = `QA price remainder ${stamp}-${remainder}`
    const created = await request.post(
      `/api/v1/finance/gyms/${gymId}/coach-plans`,
      {
        headers,
        data: {
          coach_user_id: coach.user_id,
          title,
          description: "original note",
          base_price_irr: irr,
          is_active: false,
        },
      },
    )
    expect(created.ok()).toBeTruthy()
    const plan = (await created.json()) as { id: string }
    plans.push({ id: plan.id, title, irr })
  }

  await page.goto(`${gymPath}/coach-plan`)
  for (const plan of plans) {
    const row = page.getByRole("row", { name: new RegExp(plan.title) })
    await row.getByRole("button", { name: "ویرایش" }).click()
    const dialog = page.getByRole("dialog")
    const amount = dialog.getByLabel("قیمت پایه (تومان)")
    await expect(amount).toHaveValue(String(plan.irr / 10))
    await dialog.getByLabel("توضیحات").fill("only description changed")
    const saving = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/coach-plans/${plan.id}`) &&
        response.request().method() === "PUT",
    )
    await dialog.getByRole("button", { name: "ذخیره و اعمال" }).click()
    const saved = await saving
    expect(saved.status()).toBe(200)
    expect(saved.request().postDataJSON()).toMatchObject({
      base_price_irr: plan.irr,
    })
    await expect(page.getByRole("dialog")).toHaveCount(0)
  }
})

test("UI can create and re-edit a 10.5 Toman plan without changing its price", async ({
  page,
  request,
}) => {
  const loginResponse = await request.post("/api/v1/login/access-token", {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const token = (await loginResponse.json()).access_token as string

  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
  const gymPath = new URL(page.url()).pathname
  const gymId = gymPath.split("/")[2]
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId,
  }
  const coaches = await request.get(`/api/v1/finance/gyms/${gymId}/coaches`, {
    headers,
  })
  expect(coaches.ok()).toBeTruthy()
  const coach = (await coaches.json())[0] as { user_id: string; name: string }
  const title = `QA UI fractional plan ${Date.now()}`

  await page.goto(`${gymPath}/coach-plan`)
  await page.getByRole("button", { name: "پلن جدید" }).first().click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: "انتخاب کنید" }).click()
  await page.getByRole("option", { name: new RegExp(coach.name) }).click()
  await dialog.getByLabel("عنوان پلن").fill(title)
  await dialog.getByLabel("قیمت پایه (تومان)").fill("10.5")
  await dialog.getByLabel("توضیحات").fill("created at 10.5 Toman")
  await dialog.getByRole("button", { name: "فعال" }).click()
  await page.getByRole("option", { name: "غیرفعال" }).click()
  const creating = page.waitForResponse(
    (response) =>
      response.url().endsWith("/coach-plans") &&
      response.request().method() === "POST",
  )
  await dialog.getByRole("button", { name: "ذخیره و اعمال" }).click()
  const created = await creating
  expect(created.status()).toBe(200)
  expect(created.request().postDataJSON()).toMatchObject({
    base_price_irr: 105,
  })
  await expect(page.getByRole("dialog")).toHaveCount(0)

  const row = page.getByRole("row", { name: new RegExp(title) })
  await row.getByRole("button", { name: "ویرایش" }).click()
  const editDialog = page.getByRole("dialog")
  await expect(editDialog.getByLabel("قیمت پایه (تومان)")).toHaveValue("10.5")
  await editDialog.getByLabel("توضیحات").fill("edited description only")
  const saving = page.waitForResponse(
    (response) =>
      response.url().includes("/coach-plans/") &&
      response.request().method() === "PUT",
  )
  await editDialog.getByRole("button", { name: "ذخیره و اعمال" }).click()
  const saved = await saving
  expect(saved.status()).toBe(200)
  expect(saved.request().postDataJSON()).toMatchObject({
    base_price_irr: 105,
  })
})
