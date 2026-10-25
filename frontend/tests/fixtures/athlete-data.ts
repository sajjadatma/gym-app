import { randomUUID } from "node:crypto"

import { test as base, expect } from "@playwright/test"

import type { CoachPublic } from "../../src/client"
import { API_URL, DEMO_PASSWORD } from "../credentials"

export type ManagedAthlete = {
  athleteId: string
  email: string
  headers: Record<string, string>
}

export type AthleteData = {
  marker: string
  headers: Record<string, string>
  coach: CoachPublic
  create(options?: {
    name?: string
    archived?: boolean
  }): Promise<ManagedAthlete>
  trackEmail(email: string): void
  cleanup(): Promise<void>
}

type AthleteSummary = {
  user_id: string
  email: string
  is_archived: boolean
}

export const test = base.extend<{ athleteData: AthleteData }>({
  athleteData: async ({ page, request }, use) => {
    await page.goto("/")
    await page.waitForFunction(() =>
      Boolean(localStorage.getItem("gym.activeGymId")),
    )
    const gymId = await page.evaluate(() =>
      localStorage.getItem("gym.activeGymId"),
    )
    expect(gymId).toBeTruthy()
    const login = await request.post(`${API_URL}/api/v1/login/access-token`, {
      form: { username: "ali@example.com", password: DEMO_PASSWORD },
    })
    expect(login.ok()).toBeTruthy()
    const token = (await login.json()).access_token as string
    const headers: Record<string, string> = Object.freeze({
      Authorization: `Bearer ${token}`,
      "X-Gym-ID": gymId!,
    })

    const coachesResponse = await request.get(
      `${API_URL}/api/v1/gyms/${gymId}/coaches?q=reza%40example.com`,
      { headers },
    )
    expect(coachesResponse.ok()).toBeTruthy()
    const coaches = (await coachesResponse.json()).data as CoachPublic[]
    const coach = coaches.find((item) => item.email === "reza@example.com")
    expect(coach).toBeTruthy()

    const marker = `e2e-${randomUUID()}`
    const trackedEmails = new Set<string>()
    const finalHeaders = headers
    let sequence = 0

    function trackEmail(email: string) {
      if (!email.startsWith(`${marker}-`)) {
        throw new Error(
          `Managed athlete email must start with "${marker}-": ${email}`,
        )
      }
      trackedEmails.add(email)
    }

    const data: AthleteData = {
      marker,
      headers: finalHeaders,
      coach: coach!,
      async create(options) {
        sequence += 1
        const email = `${marker}-${randomUUID()}@example.com`
        trackEmail(email)
        const created = await request.post(`${API_URL}/api/v1/athletes`, {
          headers: finalHeaders,
          data: {
            email,
            full_name: options?.name ?? `${marker} athlete ${sequence}`,
            coach_user_id: coach!.user_id,
            activation_method: "password",
            initial_password: DEMO_PASSWORD,
          },
        })
        expect(created.ok()).toBeTruthy()
        const athleteId = (await created.json()).athlete.profile
          .user_id as string
        if (options?.archived) {
          const archived = await request.post(
            `${API_URL}/api/v1/athletes/${athleteId}/archive`,
            { headers: finalHeaders },
          )
          expect(archived.ok()).toBeTruthy()
        }
        return { athleteId, email, headers: finalHeaders }
      },
      trackEmail,
      async cleanup() {
        const failures: string[] = []
        for (const email of trackedEmails) {
          const listResponse = await request.get(
            `${API_URL}/api/v1/athletes?q=${encodeURIComponent(email)}&include_archived=true`,
            { headers: finalHeaders },
          )
          if (!listResponse.ok()) {
            failures.push(
              `list ${email}: ${listResponse.status()} ${await listResponse.text()}`,
            )
            continue
          }
          const matches = (
            (await listResponse.json()).data as AthleteSummary[]
          ).filter((athlete) => athlete.email === email)
          for (const athlete of matches) {
            const archived = await request.post(
              `${API_URL}/api/v1/athletes/${athlete.user_id}/archive`,
              { headers: finalHeaders },
            )
            if (archived.status() !== 200 && archived.status() !== 404) {
              failures.push(
                `archive ${email}: ${archived.status()} ${await archived.text()}`,
              )
            }
            const deleted = await request.delete(
              `${API_URL}/api/v1/athletes/${athlete.user_id}`,
              { headers: finalHeaders },
            )
            if (deleted.status() !== 200 && deleted.status() !== 404) {
              failures.push(
                `delete ${email}: ${deleted.status()} ${await deleted.text()}`,
              )
            }
          }
        }
        if (failures.length) {
          throw new Error(
            `Managed athlete cleanup failed:\n${failures.join("\n")}`,
          )
        }
      },
    }

    try {
      await use(data)
    } finally {
      await data.cleanup()
    }
  },
})

export { expect } from "@playwright/test"
