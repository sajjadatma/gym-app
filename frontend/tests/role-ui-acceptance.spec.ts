import { statSync } from "node:fs"

import {
  type APIRequestContext,
  expect,
  type Locator,
  type Page,
  type TestInfo,
  test,
} from "@playwright/test"

import {
  ADMIN_EMAIL,
  API_URL,
  ATHLETE_EMAIL,
  DEMO_PASSWORD,
} from "./credentials"

const SUPERUSER_EMAIL = process.env.PLAYWRIGHT_SUPERUSER_EMAIL
const SUPERUSER_PASSWORD = process.env.PLAYWRIGHT_SUPERUSER_PASSWORD

async function login(page: Page, email: string, password: string) {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(email)
  await page.getByLabel(/رمز عبور/).fill(password)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL((url) => url.pathname !== "/login")
  await expect(page.locator(".m3-topbar")).toBeVisible()
}

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await request.post(`${API_URL}/api/v1/login/access-token`, {
    form: { username: email, password },
  })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).access_token as string
}

function authHeaders(token: string, gymId?: string) {
  return {
    Authorization: `Bearer ${token}`,
    ...(gymId ? { "X-Gym-ID": gymId } : {}),
  }
}

async function currentGymId(page: Page) {
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()
  return gymId!
}

async function choose(
  page: Page,
  container: Locator,
  label: string,
  option: string | RegExp,
) {
  await container
    .getByRole("button", { name: new RegExp(label) })
    .first()
    .click()
  await page.getByRole("option", { name: option }).first().click()
}

async function submitDialog(dialog: Locator, name = "ذخیره") {
  const button = dialog.getByRole("button", { name, exact: true })
  await expect(button).toBeEnabled()
  await button.click()
  await expect(dialog).toHaveCount(0)
}

async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
}

function monthStart() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

async function attachScreenshot(page: Page, testInfo: TestInfo, name: string) {
  await testInfo.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
}

