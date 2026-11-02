import { expect, type Locator, type Page, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

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

async function chooseIndex(
  page: Page,
  container: Locator,
  label: string,
  index: number,
) {
  await container
    .getByRole("button", { name: new RegExp(label) })
    .first()
    .click()
  await page.getByRole("option").nth(index).click()
}

async function openFinance(page: Page) {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()
  await page.goto(`/gyms/${gymId}/finance`)
  await expect(page.getByRole("heading", { name: "مالی باشگاه" })).toBeVisible()
}

const ATHLETE_NAME = /نیما ورزشکار/

test("gym admin invoices, takes a payment and settles a refund with the original method", async ({
  page,
}) => {
  const suffix = Date.now()
  const description = `فاکتور فاز دو ${suffix}`
  await openFinance(page)

  await page.getByRole("tab", { name: "فاکتورها" }).click()
  await page.getByRole("button", { name: "فاکتور جدید" }).click()

  const create = page.getByRole("dialog")
  await choose(page, create, "مشتری", ATHLETE_NAME)
  await create.getByLabel("شرح").first().fill(description)
  await create.getByLabel("شرح").nth(1).fill("خدمات تست فاز دو")
  await create.getByLabel("قیمت واحد").fill("100000")
  await create.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("فاکتور پیش‌نویس ساخته شد.")).toBeVisible()

  const invoiceCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: description })
    .first()
  await expect(invoiceCard.locator(".m3-status--draft")).toBeVisible()
  await expect(invoiceCard.getByText(/منبع جذب مشتری/)).toBeVisible()

  await invoiceCard
    .getByRole("button", { name: "صدور فاکتور", exact: true })
    .click()
  const issue = page.getByRole("dialog")
  await issue.getByRole("button", { name: "صدور فاکتور", exact: true }).click()
  await expect(page.getByText("فاکتور صادر شد.")).toBeVisible()
  await expect(invoiceCard.locator(".m3-status--issued")).toBeVisible()

  await page.getByRole("tab", { name: "دریافت‌ها" }).click()
  await page.getByRole("button", { name: "ثبت دریافت" }).click()
  const payment = page.getByRole("dialog")
  await choose(page, payment, "مشتری", ATHLETE_NAME)
  await payment.getByLabel(/^مبلغ/).first().fill("100000")
  await chooseIndex(page, payment, "فاکتورها", 1)
  await payment.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("دریافت ثبت شد.")).toBeVisible()
  await expect(page.getByText("نقدی").first()).toBeVisible()

  await page.getByRole("tab", { name: "بازپرداخت‌ها" }).click()
  await page.getByRole("button", { name: "درخواست بازپرداخت" }).click()
  const refund = page.getByRole("dialog")
  await choose(page, refund, "مشتری", ATHLETE_NAME)
  await choose(page, refund, "فاکتورها", /.+/)
  await refund.getByLabel(/^مبلغ/).fill("10000")
  await refund.getByLabel("دلیل").fill("بازپرداخت تست فاز دو")
  await refund.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("درخواست ثبت شد.")).toBeVisible()

  const refundCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: "بازپرداخت تست فاز دو" })
    .first()
  await expect(refundCard.getByText("در انتظار")).toBeVisible()
  // The method is defaulted to the collecting receipt's method.
  await expect(refundCard.getByText("نقدی").first()).toBeVisible()

  await refundCard.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(
    refundCard.getByRole("button", { name: "ثبت بازپرداخت" }),
  ).toBeVisible()
  await refundCard.getByRole("button", { name: "ثبت بازپرداخت" }).click()
  const record = page.getByRole("dialog")
  await record.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("بازپرداخت ثبت شد.")).toBeVisible()
  await expect(refundCard.getByText("ثبت‌شده")).toBeVisible()
})

