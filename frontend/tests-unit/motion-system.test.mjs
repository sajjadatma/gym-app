import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import path from "node:path"
import test from "node:test"

const src = path.resolve(import.meta.dirname, "../src")

test("Motion AI Kit and M3 motion tokens are centralized with standard and expressive families", async () => {
  const css = await readFile(path.join(src, "motion.css"), "utf8")
  const expected = [
    ["--m3-motion-duration-short-1", "50ms"],
    ["--m3-motion-duration-short-2", "100ms"],
    ["--m3-motion-duration-short-3", "150ms"],
    ["--m3-motion-duration-short-4", "200ms"],
  ]

  for (const [token, value] of expected) {
    assert.match(css, new RegExp(`${token}:\\s*${value}`))
  }
  assert.ok(
    css.includes(
      "--m3-motion-standard-effects-fast: var(--m3-motion-duration-short-3)",
    ),
  )
  assert.ok(
    css.includes(
      "--m3-motion-standard-effects-default: var(--m3-motion-duration-short-4)",
    ),
  )
  assert.ok(css.includes("--m3-motion-expressive-spatial-fast:"))
  assert.ok(css.includes("--m3-motion-expressive-spatial-default:"))
  assert.match(
    css,
    /--m3-motion-standard-easing:\s*cubic-bezier\(0\.2,\s*0,\s*0,\s*1\)/,
  )
  assert.match(
    css,
    /--m3-motion-standard-easing-enter:\s*cubic-bezier\(0,\s*0,\s*0,\s*1\)/,
  )
  assert.match(
    css,
    /--m3-motion-standard-easing-exit:\s*cubic-bezier\(0\.3,\s*0,\s*1,\s*1\)/,
  )
  assert.match(
    css,
    /--m3-motion-expressive-easing-spatial-fast:\s*cubic-bezier\(\s*0\.42,\s*1\.67,\s*0\.21,\s*0\.9\s*\)/,
  )
  assert.match(css, /prefers-reduced-motion:\s*reduce/)
})

test("component motion declarations use shared tokens instead of local timings", async () => {
  const css = await readFile(path.join(src, "index.css"), "utf8")
  const declarations = css.match(/(?:transition|animation):[^;]+;/g) ?? []
  const untokenized = declarations.filter(
    (value) =>
      !value.includes("var(--m3-motion-") &&
      !value.trim().startsWith("animation: none"),
  )

  assert.deepEqual(untokenized, [])
})

test("reduced motion is scoped to ASCORA surfaces and does not imply completed progress", async () => {
  const css = await readFile(path.join(src, "motion.css"), "utf8")
  const reducedMotion = css.split("@media (prefers-reduced-motion: reduce)")[1]

  assert.ok(reducedMotion.includes(".m3-app-shell"))
  assert.ok(reducedMotion.includes(".m3-scrim"))
  assert.ok(reducedMotion.includes(".m3-linear-progress span"))
  assert.doesNotMatch(reducedMotion, /html:root\s*\*/)
  assert.doesNotMatch(
    reducedMotion,
    /\.m3-linear-progress span\s*\{[^}]*width:\s*100%/s,
  )
})

test("motion token stylesheet is imported by the application", async () => {
  const main = await readFile(path.join(src, "main.tsx"), "utf8")
  const motionImport = main.indexOf('import "./motion.css"')
  assert.notEqual(motionImport, -1)
})
