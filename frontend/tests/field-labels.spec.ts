import { expect, type Page, test } from "@playwright/test"

import { ATHLETE_EMAIL, DEMO_PASSWORD } from "./credentials"

async function expectAssociatedLabels(page: Page) {
  const missing = await page.locator("body").evaluate((body) => {
    return Array.from(
      body.querySelectorAll<HTMLElement>(
        'input:not([type="hidden"]), textarea, select, [role="combobox"], [role="spinbutton"], [role="switch"]',
      ),
    )
      .filter((field) => {
        if (
          !field.getClientRects().length ||
          field.closest('[aria-hidden="true"]')
        )
          return false
        const nativeLabels = (field as HTMLInputElement).labels
        const labelledBy = (field.getAttribute("aria-labelledby") ?? "")
          .split(/\s+/)
          .some((id) => document.getElementById(id)?.textContent?.trim())
        return (
          !nativeLabels?.length &&
          !labelledBy &&
          !field.getAttribute("aria-label")?.trim()
        )
      })
      .map((field) => field.outerHTML.slice(0, 240))
  })
  expect(missing, "Every form control must have an associated label").toEqual(
    [],
  )
}

test("searches and staff forms have persistent, associated labels", async ({
  page,
}) => {
  for (const [route, searchLabel, button] of [
    ["/athletes", "جست‌وجو در ورزشکاران", "افزودن ورزشکار"],
    ["/exercises", "جست‌وجوی حرکت", "افزودن حرکت اختصاصی"],
    ["/members", "", "افزودن عضو"],
  ]) {
    await page.goto(route)
    const add = page.getByRole("button", { name: button, exact: true }).first()
    await expect(add).toBeVisible()
    if (searchLabel) {
      const search = page.getByRole("searchbox")
      await expect(search).toHaveCount(1)
      const label = page.locator(
        `label[for="${await search.getAttribute("id")}"]`,
      )
      await expect(label).toBeVisible()
      await search.fill("تست")
      await expect(label).toBeVisible()
      await search.clear()
    }
    await expectAssociatedLabels(page)
    await add.click()
    await expect(page.locator(".m3-dialog")).toBeVisible()
    await expectAssociatedLabels(page)
    await page.getByRole("button", { name: "انصراف", exact: true }).click()
  }
  await page.goto("/gyms")
  await page.getByRole("button", { name: /^باشگاه آرام/ }).click()
  await page.getByRole("button", { name: "ویرایش", exact: true }).click()
  await expect(page.locator(".m3-dialog")).toBeVisible()
  await expectAssociatedLabels(page)
})

test("program day and set fields retain their labels and focus while editing", async ({
  page,
}) => {
  await page.goto("/templates/new")
  await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
  const title = page.getByLabel("عنوان روز", { exact: true })
  await title.fill("")
  await title.pressSequentially("روز قدرت")
  await expect(title).toBeFocused()
  await expect(title).toHaveValue("روز قدرت")
  await expect(
    page.locator(`label[for="${await title.getAttribute("id")}"]`),
  ).toBeVisible()

  const exercise = page.getByRole("combobox", { name: "افزودن حرکت" })
  await exercise.click()
  await exercise.fill("پرس سینه هالتر")
  await page.getByRole("option", { name: /پرس سینه هالتر/ }).click()
  await page
    .locator(".m3-builder-add-exercise")
    .getByRole("button", { name: "افزودن", exact: true })
    .click()
  await expect(page.locator(".m3-set-editor input")).toHaveCount(7)
  await expectAssociatedLabels(page)
  for (const input of await page.locator(".m3-set-editor input").all()) {
    expect(
      await input.evaluate((el) => (el as HTMLInputElement).labels?.length),
    ).toBe(1)
  }
})

test("birth dates reject future calendar days and dates keep visible labels when empty", async ({
  page,
}) => {
  await page.goto("/athletes")
  await page
    .locator(".m3-entity-card")
    .filter({ hasText: "نیما ورزشکار" })
    .click()
  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  const calendar = page
    .getByRole("dialog")
    .filter({ has: page.getByRole("grid") })
  await calendar.getByRole("button", { name: "امروز", exact: true }).click()
  await page.getByRole("button", { name: "انتخاب تاریخ" }).first().click()
  await expect(
    calendar.getByRole("button", { name: "بعدی", exact: true }),
  ).toBeDisabled()
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "ساخت برنامه", exact: true }).click()
  const dates = page.locator(".m3-dialog .m3-date-field")
  await expect(dates).toHaveCount(2)
  for (const field of await dates.all()) {
    const label = field.locator(".m3-field__label")
    await expect(label).toBeVisible()
    const labelBox = await label.boundingBox()
    const controlBox = await field.locator(".m3-field__control").boundingBox()
    expect(labelBox!.y + labelBox!.height).toBeLessThan(controlBox!.y)
  }
  await expectAssociatedLabels(page)
})

test("athlete profile and upload controls have associated labels", async ({
  page,
}) => {
  await page.goto("/login")
  await page.evaluate(() => localStorage.removeItem("access_token"))
  await page.reload()
  await page.getByLabel(/ایمیل/).fill(ATHLETE_EMAIL)
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود", exact: true }).click()
  await page.waitForURL("**/")
  await page.goto("/my/profile")
  await expect(page.locator('input[type="file"]')).toHaveCount(1)
  await expectAssociatedLabels(page)
  const file = page.locator('input[type="file"]')
  const label = page.locator(`label[for="${await file.getAttribute("id")}"]`)
  await expect(label).toBeVisible()
  await expect(file).toHaveAccessibleDescription(/PDF/)

  // A picker beside an input must use the same visual field surface and size.
  for (const theme of ["light", "dark"]) {
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 900 })
      await page.evaluate(
        (theme) => localStorage.setItem("gym.theme", theme),
        theme,
      )
      await page.reload()
      await expect(page.getByLabel("تلفن", { exact: true })).toBeVisible()
      const styles = await page
        .locator(".m3-field__control")
        .evaluateAll((controls) => {
          return controls
            .filter(
              (control) =>
                control.querySelector("input")?.type === "text" ||
                control.closest(".m3-date-field, .m3-select"),
            )
            .map((control) => {
              const style = getComputedStyle(control)
              return {
                height: control.getBoundingClientRect().height,
                background: style.backgroundColor,
                radius: style.borderRadius,
                border: style.borderColor,
              }
            })
        })
      expect(styles.length).toBeGreaterThanOrEqual(4)
      for (const style of styles) {
        expect(style, `${theme} / ${width}px`).toEqual(styles[0])
      }
      if (width === 1280) {
        const phone = await page
          .getByLabel("تلفن", { exact: true })
          .locator("..")
          .boundingBox()
        const date = await page
          .locator(".m3-date-field .m3-field__control")
          .boundingBox()
        expect(date!.y).toBeCloseTo(phone!.y, 0)
      }
    }
  }
})