test.describe("role UI acceptance", () => {
  test("superuser completes platform finance journeys", async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(60_000)
    test.skip(
      !SUPERUSER_EMAIL || !SUPERUSER_PASSWORD,
      "PLAYWRIGHT_SUPERUSER_EMAIL/PASSWORD not configured",
    )
    const suffix = Date.now()
    await login(page, SUPERUSER_EMAIL!, SUPERUSER_PASSWORD!)
    await page.goto("/platform/finance")
    await expect(
      page.getByRole("heading", { name: "مالی پلتفرم" }),
    ).toBeVisible()
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
    await expect(page.getByText("MRR")).toBeVisible()
    await expect(page.getByText("وجه جمع‌آوری‌شده")).toBeVisible()
    await expect(page.getByText("درآمد شناسایی‌شده")).toBeVisible()

    const token = await apiLogin(request, SUPERUSER_EMAIL!, SUPERUSER_PASSWORD!)
    const createdGym = await request.post(`${API_URL}/api/v1/gyms/`, {
      headers: authHeaders(token),
      data: {
        name: `باشگاه پذیرش ${suffix}`,
        owner_email: `ui-owner-${suffix}@example.com`,
        owner_full_name: "مالک پذیرش",
        activation_method: "password",
        initial_password: "OwnerPass123!",
      },
    })
    expect(createdGym.ok()).toBeTruthy()
    const gym = (await createdGym.json()).gym as { id: string; name: string }

    // Plans and versions.
    await page.getByRole("tab", { name: "پلن‌ها" }).click()
    await page.getByRole("button", { name: "پلن جدید" }).click()
    const planDialog = page.getByRole("dialog")
    await planDialog.getByLabel("کد").fill(`UI-${suffix}`)
    await planDialog.getByLabel("نام").fill(`پلن پذیرش ${suffix}`)
    await planDialog.getByLabel("قیمت ماهانه").fill("۵۰۰۰۰۰")
    await submitDialog(planDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    const planCard = page
      .locator(".m3-card--outlined")
      .filter({ hasText: `UI-${suffix}` })
      .first()
    await expect(planCard).toBeVisible()
    await expect(planCard).toContainText("ACTIVE")
    await expect(planCard).toContainText("۵۰۰٬۰۰۰")
    await planCard.getByRole("button", { name: "نسخه جدید" }).click()
    const versionDialog = page.getByRole("dialog")
    await expect(
      versionDialog.getByRole("button", { name: "انتخاب تاریخ" }),
    ).toBeVisible()
    await versionDialog.getByLabel("قیمت ماهانه").fill("۶۰۰۰۰۰")
    await submitDialog(versionDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()
    await expect(planCard).toContainText("v2")
    await expect(planCard).toContainText("DRAFT")
    await expect(planCard).toContainText("۶۰۰٬۰۰۰")
    const activateVersion = planCard
      .getByRole("button", { name: "فعال‌سازی" })
      .first()
    await expect(activateVersion).toBeEnabled()
    await activateVersion.click()
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()
    await expect(planCard).toContainText("ACTIVE")

    // Groups and agreements.
    await page.getByRole("tab", { name: "قراردادها" }).click()
    await page.getByRole("button", { name: "گروه جدید" }).click()
    const groupDialog = page.getByRole("dialog")
    await groupDialog.getByLabel("نام").fill(`گروه پذیرش ${suffix}`)
    await choose(page, groupDialog, "باشگاه", gym.name)
    await submitDialog(groupDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    await page.getByRole("button", { name: "قرارداد جدید" }).click()
    const agreementDialog = page.getByRole("dialog")
    await choose(page, agreementDialog, "باشگاه", gym.name)
    await choose(page, agreementDialog, "مدل", "اشتراک")
    await agreementDialog.getByLabel("مبلغ اشتراک").fill("۵۰۰۰۰۰")
    await agreementDialog.getByRole("button", { name: "انتخاب تاریخ" }).click()
    const agreementDate = page
      .getByRole("dialog")
      .filter({ has: page.getByRole("grid") })
    await agreementDate
      .getByRole("gridcell")
      .filter({ hasText: /^۱$/ })
      .first()
      .click()
    await submitDialog(agreementDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    const agreementCard = page
      .locator(".m3-card--outlined")
      .filter({ hasText: "SUBSCRIPTION · v1" })
      .filter({ hasText: gym.id })
      .last()
    await expect(agreementCard).toBeVisible()
    await expect(agreementCard).toContainText("DRAFT")
    await expect(agreementCard).toContainText(/[۰-۹]/)
    const activateAgreement = agreementCard.getByRole("button", {
      name: "فعال‌سازی",
      exact: true,
    })
    await expect(activateAgreement).toBeEnabled()
    await activateAgreement.click()
    await expect(agreementCard).toContainText("EFFECTIVE")

    const agreementsResponse = await request.get(
      `${API_URL}/api/v1/platform/agreements`,
      { headers: authHeaders(token) },
    )
    expect(agreementsResponse.ok()).toBeTruthy()
    const agreement = (await agreementsResponse.json()).data
      .filter(
        (row: {
          gym_id: string | null
          mode: string
          status: string
          created_at: string
        }) =>
          row.gym_id === gym.id &&
          row.mode === "SUBSCRIPTION" &&
          row.status === "EFFECTIVE",
      )
      .sort((left: { created_at: string }, right: { created_at: string }) =>
        right.created_at.localeCompare(left.created_at),
      )[0]
    expect(agreement).toBeTruthy()

    const accrued = await request.post(
      `${API_URL}/api/v1/platform/agreements/${agreement.id}/accrue-period`,
      {
        headers: {
          ...authHeaders(token),
          "Idempotency-Key": `ui-accrue-${suffix}`,
        },
        data: { period: currentMonth() },
      },
    )
    expect(accrued.ok()).toBeTruthy()

    // Issue an invoice and record a payment.
    await page.getByRole("tab", { name: "صورتحساب‌ها" }).click()
    await page.getByRole("button", { name: "صورتحساب جدید" }).click()
    const invoiceDialog = page.getByRole("dialog")
    await choose(page, invoiceDialog, "باشگاه", gym.name)
    await submitDialog(invoiceDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    const invoiceCard = page
      .locator(".m3-card--outlined")
      .filter({ hasText: "Platform subscription" })
      .filter({ hasText: "۵۰۰٬۰۰۰" })
      .first()
    await expect(invoiceCard).toBeVisible()
    await invoiceCard.getByRole("button", { name: "ثبت پرداخت" }).click()
    const paymentDialog = page.getByRole("dialog")
    await paymentDialog.getByLabel("مبلغ").fill("۱۰۰۰۰۰")
    await submitDialog(paymentDialog, "تأیید")
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()
    await expect(invoiceCard).toContainText("۱۰۰٬۰۰۰")

    // A second gym gives us an independent receivable so cancellation can be
    // exercised without touching the partially paid invoice.
    const createdCancelGym = await request.post(`${API_URL}/api/v1/gyms/`, {
      headers: authHeaders(token),
      data: {
        name: `باشگاه لغو ${suffix}`,
        owner_email: `ui-cancel-owner-${suffix}@example.com`,
        owner_full_name: "مالک لغو",
        activation_method: "password",
        initial_password: "OwnerPass123!",
      },
    })
    expect(createdCancelGym.ok()).toBeTruthy()
    const cancelGym = (await createdCancelGym.json()).gym as {
      id: string
      name: string
    }
    const secondAgreement = await request.post(
      `${API_URL}/api/v1/platform/agreements`,
      {
        headers: {
          ...authHeaders(token),
          "Idempotency-Key": `ui-agreement-${suffix}`,
        },
        data: {
          gym_id: cancelGym.id,
          mode: "SUBSCRIPTION",
          effective_from: monthStart(),
          subscription_amount_irr: 300000,
          terms: [],
        },
      },
    )
    expect(secondAgreement.ok()).toBeTruthy()
    const secondAgreementId = (await secondAgreement.json()).id
    const activated = await request.post(
      `${API_URL}/api/v1/platform/agreements/${secondAgreementId}/activate`,
      {
        headers: {
          ...authHeaders(token),
          "Idempotency-Key": `ui-activate-${suffix}`,
        },
      },
    )
    expect(activated.ok()).toBeTruthy()
    const secondAccrued = await request.post(
      `${API_URL}/api/v1/platform/agreements/${secondAgreementId}/accrue-period`,
      {
        headers: {
          ...authHeaders(token),
          "Idempotency-Key": `ui-accrue-2-${suffix}`,
        },
        data: { period: currentMonth() },
      },
    )
    expect(secondAccrued.ok()).toBeTruthy()

    await page.reload()
    await expect(
      page.getByRole("heading", { name: "مالی پلتفرم" }),
    ).toBeVisible()
    await page.getByRole("tab", { name: "صورتحساب‌ها" }).click()
    await page.getByRole("button", { name: "صورتحساب جدید" }).click()
    const secondInvoiceDialog = page.getByRole("dialog")
    await choose(page, secondInvoiceDialog, "باشگاه", cancelGym.name)
    await submitDialog(secondInvoiceDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    const secondInvoiceCard = page
      .locator(".m3-card--outlined")
      .filter({ hasText: "Platform subscription" })
      .filter({ hasText: "۳۰۰٬۰۰۰" })
      .first()
    await expect(secondInvoiceCard).toBeVisible()
    await secondInvoiceCard
      .getByRole("button", { name: "لغو صورتحساب" })
      .click()
    const cancelDialog = page.getByRole("dialog")
    const cancelConfirm = cancelDialog.getByRole("button", {
      name: "تأیید",
      exact: true,
    })
    await expect(cancelConfirm).toBeDisabled()
    await cancelDialog.getByLabel("دلیل لغو").fill("دلیل پذیرش رابط کاربری")
    await expect(cancelConfirm).toBeEnabled()
    await cancelConfirm.click()
    await expect(cancelDialog).toHaveCount(0)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()
    await expect(secondInvoiceCard).toContainText("CANCELLED")

    // Costs, reminders and exports.
    await page.getByRole("button", { name: "هزینه جدید" }).click()
    const costDialog = page.getByRole("dialog")
    await costDialog.getByLabel("دسته هزینه").fill(`هزینه پذیرش ${suffix}`)
    await costDialog.getByLabel("مبلغ").fill("50000")
    await choose(page, costDialog, "باشگاه", gym.name)
    await submitDialog(costDialog)
    await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

    await page.getByRole("tab", { name: "مطالبات" }).click()
    await expect(page.getByText("یادآوری‌ها")).toBeVisible()
    await expect(page.getByText(/یادآوری فقط درون‌برنامه‌ای/)).toBeVisible()

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "خروجی CSV" }).click(),
    ])
    expect(download.suggestedFilename()).toBe("platform.csv")
    const downloadPath = await download.path()
    expect(downloadPath).toBeTruthy()
    expect(statSync(downloadPath!).size).toBeGreaterThan(0)

    await attachScreenshot(page, testInfo, "superuser-platform-finance")

    await page.setViewportSize({ width: 390, height: 844 })
    await expect(
      page.getByRole("heading", { name: "مالی پلتفرم" }),
    ).toBeVisible()
    await expect(
      page.locator(".m3-mobile-nav").getByText("مالی پلتفرم", { exact: true }),
    ).toBeVisible()
    await expectNoOverflow(page)
    await attachScreenshot(page, testInfo, "superuser-platform-finance-mobile")
  })

  test("gym admin reviews finance, exports and platform billing", async ({
    page,
    request,
  }, testInfo) => {
    const suffix = Date.now()
    await login(page, ADMIN_EMAIL, DEMO_PASSWORD)
    const gymId = await currentGymId(page)

    const adminToken = await apiLogin(request, ADMIN_EMAIL, DEMO_PASSWORD)
    const staffEmail = `ui-finance-${suffix}@example.com`
    const createdStaff = await request.post(
      `${API_URL}/api/v1/gyms/${gymId}/members`,
      {
        headers: authHeaders(adminToken, gymId),
        data: {
          email: staffEmail,
          full_name: "کارشناس مالی پذیرش",
          roles: ["FINANCE_STAFF"],
          activation_method: "password",
          initial_password: "StaffPass123!",
        },
      },
    )
    expect(createdStaff.ok()).toBeTruthy()

    await page.goto(`/gyms/${gymId}/finance`)
    await expect(
      page.getByRole("heading", { name: "مالی باشگاه" }),
    ).toBeVisible()
    await expect(page.getByText("داشبورد مالی")).toBeVisible()
    await expect(page.getByText("جریان نقدی خالص")).toBeVisible()
    await expect(page.getByText("درآمد شناسایی‌شده")).toBeVisible()
    await expect(page.getByText("سود عملیاتی تقریبی")).toBeVisible()

    const closePeriodButton = page.getByRole("button", { name: "بستن دوره" })
    if (await closePeriodButton.isVisible().catch(() => false)) {
      await closePeriodButton.click()
      const closeDialog = page.getByRole("dialog")
      await expect(closeDialog).toContainText("بازگشت‌پذیر نیست")
      await closeDialog.getByRole("button", { name: "انصراف" }).click()
      await expect(closeDialog).toHaveCount(0)
    }

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "خروجی CSV" }).click(),
    ])
    expect(download.suggestedFilename()).toBe("finance.csv")
    const downloadPath = await download.path()
    expect(downloadPath).toBeTruthy()
    expect(statSync(downloadPath!).size).toBeGreaterThan(0)

    await page.getByRole("tab", { name: "فاکتورها" }).click()
    await page.getByRole("button", { name: "فاکتور جدید" }).click()
    const invoiceDialog = page.getByRole("dialog")
    await invoiceDialog
      .getByRole("button", { name: "ذخیره", exact: true })
      .click()
    await expect(invoiceDialog.getByRole("alert")).toContainText(
      "مشتری را انتخاب کنید",
    )
    await invoiceDialog.getByRole("button", { name: "انصراف" }).click()

    await page.getByRole("tab", { name: "مالی پلتفرم" }).click()
    await expect(page.getByText("صورتحساب‌ها")).toBeVisible()
    await expect(page.getByText("مطالبات")).toBeVisible()
    await expect(page.getByText("یادآوری‌ها")).toBeVisible()
    await expect(page.getByRole("button", { name: "ثبت پرداخت" })).toHaveCount(
      0,
    )

    // Only the opening-balance grant supports an amount ceiling; the UI hides
    // the field for every other permission.
    await page.getByRole("tab", { name: "نمای کلی" }).click()
    await expect(page.getByText("دسترسی کارشناسان مالی")).toBeVisible()
    const staffRow = page
      .locator(".row--between")
      .filter({ hasText: staffEmail })
      .first()
    await expect(staffRow).toBeVisible()
    await staffRow.getByRole("button", { name: "مدیریت دسترسی" }).click()
    const grantDialog = page.getByRole("dialog")
    await grantDialog
      .getByRole("switch", { name: "ثبت موجودی افتتاحیه" })
      .click()
    await expect(grantDialog.getByLabel("سقف مبلغ")).toBeVisible()
    await grantDialog
      .getByRole("switch", { name: "ثبت موجودی افتتاحیه" })
      .click()
    await expect(grantDialog.getByLabel("سقف مبلغ")).toHaveCount(0)
    await grantDialog.getByRole("switch", { name: "ثبت دریافت" }).click()
    await expect(grantDialog.getByLabel("سقف مبلغ")).toHaveCount(0)
    await grantDialog.getByRole("button", { name: "انصراف" }).click()

    await attachScreenshot(page, testInfo, "gym-admin-finance")

    await page.setViewportSize({ width: 390, height: 844 })
    await expect(
      page.getByRole("heading", { name: "مالی باشگاه" }),
    ).toBeVisible()
    await expect(
      page.locator(".m3-mobile-nav").getByText("مالی", { exact: true }),
    ).toBeVisible()
    await expectNoOverflow(page)
    await attachScreenshot(page, testInfo, "gym-admin-finance-mobile")
  })

  test("finance staff sees only granted finance actions and boundaries hold", async ({
    page,
    request,
  }, testInfo) => {
    const suffix = Date.now()
    const adminToken = await apiLogin(request, ADMIN_EMAIL, DEMO_PASSWORD)
    const gymsResponse = await request.get(`${API_URL}/api/v1/gyms/`, {
      headers: authHeaders(adminToken),
    })
    expect(gymsResponse.ok()).toBeTruthy()
    const gymId = (await gymsResponse.json()).data[0].id as string

    const staffEmail = `ui-staff-${suffix}@example.com`
    const initialPassword = "StaffPass123!"
    const finalPassword = "StaffPass456!"
    const created = await request.post(
      `${API_URL}/api/v1/gyms/${gymId}/members`,
      {
        headers: authHeaders(adminToken, gymId),
        data: {
          email: staffEmail,
          full_name: "کارشناس مرزها",
          roles: ["FINANCE_STAFF"],
          activation_method: "password",
          initial_password: initialPassword,
        },
      },
    )
    expect(created.ok()).toBeTruthy()
    const staffUserId = (await created.json()).member.user_id as string

    const staffToken = await apiLogin(request, staffEmail, initialPassword)
    const changed = await request.post(`${API_URL}/api/v1/users/me/password`, {
      headers: authHeaders(staffToken),
      data: {
        current_password: initialPassword,
        new_password: finalPassword,
      },
    })
    expect(changed.ok()).toBeTruthy()

    const granted = await request.put(
      `${API_URL}/api/v1/finance/grants/${staffUserId}`,
      {
        headers: authHeaders(adminToken, gymId),
        data: {
          grants: [
            { permission: "finance.catalog.manage", amount_limit_irr: null },
            { permission: "finance.invoice.manage", amount_limit_irr: null },
            { permission: "finance.payment.record", amount_limit_irr: null },
            { permission: "finance.refund.manage", amount_limit_irr: null },
            { permission: "finance.expense.manage", amount_limit_irr: null },
            { permission: "finance.membership.manage", amount_limit_irr: null },
          ],
        },
      },
    )
    expect(granted.ok()).toBeTruthy()

    const unsupported = await request.put(
      `${API_URL}/api/v1/finance/grants/${staffUserId}`,
      {
        headers: authHeaders(adminToken, gymId),
        data: {
          grants: [
            {
              permission: "finance.payment.record",
              amount_limit_irr: 100000,
            },
          ],
        },
      },
    )
    expect(unsupported.status()).toBe(400)
    expect((await unsupported.json()).detail).toBe(
      "finance_amount_limit_not_supported",
    )

    await login(page, staffEmail, finalPassword)
    await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
    const nav = page.locator(".m3-nav-rail")
    await expect(nav.getByText("مالی", { exact: true })).toBeVisible()
    await expect(nav.getByText("اعضا", { exact: true })).toHaveCount(0)
    await expect(nav.getByText("ورزشکاران", { exact: true })).toHaveCount(0)

    await page.getByRole("button", { name: "مالی", exact: true }).click()
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
    await expect(
      page.getByRole("heading", { name: "مالی باشگاه" }),
    ).toBeVisible()

    await page.getByRole("tab", { name: "نمای کلی" }).click()
    await expect(
      page.getByRole("button", { name: "ثبت موجودی افتتاحیه" }),
    ).toHaveCount(0)
    await expect(page.getByText("دسترسی کارشناسان مالی")).toHaveCount(0)
    const [staffDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "خروجی CSV" }).click(),
    ])
    expect(staffDownload.suggestedFilename()).toBe("finance.csv")
    expect((await staffDownload.path())!).toBeTruthy()

    await page.getByRole("tab", { name: "فاکتورها" }).click()
    await expect(
      page.getByRole("button", { name: "فاکتور جدید" }),
    ).toBeVisible()
    await page.getByRole("button", { name: "فاکتور جدید" }).click()
    const customerDialog = page.getByRole("dialog")
    await customerDialog.getByRole("button", { name: /^مشتری/ }).click()
    await expect(page.getByRole("option").first()).toBeVisible()
    await page.keyboard.press("Escape")
    await customerDialog.getByRole("button", { name: "انصراف" }).click()
    await page.getByRole("tab", { name: "فروش و خدمات" }).click()
    await expect(
      page.getByRole("button", { name: "افزودن آیتم" }),
    ).toBeVisible()
    await page.getByRole("tab", { name: "دریافت‌ها" }).click()
    await expect(page.getByRole("button", { name: "ثبت دریافت" })).toBeVisible()
    await page.getByRole("tab", { name: "بازپرداخت‌ها" }).click()
    await expect(
      page.getByRole("button", { name: "درخواست بازپرداخت" }),
    ).toBeVisible()
    await page.getByRole("tab", { name: "هزینه‌ها" }).click()
    await expect(page.getByRole("button", { name: "ثبت هزینه" })).toBeVisible()
    const staffExpense = `هزینه کارشناس ${suffix}`
    await page.getByRole("button", { name: "ثبت هزینه" }).click()
    const expenseDialog = page.getByRole("dialog")
    await expenseDialog.getByLabel("دسته").fill(staffExpense)
    await expenseDialog.getByLabel(/^مبلغ/).fill("50000")
    await submitDialog(expenseDialog)
    await expect(page.getByText("هزینه ثبت شد.").first()).toBeVisible()
    const staffExpenseCard = page
      .locator(".m3-card--outlined")
      .filter({ hasText: staffExpense })
      .first()
    await expect(staffExpenseCard).toBeVisible()
    await expect(staffExpenseCard).toContainText(/[۰-۹]/)
    await expect(staffExpenseCard).toContainText(/ریال|تومان/)
    await page.getByRole("tab", { name: "عضویت‌های پولی" }).click()
    await expect(page.getByRole("button", { name: "ثبت عضویت" })).toBeVisible()
    await page.getByRole("tab", { name: "مربیان" }).click()
    await expect(
      page.getByRole("button", { name: "قرارداد جدید" }),
    ).toHaveCount(0)

    await page.goto(`/gyms/${gymId}/members`)
    await expect(page).toHaveURL(new RegExp(`/gyms/${gymId}$`))
    await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()

    const staffTokenAfter = await apiLogin(request, staffEmail, finalPassword)
    const membersDenied = await request.get(
      `${API_URL}/api/v1/gyms/${gymId}/members`,
      { headers: authHeaders(staffTokenAfter, gymId) },
    )
    expect(membersDenied.status()).toBe(403)
    expect((await membersDenied.json()).detail).toBe("gym_admin_required")

    const grantsDenied = await request.put(
      `${API_URL}/api/v1/finance/grants/${staffUserId}`,
      {
        headers: authHeaders(staffTokenAfter, gymId),
        data: { grants: [] },
      },
    )
    expect(grantsDenied.status()).toBe(403)

    await attachScreenshot(page, testInfo, "finance-staff-boundaries")

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/gyms/${gymId}/finance`)
    await expect(
      page.getByRole("heading", { name: "مالی باشگاه" }),
    ).toBeVisible()
    await expect(
      page.locator(".m3-mobile-nav").getByText("مالی", { exact: true }),
    ).toBeVisible()
    await expectNoOverflow(page)
    await attachScreenshot(page, testInfo, "finance-staff-mobile")
  })

  test("coach sees only own earnings and cannot enter gym finance", async ({
    page,
    request,
  }, testInfo) => {
    await login(page, "reza@example.com", DEMO_PASSWORD)
    const gymId = await currentGymId(page)

    await page.goto(`/gyms/${gymId}/my/earnings`)
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
    await expect(
      page.getByRole("heading", { name: "درآمد من", level: 1 }),
    ).toBeVisible()
    await expect(
      page.locator(".m3-nav-rail").getByText("درآمد من", { exact: true }),
    ).toBeVisible()
    await expect(
      page.locator(".m3-nav-rail").getByText("مالی", { exact: true }),
    ).toHaveCount(0)

    await page.goto(`/gyms/${gymId}/finance`)
    await expect(page).toHaveURL(new RegExp(`/gyms/${gymId}$`))
    await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()

    const coachToken = await apiLogin(
      request,
      "reza@example.com",
      DEMO_PASSWORD,
    )
    const me = await request.get(`${API_URL}/api/v1/users/me`, {
      headers: authHeaders(coachToken),
    })
    expect(me.ok()).toBeTruthy()
    const coachUserId = (await me.json()).id as string

    const own = await request.get(`${API_URL}/api/v1/finance/my/earnings`, {
      headers: authHeaders(coachToken, gymId),
    })
    expect(own.ok()).toBeTruthy()
    for (const row of (await own.json()).data) {
      expect(row.coach_user_id).toBe(coachUserId)
    }

    const adminDenied = await request.get(
      `${API_URL}/api/v1/finance/coach-earnings?coach_user_id=${coachUserId}`,
      { headers: authHeaders(coachToken, gymId) },
    )
    expect(adminDenied.status()).toBe(403)

    const adminToken = await apiLogin(request, ADMIN_EMAIL, DEMO_PASSWORD)
    const allGyms = await request.get(`${API_URL}/api/v1/gyms/`, {
      headers: authHeaders(adminToken),
    })
    const otherGym = (await allGyms.json()).data.find(
      (gym: { id: string }) => gym.id !== gymId,
    )
    expect(otherGym).toBeTruthy()
    const crossGym = await request.get(
      `${API_URL}/api/v1/finance/my/earnings`,
      { headers: authHeaders(coachToken, otherGym.id) },
    )
    expect(crossGym.status()).toBe(403)
    expect((await crossGym.json()).detail).toBe("not_a_gym_member")

    await attachScreenshot(page, testInfo, "coach-earnings")

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/gyms/${gymId}/my/earnings`)
    await expect(
      page.getByRole("heading", { name: "درآمد من", level: 1 }),
    ).toBeVisible()
    await expectNoOverflow(page)
    await attachScreenshot(page, testInfo, "coach-earnings-mobile")
  })

  test("athlete sees personal finance only and cannot reach gym finance", async ({
    page,
    request,
  }, testInfo) => {
    await login(page, ATHLETE_EMAIL, DEMO_PASSWORD)
    const gymId = await currentGymId(page)

    await page.goto(`/gyms/${gymId}/my/finance`)
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
    await expect(page.getByRole("heading", { name: "مالی من" })).toBeVisible()
    await expect(page.getByText("دریافت‌های من")).toBeVisible()
    await expect(page.getByText("عضویت من").first()).toBeVisible()

    await page.goto(`/gyms/${gymId}/finance`)
    await expect(page).toHaveURL(new RegExp(`/gyms/${gymId}$`))
    await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()

    const athleteToken = await apiLogin(request, ATHLETE_EMAIL, DEMO_PASSWORD)
    const account = await request.get(`${API_URL}/api/v1/finance/my/account`, {
      headers: authHeaders(athleteToken, gymId),
    })
    expect(account.ok()).toBeTruthy()

    const coachEarnings = await request.get(
      `${API_URL}/api/v1/finance/my/earnings`,
      { headers: authHeaders(athleteToken, gymId) },
    )
    expect(coachEarnings.status()).toBe(403)
    expect((await coachEarnings.json()).detail).toBe("coach_access_required")

    const financeList = await request.get(
      `${API_URL}/api/v1/finance/coach-earnings`,
      { headers: authHeaders(athleteToken, gymId) },
    )
    expect(financeList.status()).toBe(403)
    expect((await financeList.json()).detail).toBe("finance_access_denied")

    await attachScreenshot(page, testInfo, "athlete-finance")

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/gyms/${gymId}/my/finance`)
    await expect(page.getByRole("heading", { name: "مالی من" })).toBeVisible()
    await expect(
      page.locator(".m3-mobile-nav").getByText("مالی من", { exact: true }),
    ).toBeVisible()
    await expectNoOverflow(page)
    await attachScreenshot(page, testInfo, "athlete-finance-mobile")
  })
})
