import { expect, type Locator, type Page, test } from "@playwright/test"

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

async function openFinance(page: Page) {
  await page.goto("/gyms")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()
  await page.goto(`/gyms/${gymId}/finance`)
  await expect(page.getByRole("heading", { name: "مالی باشگاه" })).toBeVisible()
}

const COACH_NAME = /رضا مربی/
const ATHLETE_NAME = /نیما ورزشکار/

test("admin versions an agreement, vests earnings and records a partial settlement", async ({
  page,
}) => {
  const suffix = Date.now()
  const description = `فاکتور مربی ${suffix}`
  await openFinance(page)

  await page.getByRole("tab", { name: "قرارداد مربیان" }).click()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  const agreementDialog = page.getByRole("dialog")
  await choose(page, agreementDialog, "مربی", COACH_NAME)
  await agreementDialog
    .getByRole("button", { name: "ذخیره", exact: true })
    .click()
  await expect(page.getByText("قرارداد ثبت شد.")).toBeVisible()
  await expect(page.getByText("ACTIVE").first()).toBeVisible()

  await page.getByRole("tab", { name: "فاکتورها" }).click()
  await page.getByRole("button", { name: "فاکتور جدید" }).click()
  const invoice = page.getByRole("dialog")
  await choose(page, invoice, "مشتری", ATHLETE_NAME)
  await invoice.getByLabel("شرح").first().fill(description)
  await invoice.getByLabel("شرح").nth(1).fill("برنامه با مربی")
  await choose(page, invoice, "مربی فروش", COACH_NAME)
  await invoice.getByLabel("قیمت واحد").fill("100000")
  await invoice.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("فاکتور پیش‌نویس ساخته شد.")).toBeVisible()

  const invoiceCard = page
    .locator(".m3-card--outlined")
    .filter({ hasText: description })
    .first()
  await invoiceCard
    .getByRole("button", { name: "صدور فاکتور", exact: true })
    .click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "صدور فاکتور", exact: true })
    .click()
  await expect(page.getByText("فاکتور صادر شد.")).toBeVisible()

  await page.getByRole("tab", { name: "دریافت‌ها" }).click()
  await page.getByRole("button", { name: "ثبت دریافت" }).click()
  const payment = page.getByRole("dialog")
  await choose(page, payment, "مشتری", ATHLETE_NAME)
  await payment.getByLabel(/^مبلغ/).first().fill("100000")
  await payment
    .getByRole("button", { name: /فاکتورها/ })
    .first()
    .click()
  await page.getByRole("option").nth(1).click()
  await payment.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("دریافت ثبت شد.")).toBeVisible()

  await page.getByRole("tab", { name: "قرارداد مربیان" }).click()
  const vest = page
    .getByRole("button", { name: "تأیید واجد شرایط", exact: true })
    .first()
  await expect(vest).toBeVisible()
  await vest.click()
  const vestDialog = page.getByRole("dialog")
  await vestDialog.getByLabel("دلیل تأیید").fill("تحویل تأیید شد")
  await vestDialog.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("درآمد واجد شرایط شد.")).toBeVisible()

  await page.getByRole("button", { name: "ثبت تسویه" }).click()
  const settlement = page.getByRole("dialog")
  await choose(page, settlement, "مربی", COACH_NAME)
  await settlement.getByLabel(/^مبلغ/).fill("10000")
  await settlement.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("تسویه ثبت شد.")).toBeVisible()
  await page
    .getByRole("button", { name: "تأیید پرداخت", exact: true })
    .first()
    .click()
  await expect(page.getByText("تسویه تأیید شد.")).toBeVisible()
})
