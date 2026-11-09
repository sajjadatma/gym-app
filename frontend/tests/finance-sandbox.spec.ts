import { expect, test } from "@playwright/test"

const ADMIN_EMAIL = "ali@example.com"
const ADMIN_PASSWORD = "DemoPass123!"
const SUPERUSER_EMAIL = "finance-sandbox-admin@example.com"
const SUPERUSER_PASSWORD = "SandboxAdmin123!"

async function ensureSeededPlatformPolicy(
  request: import("@playwright/test").APIRequestContext,
) {
  const login = await request.post("/api/v1/login/access-token", {
    form: { username: SUPERUSER_EMAIL, password: SUPERUSER_PASSWORD },
  })
  expect(login.ok()).toBeTruthy()
  const token = (await login.json()).access_token as string
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.get("/api/v1/finance/platform-contracts", {
    headers,
  })
  expect(list.ok()).toBeTruthy()
  const contracts = (await list.json()) as Array<{
    id: string
    name: string
    scope: string
    status: string
    rates: Array<{ category: string; percent_bp: number }>
  }>
  for (const contract of contracts) {
    if (contract.scope === "GYM" && contract.status === "ACTIVE") {
      const archived = await request.post(
        `/api/v1/finance/platform-contracts/${contract.id}/archive`,
        { headers },
      )
      expect(archived.ok()).toBeTruthy()
    }
  }
  const expectedRates = [
    { category: "MEMBERSHIP", percent_bp: 1000 },
    { category: "NUTRITION", percent_bp: 1200 },
    { category: "TRAINING", percent_bp: 1500 },
  ]
  const activeDefault = contracts.find(
    (contract) => contract.scope === "DEFAULT" && contract.status === "ACTIVE",
  )
  const today = new Date().toISOString().slice(0, 10)
  if (!activeDefault) {
    const created = await request.post("/api/v1/finance/platform-contracts", {
      headers,
      data: {
        name: "قرارداد پیش‌فرض تست",
        scope: "DEFAULT",
        effective_from: today,
        rates: expectedRates,
      },
    })
    expect(created.ok()).toBeTruthy()
    return
  }
  const current = Object.fromEntries(
    activeDefault.rates.map((rate) => [rate.category, rate.percent_bp]),
  )
  const matches = expectedRates.every(
    (rate) => current[rate.category] === rate.percent_bp,
  )
  if (!matches) {
    const updated = await request.put(
      `/api/v1/finance/platform-contracts/${activeDefault.id}`,
      {
        headers,
        data: {
          name: activeDefault.name,
          effective_from: today,
          rates: expectedRates,
        },
      },
    )
    expect(updated.ok()).toBeTruthy()
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
  request,
}) => {
  await ensureSeededPlatformPolicy(request)
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
  await expect(page.getByRole("textbox", { name: "درصد پلتفرم" })).toHaveValue(
    /۱۵/,
  )
  await expect(page.getByText("درصد باقی‌مانده").locator("..")).toContainText(
    "۰٪",
  )
  await page.getByRole("button", { name: "ذخیره و اعمال" }).click()
  await expect(page.getByText("برنامه تمرینی").last()).toBeVisible()
  const trainingRow = page.getByRole("row", { name: /برنامه تمرینی/ }).last()
  await trainingRow.getByRole("button", { name: "ویرایش" }).click()
  const coachShare = page.getByRole("textbox", { name: /درصد مربی/ })
  await expect(coachShare).toHaveValue("۵۰")
  await coachShare.fill("49")
  await expect(page.locator(".m3-dialog .m3-remaining strong")).toHaveText("۰٪")
  await page.getByRole("button", { name: "ذخیره و اعمال فوری" }).click()
  await expect(page.getByText("برنامه تمرینی").last()).toBeVisible()

  await page.getByRole("link", { name: "فروش و پرداخت‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "فروش و پرداخت‌ها" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "فروش جدید" }).click()
  await page.getByRole("button", { name: "حق عضویت باشگاه" }).click()
  await page.getByRole("option", { name: "برنامه تمرینی" }).click()
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
  await page.getByRole("button", { name: "پلن و درخواست‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "پلن‌های فروش مربی" }),
  ).toBeVisible()
  const planOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(planOverflow).toBeLessThanOrEqual(1)
})

test("global administrator manages platform contracts and sees cross-gym overview", async ({
  page,
  request,
}) => {
  const contractName = `قرارداد اختصاصی تست ${Date.now()}`
  await ensureSeededPlatformPolicy(request)
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
  await page.getByRole("button", { name: "ذخیره و اعمال" }).click()
  const createdRow = page.getByRole("row", { name: new RegExp(contractName) })
  await expect(createdRow).toBeVisible()
  await expect(createdRow.getByText("فعال")).toBeVisible()

  const editedName = `${contractName} ویرایش`
  await createdRow.getByRole("button", { name: "ویرایش" }).click()
  await page.getByRole("textbox").first().fill(editedName)
  await page.getByRole("button", { name: "ذخیره و اعمال" }).click()
  const editedRow = page.getByRole("row", { name: new RegExp(editedName) })
  await expect(editedRow).toBeVisible()
  await expect(editedRow.getByText("فعال")).toBeVisible()

  await page.getByRole("link", { name: "مالیات‌ها" }).click()
  await expect(page.getByRole("heading", { name: "مالیات‌ها" })).toBeVisible()
  await expect(page.getByText("Value-added tax")).toBeVisible()
})

test("coach sells a training plan and receives an athlete request", async ({
  page,
  request,
}) => {
  await ensureSeededPlatformPolicy(request)
  const planTitle = `پلن آزمون ${Date.now()}`
  const athleteNote = `درخواست آزمون ${Date.now()}`

  await page.context().clearCookies()
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await page.getByRole("button", { name: "پلن و درخواست‌ها" }).click()
  await expect(
    page.getByRole("heading", { name: "پلن‌های فروش مربی" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "پلن جدید" }).first().click()
  await page.getByRole("button", { name: "انتخاب کنید مربی" }).click()
  await page.getByRole("option", { name: "رضا مربی" }).click()
  await page.getByRole("textbox", { name: "عنوان پلن" }).fill(planTitle)
  await page.getByRole("textbox", { name: "قیمت پایه (تومان)" }).fill("1000000")
  await page
    .getByRole("textbox", { name: "توضیحات" })
    .fill("برنامه اختصاصی بر اساس پرونده ورزشکار")
  await page.getByRole("button", { name: "ذخیره و اعمال" }).click()
  const planRow = page.getByRole("row", { name: new RegExp(planTitle) })
  await expect(planRow).toBeVisible()
  await expect(planRow.getByText("فعال")).toBeVisible()

  await page.context().clearCookies()
  await login(page, "nima@example.com", ADMIN_PASSWORD)
  await page.getByRole("button", { name: "برنامه من" }).click()
  await expect(page.getByText("پلن تمرینی مربی")).toBeVisible()
  await expect(page.getByText(planTitle)).toBeVisible()
  await page.getByRole("button", { name: "خرید و ارسال درخواست" }).click()
  await page.getByRole("textbox", { name: "توضیح برای مربی" }).fill(athleteNote)
  await page
    .getByRole("button", { name: "پرداخت آزمایشی و ثبت درخواست" })
    .click()
  await expect(page.getByText("درخواست برنامه برای مربی ثبت شد.")).toBeVisible()
  await expect(page.getByText("در انتظار ساخت برنامه").first()).toBeVisible()

  await page.context().clearCookies()
  await login(page, "reza@example.com", ADMIN_PASSWORD)
  await page.getByRole("button", { name: "پلن و درخواست‌ها" }).click()
  await expect(page.getByText(athleteNote)).toBeVisible()
  await expect(page.getByText("نیما ورزشکار").first()).toBeVisible()

  await page.getByRole("button", { name: "ورزشکاران" }).click()
  await page
    .getByRole("button", { name: /نیما ورزشکار/ })
    .first()
    .click()
  await page.getByRole("button", { name: "ساخت برنامه" }).first().click()
  await page.getByRole("button", { name: "درخواست خرید" }).click()
  await page.getByRole("option", { name: new RegExp(planTitle) }).click()
  await page
    .getByRole("textbox", { name: "عنوان برنامه" })
    .fill("برنامه خریداری‌شده")
  await page.getByRole("button", { name: "ایجاد" }).click()
  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit/)
})
