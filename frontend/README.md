# FormYar frontend

React + TypeScript + Vite frontend for the Gym Management MVP1.

- Persian (`fa-IR`) RTL by default; English test locale and translations are provided to verify direction/format switching.
- Google Material Design 3 tokens and components live in `src/components/M3.tsx` and `src/index.css`.
- Select, searchable ComboBox and DatePicker controls use React Aria for accessible behavior; `@internationalized/date` provides Persian/Gregorian calendar conversion.
- TanStack Router file routes are in `src/routes/`; generated `routeTree.gen.ts` is produced by Vite.
- OpenAPI types/client are generated into `src/client/` with `bun run generate-client` after a backend API change.
- PWA manifest, icons and service worker are in `public/`; the service worker is registered only in production builds.

```sh
bun install
bun run dev --host localhost --port 5173
```

The dev API URL comes from `frontend/.env` (`VITE_API_URL=http://localhost:8000`). Production builds are served by FastAPI at <http://localhost:8000> with deep-link fallback.

See the root [`README.md`](../README.md) and [`docs/local-testing.md`](../docs/local-testing.md) for setup, demo accounts and Playwright verification.

## Form controls

Use `TextField`, `SelectField`, `SearchableSelectField` and `DateField` with a visible `label`; placeholders supplement labels. Labels, validation messages and helper text are associated with the corresponding controls. Set-table inputs have explicit HTML labels and visible column headings.

`DateField` uses [React Aria DatePicker](https://react-aria.adobe.com/DatePicker) and `@internationalized/date`, styled with the existing Material 3 tokens. Persian mode uses the Jalali calendar and English mode uses Gregorian; API values remain Gregorian `YYYY-MM-DD` strings or `null`. Use `minValue`/`maxValue` for ISO date bounds and `maxToday` for birth dates. Empty fields keep their labels visible above the date segments.

Verify keyboard interaction, Jalali leap dates, ISO conversion, mobile overlays and field labels:

```sh
bunx playwright test tests/controls.spec.ts tests/field-labels.spec.ts --project=chromium
```

## Exercise categories

Owners and admins manage categories and custom movements in the exercise library. Coaches have a read-only catalog. Program and template editors filter movement choices by the selected day categories; existing mixed days remain supported. Day category labels appear in the athlete view and print/PDF, using the saved category snapshot. API types are generated from the backend schema; regenerate them after backend schema changes.
