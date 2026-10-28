import assert from "node:assert/strict"
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import test from "node:test"

import { buildServiceWorker } from "../scripts/build-service-worker.mjs"

const TOKEN = "__FORMYAR_BUILD_ID__"

async function fixture({
  template = `const CACHE = "formyar-shell-${TOKEN}"\n`,
  index = "<html>shell</html>\n",
  assets = ["a.js", "b.css"],
} = {}) {
  const root = await mkdtemp(path.join(tmpdir(), "formyar-sw-"))
  const output = path.join(root, "output")
  const templatePath = path.join(root, "sw-template.js")
  await mkdir(path.join(output, "assets"), { recursive: true })
  await writeFile(templatePath, template)
  await writeFile(path.join(output, "index.html"), index)
  for (const asset of assets) {
    await writeFile(path.join(output, "assets", asset), `/* ${asset} */`)
  }
  return { root, output, templatePath, template }
}

test("build id changes with shell, assets or worker but is stable for identical builds", async () => {
  const first = await fixture()
  try {
    const id1 = await buildServiceWorker(first.output, first.templatePath)
    const id2 = await buildServiceWorker(first.output, first.templatePath)
    assert.equal(id1, id2)
    assert.match(id1, /^[a-f0-9]{16}$/)
    const output = await readFile(path.join(first.output, "sw.js"), "utf8")
    assert.ok(output.includes(`formyar-shell-${id1}`))
    assert.equal(output.includes(TOKEN), false)

    const shell = await fixture({ index: "<html>new shell</html>\n" })
    assert.notEqual(
      await buildServiceWorker(shell.output, shell.templatePath),
      id1,
    )
    await rm(shell.root, { recursive: true, force: true })

    const assets = await fixture({ assets: ["a.js", "c.js"] })
    assert.notEqual(
      await buildServiceWorker(assets.output, assets.templatePath),
      id1,
    )
    await rm(assets.root, { recursive: true, force: true })

    const worker = await fixture({
      template: `const CACHE = "formyar-shell-${TOKEN}-v2"\n`,
    })
    assert.notEqual(
      await buildServiceWorker(worker.output, worker.templatePath),
      id1,
    )
    await rm(worker.root, { recursive: true, force: true })
  } finally {
    await rm(first.root, { recursive: true, force: true })
  }
})

test("build injects every emitted asset into the precache list", async () => {
  const fixtureRoot = await fixture({
    template: `const PRECACHE = ["/", __FORMYAR_PRECACHE_ASSETS__]\nconst CACHE = "formyar-shell-${TOKEN}"\n`,
    assets: ["index-abc.js", "index-def.css"],
  })
  try {
    await buildServiceWorker(fixtureRoot.output, fixtureRoot.templatePath)
    const output = await readFile(
      path.join(fixtureRoot.output, "sw.js"),
      "utf8",
    )
    assert.ok(output.includes('"/assets/index-abc.js"'))
    assert.ok(output.includes('"/assets/index-def.css"'))
    assert.equal(output.includes("__FORMYAR_PRECACHE_ASSETS__"), false)
  } finally {
    await rm(fixtureRoot.root, { recursive: true, force: true })
  }
})

test("build fails when emitted index is missing", async () => {
  const empty = await mkdtemp(path.join(tmpdir(), "formyar-sw-empty-"))
  try {
    await assert.rejects(
      () => buildServiceWorker(empty),
      /Cannot build service worker/,
    )
  } finally {
    await rm(empty, { recursive: true, force: true })
  }
})