test("gym admin records and pays an expense and manages a paid membership", async ({
  page,
  request,
}) => {
  const suffix = Date.now()
  const category = `هزینه تست ${suffix}`
  await openFinance(page)

  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()
  const login = await request.post(`${API_URL}/api/v1/login/access-token`, {
    form: { username: "ali@example.com", password: DEMO_PASSWORD },
  })
  expect(login.ok()).toBeTruthy()
  const token = (await login.json()).access_token as string
  const admin = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }

  await page.getByRole("tab", { name: "هزینه‌ها" }).click()
  await page.getByRole("button", { name: "ثبت هزینه" }).click()
  const expense = page.getByRole("dialog")
  await expense.getByLabel("دسته").fill(category)
  await expense.getByLabel(/^مبلغ/).fill("50000")
  await expense.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("هزینه ثبت شد.")).toBeVisible()

  const expenseCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: category })
    .first()
  await expect(expenseCard.getByText("پرداخت‌نشده")).toBeVisible()
  await expenseCard
    .getByRole("button", { name: "ثبت پرداخت", exact: true })
    .click()
  const pay = page.getByRole("dialog")
  await pay.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("پرداخت هزینه ثبت شد.")).toBeVisible()
  await expect(expenseCard.getByText("پرداخت‌شده")).toBeVisible()

  // A membership period is unique per athlete while active; clear any leftover
  // period from an interrupted earlier run before exercising the UI.
  const memberships = await request.get(
    `${API_URL}/api/v1/finance/memberships`,
    { headers: admin },
  )
  expect(memberships.ok()).toBeTruthy()
  const members = await request.get(
    `${API_URL}/api/v1/gyms/${gymId}/members?limit=50`,
    { headers: admin },
  )
  expect(members.ok()).toBeTruthy()
  const athlete = (await members.json()).data.find(
    (member: { email: string }) => member.email === "nima@example.com",
  )
  expect(athlete).toBeTruthy()
  for (const membership of (await memberships.json()).data) {
    if (
      membership.athlete_user_id === athlete.user_id &&
      ["ACTIVE", "FROZEN"].includes(membership.status)
    ) {
      const cancelled = await request.post(
        `${API_URL}/api/v1/finance/memberships/${membership.id}/cancel`,
        {
          headers: admin,
          data: {
            cancelled_on: new Date().toISOString().slice(0, 10),
            reason: "automated test cleanup",
          },
        },
      )
      expect(cancelled.ok()).toBeTruthy()
    }
  }

  await page.getByRole("tab", { name: "عضویت‌های پولی" }).click()
  await page.getByRole("button", { name: "ثبت عضویت" }).click()
  const membership = page.getByRole("dialog")
  await choose(page, membership, "مشتری", ATHLETE_NAME)
  await membership.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("عضویت ثبت شد.")).toBeVisible()

  const activeMembership = page
    .locator(".m3-card--outlined")
    .filter({ has: page.locator(".m3-status--active") })
    .first()
  await expect(activeMembership).toBeVisible()
  await expect(activeMembership.getByText("نیما ورزشکار").first()).toBeVisible()
  await activeMembership
    .getByRole("button", { name: "توقف", exact: true })
    .click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "تأیید", exact: true })
    .click()

  const frozenMembership = page
    .locator(".m3-card--outlined")
    .filter({ has: page.locator(".m3-status--frozen") })
    .first()
  await expect(frozenMembership).toBeVisible()
  await frozenMembership
    .getByRole("button", { name: "ادامه", exact: true })
    .click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "تأیید", exact: true })
    .click()

  const resumedMembership = page
    .locator(".m3-card--outlined")
    .filter({ has: page.locator(".m3-status--active") })
    .first()
  await expect(resumedMembership).toBeVisible()
  const cancelledBefore = await page.locator(".m3-status--cancelled").count()
  await resumedMembership
    .getByRole("button", { name: "لغو", exact: true })
    .click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "تأیید", exact: true })
    .click()
  await expect(page.locator(".m3-status--cancelled")).toHaveCount(
    cancelledBefore + 1,
  )
})
