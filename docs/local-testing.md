# Local testing and accepted MVP1 walkthroughs

Everything here is **local-only**. Demo credentials are deliberately fake and must never be reused outside this project.

## Running services

Development and staging are isolated local environments; neither can connect
to the production Neon database.

```sh
npm run dev     # development: 5173 + 8000
npm run stage   # staging:     5174 + 8001
```

- Development: <http://localhost:5173> · API <http://127.0.0.1:8000/docs>
- Staging: <http://localhost:5174> · API <http://127.0.0.1:8001/docs>
- Private uploads: `backend/uploads/development-body-analysis/` and
  `backend/uploads/staging-body-analysis/` (Git-ignored)

Each command creates its database if needed, applies migrations, bootstraps
the local superuser and seeds demo data. See
[`environments.md`](environments.md) for the full environment contract.

## Demo accounts

Demo data is seeded automatically by `npm run dev` / `npm run stage`. The seed
is idempotent. Shared demo password: `DemoPass123!` (fake, local only).

| Account | Password | Access |
|---|---|---|
| `ali@example.com` | `DemoPass123!` | Owner + Gym Admin + Coach of **باشگاه آرام**, Coach of **باشگاه پویا**, Gym Admin of **باشگاه توان** |
| `bob@example.com` | `DemoPass123!` | Owner of **باشگاه پویا** |
| `omid@example.com` | `DemoPass123!` | Owner of **باشگاه توان** |
| `reza@example.com` | `DemoPass123!` | Coach in **باشگاه آرام** |
| `sara@example.com` | `DemoPass123!` | Coach in **باشگاه پویا** |
| `nima@example.com` | `DemoPass123!` | Athlete in **باشگاه آرام**, coach: Reza, active + archived programs |
| `mina@example.com` | `DemoPass123!` | Athlete in **باشگاه پویا**, coach: Sara |
| `multi.athlete@example.com` | `DemoPass123!` | Athlete in both **آرام** and **پویا**, independent profiles/programs and coach assignments |

The local superusers are `development-admin@example.com` in development and
`staging-admin@example.com` in staging. Their passwords are stored only in the
Git-ignored `.env.dev` / `.env.stage` files. Production credentials are never
used locally.

## Walkthroughs

### 1. Multi-gym identity, roles and isolation

1. Sign in as `ali@example.com`.
2. Use the gym chip in the top bar to switch between **باشگاه آرام**, **باشگاه پویا**, and **باشگاه توان**.
3. Ali is admin in آرام and توان, but coach in پویا. In coach mode, the nav shows only dashboard, athletes, exercises and templates; in admin mode it also shows team and gyms.
4. Athletes and programs change with the active gym. A program created in آرام is not visible in پویا or توان.
5. Login as `reza@example.com`: only athletes assigned to Reza in the active gym are listed. Mina (باشگاه پویا) is not accessible in آرام.

### 2. Coach reassignment history

1. As Ali (admin mode, باشگاه آرام), open **ورزشکاران → نیما ورزشکار**.
2. Choose **تغییر مربی**. The confirmation explains that the previous coach loses access.
3. Select **علی** (or another coach) and confirm. The assignment history now has two rows.
4. Log in as Reza in a separate browser profile: Nima is no longer in Reza's list and direct access returns an error.
5. The new coach can open Nima's active and archived versions and create a new version from them.
6. Reassign Nima back to Reza afterwards to preserve the demo state.

### 3. Athlete experience, privacy and print/PDF

1. Sign in as `nima@example.com`.
2. **برنامه من** shows the active program and archive. Open it and select days; each set can have different reps, weight, intensity, rest, duration and note.
3. The private note `PRIVATE-DEMO-NOTE` is never visible in the athlete UI, athlete program view or print view.
4. Upload a PDF/JPEG/PNG body-analysis file on **پرونده من** (max 10 MB). Another athlete cannot download it.
5. Open **چاپ/PDF**. The A4 print view contains athlete, gym, coach, version, days, exercises, sets and Persian/Jalali dates. Use the browser print dialog and choose **Save as PDF**.

### 4. Templates and exercise library

