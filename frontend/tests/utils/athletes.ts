import { expect, type Page } from "@playwright/test"

/**
 * Select an athlete from the gym athletes list regardless of the current
 * pagination page or card/table view. Filtering first is also a realistic
 * user path and keeps tests independent of list size.
 */
export async function openAthlete(page: Page, name: string) {
  const search = page.getByLabel(
    /جستجوی نام، ایمیل یا تلفن|Search name, email or phone/,
  )
  await search.fill(name)
  const target = page.getByRole("button", { name: new RegExp(name) }).first()
  await expect(target).toBeVisible()
  await target.click()
}
