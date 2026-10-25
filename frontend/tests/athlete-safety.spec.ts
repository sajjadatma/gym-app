import { API_URL } from "./credentials"
import { expect, test } from "./fixtures/athlete-data"

function deletePath(url: string) {
  return new URL(url).pathname
}

test("archive confirmation cannot close while the mutation is pending", async ({
  page,
  athleteData,
}) => {
  const target = await athleteData.create({
    name: `busy-archive-${Date.now()}`,
  })
  let release: (() => void) | undefined
  let archiveCalls = 0
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route("**/api/v1/athletes/*/archive", async (route) => {
    archiveCalls += 1
    await gate
    await route.continue()
  })

  await page.goto("/athletes")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(target.email)
  const card = page.locator(".m3-entity-card").first()
  await card.getByRole("button", { name: "آرشیو ورزشکار", exact: true }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: "آرشیو", exact: true }).click()
  await expect.poll(() => archiveCalls).toBe(1)

  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible()
  const headerClose = dialog.getByRole("button", { name: "بستن" })
  await expect(headerClose).toBeDisabled()
  await expect(dialog.getByRole("button", { name: "انصراف" })).toBeDisabled()
  await headerClose.evaluate((element) =>
    (element as HTMLButtonElement).click(),
  )
  await expect(dialog).toBeVisible()

  release?.()
  await expect(dialog).toHaveCount(0)
  expect(archiveCalls).toBe(1)
})

for (const failure of ["500", "abort"] as const) {
  test(`partial permanent deletion retries only failed athletes (${failure})`, async ({
    page,
    athleteData,
    request,
  }) => {
    const marker = `partial-delete-${failure}-${Date.now()}`
    const created = [
      await athleteData.create({
        name: `${marker} first`,
        archived: true,
      }),
      await athleteData.create({
        name: `${marker} second`,
        archived: true,
      }),
    ]
    const targetIds = new Set(created.map((target) => target.athleteId))
    const deletedIds: string[] = []
    let failedOnce = false
    await page.route("**/api/v1/athletes/*", async (route) => {
      if (route.request().method() !== "DELETE") {
        await route.continue()
        return
      }
      const athleteId = deletePath(route.request().url()).split("/").pop()
      if (!athleteId || !targetIds.has(athleteId)) {
        await route.continue()
        return
      }
      deletedIds.push(athleteId)
      if (!failedOnce && deletedIds.length === 2) {
        failedOnce = true
        if (failure === "500") {
          await route.fulfill({
            status: 500,
            contentType: "application/json",
            body: JSON.stringify({ detail: "temporary_failure" }),
          })
        } else {
          await route.abort("failed")
        }
        return
      }
      await route.continue()
    })

    await page.goto("/athletes/archived")
    await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(marker)
    const rows = page.locator(".m3-archive-table tbody tr")
    await expect(rows).toHaveCount(2)
    await page.getByRole("checkbox", { name: "انتخاب همه" }).check()
    await page.getByRole("button", { name: "حذف انتخاب‌شده‌ها" }).click()
    const dialog = page.getByRole("dialog")
    const submit = dialog.getByRole("button", { name: "حذف دائمی" })
    await expect(submit).toBeDisabled()
    await dialog.getByRole("textbox").fill("wrong")
    await expect(submit).toBeDisabled()
    await dialog.getByRole("textbox").fill("حذف")
    await expect(submit).toBeEnabled()

    await submit.click()
    const alert = dialog.getByRole("alert")
    await expect(alert).toContainText("۱ حذف شد")
    await expect(alert).toContainText("۱ ناموفق")
    await expect(alert).toBeFocused()
    expect(deletedIds).toHaveLength(2)
    const [successId, failedId] = deletedIds
    expect(successId).not.toBe(failedId)

    const failedTarget = created.find((target) => target.athleteId === failedId)
    expect(failedTarget).toBeTruthy()
    const stillThere = await request.get(
      `${API_URL}/api/v1/athletes/${failedId}`,
      { headers: athleteData.headers },
    )
    expect(stillThere.status()).toBe(200)
    const alreadyDeleted = await request.get(
      `${API_URL}/api/v1/athletes/${successId}`,
      { headers: athleteData.headers },
    )
    expect(alreadyDeleted.status()).toBe(404)

    await submit.click()
    await expect(dialog).toHaveCount(0)
    expect(deletedIds).toEqual([successId, failedId, failedId])

    const listing = await request.get(
      `${API_URL}/api/v1/athletes?q=${encodeURIComponent(marker)}&include_archived=true`,
      { headers: athleteData.headers },
    )
    expect(listing.ok()).toBeTruthy()
    expect((await listing.json()).count).toBe(0)
  })
}

