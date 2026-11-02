import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

test("athlete reviews own bills, receipts and membership and requests a refund", async ({
  page,
  request,
}) => {
  await page.goto("/my")
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
  const athlete = (await members.json()).data.find(
    (member: { email: string }) => member.email === "nima@example.com",
  )
  expect(athlete).toBeTruthy()

  // Create a fresh paid invoice for this athlete so the refund request has an
  // identifiable ceiling even when the demo database already has history.
  const suffix = Date.now()
  const description = `فاکتور ورزشکار ${suffix}`
  const created = await request.post(`${API_URL}/api/v1/finance/invoices`, {
    headers: admin,
    data: {
      customer_user_id: athlete.user_id,
      acquisition_source: "GYM",
      discount_funding: "GYM",
      description,
      lines: [
        {
          kind: "SERVICE",
          description: "خدمات تست ورزشکار",
          quantity: 1,
          unit_price_irr: 200_000,
          line_discount_irr: 0,
        },
      ],
    },
  })
  expect(created.ok()).toBeTruthy()
  const invoice = (await created.json()) as { id: string }

  const today = new Date().toISOString().slice(0, 10)
  const issued = await request.post(
    `${API_URL}/api/v1/finance/invoices/${invoice.id}/issue`,
    {
      headers: { ...admin, "Idempotency-Key": `issue-${suffix}` },
      data: { posting_date: today },
    },
  )
  expect(issued.ok()).toBeTruthy()

  const receipt = await request.post(`${API_URL}/api/v1/finance/receipts`, {
    headers: { ...admin, "Idempotency-Key": `receipt-${suffix}` },
    data: {
      customer_user_id: athlete.user_id,
      method: "TRANSFER",
      amount_irr: 200_000,
      received_on: today,
      allocations: [{ invoice_id: invoice.id, amount_irr: 200_000 }],
    },
  })
  expect(receipt.ok()).toBeTruthy()

  await page.goto(`/gyms/${gymId}/my/finance`)
  await expect(page.getByRole("heading", { name: "مالی من" })).toBeVisible()

  const financeNav = page
    .locator(".m3-mobile-nav")
    .getByText("مالی من", { exact: true })
  await expect(financeNav).toBeVisible()

  await expect(page.getByText("خدمات تست ورزشکار").first()).toBeVisible()
  await expect(page.getByText("دریافت‌های من")).toBeVisible()
  await expect(page.getByText("انتقال بانکی").first()).toBeVisible()
  await expect(page.getByText("عضویت من").first()).toBeVisible()

  await page.getByRole("button", { name: "درخواست بازپرداخت" }).first().click()
  const dialog = page.getByRole("dialog")
  await dialog
    .getByRole("button", { name: /فاکتورها/ })
    .first()
    .click()
  await page.getByRole("option").first().click()
  await dialog.getByLabel(/^مبلغ/).fill("5000")
  await dialog.getByLabel("دلیل").fill("درخواست بازپرداخت ورزشکار")
  await dialog.getByRole("button", { name: "تأیید", exact: true }).click()
  await expect(page.getByText("درخواست ثبت شد.")).toBeVisible()
  await expect(page.getByText("در انتظار").first()).toBeVisible()
  await expect(
    page.getByText("درخواست بازپرداخت ورزشکار").first(),
  ).toBeVisible()

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
