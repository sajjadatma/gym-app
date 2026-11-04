import {
  type APIRequestContext,
  expect,
  type Locator,
  type Page,
  test,
} from "@playwright/test"

import { API_URL } from "./credentials"

const SUPERUSER_EMAIL = process.env.PLAYWRIGHT_SUPERUSER_EMAIL
const SUPERUSER_PASSWORD = process.env.PLAYWRIGHT_SUPERUSER_PASSWORD

test.skip(
  !SUPERUSER_EMAIL || !SUPERUSER_PASSWORD,
  "PLAYWRIGHT_SUPERUSER_EMAIL/PASSWORD not configured",
)

async function login(page: Page) {
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(SUPERUSER_EMAIL!)
  await page.getByLabel(/رمز عبور/).fill(SUPERUSER_PASSWORD!)
  await page.getByRole("button", { name: "ورود" }).click()
  await page.waitForURL((url) => url.pathname !== "/login")
}

async function apiLogin(request: APIRequestContext) {
  const response = await request.post(`${API_URL}/api/v1/login/access-token`, {
    form: { username: SUPERUSER_EMAIL!, password: SUPERUSER_PASSWORD! },
  })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).access_token as string
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

async function choose(
  page: Page,
  container: Locator,
  label: string,
  option: string,
) {
  await container
    .getByRole("button", { name: new RegExp(label) })
    .first()
    .click()
  await page.getByRole("option", { name: option }).first().click()
}

