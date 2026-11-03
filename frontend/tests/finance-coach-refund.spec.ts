import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

test("post-payout refund opens and resolves a coach discrepancy", async ({
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
  const rows = (await members.json()).data
  const coach = rows.find(
    (member: { email: string }) => member.email === "reza@example.com",
  )
  const athlete = rows.find(
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
  const agreementId = (await agreement.json()).id
  const activated = await request.post(
    `${API_URL}/api/v1/finance/coach-agreements/${agreementId}/activate`,
    { headers: admin },
  )
  expect(activated.ok()).toBeTruthy()

  const invoice = await request.post(`${API_URL}/api/v1/finance/invoices`, {
    headers: admin,
    data: {
      customer_user_id: athlete.user_id,
      acquisition_source: "GYM",
      discount_funding: "GYM",
      description: `discrepancy ${suffix}`,
      lines: [
        {
          kind: "PROGRAM",
          description: "program",
          quantity: 1,
          unit_price_irr: 100_000,
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
      headers: { ...admin, "Idempotency-Key": `discrepancy-issue-${suffix}` },
      data: { posting_date: new Date().toISOString().slice(0, 10) },
    },
  )
  expect(issued.ok()).toBeTruthy()
  const receipt = await request.post(`${API_URL}/api/v1/finance/receipts`, {
    headers: { ...admin, "Idempotency-Key": `discrepancy-receipt-${suffix}` },
    data: {
      customer_user_id: athlete.user_id,
      method: "CASH",
      amount_irr: 100_000,
      received_on: new Date().toISOString().slice(0, 10),
      allocations: [{ invoice_id: invoiceId, amount_irr: 100_000 }],
    },
  })
  expect(receipt.ok()).toBeTruthy()

  const earnings = await request.get(
    `${API_URL}/api/v1/finance/coach-earnings?coach_user_id=${coach.user_id}`,
    { headers: admin },
  )
  const earning = (await earnings.json()).data.find(
    (row: { invoice_id: string }) => row.invoice_id === invoiceId,
  )
  expect(earning).toBeTruthy()
  const vested = await request.post(
    `${API_URL}/api/v1/finance/coach-earnings/${earning.id}/vest`,
    { headers: admin, data: { reason: "delivery attested" } },
  )
  expect(vested.ok()).toBeTruthy()

  // Settle every eligible Reza earning so the refunded share is already paid.
  const refreshed = await request.get(
    `${API_URL}/api/v1/finance/coach-earnings?coach_user_id=${coach.user_id}`,
    { headers: admin },
  )
  const eligible = (await refreshed.json()).data.reduce(
    (sum: number, row: { eligible_irr: number }) => sum + row.eligible_irr,
    0,
  )
  const settlement = await request.post(
    `${API_URL}/api/v1/finance/coach-settlements`,
    {
      headers: { ...admin, "Idempotency-Key": `discrepancy-settle-${suffix}` },
      data: {
        coach_user_id: coach.user_id,
        amount_irr: eligible,
        method: "CASH",
        paid_on: new Date().toISOString().slice(0, 10),
      },
    },
  )
  expect(settlement.ok()).toBeTruthy()
  expect(
    (
      await request.post(
        `${API_URL}/api/v1/finance/coach-settlements/${(await settlement.json()).id}/confirm`,
        { headers: admin },
      )
    ).ok(),
  ).toBeTruthy()

  const requested = await request.post(`${API_URL}/api/v1/finance/refunds`, {
    headers: { ...admin, "Idempotency-Key": `discrepancy-refund-${suffix}` },
    data: {
      source: "INVOICE",
      customer_user_id: athlete.user_id,
      invoice_id: invoiceId,
      amount_irr: 70_000,
      reason: "refund after payout",
    },
  })
  expect(requested.ok()).toBeTruthy()
  const refundId = (await requested.json()).id
  expect(
    (
      await request.post(
        `${API_URL}/api/v1/finance/refunds/${refundId}/approve`,
        { headers: admin },
      )
    ).ok(),
  ).toBeTruthy()
  expect(
    (
      await request.post(
        `${API_URL}/api/v1/finance/refunds/${refundId}/record`,
        {
          headers: { ...admin, "Idempotency-Key": `discrepancy-rec-${suffix}` },
          data: { posting_date: new Date().toISOString().slice(0, 10) },
        },
      )
    ).ok(),
  ).toBeTruthy()

  await page.goto(`/gyms/${gymId}/finance`)
  await page.getByRole("tab", { name: "قرارداد مربیان" }).click()
  await expect(page.getByText("OPEN").first()).toBeVisible()
  await page
    .getByRole("button", { name: "ثبت حل مغایرت", exact: true })
    .first()
    .click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("توضیح حل").fill("تسویه دستی با مربی")
  await dialog.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("مغایرت حل شد.")).toBeVisible()
})