1. As Ali/Reza in **باشگاه آرام**, open **قالب‌ها**.
2. The seeded template is reusable; applying it to an athlete creates an independent **draft** version.
3. Edit the template and re-apply it: previously created copies remain unchanged.
4. Open **کتابخانه حرکات**. The 54 seeded global exercises plus the custom `پرس سینه با کش` exercise are listed. The custom exercise is scoped to باشگاه آرام.

### Exercise categories and catalog permissions

1. As Ali in admin mode in **باشگاه آرام**, open **کتابخانه حرکات → افزودن دسته‌بندی** and create a category. The category belongs to this gym; the global categories remain available.
2. Choose **افزودن حرکت اختصاصی**, select the category, and save a movement. Existing custom movements can be edited by the gym owner/admin.
3. Sign in as Reza: the library is readable and filterable, but category/movement creation and editing controls are absent. Direct write requests are also rejected with HTTP 403.
4. In a program or template, add a day and choose **دسته‌بندی روز**. Its movement selectors only offer that category. A day using the default title adopts the category name, e.g. **روز ۱ — بازو** in the athlete view and print output.
5. Changing a day to a conflicting category shows an error without deleting its movements. Mixed days remain available, including existing multi-group days.
6. Save/reload, publish, create a new draft, or apply a template: day categories persist. Published category/movement names are snapshots and do not change when the catalog changes.

### 5. Program lifecycle

1. As an admin/coach, create a draft for an athlete and add days/exercises/sets.
2. Saving preserves drafts. Publishing archives the previously active version and activates the new one.
3. Active programs can be edited in place; archived versions are read-only; **ساخت نسخه جدید** creates an editable draft based on them.
4. Each athlete/gym has at most one active program; old published content and coach identity remain in history.
5. A new coach after reassignment can open old programs and derive new versions without modifying history.

### 6. Invitation and password flows

1. As an admin, add a coach or athlete with **ارسال دعوت‌نامه**.
2. Open Mailpit at <http://localhost:8025>. The Persian RTL invitation contains the activation link; no raw password is sent.
3. Open the link, choose a password and confirm. Sign in with the new account.
4. The alternative **رمز عبور اولیه** method shows the initial password once; the account must change it at first login before any other API is allowed.
5. Forgot-password links also arrive in Mailpit and use a purpose-bound, expiring token.

### 7. Ownership transfer

1. As Ali, open **باشگاه‌ها → باشگاه آرام → انتقال مالکیت**.
2. A non-owner gym admin cannot transfer ownership; an owner or global Super Admin can.
3. Transfer to an existing member (for example Reza). The previous owner loses implicit admin rights; independent roles remain unchanged.
4. The new owner (or the Super Admin) can transfer it back.

### 8. PWA and locale

1. Build the production frontend (`cd frontend && bun run build`) and open <http://localhost:8000> (FastAPI serves the built app).
2. Chrome should offer install; the manifest, 192/512 icons and service worker are served locally.
3. In the account menu, switch language to English: layout direction becomes LTR, labels switch, and numbers/dates use locale formatting. Switch back to فارسی for RTL/Jalali.
4. Phone-sized emulation in browser devtools is sufficient; no physical device is required.

## Automated verification

```sh
cd backend && uv run pytest -q
cd frontend && bunx playwright test
cd frontend && bun run build
PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test
```

The backend tests use `gym_app_test` and fake credentials. Playwright uses demo accounts only. See [`implementation-progress.md`](implementation-progress.md) for the latest recorded results.

## Reset

```sh
npm run db:reset:dev -- --yes
npm run db:reset:stage -- --yes
```

The script refuses non-local hosts and only resets names ending `_dev` or
`_stage`. It never touches `gym_test`, unknown databases or production Neon
data.

## Known limits (approved MVP1 scope)

- Development and staging are local; production runs on Vercel with Neon.
- PDF is produced through the browser's print-to-PDF dialog, not a server-side PDF renderer.
- Local email uses Mailpit; production SMTP is configured separately.
- Local body-analysis files use disk; production uses Neon Object Storage.
- No attendance, actual workout logging, progress analytics, chat, nutrition, payments, AI generation or native apps.
