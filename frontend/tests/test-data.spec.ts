import { randomUUID } from "node:crypto"
import { API_URL, DEMO_PASSWORD } from "./credentials"
import { expect, test } from "./fixtures/athlete-data"

function listingUrl(email?: string) {
  const query = new URLSearchParams({ include_archived: "true" })
  if (email) query.set("q", email)
  return `${API_URL}/api/v1/athletes?${query.toString()}`
}

test("managed athlete cleanup is idempotent and preserves seeded athletes", async ({
  athleteData,
  request,
}) => {
  const beforeResponse = await request.get(listingUrl(), {
    headers: athleteData.headers,
  })
  expect(beforeResponse.ok()).toBeTruthy()
  const before = await beforeResponse.json()
  const nimaResponse = await request.get(listingUrl("nima@example.com"), {
    headers: athleteData.headers,
  })
  expect(nimaResponse.ok()).toBeTruthy()
  const nima = (await nimaResponse.json()).data[0]
  expect(nima).toBeTruthy()
  const nimaBeforeResponse = await request.get(
    `${API_URL}/api/v1/athletes/${nima.user_id}`,
    { headers: athleteData.headers },
  )
  expect(nimaBeforeResponse.ok()).toBeTruthy()
  const nimaBefore = await nimaBeforeResponse.json()

  const active = await athleteData.create({
    name: `${athleteData.marker} active`,
  })
  const archived = await athleteData.create({
    name: `${athleteData.marker} archived`,
    archived: true,
  })

  await athleteData.cleanup()
  await athleteData.cleanup()

  for (const target of [active, archived]) {
    const missing = await request.get(
      `${API_URL}/api/v1/athletes/${target.athleteId}`,
      { headers: athleteData.headers },
    )
    expect(missing.status()).toBe(404)
  }

  const afterResponse = await request.get(listingUrl(), {
    headers: athleteData.headers,
  })
  expect(afterResponse.ok()).toBeTruthy()
  const after = await afterResponse.json()
  expect(after.count).toBe(before.count)

  const nimaAfterResponse = await request.get(
    `${API_URL}/api/v1/athletes/${nima.user_id}`,
    { headers: athleteData.headers },
  )
  expect(nimaAfterResponse.ok()).toBeTruthy()
  expect(await nimaAfterResponse.json()).toEqual(nimaBefore)
})

test("managed athlete cleanup runs after a thrown test operation", async ({
  athleteData,
  request,
}) => {
  const email = `${athleteData.marker}-import-${randomUUID()}@example.com`
  athleteData.trackEmail(email)
  const csv = [
    "email,full_name,phone,coach_email,training_goal,height_cm,weight_kg,training_days_count",
    `${email},ورزشکار پاک‌سازی,09120000011,reza@example.com,قدرت,180,80,3`,
  ].join("\n")
  const imported = await request.post(`${API_URL}/api/v1/athletes/import`, {
    headers: athleteData.headers,
    multipart: {
      file: {
        name: "cleanup.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv, "utf8"),
      },
      activation_method: "password",
      initial_password: DEMO_PASSWORD,
    },
  })
  expect(imported.ok()).toBeTruthy()
  expect((await imported.json()).created).toBe(1)

  let deliberateError: unknown
  try {
    throw new Error("deliberate test failure after creating managed data")
  } catch (error) {
    deliberateError = error
  } finally {
    await athleteData.cleanup()
  }
  expect(deliberateError).toBeInstanceOf(Error)

  const afterResponse = await request.get(listingUrl(email), {
    headers: athleteData.headers,
  })
  expect(afterResponse.ok()).toBeTruthy()
  expect((await afterResponse.json()).count).toBe(0)
})

test("managed athlete cleanup refuses unowned email", async ({
  athleteData,
  request,
}) => {
  const nimaResponse = await request.get(listingUrl("nima@example.com"), {
    headers: athleteData.headers,
  })
  expect(nimaResponse.ok()).toBeTruthy()
  const nima = (await nimaResponse.json()).data[0]
  expect(nima).toBeTruthy()
  const beforeResponse = await request.get(
    `${API_URL}/api/v1/athletes/${nima.user_id}`,
    { headers: athleteData.headers },
  )
  expect(beforeResponse.ok()).toBeTruthy()
  const before = await beforeResponse.json()

  expect(() => athleteData.trackEmail("nima@example.com")).toThrow()

  const afterResponse = await request.get(
    `${API_URL}/api/v1/athletes/${nima.user_id}`,
    { headers: athleteData.headers },
  )
  expect(afterResponse.ok()).toBeTruthy()
  expect(await afterResponse.json()).toEqual(before)
})
