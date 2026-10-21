import { expect, test } from "@playwright/test"

import { API_URL, DEMO_PASSWORD } from "./credentials"

test("admin builds, saves and publishes a program through the UI", async ({
  page,
  request,
}) => {
  await page.goto("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const gymId = await page.evaluate(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  expect(token).toBeTruthy()
  expect(gymId).toBeTruthy()
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Gym-ID": gymId!,
  }

  const coachesResponse = await request.get(
    `${API_URL}/api/v1/gyms/${gymId}/coaches`,
    { headers },
  )
  expect(coachesResponse.ok()).toBeTruthy()
  const coaches = (await coachesResponse.json()).data
  const coach = coaches.find(
    (item: { email: string }) => item.email === "reza@example.com",
  )
  expect(coach).toBeTruthy()

  const email = `ui-builder-${Date.now()}@example.com`
  const athleteResponse = await request.post(`${API_URL}/api/v1/athletes`, {
    headers,
    data: {
      email,
      full_name: "ورزشکار آزمون رابط",
      coach_user_id: coach.user_id,
      activation_method: "password",
      initial_password: DEMO_PASSWORD,
      training_goal: "آزمون برنامه‌ساز",
    },
  })
  expect(athleteResponse.ok()).toBeTruthy()
  const athleteId = (await athleteResponse.json()).athlete.profile.user_id

  await page.goto(`/athletes/${athleteId}`)
  await page.getByRole("button", { name: "ساخت برنامه" }).click()
  const createDialog = page.getByRole("dialog")
  await createDialog.getByLabel(/عنوان برنامه/).fill("برنامه آزمون رابط")
  await createDialog.getByRole("button", { name: "ایجاد" }).click()

  await expect(page).toHaveURL(/\/programs\/[^/]+\/edit$/)
  await expect(
    page.getByRole("heading", { name: "برنامه آزمون رابط" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "افزودن روز" }).click()
  const addExercise = page.locator(".m3-builder-add-exercise")
  await addExercise.locator("select").selectOption({
    label: "پرس سینه هالتر · سینه",
  })
  await addExercise.getByRole("button", { name: "افزودن" }).click()
  await expect(
    page.locator(".m3-set-editor input[type=number]").first(),
  ).toHaveValue("8")

  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click()
  await expect(page.getByText("پیش‌نویس برنامه ذخیره شد.")).toBeVisible()

  await page.getByRole("button", { name: "انتشار برنامه" }).click()
  const publishDialog = page.getByRole("dialog")
  await expect(publishDialog).toBeVisible()
  await publishDialog.getByRole("button", { name: "انتشار برنامه" }).click()
  await expect(page).toHaveURL(new RegExp(`/athletes/${athleteId}$`))
  await expect(page.getByText("برنامه آزمون رابط").first()).toBeVisible()

  const archive = await request.post(
    `${API_URL}/api/v1/athletes/${athleteId}/archive`,
    { headers },
  )
  expect(archive.ok()).toBeTruthy()
})
