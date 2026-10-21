# Local testing and accepted MVP1 walkthroughs

Everything here is **local-only**. Demo credentials are deliberately fake and must never be reused outside this project.

## Running services

```sh
brew services start postgresql@17   # if not already running
brew services start mailpit
cd backend && uv run fastapi dev --host 127.0.0.1 --port 8000
cd frontend && bun run dev --host localhost --port 5173
```

- App: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Mailpit: <http://localhost:8025>
- Private uploads: `backend/uploads/body-analysis/` (Git-ignored)

## Demo accounts

Seed with:

```sh
cd backend
uv run python scripts/seed_demo.py
```

The seed is idempotent. Shared demo password: `DemoPass123!` (fake, local only).

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

The **real global Super Admin** is `sajjadnaserizadeh@gmail.com` (`Sajjad Naseri`). Its password is supplied only through the Git-ignored local `.env` (`FIRST_SUPERUSER_PASSWORD`). Do not add it to this document, tests or fixtures.

Verify its login without printing the secret:

```sh
cd backend
uv run python scripts/verify_superadmin_login.py
```

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

### 5. Program lifecycle

1. As an admin/coach, create a draft for an athlete and add days/exercises/sets.
2. Saving preserves drafts. Publishing archives the previously active version and activates the new one.
3. Active/archived versions are read-only; **ساخت نسخه جدید** creates an editable draft based on them.
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
cd backend
CONFIRM_RESET_GYM_APP=YES SEED_DEMO_DATA=YES bash scripts/reset_dev_db.sh
```

The script refuses to run without confirmation and only resets the database named exactly `gym_app`; it also clears the local body-analysis upload directory so the reset is predictable. It never touches `gym_app_test`, unknown databases or production data.

## Known limits (approved MVP1 scope)

- Local development and manual acceptance only; no public hosting.
- PDF is produced through the browser's print-to-PDF dialog, not a server-side PDF renderer.
- Mailpit is the only email transport; no real SMTP/email provider.
- Body-analysis files are local; no cloud object storage or media processing.
- No attendance, actual workout logging, progress analytics, chat, nutrition, payments, AI generation or native apps.