function monthStart() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`
}

function today() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

function accrualPeriodFor(date: Date) {
  let year = date.getFullYear()
  let month = date.getMonth()
  if (date.getDate() > 1) {
    month += 1
    if (month > 11) {
      month = 0
      year += 1
    }
  }
  return `${year}-${String(month + 1).padStart(2, "0")}`
}

async function submitDialog(dialog: Locator, name = "ذخیره") {
  const button = dialog.getByRole("button", { name, exact: true })
  await expect(button).toBeEnabled()
  await button.click()
  await expect(dialog).toHaveCount(0)
}

test("superuser configures multi-gym group billing and issues a consolidated invoice", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(120_000)
  const suffix = Date.now()
  const token = await apiLogin(request)
  const gyms: Array<{ id: string; name: string }> = []
  for (const label of ["آلفا", "بتا"]) {
    const created = await request.post(`${API_URL}/api/v1/gyms/`, {
      headers: authHeaders(token),
      data: {
        name: `باشگاه گروه ${label} ${suffix}`,
        owner_email: `group-${label}-${suffix}@example.com`,
        owner_full_name: `مالک ${label}`,
        activation_method: "password",
        initial_password: "OwnerPass123!",
      },
    })
    expect(created.ok()).toBeTruthy()
    gyms.push((await created.json()).gym)
  }
  const groupName = `گروه پذیرش ${suffix}`

  await login(page)
  await page.goto("/platform/finance")
  await page.getByRole("tab", { name: "قراردادها" }).click()

  // Create a two-gym group with 70/30 allocations.
  await page.getByRole("button", { name: "گروه جدید" }).click()
  const groupDialog = page.getByRole("dialog")
  await groupDialog.getByLabel("نام").fill(groupName)
  await choose(page, groupDialog, "باشگاه ۱", gyms[0].name)
  await groupDialog.getByLabel("سهم ۱ (٪)").fill("۷۰")
  await groupDialog.getByRole("button", { name: "افزودن باشگاه" }).click()
  await choose(page, groupDialog, "باشگاه ۲", gyms[1].name)
  await groupDialog.getByLabel("سهم ۲ (٪)").fill("۲۰")
  await groupDialog.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(groupDialog.getByRole("alert")).toContainText(
    "مجموع سهم‌ها باید ۱۰۰٪ باشد",
  )
  await groupDialog.getByLabel("سهم ۲ (٪)").fill("۳۰")
  await submitDialog(groupDialog)
  await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

  const groupCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: groupName })
    .first()
  await expect(groupCard).toContainText(gyms[0].name)
  await expect(groupCard).toContainText("۷۰٪")
  await expect(groupCard).toContainText(gyms[1].name)
  await expect(groupCard).toContainText("۳۰٪")

  // Edit the group allocations to 60/40.
  await groupCard.getByRole("button", { name: "ویرایش" }).click()
  const editDialog = page.getByRole("dialog")
  await editDialog.getByLabel("سهم ۱ (٪)").fill("۶۰")
  await editDialog.getByLabel("سهم ۲ (٪)").fill("۴۰")
  await submitDialog(editDialog)
  await expect(page.getByText("ذخیره شد.").first()).toBeVisible()
  await expect(groupCard).toContainText("۶۰٪")
  await expect(groupCard).toContainText("۴۰٪")

  // Create a group subscription agreement with a 5% volume discount.
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  const agreementDialog = page.getByRole("dialog")
  await choose(page, agreementDialog, "گروه", groupName)
  await choose(page, agreementDialog, "مدل", "اشتراک")
  await agreementDialog.getByLabel("مبلغ اشتراک").fill("۱۰۰۰۰۰۰")
  await agreementDialog.getByLabel("تخفیف حجمی (٪)").fill("۱۲۰")
  await agreementDialog
    .getByRole("button", { name: "ذخیره", exact: true })
    .click()
  await expect(agreementDialog.getByRole("alert")).toContainText(
    "تخفیف حجمی باید بین ۰ و ۱۰۰٪ باشد",
  )
  await agreementDialog.getByLabel("تخفیف حجمی (٪)").fill("۵")
  await agreementDialog.getByRole("button", { name: "انتخاب تاریخ" }).click()
  const agreementDate = page
    .getByRole("dialog")
    .filter({ has: page.getByRole("grid") })
  await agreementDate.getByRole("button", { name: "قبلی" }).click()
  await agreementDate
    .getByRole("gridcell")
    .filter({ hasText: /^۱$/ })
    .first()
    .click()
  await submitDialog(agreementDialog)
  await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

  const agreementCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: groupName })
    .filter({ hasText: "SUBSCRIPTION" })
    .last()
  await expect(agreementCard).toContainText("DRAFT")
  await expect(agreementCard).toContainText("۵٪")
  const activate = agreementCard.getByRole("button", {
    name: "فعال‌سازی",
    exact: true,
  })
  await expect(activate).toBeEnabled()
  await activate.click()
  await expect(agreementCard).toContainText("EFFECTIVE")

  // Accrue both branches for the current month.
  await agreementCard.getByRole("button", { name: "ثبت تعهد دوره" }).click()
  const accrualDialog = page.getByRole("dialog")
  const accrualPeriod = accrualDialog.getByLabel("دوره میلادی (YYYY-MM)")
  await expect(accrualPeriod).toHaveValue(/^\d{4}-(0[1-9]|1[0-2])$/)
  await accrualPeriod.fill(currentMonth())
  await choose(page, accrualDialog, "شعبه", "همه شعب")
  await accrualDialog
    .getByRole("button", { name: "تأیید", exact: true })
    .click()
  await expect(accrualDialog).toHaveCount(0)
  await expect(page.getByText("تعهد دوره ثبت شد.").first()).toBeVisible()

  // Issue the consolidated group invoice.
  await page.getByRole("tab", { name: "صورتحساب‌ها" }).click()
  await page.getByRole("button", { name: "صورتحساب جدید" }).click()
  const invoiceDialog = page.getByRole("dialog")
  await choose(page, invoiceDialog, "دامنه", "گروه")
  await choose(page, invoiceDialog, "گروه صورتحساب", groupName)
  await submitDialog(invoiceDialog)
  await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

  const invoiceCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: groupName })
    .first()
  await expect(invoiceCard).toContainText("۹۵۰٬۰۰۰")
  await expect(invoiceCard).toContainText("۵۰٬۰۰۰")
  await expect(invoiceCard).toContainText(gyms[0].name)
  await expect(invoiceCard).toContainText("۶۰۰٬۰۰۰")
  await expect(invoiceCard).toContainText("۳۰٬۰۰۰")
  await expect(invoiceCard).toContainText("۵۷۰٬۰۰۰")
  await expect(invoiceCard).toContainText(gyms[1].name)
  await expect(invoiceCard).toContainText("۴۰۰٬۰۰۰")
  await expect(invoiceCard).toContainText("۲۰٬۰۰۰")
  await expect(invoiceCard).toContainText("۳۸۰٬۰۰۰")

  // Exact accounting facts through the API.
  const invoicesResponse = await request.get(
    `${API_URL}/api/v1/platform/invoices`,
    { headers: authHeaders(token) },
  )
  expect(invoicesResponse.ok()).toBeTruthy()
  const groupId = await groupsResponseGroupId(request, token, groupName)
  const invoice = (await invoicesResponse.json()).data.find(
    (row: { group_id: string | null }) => row.group_id === groupId,
  )
  expect(invoice).toBeTruthy()
  expect(invoice.discount_irr).toBe(50_000)
  expect(invoice.total_irr).toBe(950_000)
  const lineByGym = new Map(
    invoice.lines.map((line: { gym_id: string }) => [line.gym_id, line]),
  )
  const alphaLine = lineByGym.get(gyms[0].id) as {
    gross_irr: number
    discount_irr: number
    amount_irr: number
  }
  const betaLine = lineByGym.get(gyms[1].id) as {
    gross_irr: number
    discount_irr: number
    amount_irr: number
  }
  expect(alphaLine).toMatchObject({
    gross_irr: 600_000,
    discount_irr: 30_000,
    amount_irr: 570_000,
  })
  expect(betaLine).toMatchObject({
    gross_irr: 400_000,
    discount_irr: 20_000,
    amount_irr: 380_000,
  })
  expect(invoice.lines).toHaveLength(2)

  for (const [gym, expected] of [
    [gyms[0], 570_000],
    [gyms[1], 380_000],
  ] as const) {
    const report = await request.get(
      `${API_URL}/api/v1/platform/reports/gyms/${gym.id}`,
      {
        headers: authHeaders(token),
        params: { from_date: monthStart(), to_date: today() },
      },
    )
    expect(report.ok()).toBeTruthy()
    const detail = await report.json()
    expect(detail.recognized_revenue_irr).toBe(expected)
    expect(detail.receivable_irr).toBe(expected)
  }

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
  await testInfo.attach("platform-group-billing", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})

test("superuser accrues a default-dated agreement using the earliest valid period", async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const suffix = Date.now()
  const token = await apiLogin(request)
  const created = await request.post(`${API_URL}/api/v1/gyms/`, {
    headers: authHeaders(token),
    data: {
      name: `باشگاه تعهد پیش‌فرض ${suffix}`,
      owner_email: `default-accrual-${suffix}@example.com`,
      owner_full_name: "مالک تعهد",
      activation_method: "password",
      initial_password: "OwnerPass123!",
    },
  })
  expect(created.ok()).toBeTruthy()
  const gym = (await created.json()).gym as { id: string; name: string }

  await login(page)
  await page.goto("/platform/finance")
  await page.getByRole("tab", { name: "قراردادها" }).click()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  const dialog = page.getByRole("dialog")
  await choose(page, dialog, "باشگاه", gym.name)
  await choose(page, dialog, "مدل", "اشتراک")
  await dialog.getByLabel("مبلغ اشتراک").fill("۵۰۰۰۰۰")
  await submitDialog(dialog)
  await expect(page.getByText("ذخیره شد.").first()).toBeVisible()

  const card = page
    .locator(".m3-card--outlined")
    .filter({ hasText: gym.name })
    .filter({ hasText: "SUBSCRIPTION" })
    .last()
  const activate = card.getByRole("button", {
    name: "فعال‌سازی",
    exact: true,
  })
  await expect(activate).toBeEnabled()
  await activate.click()
  await expect(card).toContainText("EFFECTIVE")

  await card.getByRole("button", { name: "ثبت تعهد دوره" }).click()
  const accrualDialog = page.getByRole("dialog")
  const expectedPeriod = accrualPeriodFor(new Date())
  await expect(accrualDialog.getByLabel("دوره میلادی (YYYY-MM)")).toHaveValue(
    expectedPeriod,
  )
  await accrualDialog
    .getByRole("button", { name: "تأیید", exact: true })
    .click()
  await expect(accrualDialog).toHaveCount(0)
  await expect(page.getByText("تعهد دوره ثبت شد.").first()).toBeVisible()

  const receivables = await request.get(
    `${API_URL}/api/v1/platform/receivables`,
    { headers: authHeaders(token), params: { gym_id: gym.id } },
  )
  expect(receivables.ok()).toBeTruthy()
  const rows = (await receivables.json()).data as Array<{
    amount_irr: number
    source_key: string
  }>
  expect(rows).toHaveLength(1)
  expect(rows[0].amount_irr).toBe(500_000)
  expect(rows[0].source_key).toContain(expectedPeriod)
})

async function groupsResponseGroupId(
  request: APIRequestContext,
  token: string,
  groupName: string,
) {
  const response = await request.get(`${API_URL}/api/v1/platform/groups`, {
    headers: authHeaders(token),
  })
  expect(response.ok()).toBeTruthy()
  const group = (await response.json()).data.find(
    (row: { name: string }) => row.name === groupName,
  )
  expect(group).toBeTruthy()
  return group.id as string
}
