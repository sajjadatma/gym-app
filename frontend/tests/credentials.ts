export const DEMO_PASSWORD = "DemoPass123!"
export const ADMIN_EMAIL = "ali@example.com"
export const ATHLETE_EMAIL = "nima@example.com"
export const API_URL =
  process.env.VITE_API_URL ??
  process.env.PLAYWRIGHT_API_URL ??
  "http://localhost:8000"
