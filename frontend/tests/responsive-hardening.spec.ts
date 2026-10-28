import { expect, type Page, test } from "@playwright/test"

const GYM_ID = "11111111-1111-4111-8111-111111111111"
const USER_ID = "22222222-2222-4222-8222-222222222222"
const VERSION_ID = "33333333-3333-4333-8333-333333333333"

type Role = "GYM_ADMIN" | "COACH" | "ATHLETE"

const gym = {
  id: GYM_ID,
  name: "باشگاه آزمایشی",
  description: null,
  address: null,
  phone: null,
  brand_primary_color: null,
  brand_accent_color: null,
  logo_url: null,
  owner_id: USER_ID,
  owner_name: "مدیر آزمایشی",
  is_active: true,
  created_at: "2025-01-01T08:00:00Z",
  is_owner: true,
  my_roles: ["GYM_ADMIN"] as Role[],
  stats: null,
}

function gymFor(role: Role) {
  return { ...gym, my_roles: [role], is_owner: role === "GYM_ADMIN" }
}

function me(role: Role) {
  return {
    id: USER_ID,
    email: "review@example.com",
    full_name: "کاربر آزمایشی",
    phone: null,
    is_active: true,
    is_superuser: false,
    must_change_password: false,
    created_at: "2025-01-01T08:00:00Z",
    gyms: [
      {
        gym_id: GYM_ID,
        gym_name: gym.name,
        roles: [role],
        is_owner: role === "GYM_ADMIN",
      },
    ],
  }
}

const version = {
  id: VERSION_ID,
  program_id: "44444444-4444-4444-8444-444444444444",
  athlete_user_id: "55555555-5555-4555-8555-555555555555",
  athlete_name: "ورزشکار آزمایشی",
  title: "برنامه آزمون",
  goal: null,
  version_number: 1,
  revision: 1,
  status: "ACTIVE" as const,
  coach_id: USER_ID,
  coach_name: "مربی آزمایشی",
  start_date: null,
  end_date: null,
  created_at: "2025-02-01T08:00:00Z",
  published_at: "2025-02-01T08:00:00Z",
  archived_at: null,
  day_count: 1,
  notes: null,
  days: [
    {
      day_number: 1,
      weekday: null,
      title: "روز اول",
      notes: null,
      category_id: null,
      category_ids: [],
      category_names: [],
      category_name: null,
      id: "66666666-6666-4666-8666-666666666666",
      exercises: [
        {
          exercise_id: "77777777-7777-4777-8777-777777777777",
          order_index: 0,
          notes: null,
          id: "88888888-8888-4888-8888-888888888888",
          exercise_name: "پرس سینه",
          muscle_group: "سینه",
          sets: [
            {
              set_number: 1,
              reps_min: 8,
              reps_max: 10,
              weight_kg: 40,
              intensity: "RPE 8",
              rest_seconds: 60,
              duration_seconds: 45,
              note: "آرام",
              id: "99999999-9999-4999-8999-999999999999",
            },
          ],
        },
      ],
    },
  ],
}

const athleteSummary = {
  user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  gym_id: GYM_ID,
  email: "athlete@example.com",
  full_name: "ورزشکار آزمایشی",
  phone: "09120000000",
  is_active: true,
  is_archived: false,
  coach_user_id: USER_ID,
  coach_name: "مربی آزمایشی",
  active_program_id: null,
  active_program_title: null,
  active_program_version: null,
  created_at: "2025-01-01T08:00:00Z",
}

function overview() {
  const profile = {
    user_id: athleteSummary.user_id,
    gym_id: GYM_ID,
    email: athleteSummary.email,
    full_name: athleteSummary.full_name,
    phone: athleteSummary.phone,
    birth_date: null,
    height_cm: 180,
    weight_kg: 80,
    chest_cm: null,
    waist_cm: null,
    hips_cm: null,
    arm_cm: null,
    thigh_cm: null,
    training_goal: null,
    sports_history: null,
    fitness_level: null,
    limitations: null,
    training_days: [],
    training_days_count: null,
    equipment: null,
    is_archived: false,
    created_at: "2025-01-01T08:00:00Z",
    updated_at: "2025-01-01T08:00:00Z",
  }
  return {
    kind: "ATHLETE",
    focus_gym_id: GYM_ID,
    focus_gym_name: gym.name,
    account: {
      user_id: athleteSummary.user_id,
      email: athleteSummary.email,
      full_name: athleteSummary.full_name,
      phone: athleteSummary.phone,
      is_active: true,
      created_at: "2025-01-01T08:00:00Z",
    },
    memberships: [
      {
        membership_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        gym_id: GYM_ID,
        gym_name: gym.name,
        roles: ["ATHLETE"],
        is_active: true,
        is_owner: false,
        created_at: "2025-01-01T08:00:00Z",
      },
    ],
    athlete: {
      profile,
      measurements_updated_at: "2025-01-01T08:00:00Z",
      internal_coach_note: null,
      current_coach: null,
      assignments: [],
      programs: [
        {
          ...version,
          days: version.days,
        },
      ],
      body_files: [],
    },
    coach: null,
    stats: {
      memberships: 1,
      assignments: 0,
      active_assignments: 0,
      program_versions: 1,
      active_program_versions: 1,
      body_files: 0,
    },
    history: [],
    generated_at: "2025-01-01T08:00:00Z",
  }
}

