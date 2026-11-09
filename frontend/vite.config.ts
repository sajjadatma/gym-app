import { realpathSync } from "node:fs"
import path from "node:path"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const apiTarget = env.VITE_API_URL || "http://localhost:8000"
  const nodeModulesReal = realpathSync(
    path.resolve(import.meta.dirname, "node_modules"),
  )
  const dependencyRoot = path.resolve(nodeModulesReal, "..")
  return {
    build: {
      outDir: "../backend/app/frontend",
      emptyOutDir: true,
    },
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      fs: {
        allow: [import.meta.dirname, nodeModulesReal, dependencyRoot],
      },
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
      react(),
    ],
  }
})
