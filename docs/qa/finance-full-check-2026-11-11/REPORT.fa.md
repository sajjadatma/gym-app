# آزمون کلی نهایی ASCORA — ۱۱ نوامبر ۲۰۲۶

**تاریخ محلی:** ۲۰ آبان ۱۴۰۵، Asia/Tehran  
**برنچ:** `codex/finance-sandbox-v2`  
**نسخه:** HEAD `0b94e5cb3fd80560766e71d98eeaafee8c64c734` همراه اصلاحات کامیت‌نشدهٔ مالی و combobox.

**نتیجه: تمام کنترل‌های اجراشده پاس شدند؛ شکست یا flake ثبت نشد و این دور باگ جدیدی در سناریوهای آزموده‌شده نشان نداد.**

## نتایج مستقل این اجرا

| بررسی | نتیجه |
|---|---|
| کل backend suite با `TZ=Asia/Tehran` | **۲۱۶ پاس**، صفر شکست؛ ۱۶ هشدار deprecation؛ حدود ۱۲۴ ثانیه |
| مجموعهٔ migration در اجرای جدا با `TZ=UTC` | **۸ پاس**، صفر شکست |
| `alembic check` روی دیتابیس تازهٔ مهاجرت‌شده | **No new upgrade operations detected** |
| Ruff: `check app tests scripts` | پاس |
| Mypy: `app` | پاس، ۴۵ فایل |
| frontend production build، شامل TypeScript و service worker | پاس |
| frontend lint | پاس، ۱۶۷ فایل |
| Node unit tests | **۱۶ پاس**، صفر شکست |
| کل Playwright روی build تولیدی، `--retries=0` | **۱۴۸ پاس، ۱ skip طراحی‌شده، صفر شکست و صفر flaky**؛ حدود ۱۳۷ ثانیه |
| تطبیق نسخهٔ سورس در ابتدا و انتهای اجرا | **۳۲۳ فایل ثابت**؛ تغییر هم‌زمانی مشاهده نشد |

تنها skip، تست بازیابی گروهی ورزشکاران در project `mobile-admin` است؛ این عملیات در طراحی فعلی فقط در جدول دسکتاپ ارائه می‌شود. هیچ تست شکست‌خورده‌ای با retry سبز نشده و در این اجرا تست جدیدی skip نشده است.

## دامنهٔ پوشش

کل تست‌های موجود اجرا شدند، شامل regressionهای مالی قرارداد جاری/تاریخی و legacy، خرید اتمیک و idempotency، تخصیص و بازپرداخت، رقابت هم‌زمان، تسویه، گزارش و CSV، BIGINT و upgrade/downgrade، نقش‌ها و جداسازی باشگاه‌ها.

در مرورگر، تست‌های مدیر سراسری و PWA تولیدی فعال شدند. مسیرهای مدیر باشگاه، مربی و ورزشکار، خرید پلن و درخواست برنامه، ساخت/انتشار برنامه، انتخاب حرکت، فرم‌ها، RTL/LTR، موبایل و responsive، تاریخ‌ها، offline و service worker پوشش داده شدند. هشت تست جدید کلیک/لمس combobox نیز جزو همین اجرای کامل بودند؛ بازشدن با ورودی و فلش، ماوس، touch، کیبورد، Escape، بازشدن مجدد و dismissal را بررسی کردند.

## روش و ایزوله‌سازی

از آخرین وضعیت واقعی worktree، شامل فایل‌های tracked و فایل‌های جدید backend/frontend، یک کپی مستقل در `/private/tmp/gym-final-qa-20261111` ساخته شد. hash تمام ۳۲۳ فایل سورس در [manifest](evidence/source-manifest.json) ثبت و پایان اجرا دوباره با worktree مقایسه شد؛ [نتیجهٔ تطبیق](evidence/source-consistency.json) بدون اختلاف است.

دیتابیس‌های این اجرا همگی تازه و محلی بودند:

- `gym_final_qa_backend_20261111_test`: backend suite و fixtureهای پاک‌کننده.
- `gym_final_qa_ui_20261111_test`: داده‌های demo و مرورگر.
- `gym_final_qa_migration_20261111_test`: دیتابیس موقت migration؛ نام ثابت تست فقط در کپی QA تغییر کرد تا با کارهای دیگر تداخل نکند.

backend مربوط به مرورگر روی `127.0.0.1:8051` بود و همان backend، build تولیدی را سرو می‌کرد. build با API هم‌مبدأ ساخته شد؛ متغیرهای API مرورگر و `FRONTEND_HOST` به همان origin اشاره داشتند. تمام حساب‌ها و پرداخت‌ها ساختگی بودند و SMTP فقط به Mailpit محلی وصل بود.

در این دور هیچ source محصولی تغییر نکرد و دیتابیس اصلی sandbox/dev/stage/production migrate یا reset نشد. این دور نیز تاریخچهٔ migration اصلی را بازنویسی یا مجدداً ممیزی نکرد؛ شواهد مقایسهٔ محتوای بکاپ در گزارش مستقل اصلاح combobox قرار دارند.

## دستورهای اصلی

```sh
# backend؛ ENV_FILE فقط دیتابیس‌های تازهٔ این اجرا را مشخص می‌کند
TZ=Asia/Tehran ENV_FILE=/private/tmp/gym-final-qa-20261111/.env.qa PYTHONPATH=. python -m pytest -q --tb=short
TZ=UTC ENV_FILE=/private/tmp/gym-final-qa-20261111/.env.qa PYTHONPATH=. python -m pytest tests/test_migrations.py -q --tb=short
ENV_FILE=/private/tmp/gym-final-qa-20261111/.env.qa-ui python -m alembic check
ruff check app tests scripts
mypy app

# frontend
VITE_API_URL= bun run build
bun run lint:check
node --test tests-unit/*.test.mjs
VITE_API_URL=http://127.0.0.1:8051 PLAYWRIGHT_API_URL=http://127.0.0.1:8051 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8051 PLAYWRIGHT_SUPERUSER_EMAIL=finance-sandbox-admin@example.com PLAYWRIGHT_SUPERUSER_PASSWORD=SandboxAdmin123! PWA_PROD=1 bunx playwright test --retries=0 --reporter=line,json
```

Python و ابزارهای backend از محیط آمادهٔ dev پروژه استفاده کردند؛ مقدارهای بالا credentialهای fake آزمایشی هستند. اجرای مجدد pytest باید فقط روی دیتابیس disposable انجام شود، چون fixtureها جدول‌های دیتابیس تست را پاک می‌کنند.

## شواهد

- [کل بک‌اند](evidence/backend-full.log)
- [migration در UTC](evidence/migrations-utc.log)، [schema check](evidence/alembic-check.log)
- [Ruff](evidence/ruff.log)، [Mypy](evidence/mypy.log)
- [بیلد](evidence/build.log)، [lint](evidence/lint.log)، [Node](evidence/node-tests.log)
- [کل مرورگر، لاگ](evidence/playwright-full.log)، [خروجی ساختاریافته](evidence/playwright-full.json)

این نتیجه تأیید اجرای موفق مجموعهٔ فعلی روی Chromium و محیط محلیِ مستقل است. تست دستگاه فیزیکی، مرورگرهای دیگر، بار تولید و درگاه واقعی در این اجرا انجام نشده است. هیچ commit، merge، push یا deploy انجام نشد.