test("busy permanent deletion cannot be dismissed or submitted twice", async ({
  page,
  athleteData,
}) => {
  const target = await athleteData.create({
    name: `busy-delete-${Date.now()}`,
    archived: true,
  })
  let release: (() => void) | undefined
  let deleteCalls = 0
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route("**/api/v1/athletes/*", async (route) => {
    if (
      route.request().method() === "DELETE" &&
      deletePath(route.request().url()).endsWith(
        `/athletes/${target.athleteId}`,
      )
    ) {
      deleteCalls += 1
      await gate
    }
    await route.continue()
  })

  await page.goto("/athletes/archived")
  await page.getByLabel("جستجوی نام، ایمیل یا تلفن").fill(target.email)
  const row = page.locator(".m3-archive-table tbody tr").first()
  const deleteButton = row.getByRole("button", {
    name: "حذف",
    exact: true,
  })

  // Idle cancellation keeps focus trapped and restores the initiating button.
  await deleteButton.click()
  const idleDialog = page.getByRole("dialog")
  const idleConfirmation = idleDialog.getByRole("textbox")
  await expect(idleConfirmation).toBeFocused()
  await page.keyboard.press("Shift+Tab")
  expect(
    await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[role="dialog"]')),
    ),
  ).toBe(true)
  await page.keyboard.press("Tab")
  expect(
    await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[role="dialog"]')),
    ),
  ).toBe(true)
  await page.keyboard.press("Escape")
  await expect(idleDialog).toHaveCount(0)
  await expect(deleteButton).toBeFocused()
  expect(deleteCalls).toBe(0)

  await deleteButton.click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("textbox").fill(target.email)
  const submit = dialog.getByRole("button", { name: "حذف دائمی" })
  await submit.click()
  await expect.poll(() => deleteCalls).toBe(1)

  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible()
  const headerClose = dialog.getByRole("button", { name: "بستن" })
  await expect(headerClose).toBeDisabled()
  await headerClose.evaluate((element) =>
    (element as HTMLButtonElement).click(),
  )
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole("button", { name: "انصراف" })).toBeDisabled()
  await expect(submit).toBeDisabled()
  expect(deleteCalls).toBe(1)

  release?.()
  await expect(dialog).toHaveCount(0)
  expect(deleteCalls).toBe(1)
})

test("import mutation cannot be dismissed while submitting", async ({
  page,
  athleteData,
}) => {
  const email = `${athleteData.marker}-import-${Date.now()}@example.com`
  athleteData.trackEmail(email)
  await page.goto("/athletes")
  await page.getByRole("button", { name: "ورود گروهی", exact: true }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()

  const csv = [
    "email,full_name,phone,coach_email,training_goal,height_cm,weight_kg,training_days_count",
    `${email},ورزشکار ورود ایمن,09120000010,reza@example.com,قدرت,180,80,3`,
    "bad-email,ردیف نامعتبر,,,,,,",
  ].join("\n")
  const fileInput = dialog.getByLabel("فایل ورودی")
  await expect(fileInput).toHaveAttribute("aria-label", "فایل ورودی")
  await fileInput.setInputFiles({
    name: "athletes.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv, "utf8"),
  })

  await dialog.getByRole("button", { name: "بررسی و پیش‌نمایش" }).click()
  await expect(dialog.getByText(/آماده ورود: ۱/)).toBeVisible()
  await expect(dialog.getByText(/خطا: ۱/)).toBeVisible()

  let release: (() => void) | undefined
  let importCalls = 0
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route("**/api/v1/athletes/import", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue()
      return
    }
    importCalls += 1
    await gate
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: 2,
        created: 1,
        skipped: 0,
        failed: [
          {
            row_number: 2,
            email: "bad-email",
            messages: ["invalid_email"],
          },
        ],
      }),
    })
  })

  const submit = dialog.getByRole("button", { name: /ورود ۱ ورزشکار/ })
  await submit.click()
  await expect.poll(() => importCalls).toBe(1)
  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible()
  const headerClose = dialog.getByRole("button", { name: "بستن" })
  await expect(headerClose).toBeDisabled()
  await expect(dialog.getByRole("button", { name: "بازگشت" })).toBeDisabled()
  await expect(submit).toBeDisabled()
  await headerClose.evaluate((element) =>
    (element as HTMLButtonElement).click(),
  )
  await expect(dialog).toBeVisible()
  await expect(page.getByRole("dialog")).toHaveCount(1)
  expect(importCalls).toBe(1)

  release?.()
  await expect(
    dialog.getByRole("heading", { name: "ورود انجام شد" }),
  ).toBeVisible()
  await expect(dialog.getByText(/ایجادشده: ۱/)).toBeVisible()
  await dialog.getByRole("button", { name: "پایان" }).click()
  await expect(dialog).toHaveCount(0)
})
