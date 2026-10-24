import { createHash } from "node:crypto"
import { readdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(scriptDir, "..")
const defaultTemplate = path.join(frontendDir, "public", "sw.js")
const defaultOutput = path.resolve(frontendDir, "../backend/app/frontend")

/**
 * Write the production service worker with a build-scoped cache name.
 *
 * @param {string} outputDir Vite output directory.
 * @param {string} [workerTemplatePath] Worker template containing the build token.
 * @returns {Promise<string>} The 16-character build id.
 */
export async function buildServiceWorker(
  outputDir,
  workerTemplatePath = defaultTemplate,
) {
  const indexPath = path.join(outputDir, "index.html")
  const assetsDir = path.join(outputDir, "assets")
  let template
  let index
  let assets
  try {
    ;[template, index, assets] = await Promise.all([
      readFile(workerTemplatePath, "utf8"),
      readFile(indexPath, "utf8"),
      readdir(assetsDir),
    ])
  } catch (error) {
    throw new Error(
      `Cannot build service worker; missing build input: ${error.message}`,
      { cause: error },
    )
  }

  const assetNames = assets.sort().map((name) => `assets/${name}`)
  const hash = createHash("sha256")
  hash.update(template)
  hash.update("\0")
  hash.update(index)
  for (const name of assetNames) {
    hash.update("\0")
    hash.update(name)
  }
  const buildId = hash.digest("hex").slice(0, 16)
  const output = template.split("__FORMYAR_BUILD_ID__").join(buildId)
  if (output.includes("__FORMYAR_BUILD_ID__")) {
    throw new Error("Service worker template still contains the build token")
  }
  await writeFile(path.join(outputDir, "sw.js"), output)
  return buildId
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  const outputDir = process.argv[2]
    ? path.resolve(process.argv[2])
    : defaultOutput
  try {
    const buildId = await buildServiceWorker(outputDir)
    console.log(`[pwa] service worker cache build ${buildId}`)
  } catch (error) {
    console.error(`[pwa] ${error.message}`)
    process.exitCode = 1
  }
}
