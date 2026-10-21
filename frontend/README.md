# FormYar frontend

React + TypeScript + Vite frontend for the Gym Management MVP1.

- Persian (`fa-IR`) RTL by default; English test locale and translations are provided to verify direction/format switching.
- Google Material Design 3 tokens and components live in `src/components/M3.tsx` and `src/index.css`.
- TanStack Router file routes are in `src/routes/`; generated `routeTree.gen.ts` is produced by Vite.
- OpenAPI types/client are generated into `src/client/` with `bun run generate-client` after a backend API change.
- PWA manifest, icons and service worker are in `public/`; the service worker is registered only in production builds.

```sh
bun install
bun run dev --host localhost --port 5173
```

The dev API URL comes from `frontend/.env` (`VITE_API_URL=http://localhost:8000`). Production builds are served by FastAPI at <http://localhost:8000> with deep-link fallback.

See the root [`README.md`](../README.md) and [`docs/local-testing.md`](../docs/local-testing.md) for setup, demo accounts and Playwright verification.