async function prepare(
  page: Page,
  {
    role,
    activeGym = true,
    view = "grid",
    personOverview = false,
    program = false,
    athletes = false,
  }: {
    role: Role
    activeGym?: boolean
    view?: "grid" | "table"
    personOverview?: boolean
    program?: boolean
    athletes?: boolean
  },
) {
  await page.addInitScript(
    ({ gymId, active, athleteView, activeRole }) => {
      if (active) {
        localStorage.setItem("gym.activeGymId", gymId)
        localStorage.setItem("gym.activeRole", activeRole)
      } else {
        localStorage.removeItem("gym.activeGymId")
      }
      localStorage.setItem("gym.athletes.view", athleteView)
      localStorage.setItem("gym.locale", "fa")
      localStorage.setItem("gym.theme", "light")
    },
    { gymId: GYM_ID, active: activeGym, athleteView: view, activeRole: role },
  )

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      })

    if (path === "/api/v1/users/me") return json(me(role))
    if (path === "/api/v1/gyms/" || path === "/api/v1/gyms") {
      return json({ data: [gymFor(role)], count: 1 })
    }
    if (athletes && path === "/api/v1/athletes") {
      return json({ data: [athleteSummary], count: 1 })
    }
    if (
      personOverview &&
      path === `/api/v1/people/${athleteSummary.user_id}/overview`
    ) {
      return json(overview())
    }
    if (program && path === `/api/v1/program-versions/${VERSION_ID}`) {
      return json(version)
    }
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "not_found" }),
    })
  })
}

test("workout duration stays visible on a phone", async ({ page }) => {
  await prepare(page, { role: "ATHLETE", program: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/gyms/${GYM_ID}/my/programs/${VERSION_ID}`)

  const setRow = page.locator(".m3-set-row").first()
  await expect(setRow).toBeVisible()
  await expect(setRow.getByText("مدت")).toBeVisible()
  await expect(setRow.getByText("۴۵ ثانیه")).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})

test("overview set rows render every column in order", async ({ page }) => {
  await prepare(page, { role: "GYM_ADMIN", personOverview: true })
  await page.goto(
    `/people/${athleteSummary.user_id}?gym=${GYM_ID}&kind=ATHLETE`,
  )

  const cells = page.locator(".person-set-table tbody tr").first().locator("td")
  await expect(cells).toHaveCount(7)
  await expect(cells.nth(4)).toHaveText("۴۵ ثانیه")
  await expect(cells.nth(5)).toHaveText("RPE 8")
  await expect(cells.nth(6)).toHaveText("آرام")
})

test("coaches only see actions the overview API authorizes", async ({
  page,
}) => {
  await prepare(page, { role: "COACH", athletes: true, view: "grid" })
  await page.goto(`/gyms/${GYM_ID}/athletes`)

  const card = page.locator(".m3-entity-card").first()
  await expect(card).toBeVisible()
  await expect(card.getByRole("button", { name: "جزئیات" })).toHaveCount(0)
  await expect(
    card.getByRole("button", { name: "باز کردن", exact: true }),
  ).toBeVisible()

  await page.getByRole("button", { name: "جدول", exact: true }).click()
  const row = page.locator(".m3-data-table tbody tr").first()
  await expect(row).toBeVisible()
  await expect(row.getByRole("button", { name: "جزئیات" })).toHaveCount(0)
  await expect(
    row.getByRole("button", { name: "اقدام‌های بیشتر" }),
  ).toBeVisible()
})

test("account menu stays inside a landscape viewport and closes on Escape", async ({
  page,
}) => {
  await prepare(page, { role: "GYM_ADMIN", activeGym: false })
  await page.setViewportSize({ width: 844, height: 390 })
  await page.goto("/profile")

  const trigger = page.locator(".m3-topbar__actions button").first()
  await trigger.click()
  const menu = page.locator(".m3-menu")
  await expect(menu).toBeVisible()

  const box = await menu.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(390)

  await page.keyboard.press("Escape")
  await expect(menu).toHaveCount(0)
  await expect(trigger).toHaveAttribute("aria-expanded", "false")
})
