#!/usr/bin/env node
/**
 * Starts the backend (FastAPI/uv) and frontend (Vite/bun) dev servers
 * together with labelled output. `npm run dev` from the repo root.
 *
 * Exit codes follow the first child that exits, and Ctrl+C stops both.
 */
import { spawn, spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

const label = (name, chunk) =>
  chunk
    .toString()
    .split(/(?<=\n)|(?=\n)/)
    .map((line) => (/\n/.test(line) ? line : `[${name}] ${line}`))
    .join("")

function start(name, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["inherit", "pipe", "pipe"],
  })
  child.stdout.on("data", (chunk) => process.stdout.write(label(name, chunk)))
  child.stderr.on("data", (chunk) => process.stderr.write(label(name, chunk)))
  child.on("error", (error) => {
    if (error.code === "ENOENT") {
      console.error(
        `\n[${name}] Required command "${command}" was not found in PATH. Install ${command} and retry.`,
      )
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

let shuttingDown = false
function shutdown() {
  if (shuttingDown) return
  shuttingDown = true
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill("SIGTERM")
  }
}

const children = []
process.on("SIGINT", () => {
  console.log("\nStopping dev servers…")
  shutdown()
})
process.on("SIGTERM", shutdown)

// Postgres must be reachable before FastAPI boots; start the Homebrew
// service best-effort on macOS so a fresh shell just works.
if (process.platform === "darwin") {
  const ready = spawnSync("pg_isready", ["-h", "localhost", "-p", "5432"], {
    encoding: "utf8",
  })
  if (ready.status !== 0) {
    console.log("[postgres] not reachable — trying brew services start…")
    const started = spawnSync(
      "brew",
      ["services", "start", "postgresql@17"],
      { encoding: "utf8" },
    )
    console.log(started.stdout?.trim() || started.stderr?.trim() || "done")
  }
}

console.log("[setup] applying database migrations…")
const migrate = spawnSync(
  "uv",
  ["run", "alembic", "upgrade", "head"],
  { cwd: path.join(rootDir, "backend"), encoding: "utf8" },
)
if (migrate.status !== 0) {
  console.error(
    `[setup] alembic upgrade failed:\n${migrate.stderr || migrate.stdout || "no output"}`,
  )
  process.exit(1)
}
console.log("[setup] database schema up to date.")

const backendDir = path.join(rootDir, "backend")
const frontendDir = path.join(rootDir, "frontend")

children.push(
  start("backend", "uv", ["run", "fastapi", "dev", "--host", "127.0.0.1", "--port", "8000"], backendDir),
)

if (existsSync(path.join(frontendDir, "node_modules"))) {
  children.push(
    start("frontend", "bun", ["run", "dev", "--host", "localhost", "--port", "5173"], frontendDir),
  )
} else {
  console.log("[setup] installing frontend dependencies (bun)…")
  spawnSync("bun", ["install"], { cwd: frontendDir, stdio: "inherit" })
  children.push(
    start("frontend", "bun", ["run", "dev", "--host", "localhost", "--port", "5173"], frontendDir),
  )
}

console.log("\n[dev] backend → http://127.0.0.1:8000  frontend → http://localhost:5173\n")
