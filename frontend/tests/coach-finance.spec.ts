import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

test("coach sees own calculated, vested and settled earnings", async ({
  page,
  request,
}) => {
  await page.goto("/")
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
  expect(members.ok()).toBeTruthy()
  const coach = (await members.json()).data.find(
    (member: { email: string }) => member.email === "reza@example.com",
  )
  const athlete = (await members.json()).data.find(
    (member: { email: string }) => member.email === "nima@example.com",
  )
  expect(coach).toBeTruthy()
  expect(athlete).toBeTruthy()

  const suffix = Date.now()
  const agreement = await request.post(
    `${API_URL}/api/v1/finance/coach-agreements`,
    {
      headers: admin,
      data: {
        coach_user_id: coach.user_id,
        effective_from: "2026-01-01",
        mode: "DIRECT",
        vesting_mode: "MANUAL",
        vesting_days: 0,
        terms: [
          { recipient: "COACH", basis: "PERCENT", percent_bp: 3000 },
          { recipient: "GYM", basis: "PERCENT", percent_bp: 7000 },
        ],
      },
    },
  )
  expect(agreement.ok()).toBeTruthy()
  const activated = await request.post(
    `${API_URL}/api/v1/finance/coach-agreements/${(await agreement.json()).id}/activate`,
    { headers: admin },
  )
  expect(activated.ok()).toBeTruthy()

  const invoice = await request.post(`${API_URL}/api/v1/finance/invoices`, {
    headers: admin,
    data: {
      customer_user_id: athlete.user_id,
      acquisition_source: "GYM",
      discount_funding: "GYM",
      description: `coach ui ${suffix}`,
      lines: [
        {
          kind: "PROGRAM",
          description: "coached program",
          quantity: 1,
          unit_price_irr: 200_000,
          coach_user_id: coach.user_id,
        },
      ],
    },
  })
  expect(invoice.ok()).toBeTruthy()
  const invoiceId = (await invoice.json()).id
  const issued = await request.post(
    `${API_URL}/api/v1/finance/invoices/${invoiceId}/issue`,
    {
      headers: { ...admin, "Idempotency-Key": `coach-issue-${suffix}` },
      data: { posting_date: new Date().toISOString().slice(0, 10) },
    },
  )
  expect(issued.ok()).toBeTruthy()
  const receipt = await request.post(`${API_URL}/api/v1/finance/receipts`, {
    headers: { ...admin, "Idempotency-Key": `coach-receipt-${suffix}` },
    data: {
      customer_user_id: athlete.user_id,
      method: "CASH",
      amount_irr: 200_000,
      received_on: new Date().toISOString().slice(0, 10),
      allocations: [{ invoice_id: invoiceId, amount_irr: 200_000 }],
    },
  })
  expect(receipt.ok()).toBeTruthy()

  const earnings = await request.get(
    `${API_URL}/api/v1/finance/coach-earnings?coach_user_id=${coach.user_id}`,
    { headers: admin },
  )
  expect(earnings.ok()).toBeTruthy()
  const earning = (await earnings.json()).data.find(
    (row: { invoice_id: string }) => row.invoice_id === invoiceId,
  )
  expect(earning).toBeTruthy()
  expect(earning.coach_share_irr).toBe(60_000)
  const vested = await request.post(
    `${API_URL}/api/v1/finance/coach-earnings/${earning.id}/vest`,
    { headers: admin, data: { reason: "delivery attested" } },
  )
  expect(vested.ok()).toBeTruthy()
  const settlement = await request.post(
    `${API_URL}/api/v1/finance/coach-settlements`,
    {
      headers: { ...admin, "Idempotency-Key": `coach-settle-${suffix}` },
      data: {
        coach_user_id: coach.user_id,
        amount_irr: 10_000,
        method: "CASH",
        paid_on: new Date().toISOString().slice(0, 10),
      },
    },
  )
  expect(settlement.ok()).toBeTruthy()

  await page.goto(`/gyms/${gymId}/my/earnings`)
  await expect(
    page.getByRole("heading", { name: "درآمد من", level: 1 }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "درآمد من" }).first(),
  ).toBeVisible()
  await expect(page.getByText("تسویه‌شده").first()).toBeVisible()
  await expect(page.getByText("۶۰٬۰۰۰ ریال").first()).toBeVisible()
  await expect(page.getByText("۱۰٬۰۰۰ ریال").first()).toBeVisible()

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
