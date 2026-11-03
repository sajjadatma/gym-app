import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

test("manual bank statement line remains visible until matched to a receipt", async ({
  page,
  request,
}) => {
  await page.goto("/gyms")
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
  const members = await request.get(
    `${API_URL}/api/v1/gyms/${gymId}/members?limit=50`,
    { headers: admin },
  )
  const athlete = (await members.json()).data.find(
    (member: { email: string }) => member.email === "nima@example.com",
  )
  expect(athlete).toBeTruthy()
  const suffix = Date.now()
  const invoice = await request.post(`${API_URL}/api/v1/finance/invoices`, {
    headers: admin,
    data: {
      customer_user_id: athlete.user_id,
      acquisition_source: "GYM",
      discount_funding: "GYM",
      description: `reconciliation ${suffix}`,
      lines: [
        {
          kind: "CUSTOM",
          description: "reconciliation sale",
          quantity: 1,
          unit_price_irr: 123_456,
        },
      ],
    },
  })
  expect(invoice.ok()).toBeTruthy()
  const invoiceId = (await invoice.json()).id
  const issued = await request.post(
    `${API_URL}/api/v1/finance/invoices/${invoiceId}/issue`,
    {
      headers: { ...admin, "Idempotency-Key": `recon-issue-${suffix}` },
      data: { posting_date: new Date().toISOString().slice(0, 10) },
    },
  )
  expect(issued.ok()).toBeTruthy()
  const receipt = await request.post(`${API_URL}/api/v1/finance/receipts`, {
    headers: { ...admin, "Idempotency-Key": `recon-receipt-${suffix}` },
    data: {
      customer_user_id: athlete.user_id,
      method: "TRANSFER",
      amount_irr: 123_456,
      received_on: new Date().toISOString().slice(0, 10),
      allocations: [{ invoice_id: invoiceId, amount_irr: 123_456 }],
    },
  })
  expect(receipt.ok()).toBeTruthy()

  await page.goto(`/gyms/${gymId}/finance`)
  await page.getByRole("tab", { name: "دریافت‌ها" }).click()
  await page.getByRole("button", { name: "افزودن ردیف صورت‌حساب" }).click()
  const create = page.getByRole("dialog")
  await create.getByLabel(/^مبلغ/).fill("123456")
  await create.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(page.getByText("ردیف صورت‌حساب ثبت شد.")).toBeVisible()

  const line = page
    .locator(".m3-card--outlined, .m3-card")
    .filter({ hasText: "UNMATCHED" })
    .first()
  await expect(line).toBeVisible()
  await line.getByRole("button", { name: "تطبیق دریافت" }).click()
  const match = page.getByRole("dialog")
  await match
    .getByRole("button", { name: /دریافت تأییدشده/ })
    .first()
    .click()
  await page.getByRole("option").first().click()
  await match.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("تطبیق انجام شد.")).toBeVisible()
  await expect(page.getByText("MATCHED").first()).toBeVisible()
})
