import { defineConfig, devices } from "@playwright/test"
import "dotenv/config"

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173"

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "blob" : "html",
  use: {
    baseURL,
    trace: "on-first-retry",
    locale: "fa-IR",
  },
  projects: [
    { name: "admin-setup", testMatch: /admin\.setup\.ts/ },
    { name: "athlete-setup", testMatch: /athlete\.setup\.ts/ },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/admin.json",
      },
      dependencies: ["admin-setup"],
      testIgnore: [/athlete\.spec\.ts/, /superuser-context\.spec\.ts/],
    },
    {
      name: "superuser",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /superuser-context\.spec\.ts/,
    },
    {
      name: "responsive",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /responsive-hardening\.spec\.ts/,
    },
    {
      name: "mobile-admin",
      use: {
        ...devices["Pixel 5"],
        storageState: "playwright/.auth/admin.json",
      },
      dependencies: ["admin-setup"],
      testMatch: /athlete-(archive|import)\.spec\.ts/,
    },
    {
      name: "mobile",
      use: {
        ...devices["Pixel 5"],
        storageState: "playwright/.auth/athlete.json",
      },
      dependencies: ["athlete-setup"],
      testMatch: /athlete\.spec\.ts/,
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "bun run dev --host localhost --port 5173",
        url: baseURL,
        reuseExistingServer: true,
      },
})
