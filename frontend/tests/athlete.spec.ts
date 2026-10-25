import fs from "node:fs"
import path from "node:path"
import { expect, test } from "@playwright/test"

test("athlete sees active program, sets and can generate a Persian PDF", async ({
  page,
}) => {
  await page.goto("/my")
  await expect(page.getByRole("heading", { name: "برنامه من" })).toBeVisible()
  await expect(page.getByText("برنامه قدرتی ۸ هفته‌ای").first()).toBeVisible()
  await expect(page.locator(".m3-mobile-nav")).toBeVisible()

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)

  await page.getByRole("button", { name: "مشاهده" }).first().click()
  await expect(page).toHaveURL(/\/my\/programs\/[^/]+$/)
  await expect(page.getByText("پرس سینه هالتر").first()).toBeVisible()
  await expect(page.getByText("PRIVATE-DEMO-NOTE")).toHaveCount(0)

  const versionId = page.url().split("/").pop()
  await page.goto(`/print/${versionId}`)
  await expect(page.getByText("نسخه چاپی برنامه")).toHaveCount(0)
  await expect(page.getByText("چاپ یا ذخیره PDF")).toBeVisible()
  await expect(page.locator(".m3-print-sheet")).toBeVisible()
  await expect(page.getByText("PRIVATE-DEMO-NOTE")).toHaveCount(0)

  const pdfPath = path.join("test-results", "program-print.pdf")
  fs.mkdirSync("test-results", { recursive: true })
  await page.emulateMedia({ media: "print" })
  await page.pdf({ path: pdfPath, format: "A4", printBackground: true })
  const pdf = fs.readFileSync(pdfPath)
  expect(pdf.subarray(0, 4).toString()).toBe("%PDF")
  expect(pdf.length).toBeGreaterThan(1000)
})

test("athlete profile saves without equipment, uses numbered days and redirects to the dashboard", async ({
  page,
}) => {
  await page.goto("/my/profile")
  await expect(page.getByRole("heading", { name: "پرونده من" })).toBeVisible()
  await expect(page.getByText("PRIVATE-DEMO-NOTE")).toHaveCount(0)
  await expect(page.getByLabel("تجهیزات در دسترس")).toHaveCount(0)
  const trainingDays = page.getByLabel("تعداد روز تمرین در هفته")
  await expect(trainingDays).toHaveAttribute("type", "number")
  await expect(trainingDays).toHaveAttribute("min", "1")
  await expect(trainingDays).toHaveAttribute("max", "7")

  const dateSegments = page.locator(".m3-date-field .m3-date-segment")
  await expect(dateSegments).toHaveCount(3)
  const segmentOrder = await dateSegments.evaluateAll((segments) =>
    segments
      .map((segment) => segment.getAttribute("data-type"))
      .filter((type) => type && type !== "literal"),
  )
  expect(segmentOrder).toEqual(["day", "month", "year"])

  await page.getByRole("button", { name: "ذخیره پرونده" }).click()
  await expect(page.getByText("پرونده شما ذخیره شد.")).toBeVisible()
  await expect(page).toHaveURL(/\/gyms\/[^/]+$/)
})

test("athlete landing highlights the dashboard nav item", async ({ page }) => {
  await page.goto("/")
  await expect(
    page.locator(".m3-mobile-nav__item[aria-current='page']"),
  ).toHaveText(/داشبورد/)
})

test("athlete deep links to staff pages fall back to the club dashboard", async ({
  page,
}) => {
  await page.goto("/")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(gymId).toBeTruthy()
  await page.goto(`/gyms/${gymId}/athletes`)
  await expect(page).toHaveURL(new RegExp(`/gyms/${gymId}$`))
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
})
