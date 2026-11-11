import { expect, test } from "@playwright/test"

for (const width of [1280, 390]) {
  for (const trigger of ["input", "chevron"] as const) {
    test(`${width}: one ${trigger} click opens exercise options and mouse selection works`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto("/templates/new")
      await page
        .getByRole("button", { name: "افزودن روز", exact: true })
        .click()
      await page.getByRole("checkbox", { name: "بازو", exact: true }).check()
      const add = page.locator(".m3-builder-add-exercise")
      const input = add.getByRole("combobox")
      await page.locator("h1").click()
      if (trigger === "input") await input.click()
      else await add.locator(".m3-combobox__trigger").click()
      await expect(input).toHaveAttribute("aria-expanded", "true")
      await expect(
        page.getByRole("option", { name: "جلوبازو هالتر · بازو", exact: true }),
      ).toBeVisible()
      await input.fill("جلوبازو هالتر")
      await expect(input).toHaveAttribute("aria-expanded", "true")
      await page
        .getByRole("option", { name: "جلوبازو هالتر · بازو", exact: true })
        .click()
      await expect(input).toHaveValue("جلوبازو هالتر · بازو")
      await expect(input).toHaveAttribute("aria-expanded", "false")
      await add.getByRole("button", { name: "افزودن", exact: true }).click()
      await expect(page.locator(".m3-exercise-block")).toHaveCount(1)
    })
  }
}

for (const width of [1280, 390]) {
  test(`${width}: Escape, keyboard selection, reopening and outside dismissal work`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto("/templates/new")
    await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
    await page.getByRole("checkbox", { name: "بازو", exact: true }).check()
    const add = page.locator(".m3-builder-add-exercise")
    const input = add.getByRole("combobox")
    await input.focus()
    await input.press("ArrowDown")
    await expect(page.getByRole("listbox")).toBeVisible()
    await input.press("Escape")
    await expect(input).toHaveAttribute("aria-expanded", "false")
    await expect(input).toBeFocused()
    await input.click()
    await expect(page.getByRole("listbox")).toBeVisible()
    await input.fill("جلوبازو هالتر")
    await input.press("ArrowDown")
    await input.press("Enter")
    await expect(input).toHaveValue("جلوبازو هالتر · بازو")
    await add.locator(".m3-combobox__trigger").click()
    await expect(page.getByRole("listbox")).toBeVisible()
    await add.locator(".m3-combobox__trigger").click()
    await expect(input).toHaveAttribute("aria-expanded", "false")
    await input.click()
    await expect(page.getByRole("listbox")).toBeVisible()
    await page.locator("h1").click()
    await expect(input).toHaveAttribute("aria-expanded", "false")
    await expect(input).toHaveValue("جلوبازو هالتر · بازو")
  })
}

test.describe("touch input", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } })
  for (const trigger of ["input", "chevron"] as const) {
    test(`a single ${trigger} tap opens and selects an option`, async ({
      page,
    }) => {
      await page.goto("/templates/new")
      await page.getByRole("button", { name: "افزودن روز", exact: true }).tap()
      await page.getByRole("checkbox", { name: "بازو", exact: true }).check()
      const add = page.locator(".m3-builder-add-exercise")
      const input = add.getByRole("combobox")
      if (trigger === "input") await input.tap()
      else await add.locator(".m3-combobox__trigger").tap()
      await expect(
        page.getByRole("option", { name: "جلوبازو هالتر · بازو", exact: true }),
      ).toBeVisible()
      // React Aria keeps the popup clipped while the touch keyboard settles.
      // A visible DOM box alone does not mean the options can receive taps.
      await expect(page.locator(".m3-combobox__popover")).toHaveCSS(
        "opacity",
        "1",
      )
      await expect(page.locator(".m3-combobox__popover")).toHaveCSS(
        "clip-path",
        "none",
      )
      await page
        .getByRole("option", { name: "جلوبازو هالتر · بازو", exact: true })
        .tap()
      await expect(input).toHaveValue("جلوبازو هالتر · بازو")
      await expect(input).toHaveAttribute("aria-expanded", "false")
    })
  }
})
