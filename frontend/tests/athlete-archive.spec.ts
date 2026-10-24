import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

async function createArchivedAthlete(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
  name: string,
) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }
  const coaches = await request.get(`${API_URL}/api/v1/gyms/${gymId}/coaches`, {
    headers,
  })
  expect(coaches.ok()).toBeTruthy()
  const coach = (await coaches.json()).data.find(
    (item: { email: string }) => item.email === "reza@example.com",
  )
  expect(coach).toBeTruthy()
  const email = `archive-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`
  const created = await request.post(`${API_URL}/api/v1/athletes`, {
    headers,
    data: {
      email,
      full_name: name,
      coach_user_id: coach.user_id,
      activation_method: "password",
      initial_password: DEMO_PASSWORD,
    },
  })
  expect(created.ok()).toBeTruthy()
  const athleteId = (await created.json()).athlete.profile.user_id
  const archived = await request.post(
    `${API_URL}/api/v1/athletes/${athleteId}/archive`,
    { headers },
  )
  expect(archived.ok()).toBeTruthy()
  return { athleteId, email, headers }
}

test("archived athletes can be restored or permanently deleted", async ({
  page,
  request,
}) => {
  await page.goto("/athletes")
  const restoreTarget = await createArchivedAthlete(
    page,
    request,
    "ورزشکار بازیابی آزمون",
  )
  const deleteTarget = await createArchivedAthlete(
    page,
    request,
    "ورزشکار حذف آزمون",
  )

  await page.goto("/athletes/archived")
  await expect(
    page.getByRole("heading", { name: "ورزشکاران آرشیوشده" }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "آرشیو" })).toHaveClass(
    /is-active/,
  )

  const restoreRow = page
    .locator(".m3-archive-table tbody tr")
    .filter({ hasText: restoreTarget.email })
  await restoreRow.getByRole("button", { name: "بازیابی", exact: true }).click()
  await expect(page.getByText("ورزشکار بازیابی شد.")).toBeVisible()
  await expect(restoreRow).toHaveCount(0)

  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(restoreTarget.email)
  await page.goto("/athletes")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(restoreTarget.email)
  await expect(page.locator(".m3-entity-card")).toHaveCount(1)

  await page.goto("/athletes/archived")
  const deleteRow = page
    .locator(".m3-archive-table tbody tr")
    .filter({ hasText: deleteTarget.email })
  await deleteRow.getByRole("button", { name: "حذف", exact: true }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toContainText("حذف دائمی ورزشکار")
  await dialog.getByLabel(/برای تأیید، ایمیل/).fill(deleteTarget.email)
  await dialog.getByRole("button", { name: "حذف دائمی" }).click()
  await expect(page.getByText("ورزشکار حذف شد.")).toBeVisible()
  await expect(deleteRow).toHaveCount(0)

  const missing = await request.get(
    `${API_URL}/api/v1/athletes/${deleteTarget.athleteId}`,
    { headers: deleteTarget.headers },
  )
  expect(missing.status()).toBe(404)

  // Clean up the restored athlete from later runs.
  await request.post(
    `${API_URL}/api/v1/athletes/${restoreTarget.athleteId}/archive`,
    { headers: restoreTarget.headers },
  )
  await request.delete(
    `${API_URL}/api/v1/athletes/${restoreTarget.athleteId}`,
    { headers: restoreTarget.headers },
  )
})

test("archived athletes can be restored in bulk", async ({ page, request }) => {
  await page.goto("/athletes")
  const marker = `بازیابی گروهی ${Date.now()}`
  const first = await createArchivedAthlete(page, request, `${marker} ۱`)
  const second = await createArchivedAthlete(page, request, `${marker} ۲`)

  await page.goto("/athletes/archived")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(marker)
  const rows = page.locator(".m3-archive-table tbody tr")
  await expect(rows).toHaveCount(2)
  await page.getByRole("checkbox", { name: "انتخاب همه" }).check()
  await expect(page.locator(".m3-selection-bar__count")).toHaveText(
    /۲ انتخاب‌شده/,
  )
  await page.getByRole("button", { name: "بازیابی انتخاب‌شده‌ها" }).click()
  await expect(page.getByText(/۲ ورزشکار بازیابی شد/)).toBeVisible()
  await expect(rows).toHaveCount(0)

  for (const target of [first, second]) {
    await request.post(
      `${API_URL}/api/v1/athletes/${target.athleteId}/archive`,
      { headers: target.headers },
    )
    await request.delete(`${API_URL}/api/v1/athletes/${target.athleteId}`, {
      headers: target.headers,
    })
  }
})

async function createActiveAthlete(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
  name: string,
) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }
  const coaches = await request.get(`${API_URL}/api/v1/gyms/${gymId}/coaches`, {
    headers,
  })
  const coach = (await coaches.json()).data.find(
    (item: { email: string }) => item.email === "reza@example.com",
  )
  const email = `archive-list-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`
  const created = await request.post(`${API_URL}/api/v1/athletes`, {
    headers,
    data: {
      email,
      full_name: name,
      coach_user_id: coach.user_id,
      activation_method: "password",
      initial_password: DEMO_PASSWORD,
    },
  })
  expect(created.ok()).toBeTruthy()
  return {
    athleteId: (await created.json()).athlete.profile.user_id as string,
    email,
    headers,
  }
}

test("archive is available on cards and as a table bulk action", async ({
  page,
  request,
}) => {
  await page.goto("/athletes")
  const cardTarget = await createActiveAthlete(
    page,
    request,
    "آرشیو کارت آزمون",
  )
  await page.goto("/athletes")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(cardTarget.email)
  const card = page.locator(".m3-entity-card").first()
  await expect(card).toBeVisible()
  await card.getByRole("button", { name: "آرشیو ورزشکار", exact: true }).click()
  const cardDialog = page.getByRole("dialog")
  await expect(cardDialog).toContainText("آرشیو ورزشکار")
  await cardDialog.getByRole("button", { name: "آرشیو", exact: true }).click()
  await expect(page.getByText("ورزشکار آرشیو شد.")).toBeVisible()
  await expect(page.locator(".m3-entity-card")).toHaveCount(0)

  const marker = `آرشیو گروهی جدول ${Date.now()}`
  const first = await createActiveAthlete(page, request, `${marker} ۱`)
  const second = await createActiveAthlete(page, request, `${marker} ۲`)
  await page.goto("/athletes")
  await page.getByRole("button", { name: "جدول", exact: true }).click()
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(marker)
  const rows = page.locator(".m3-data-table tbody tr")
  await expect(rows).toHaveCount(2)
  await page.getByRole("checkbox", { name: "انتخاب همه" }).check()
  await page.getByRole("button", { name: "آرشیو انتخاب‌شده‌ها" }).click()
  const bulkDialog = page.getByRole("dialog")
  await expect(bulkDialog).toContainText("آرشیو ۲ ورزشکار")
  await bulkDialog.getByRole("button", { name: "آرشیو", exact: true }).click()
  await expect(page.getByText(/۲ ورزشکار آرشیو شد/)).toBeVisible()
  await expect(rows).toHaveCount(0)

  for (const target of [cardTarget, first, second]) {
    await request.delete(`${API_URL}/api/v1/athletes/${target.athleteId}`, {
      headers: target.headers,
    })
  }
})
