# اجرای محلی dev و stage — ۲۰ آبان ۱۴۰۵

کد در worktree برنچ `codex/finance-sandbox-v2` اجرا شد:
`/Users/sajad/.local/share/opencode/worktree/886215/finance-sandbox-v2`

| محیط | رابط کاربری | API | دیتابیس | revision |
|---|---|---|---|---|
| dev | http://localhost:5173 | http://localhost:8000 | gym_dev | c3f4a5b6d7e8 |
| stage | http://localhost:5174 | http://localhost:8001 | gym_stage | c3f4a5b6d7e8 |

هر دو محیط با `npm run dev` و `npm run stage` فعال‌اند. قبل از migration از هر دو دیتابیس بکاپ گرفته شد. bootstrap بدون reset انجام شد و seed مالی به‌صورت idempotent اجرا شد. هر دیتابیس پس از seed یک sale، یک payment و یک قرارداد فعال پلتفرم دارد.

## اعتبارسنجی

- ورود از مرورگر به هر دو محیط در یک browser context: PASS.
- حفظ هویت مستقل هر محیط بعد از ورود به محیط دیگر: PASS.
- نمایش صفحه فروش و پاسخ ۲۰۰ پیش‌نمایش با مبلغ فارسی در هر دو محیط: PASS.
- ارسال صحیح CSRF و وجود چهار کوکی مجزای ورود/CSRF: PASS.
- ورود مدیر دموی باشگاه `ali@example.com` با اطلاعات ورود مستندشده در راهنمای محلی در هر دو محیط: PASS.
- frontend lint: ۱۶۷ فایل، بدون خطا؛ TypeScript: بدون خطا.
- بررسی قرارداد تنظیمات محیط‌ها: PASS.

در smoke test فروش جدیدی ثبت نشد؛ فقط پیش‌نمایش محاسبه شد. این بررسی برای اجرای دو محیط است و جایگزین گزارش رگرسیون کامل قبلی نیست.

## تغییرات لازم برای اجرای هم‌زمان

فرانت‌اند نام کوکی CSRF را از `VITE_CSRF_COOKIE_NAME` می‌خواند و launcher آن را از `CSRF_COOKIE_NAME` محیط تأمین می‌کند. مثال تنظیمات، نام کوکی ورود و CSRF مجزا برای dev و stage دارد. کوکی‌های localhost بین پورت‌ها مشترک‌اند؛ این تغییر از تداخل ورود دو محیط جلوگیری می‌کند.

تنظیمات خصوصی هر محیط در فایل git-ignored `.env.dev` و `.env.stage` همان worktree است. نام حساب superuser در dev برابر `development-finance-admin@example.com` و در stage برابر `staging-finance-admin@example.com` است؛ رمز هرکدام در فایل محیط مربوطه نگهداری می‌شود.

به‌علت در دسترس نبودن دریافت وابستگی build از PyPI، runtime از کش محلی uv آماده شد. `UV_NO_SYNC=true` در فایل‌های خصوصی محیط، اجرای مجدد را بدون نیاز به دریافت بسته ممکن می‌کند. برای تغییر وابستگی‌ها باید sync متناسب انجام شود.

بکاپ‌ها در مسیر زیر همان worktree قرار دارند:
`backend/uploads/local-environment-backups/2026-11-11/`

لاگ‌ها، تصویر هر محیط و نتیجه ساختاریافته smoke test:
`/private/tmp/ascora-dev-stage-20261111/`
