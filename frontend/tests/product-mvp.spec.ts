import {
  type APIRequestContext,
  expect,
  type Page,
  test,
} from "@playwright/test"
import { DEMO_PASSWORD } from "./credentials"

const API = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8012"
async function token(request: APIRequestContext, email: string) {
  const r = await request.post(`${API}/api/v1/login/access-token`, {
    form: { username: email, password: DEMO_PASSWORD },
  })
  expect(r.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await r.json()).access_token}` }
}
async function fixture(request: APIRequestContext) {
  const owner = await token(request, "ali@example.com")
  const coach = await token(request, "reza@example.com")
  const athlete = await token(request, "nima@example.com")
  const r = await request.get(`${API}/api/v1/gyms/`, { headers: owner })
  const gym = (await r.json()).data.find((g: { name: string }) =>
    g.name.includes("آرام"),
  )
  const a = await request.get(`${API}/api/v1/users/me`, { headers: athlete })
  return {
    gymId: gym.id as string,
    athleteId: (await a.json()).id as string,
    owner: { ...owner, "X-Gym-ID": gym.id },
    coach: { ...coach, "X-Gym-ID": gym.id },
    athlete: { ...athlete, "X-Gym-ID": gym.id },
  }
}
async function login(page: Page, email: string) {
  await page.context().clearCookies()
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(email)
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود", exact: true }).click()
  await expect(page).not.toHaveURL(/login/)
}
async function buy(
  request: APIRequestContext,
  f: Awaited<ReturnType<typeof fixture>>,
) {
  const offer = await request.get(
    `${API}/api/v1/finance/gyms/${f.gymId}/athlete/training-offer`,
    { headers: f.athlete },
  )
  const o = await offer.json()
  const response = await request.post(
    `${API}/api/v1/finance/gyms/${f.gymId}/athlete/training-purchases`,
    {
      headers: f.athlete,
      data: {
        plan_id: o.plan.id,
        quote_token: o.quote_token,
        idempotency_key: crypto.randomUUID(),
        note: `MVP browser ${Date.now()}`,
      },
    },
  )
  expect(response.status()).toBe(200)
  return response.json()
}

test("athlete receives printable invoice and receipt with no refund action", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  const purchase = await buy(request, f)
  await login(page, "nima@example.com")
  await page.goto(`/gyms/${f.gymId}/my`)
  await expect(
    page.getByRole("button", { name: "فاکتور و رسید" }).first(),
  ).toBeVisible()
  await page.goto(`/gyms/${f.gymId}/my/purchases/${purchase.sale.id}`)
  await expect(
    page.getByRole("heading", { name: "فاکتور خرید", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "رسید پرداخت", exact: true }),
  ).toBeVisible()
  await expect(page.getByText(/^PAY-/)).toBeVisible()
  await expect(
    page.getByRole("button", { name: /بازگشت وجه|انصراف خرید/ }),
  ).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy()
  await page.emulateMedia({ media: "print" })
  await expect(page.locator(".m3-nav-rail")).toBeHidden()
  await expect(page.locator(".m3-topbar")).toBeHidden()
  const pdf = await page.pdf({ format: "A4", printBackground: true })
  expect(pdf.subarray(0, 4).toString()).toBe("%PDF")
  expect(pdf.length).toBeGreaterThan(1000)
  await page.screenshot({
    path: test.info().outputPath("invoice-print.png"),
    fullPage: true,
  })
})

test("price change requires review and another explicit confirmation", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  await login(page, "nima@example.com")
  await page.goto(`/gyms/${f.gymId}/my`)
  await page.getByRole("button", { name: "خرید و ارسال درخواست" }).click()
  const offer = await request.get(
    `${API}/api/v1/finance/gyms/${f.gymId}/athlete/training-offer`,
    { headers: f.athlete },
  )
  const old = await offer.json()
  const changed = {
    title: old.plan.title,
    description: old.plan.description,
    base_price_irr: old.plan.base_price_irr + 1000000,
    is_active: true,
  }
  try {
    expect(
      (
        await request.put(
          `${API}/api/v1/finance/gyms/${f.gymId}/coach-plans/${old.plan.id}`,
          { headers: f.coach, data: changed },
        )
      ).status(),
    ).toBe(200)
    const pending = page.waitForResponse((r) =>
      r.url().endsWith("/athlete/training-purchases"),
    )
    await page
      .getByRole("button", { name: "پرداخت آزمایشی و ثبت درخواست" })
      .click()
    expect((await pending).status()).toBe(409)
    await expect(
      page.getByRole("dialog").getByText(/مبلغ به‌روز را بررسی/),
    ).toBeVisible()
    const confirm = page.waitForResponse((r) =>
      r.url().endsWith("/athlete/training-purchases"),
    )
    await page
      .getByRole("button", { name: "پرداخت آزمایشی و ثبت درخواست" })
      .click()
    expect((await confirm).status()).toBe(200)
    await expect(page.getByRole("dialog")).toHaveCount(0)
  } finally {
    await request.put(
      `${API}/api/v1/finance/gyms/${f.gymId}/coach-plans/${old.plan.id}`,
      {
        headers: f.coach,
        data: {
          title: old.plan.title,
          description: old.plan.description,
          base_price_irr: old.plan.base_price_irr,
          is_active: true,
        },
      },
    )
  }
})

test("athlete service failure offers retry instead of claiming no plan", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  await login(page, "nima@example.com")
  let fail = true
  await page.route("**/athlete/training-offer", (route) =>
    fail
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: '{"detail":"review_failure"}',
        })
      : route.continue(),
  )
  await page.goto(`/gyms/${f.gymId}/my`)
  await expect(
    page.getByRole("button", { name: /تلاش دوباره|تلاش مجدد/ }),
  ).toBeVisible()
  await expect(page.getByText(/در حال حاضر پلن فعالی/)).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: /تلاش دوباره|تلاش مجدد/ }).click()
  await expect(
    page.getByRole("button", { name: "خرید و ارسال درخواست" }),
  ).toBeVisible()
})

test("coach sees private earnings and a failed request queue shows retry", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  await login(page, "reza@example.com")
  await page.route("**/program-requests", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"review_failure"}',
    }),
  )
  await page.goto(`/gyms/${f.gymId}/coach-plan`)
  await expect(
    page.getByRole("heading", { name: "صورت‌حساب من", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText("سهم محاسبه‌شده من", { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /تلاش دوباره|تلاش مجدد/ }),
  ).toBeVisible()
  await expect(
    page.getByText("هنوز درخواستی ثبت نشده است", { exact: true }),
  ).toHaveCount(0)
})

test("athlete records Persian actual reps and weight and coach reads history", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  await login(page, "nima@example.com")
  await page.goto(`/gyms/${f.gymId}/my`)
  await page
    .getByRole("button", { name: "مشاهده", exact: true })
    .first()
    .click()
  await page.getByRole("button", { name: "ثبت عملکرد این جلسه" }).click()
  const dialog = page.getByRole("dialog")
  await dialog
    .getByLabel(/تکرار واقعی/)
    .first()
    .fill("۱۲")
  await dialog
    .getByLabel(/وزنه واقعی/)
    .first()
    .fill("۲۲٫۵")
  await dialog.getByLabel("ست انجام شد", { exact: true }).first().check()
  await dialog.getByLabel("سختی جلسه از ۱ تا ۱۰").fill("۷")
  const note = `MVP feedback ${Date.now()}`
  await dialog.getByLabel("یادداشت و بازخورد جلسه").fill(note)
  const pending = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" && r.url().endsWith("/workout-sessions"),
  )
  await dialog.getByRole("button", { name: "ذخیره عملکرد جلسه" }).click()
  const response = await pending
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON().sets[0]).toMatchObject({
    reps: 12,
    weight_kg: 22.5,
    completed: true,
  })
  await expect(dialog).toHaveCount(0)
  await page.locator("details").first().locator("summary").click()
  await expect(page.getByText(note, { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy()
  await page.screenshot({
    path: test.info().outputPath("athlete-progress-mobile.png"),
    fullPage: true,
  })
  await login(page, "reza@example.com")
  await page.goto(`/gyms/${f.gymId}/athletes/${f.athleteId}`)
  await page.getByRole("tab", { name: "تمرین و پیشرفت" }).click()
  await page.locator("details").first().locator("summary").click()
  await expect(page.getByText(note, { exact: true })).toBeVisible()
})

test("dashboard links open requests and draft deletion preserves paid entitlement", async ({
  page,
  request,
}) => {
  const f = await fixture(request)
  const bought = await buy(request, f)
  await login(page, "reza@example.com")
  await page.goto(`/gyms/${f.gymId}`)
  await expect(
    page.getByRole("heading", { name: "کارهای امروز", exact: true }),
  ).toBeVisible()
  const url = `${API}/api/v1/athletes/${f.athleteId}/programs`
  const first = await request.post(url, {
    headers: f.coach,
    data: {
      title: "MVP draft to delete",
      purchase_request_id: bought.request.id,
    },
  })
  expect(first.status()).toBe(200)
  const v = await first.json()
  expect(
    (
      await request.delete(`${API}/api/v1/program-versions/${v.id}`, {
        headers: f.coach,
      })
    ).status(),
  ).toBe(200)
  const replacement = await request.post(url, {
    headers: f.coach,
    data: {
      title: "MVP replacement draft",
      purchase_request_id: bought.request.id,
    },
  })
  expect(replacement.status()).toBe(200)
  await page.goto(`/gyms/${f.gymId}/coach-plan`)
  await expect(
    page.getByText("در حال آماده‌سازی", { exact: true }).first(),
  ).toBeVisible()
  await login(page, "nima@example.com")
  await page.goto(`/gyms/${f.gymId}/my`)
  await expect(
    page.getByText("در حال آماده‌سازی", { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByText("MVP replacement draft", { exact: true }),
  ).toHaveCount(0)
  const replacementVersion = await replacement.json()
  const versionsResponse = await request.get(url, { headers: f.athlete })
  const active = (await versionsResponse.json()).data.find(
    (row: { status: string }) => row.status === "ACTIVE",
  )
  const activeResponse = await request.get(
    `${API}/api/v1/program-versions/${active.id}`,
    { headers: f.athlete },
  )
  const structure = await activeResponse.json()
  const saved = await request.put(
    `${API}/api/v1/program-versions/${replacementVersion.id}`,
    {
      headers: f.coach,
      data: {
        title: "MVP delivered program",
        days: structure.days,
        expected_revision: replacementVersion.revision,
      },
    },
  )
  expect(saved.status()).toBe(200)
  const published = await request.post(
    `${API}/api/v1/program-versions/${replacementVersion.id}/publish`,
    { headers: f.coach },
  )
  expect(published.status()).toBe(200)
  await page.reload()
  await page
    .getByRole("button", { name: "مشاهده برنامه تحویل‌شده" })
    .first()
    .click()
  await expect(page).toHaveURL(
    new RegExp(`/my/programs/${replacementVersion.id}`),
  )
  await expect(
    page.getByRole("heading", { name: "MVP delivered program", exact: true }),
  ).toBeVisible()
})
