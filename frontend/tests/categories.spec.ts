import { expect, test } from "@playwright/test"
import { API_URL, DEMO_PASSWORD } from "./credentials"

test("admin creates catalog entries; coach selects them; day categories reach athlete and print", async ({
  page,
  request,
}) => {
  await page.goto("/exercises")
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  const adminLogin = await request.post(
    `${API_URL}/api/v1/login/access-token`,
    { form: { username: "ali@example.com", password: DEMO_PASSWORD } },
  )
  expect(adminLogin.ok()).toBeTruthy()
  const adminToken = (await adminLogin.json()).access_token
  const admin = {
    Authorization: `Bearer ${adminToken}`,
    "X-Gym-ID": gymId!,
  }
  const suffix = Date.now()
  const categoryName = `دسته نمونه ${suffix}`
  const exerciseName = `حرکت نمونه ${suffix}`
  await page
    .getByRole("button", { name: "افزودن دسته‌بندی", exact: true })
    .click()
  await page.getByLabel(/نام دسته‌بندی/).fill(categoryName)
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "ایجاد", exact: true })
    .click()
  await expect(page.getByText("دسته‌بندی جدید ساخته شد.")).toBeVisible()
  await page
    .getByRole("button", { name: "افزودن حرکت اختصاصی", exact: true })
    .first()
    .click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel(/نام حرکت/).fill(exerciseName)
  await expect(dialog.getByRole("button", { name: /دسته‌بندی/ })).toContainText(
    categoryName,
  )
  await dialog.getByRole("button", { name: "ذخیره", exact: true }).click()
  await expect(
    page.locator(".m3-card-grid").getByText(exerciseName, { exact: true }),
  ).toBeVisible()

  const coaches = await request.get(
    `${API_URL}/api/v1/gyms/${gymId}/coaches?q=reza%40example.com`,
    {
      headers: admin,
    },
  )
  const coach = (await coaches.json()).data.find(
    (item: { email: string }) => item.email === "reza@example.com",
  )
  const email = `category-athlete-${suffix}@example.com`
  const created = await request.post(`${API_URL}/api/v1/athletes`, {
    headers: admin,
    data: {
      email,
      full_name: `ورزشکار دسته نمونه ${suffix}`,
      coach_user_id: coach.user_id,
      activation_method: "password",
      initial_password: DEMO_PASSWORD,
    },
  })
  expect(created.ok()).toBeTruthy()
  const athleteId = (await created.json()).athlete.profile.user_id
  await page.context().clearCookies()
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill("reza@example.com")
  await page.getByLabel(/رمز عبور/).fill(DEMO_PASSWORD)
  await page.getByRole("button", { name: "ورود", exact: true }).click()
  await page.waitForURL("**/")
  await page.goto("/exercises")
  await expect(
    page.getByRole("heading", { name: "کتابخانه حرکات" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "افزودن دسته‌بندی", exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "افزودن حرکت اختصاصی", exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "ویرایش", exact: true }),
  ).toHaveCount(0)
  const coachLogin = await request.post(
    `${API_URL}/api/v1/login/access-token`,
    { form: { username: "reza@example.com", password: DEMO_PASSWORD } },
  )
  expect(coachLogin.ok()).toBeTruthy()
  const coachToken = (await coachLogin.json()).access_token
  const rejected = await request.post(`${API_URL}/api/v1/exercise-categories`, {
    headers: { Authorization: `Bearer ${coachToken}`, "X-Gym-ID": gymId! },
    data: { name: `forbidden-${suffix}` },
  })
  expect(rejected.status()).toBe(403)

  await page.goto(`/athletes/${athleteId}`)
  await page
    .locator(".m3-page-header")
    .getByRole("button", { name: "ساخت برنامه", exact: true })
    .click()
  await dialog.getByLabel(/عنوان برنامه/).fill(`برنامه دسته نمونه ${suffix}`)
  await dialog.getByRole("button", { name: "ایجاد", exact: true }).click()
  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  const versionId =
    new URL(page.url()).pathname.match(/\/programs\/([^/]+)\/edit/)?.[1] ?? ""
  await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
  await page.getByRole("checkbox", { name: categoryName, exact: true }).check()
  const add = page.locator(".m3-builder-add-exercise")
  await add.getByRole("combobox").click()
  await expect(
    page.getByRole("option", { name: /پرس سینه هالتر/ }),
  ).toHaveCount(0)
  await add.getByRole("combobox").fill(exerciseName)
  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("Enter")
  await add.getByRole("button", { name: "افزودن", exact: true }).click()
  await page.getByRole("button", { name: "ذخیره پیش‌نویس", exact: true }).click()
  await expect(page.getByText("برنامه ذخیره شد.")).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole("checkbox", { name: categoryName, exact: true }),
  ).toBeChecked()
  await page.getByRole("button", { name: "انتشار برنامه", exact: true }).click()
  await dialog
    .getByRole("button", { name: "انتشار برنامه", exact: true })
    .click()
  await expect(page).toHaveURL(new RegExp(`/gyms/[^/]+/athletes/${athleteId}$`))
  await page.goto(`/print/${versionId}`)
  await expect(page.locator(".m3-print-day__title")).toHaveText(
    `روز ۱ — ${categoryName}`,
  )

  const login = await request.post(`${API_URL}/api/v1/login/access-token`, {
    form: { username: email, password: DEMO_PASSWORD },
  })
  const athleteToken = (await login.json()).access_token
  const changed = await request.post(`${API_URL}/api/v1/users/me/password`, {
    headers: { Authorization: `Bearer ${athleteToken}` },
    data: { current_password: DEMO_PASSWORD, new_password: "DemoAthlete456!" },
  })
  expect(changed.ok()).toBeTruthy()
  await page.context().clearCookies()
  await page.goto("/login")
  await page.getByLabel(/ایمیل/).fill(email)
  await page.getByLabel(/رمز عبور/).fill("DemoAthlete456!")
  await page.getByRole("button", { name: "ورود", exact: true }).click()
  await page.waitForURL("**/")
  await page.goto(`/my/programs/${versionId}`)
  await expect(
    page.getByRole("tab", { name: `روز ۱ — ${categoryName}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(exerciseName, { exact: false }).first(),
  ).toBeVisible()
  expect(
    (
      await request.post(`${API_URL}/api/v1/athletes/${athleteId}/archive`, {
        headers: admin,
      })
    ).ok(),
  ).toBeTruthy()
})

test("category changes protect existing movements from incompatible choices", async ({
  page,
}) => {
  await page.goto("/templates/new")
  await page.getByRole("button", { name: "افزودن روز", exact: true }).click()
  const category = page.getByRole("checkbox", { name: "بازو", exact: true })
  await category.check()
  const add = page.locator(".m3-builder-add-exercise")
  await add.getByRole("combobox").click()
  await add.getByRole("combobox").fill("جلوبازو هالتر")
  await expect(add.getByRole("combobox")).toHaveAttribute(
    "aria-expanded",
    "true",
  )
  await expect(
    page.getByRole("option", { name: "جلوبازو هالتر · بازو", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("option", { name: /پرس سینه هالتر/ }),
  ).toHaveCount(0)
  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("Enter")
  await add.getByRole("button", { name: "افزودن", exact: true }).click()
  await page.getByRole("checkbox", { name: "سینه", exact: true }).check()
  await expect(
    page.getByRole("checkbox", { name: "سینه", exact: true }),
  ).toBeChecked()
  await category.click()
  await expect(page.getByText(/برای حذف این دسته/)).toBeVisible()
  await expect(category).toBeChecked()
  await expect(page.locator(".m3-exercise-block")).toHaveCount(1)
})
