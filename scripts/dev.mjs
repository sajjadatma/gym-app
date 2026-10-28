#!/usr/bin/env node
/**
 * Run a fully isolated local environment.
 *
 *   npm run dev            # development: http://localhost:5173
 *   npm run stage          # staging-like: http://localhost:5174
 *
 * Both use local PostgreSQL databases and local uploads. Remote databases are
 * rejected before migrations or servers start.
 */
import { spawn, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const envArgIndex = process.argv.indexOf("--env")
const envName =
  envArgIndex >= 0 ? process.argv[envArgIndex + 1] : "dev"
if (!["dev", "stage"].includes(envName)) {
  console.error(`[env] unknown environment "${envName}" (expected dev or stage)`)
  process.exit(1)
}

const envFile = path.join(rootDir, `.env.${envName}`)
if (!existsSync(envFile)) {
  console.error(
    `[env] ${path.basename(envFile)} is missing. Copy ${path.basename(envFile)}.example and fill it in.`,
  )
  process.exit(1)
}

function readEnv(file) {
  const values = {}
  for (const raw of readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith("#") || !line.includes("=")) continue
    const index = line.indexOf("=")
    const key = line.slice(0, index).trim()
    let value = line.slice(index + 1).trim()
    if (
      value.length >= 2 &&
      value[0] === value[value.length - 1] &&
      (value[0] === '"' || value[0] === "'")
    ) {
      value = value.slice(1, -1)
    }
    values[key] = value
  }
  return values
}

const values = readEnv(envFile)
const expectedEnvironment = envName === "dev" ? "development" : "staging"
if (values.FASTAPI_ENV !== expectedEnvironment) {
  console.error(
    `[env] ${path.basename(envFile)} must set FASTAPI_ENV=${expectedEnvironment}`,
  )
  process.exit(1)
}

const databaseUrl = values.DATABASE_URL || ""
let databaseHost = ""
try {
  databaseHost = new URL(databaseUrl.replace(/^postgresql\+psycopg:/, "postgresql:")).hostname
} catch {
  console.error("[env] DATABASE_URL is missing or invalid")
  process.exit(1)
}
if (!["localhost", "127.0.0.1", "::1", "db"].includes(databaseHost)) {
  console.error(
    `[env] refusing to run locally against remote database host "${databaseHost}"`,
  )
  process.exit(1)
}

const frontendPort = values.FRONTEND_PORT || (envName === "dev" ? "5173" : "5174")
const backendPort = values.BACKEND_PORT || (envName === "dev" ? "8000" : "8001")
const childEnv = {
  ...process.env,
  ...values,
  ENV_FILE: envFile,
}

console.log(`[env] ${envName} → ${path.basename(envFile)}`)
console.log("[setup] preparing local database and demo data…")
const bootstrap = spawnSync(
  "uv",
  ["run", "--project", "backend", "python", "scripts/bootstrap-local.py", "--env", envName],
  { cwd: rootDir, env: childEnv, stdio: "inherit" },
)
if (bootstrap.status !== 0) {
  console.error("[setup] local database preparation failed")
  process.exit(bootstrap.status ?? 1)
}

const label = (name, chunk) =>
  chunk
    .toString()
    .split(/(?<=\n)|(?=\n)/)
    .map((line) => (/\n/.test(line) ? line : `[${name}] ${line}`))
    .join("")

const children = []
let shuttingDown = false
function shutdown() {
  if (shuttingDown) return
  shuttingDown = true
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill("SIGTERM")
  }
}

function start(name, command, args, cwd, env) {
  const child = spawn(command, args, {
    cwd,
    env: { ...childEnv, ...env, PYTHONUNBUFFERED: "1" },
    stdio: ["inherit", "pipe", "pipe"],
  })
  child.stdout.on("data", (chunk) => process.stdout.write(label(name, chunk)))
  child.stderr.on("data", (chunk) => process.stderr.write(label(name, chunk)))
  child.on("error", (error) => {
    if (error.code === "ENOENT") {
      console.error(`[${name}] command "${command}" was not found in PATH`)
    } else {
      console.error(`[${name}] ${error}`)
    }
    process.exitCode = 1
  })
  child.on("exit", (code, signal) => {
    if (!shuttingDown && (code !== 0 || signal)) {
      console.error(`[${name}] exited with ${code ?? signal ?? "unknown"}`)
      shutdown()
    }
  })
  return child
}

process.on("SIGINT", () => {
  console.log("\nStopping local servers…")
  shutdown()
})
process.on("SIGTERM", shutdown)

const backendCommand =
  envName === "dev"
    ? ["uv", ["run", "fastapi", "dev", "--host", "127.0.0.1", "--port", backendPort]]
    : ["uv", ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", backendPort]]

children.push(
  start("backend", backendCommand[0], backendCommand[1], path.join(rootDir, "backend")),
)

const frontendEnv = {
  VITE_API_URL: values.VITE_API_URL || `http://localhost:${backendPort}`,
  VITE_MAX_UPLOAD_BYTES: values.VITE_MAX_UPLOAD_BYTES || "10485760",
  VITE_MAX_IMPORT_BYTES: values.VITE_MAX_IMPORT_BYTES || "5242880",
}
children.push(
  start(
    "frontend",
    "bun",
    ["run", "dev", "--host", "localhost", "--port", frontendPort, "--strictPort"],
    path.join(rootDir, "frontend"),
    frontendEnv,
  ),
)

console.log(
  `\n[${envName}] frontend → http://localhost:${frontendPort}  backend → http://127.0.0.1:${backendPort}\n`,
)
