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

function me(role: Role, superuser = false) {
  return {
    id: USER_ID,
    email: "review@example.com",
    full_name: "کاربر آزمایشی",
    phone: null,
    is_active: true,
    is_superuser: superuser,
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

const category = {
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  name: "سینه",
  gym_id: GYM_ID,
}

const exercise = {
  id: "77777777-7777-4777-8777-777777777777",
  name_fa: "پرس سینه",
  muscle_group: "سینه",
  category_id: category.id,
  description: null,
  instructions: null,
  is_custom: true,
  gym_id: GYM_ID,
}

function athleteProfile() {
  return {
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
}

function athleteDetail() {
  return {
    profile: athleteProfile(),
    coach_user_id: USER_ID,
    coach_name: "مربی آزمایشی",
    coach_email: "coach@example.com",
    assignments: [],
    body_files: [],
    internal_coach_note: null,
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

const superuserAthlete = {
  user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  gym_id: GYM_ID,
  gym_name: gym.name,
  email: "athlete@example.com",
  full_name: "ورزشکار آزمایشی",
  phone: "09120000000",
  is_archived: false,
  coach_user_id: USER_ID,
  coach_name: "مربی آزمایشی",
  created_at: "2025-01-01T08:00:00Z",
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
  const profile = athleteProfile()
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
    programEditor = false,
    athleteRecord = false,
    superuser = false,
    locale = "fa",
    globalAthletes = false,
    offlineIdentity = false,
  }: {
    role: Role
    activeGym?: boolean
    view?: "grid" | "table"
    personOverview?: boolean
    program?: boolean
    athletes?: boolean
    programEditor?: boolean
    athleteRecord?: boolean
    superuser?: boolean
    locale?: "fa" | "en"
    globalAthletes?: boolean
    offlineIdentity?: boolean
  },
) {
  await page.addInitScript(
    ({ gymId, active, athleteView, activeRole, language, offline }) => {
      if (active) {
        localStorage.setItem("gym.activeGymId", gymId)
        localStorage.setItem("gym.activeRole", activeRole)
      } else {
        localStorage.removeItem("gym.activeGymId")
      }
      localStorage.setItem("gym.athletes.view", athleteView)
      localStorage.setItem("superuser.athletes.view", athleteView)
      localStorage.setItem("gym.locale", language)
      localStorage.setItem("gym.theme", "light")
      if (offline) {
        Object.defineProperty(navigator, "onLine", {
          configurable: true,
          get: () => false,
        })
      }
    },
    {
      gymId: GYM_ID,
      active: activeGym,
      athleteView: view,
      activeRole: role,
      language: locale,
      offline: offlineIdentity,
    },
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

    if (path === "/api/v1/users/me") {
      if (offlineIdentity) return route.abort("internetdisconnected")
      return json(me(role, superuser))
    }
    if (path === "/api/v1/gyms/" || path === "/api/v1/gyms") {
      return json({ data: [gymFor(role)], count: 1 })
    }
    if (athletes && path === "/api/v1/athletes") {
      return json({ data: [athleteSummary], count: 1 })
    }
    if (globalAthletes && path === "/api/v1/superuser/athletes") {
      return json({ data: [superuserAthlete], count: 1 })
    }
    if (programEditor && path === "/api/v1/exercises") {
      return json({ data: [exercise], count: 1 })
    }
    if (programEditor && path === "/api/v1/exercise-categories") {
      return json({ data: [category], count: 1 })
    }
    if (
      programEditor &&
      path === `/api/v1/athletes/${athleteSummary.user_id}`
    ) {
      return json(athleteDetail())
    }
    if (
      athleteRecord &&
      path === `/api/v1/athletes/${athleteSummary.user_id}`
    ) {
      return json(athleteDetail())
    }
    if (
      athleteRecord &&
      path === `/api/v1/athletes/${athleteSummary.user_id}/programs`
    ) {
      return json({ data: [], count: 0 })
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

test("tables follow the active locale direction", async ({ page }) => {
  await prepare(page, {
    role: "GYM_ADMIN",
    athletes: true,
    program: true,
    view: "table",
    locale: "en",
  })
  await page.goto(`/gyms/${GYM_ID}/athletes`)

  await expect(page.locator("html")).toHaveAttribute("dir", "ltr")
  const table = page.locator(".m3-data-table").first()
  await expect(table).toBeVisible()
  await expect(table).toHaveCSS("direction", "ltr")

  await page.goto(`/print/${VERSION_ID}`)
  await expect(page.locator(".m3-print-sheet")).toHaveCSS("direction", "ltr")

  await page.goto(`/gyms/${GYM_ID}/athletes`)
  await page.locator(".m3-topbar__actions button").first().click()
  await page.locator(".m3-menu").getByRole("button", { name: /فارسی/ }).click()
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
  await expect(page.locator(".m3-data-table").first()).toHaveCSS(
    "direction",
    "rtl",
  )
})

test("mobile table cells keep status content inside their column", async ({
  page,
}) => {
  await prepare(page, {
    role: "COACH",
    athletes: true,
    view: "table",
  })
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto(`/gyms/${GYM_ID}/athletes`)

  const cell = page
    .locator(".m3-data-table tbody tr")
    .first()
    .locator(".m3-people-table__status")
  await expect(cell).toBeVisible()
  const fit = await cell.evaluate((element) => ({
    client: element.clientWidth,
    scroll: element.scrollWidth,
  }))
  expect(fit.scroll).toBeLessThanOrEqual(fit.client + 1)
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})

test("global athlete tables keep the club visible on phones", async ({
  page,
}) => {
  await prepare(page, {
    role: "GYM_ADMIN",
    activeGym: false,
    superuser: true,
    globalAthletes: true,
    view: "table",
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/athletes")

  const club = page
    .locator(".m3-data-table tbody tr")
    .first()
    .locator(".m3-people-table__club")
  await expect(club).toBeVisible()
  await expect(club).toContainText(gym.name)
})

test("mobile action controls meet the minimum touch size", async ({ page }) => {
  await prepare(page, { role: "GYM_ADMIN", athletes: true, view: "table" })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/gyms/${GYM_ID}/athletes`)

  const details = page
    .locator(".m3-data-table tbody tr")
    .first()
    .getByRole("button", { name: "جزئیات" })
  await expect(details).toBeVisible()
  for (const target of [
    details,
    page.locator(".m3-topbar__actions button").first(),
    page
      .locator(".m3-data-table tbody tr")
      .first()
      .getByRole("button", { name: "اقدام‌های بیشتر" }),
  ]) {
    const box = await target.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(44)
    expect(box!.width).toBeGreaterThanOrEqual(44)
  }
})

test("mobile inputs stay at a readable size", async ({ page }) => {
  await prepare(page, { role: "GYM_ADMIN", activeGym: false })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/login")

  const input = page.locator(".m3-field__input").first()
  await expect(input).toBeVisible()
  const fontSize = await input.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  )
  expect(fontSize).toBeGreaterThanOrEqual(16)
})

test("program editor labels stay legible on phones", async ({ page }) => {
  await prepare(page, {
    role: "COACH",
    program: true,
    programEditor: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/gyms/${GYM_ID}/programs/${VERSION_ID}/edit`)

  const field = page.locator(".program-set-field").first()
  await expect(field).toBeVisible()
  const labelSize = await field.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element, "::before").fontSize),
  )
  const inputSize = await field
    .locator("input")
    .evaluate((element) =>
      Number.parseFloat(getComputedStyle(element).fontSize),
    )
  expect(labelSize).toBeGreaterThanOrEqual(10)
  expect(inputSize).toBeGreaterThanOrEqual(16)
})

test("row action menu closes on Tab and stays open on its own scroll", async ({
  page,
}) => {
  await prepare(page, { role: "GYM_ADMIN", athletes: true, view: "table" })
  await page.goto(`/gyms/${GYM_ID}/athletes`)

  const row = page.locator(".m3-data-table tbody tr").first()
  const more = row.getByRole("button", { name: "اقدام‌های بیشتر" })
  await more.click()
  const menu = page.getByRole("menu")
  await expect(menu).toBeVisible()
  await expect(menu.getByRole("menuitem").first()).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(page.getByRole("menu")).toHaveCount(0)
  await expect(more).toBeFocused()

  await more.click()
  await expect(menu).toBeVisible()
  await menu.dispatchEvent("scroll")
  await expect(menu).toBeVisible()
})

test("athlete record tabs support arrow keys and expose a panel", async ({
  page,
}) => {
  await prepare(page, {
    role: "GYM_ADMIN",
    athleteRecord: true,
  })
  await page.goto(`/gyms/${GYM_ID}/athletes/${athleteSummary.user_id}`)

  const tabs = page.getByRole("tab")
  await expect(tabs).toHaveCount(3)
  await expect(tabs.nth(0)).toHaveAttribute("tabindex", "0")
  await expect(tabs.nth(1)).toHaveAttribute("tabindex", "-1")
  await tabs.nth(0).focus()
  await page.keyboard.press("ArrowLeft")
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true")
  await expect(tabs.nth(1)).toBeFocused()
  await expect(page.getByRole("tabpanel")).toBeVisible()
})

test("offline notice appears and clears when the connection returns", async ({
  page,
}) => {
  await prepare(page, { role: "GYM_ADMIN", athletes: true })
  await page.goto(`/gyms/${GYM_ID}/athletes`)
  const notice = page.locator(".m3-offline-banner")
  await expect(notice).toHaveCount(0)

  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    })
    window.dispatchEvent(new Event("offline"))
  })
  await expect(notice).toBeVisible()
  await expect(notice).toContainText("اتصال اینترنت قطع است")

  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => true,
    })
    window.dispatchEvent(new Event("online"))
  })
  await expect(notice).toHaveCount(0)
})

test("offline identity failure shows recovery instead of the login form", async ({
  page,
}) => {
  await prepare(page, { role: "GYM_ADMIN", offlineIdentity: true })
  await page.goto("/profile")

  await expect(page.getByRole("heading", { name: "بدون اتصال" })).toBeVisible()
  await expect(page.getByLabel(/ایمیل/)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "تلاش دوباره" })).toBeVisible()
})
