> **الحاقیهٔ ۱۱ نوامبر ۲۰۲۶:** مشکل کلیک combobox در خود محصول اصلاح و کل مرورگر ۱۴۸/۱۴۹ پاس (یک skip طراحی‌شده) شد. محتوای مشترک هر ۱۵ جدول مالی با بکاپ تطبیق داده شد؛ revision بکاپ و دیتابیس فعلی متفاوت است، بنابراین ادعای مطلق «هیچ migration روی اصلی انجام نشده» برای کل بازه قابل استناد نیست. [گزارش اصلاح و تصحیح شواهد](../combobox-product-fix-2026-11-11/REPORT.fa.md). متن زیر گزارش تاریخی دور دوم است.

# اعتبارسنجی پس از اصلاح دور دوم — ASCORA Finance Sandbox V2

**تاریخ:** ۱۰ نوامبر ۲۰۲۶، ۱۹ آبان ۱۴۰۵  
**برنچ:** `codex/finance-sandbox-v2`  
**HEAD:** `0b94e5cb3fd80560766e71d98eeaafee8c64c734` به‌همراه تغییرات کامیت‌نشده  
**وضعیت انتشار:** تأیید نهایی انتشار نیست. هیچ push، merge، deploy یا درگاه واقعی انجام نشده است.

## ۱. خلاصهٔ اجرایی

| مورد | وضعیت | تغییر اصلی | شاهد |
|---|---|---|---|
| **FIN-R01** — قرارداد آرشیوشدهٔ قدیمی | **Fixed** | resolverهای پلتفرم و مربی فقط archived دارای `archived_at` معتبر یا `effective_to` صریح را تاریخی می‌دانند؛ قرارداد قدیمی بدون timestamp برای امروز معتبر نیست. | ۳ تست backend + تست migration |
| **FIN-R02** — خرید غیراتمی | **Fixed** | خرید پلن در یک تراکنش واحد با `_lock_finance_gym`، `commit=False` در helperها و یک commit نهایی؛ خطا کل خرید را rollback می‌کند. | ۳ تست backend شامل race سرویس، race HTTP و شکست تزریقی + retry |
| **FIN-R03** — گردشدن قیمت پلن | **Fixed** | `irrToTomanInput` برای مقدار قابل ویرایش اضافه شد؛ نمایش `irrToToman` دقیق شد (۱۰۵ ریال = ۱۰٫۵ تومان). | ۲ تست Playwright شامل باقی‌مانده‌های ۰ تا ۹ و ساخت/ویرایش ۱۰٫۵ |
| **UI-R01** — combobox حرکت در build تولیدی | **Fixed در سطح harness** | ریشه: `click()` + `fill()` تک‌رویدادی با بازشدن popover مبتنی بر focus در React Aria مسابقه می‌دهد. تست‌ها با `ArrowDown` و تایپ واقعی (`pressSequentially`) اصلاح شدند؛ کامپوننت محصول تغییر نکرد. | ۷ اجرای هدفمند بدون retry + کل Playwright |
| **QA-R01** — race استخراج gymId | **Fixed** | انتظار صریح `toHaveURL(/\/gyms\/[^/]+$/)` پیش از خواندن `pathname` در مسیرهای مالی. | ۹ تست مالی Playwright |
| **QA-R02** — assertion motion وابسته به واحد | **Fixed** | نرمال‌سازی `ms`/`s` با `durationMs` و حفظ assertionهای easing و reduced-motion. | ۲ project بدون retry |
| **QA-R03** — ناپایداری انتخاب مربی | **Fixed** | انتظار visible شدن option، کلیک واقعی و assertion مقدار combobox؛ رویکرد `focus()+Enter` که انتخاب را ثبت نمی‌کرد حذف شد. | تست هدفمند + کل suite سوپرادمین |

## ۲. محیط و ایزوله‌سازی

- محیط اصلی کاربر روی `http://localhost:5180` (UI) و `http://127.0.0.1:8010` (API) دست‌نخورده باقی ماند.
- دیتابیس اصلی `gym_finance_sandbox_v2` روی revision `c3f4a5b6d7e8` است. بکاپ پیش از migration در `/private/var/folders/pk/nrxwwmj91jxc9_pgv18y6mcr0000gn/T/opencode/gym_finance_sandbox_v2_before_finance_fix.dump` نگه داشته شده است.
- هیچ دیتابیس dev/stage/sandbox/production/Neon reset یا migrate نشد.
- دیتابیس‌های disposable دارای پسوند `_test`:
  - `gym_finance_fix_20261110_test` — `TEST_DATABASE_URL` تست‌های backend.
  - `gym_app_migration_test` — مخصوص `tests/test_migrations.py` (هر اجرا از نو ساخته می‌شود).
  - `gym_finance_alembic_final_20261110_test` — `alembic check`.
  - `gym_finance_ui_final_20261110_test` — بررسی‌های هدفمند مرورگر.
  - `gym_finance_full_ui_20261110_test` — دو اجرای کامل Playwright؛ از نو ساخته و seed شد.
- build تولیدی با `VITE_API_URL=` (same-origin) ساخته و روی همان origin سرو شد؛ برای suite کامل، backend روی `127.0.0.1:8022` و UI سروشده توسط همان backend استفاده شد. هیچ درگاه واقعی، ایمیل واقعی یا پرداخت واقعی درگیر نبود.
- حساب‌ها و رمزها همان credentialهای fake محلی پروژه هستند.

## ۳. جزئیات موارد

### FIN-R01 — قرارداد آرشیوشدهٔ قدیمی نباید برای امروز معتبر باشد

**ریشه:** resolver قبلی هر قرارداد `ARCHIVED` را تا وقتی `archived_at > on_date` بود معتبر می‌دانست؛ ردیف‌های قدیمی که قبل از افزودن ستون `archived_at` آرشیو شده بودند مقدار `NULL` داشتند و در نتیجه برای «امروز» هم resolve می‌شدند.

**اصلاح:** در `backend/app/services/finance.py` (حدود خطوط ۶۱۸ و ۱۳۲۴):

- `ACTIVE` همیشه معتبر است.
- `ARCHIVED` فقط اگر `archived_at` غیر NULL و بزرگ‌تر از تاریخ مورد بررسی باشد، یا اگر `archived_at` NULL باشد و `effective_to` صریح داشته باشد.
- ترتیب انتخاب با `CASE` ابتدا `ACTIVE` را ترجیح می‌دهد.
- همین قاعده در `resolve_coach_contract` اعمال شد.

**تست‌ها:**

- `test_qa_legacy_archived_override_does_not_apply_today` — override قدیمی archived بدون timestamp برای امروز اعمال نمی‌شود و sale با نرخ پیش‌فرض ساخته می‌شود.
- `test_qa_legacy_archived_override_with_explicit_end_is_historical` — همان ردیف با `effective_to` صریح برای تاریخ گذشته resolve می‌شود، ولی برای امروز نه.
- `test_qa_legacy_archived_coach_contract_does_not_authorize_new_sale` — قرارداد مربی archived قدیمی مجوز sale جدید نمی‌دهد (`coach_contract_missing`).
- `test_finance_legacy_archived_overrides_are_historical_after_upgrade` در `backend/tests/test_migrations.py:412` — از revision `b8d1e2f3a4c5` با دادهٔ legacy به head upgrade می‌کند و بررسی می‌کند `archived_at` همچنان NULL بماند، `effective_to` حفظ شود، امروز به default برگردد و تاریخ گذشته به override تاریخی resolve شود.

**شاهد:** `evidence/finance-targeted-backend.log` و `evidence/migrations-utc.log`.

### FIN-R02 — خرید پلن باید اتمی باشد

**ریشه:** `purchase_training_plan` sale و payment را در commitهای جداگانه می‌ساخت؛ شکست در ساخت request یا خطای هم‌زمانی می‌توانست sale/payment یتیم باقی بگذارد.

**اصلاح:** `purchase_training_plan` (حدود خط ۱۷۵۶):

- `_lock_finance_gym` در ابتدای عملیات.
- `create_sale`, `simulate_payment` و `_create_program_request_after_payment` با `commit=False`.
- یک `session.commit()` نهایی؛ در هر خطا `rollback` کامل.
- در برخورد unique، همان payment موجود بازیابی می‌شود و نتیجهٔ idempotent برمی‌گردد.
- helper بازیابی `_existing_purchase_result` (حدود خط ۱۷۰۰) برای retry همان خرید و ترمیم request گم‌شده.

**تست‌ها:**

- `test_qa_concurrent_purchase_retry_is_atomic` — دو worker هم‌زمان با یک idempotency key؛ نتیجه یکسان و دقیقاً **۱ sale، ۱ payment، ۱ request**.
- `test_qa_http_concurrent_purchase_retry_is_idempotent` — همان سناریو از مسیر HTTP.
- `test_qa_purchase_failure_rolls_back_and_retry_recovers` — شکست تزریقی بعد از payment؛ هیچ sale/payment باقی نمی‌ماند و retry همان key خرید کامل را می‌سازد.

**شاهد:** `evidence/finance-targeted-backend.log` (۶ تست هدفمند R01/R02).

### FIN-R03 — حفظ دقیق قیمت پلن در ویرایش metadata-only

**ریشه:** فرم ویرایش از `irrToToman` با `Math.round` استفاده می‌کرد؛ ۱۰۵ ریال به ۱۱ تومان گرد می‌شد و ذخیرهٔ مجدد آن را ۱۱۰ ریال می‌کرد.

**اصلاح:**

- `frontend/src/lib/finance-ui.ts:129` — `irrToTomanInput(value) = String(value / 10)` برای مقدار قابل ویرایش.
- `irrToToman` برای نمایش نیز دقیق شد تا ۱۰٫۵ تومان حفظ شود.
- `frontend/src/pages/finance/CoachPlanPage.tsx:86` از `irrToTomanInput` استفاده می‌کند.

**تست‌ها:**

- `metadata-only plan edits preserve every IRR remainder` — برای ۱۰ پلن با باقی‌مانده‌های ۰ تا ۹، ویرایش فقط توضیحات همان `base_price_irr` را در payload نگه می‌دارد.
- `UI can create and re-edit a 10.5 Toman plan without changing its price` — ساخت با ورودی ۱۰٫۵ تومان (`base_price_irr=105`) و ویرایش مجدد بدون تغییر قیمت.

**شاهد:** `evidence/finance-targeted-frontend.log`.

### UI-R01 — انتخاب حرکت در build تولیدی

**بازتولید:** روی build تولیدی same-origin، هر دو مسیر `categories.spec.ts` (تست تغییر دسته) و `program-authoring.spec.ts` شکست خوردند: پس از `.fill()` مقدار input خالی و `aria-expanded=false` می‌ماند.

**ریشه‌یابی:** تست ابتدا `.click()` می‌کند و بلافاصله `.fill()` با کل رشته. در build تولیدی، بازشدن popover مبتنی بر focus و بستن آن در همان چرخهٔ pointer event با تک‌رویداد `input` حاصل از `fill` مسابقه می‌دهد؛ React مقدار controlled input را به حالت انتخاب‌نشده برمی‌گرداند. تایپ واقعی چندین رویداد جداگانه بعد از task کلیک تولید می‌کند و این مسابقه را ندارد. این یک نقص readiness در harness است، نه regression مالی؛ تایپ واقعی و انتخاب ماوس/کیبورد در product بررسی شد.

**اصلاح harness:**

- `frontend/tests/categories.spec.ts:121` و `:182` — ابتدا `ArrowDown` برای بازکردن قطعی listbox، سپس `pressSequentially` برای تایپ واقعی.
- `frontend/tests/program-authoring.spec.ts:48` — همان الگو.
- `frontend/tests/athletes-list.spec.ts:84` — `ArrowDown` بعد از کلیک برای بازکردن قطعی picker پیش از assertion تعداد optionها.
- کامپوننت `frontend/src/components/M3.tsx` تغییر نکرد و پس از آزمایش‌های product-level به نسخهٔ اصلی بازگشت.

**شاهد:** `evidence/ui-r01-repeat.log` (۷ اجرا = setup + ۳ تست × ۲ بار، همه پاس) و دو اجرای کامل Playwright.

**مورد باقی‌مانده:** کلیک صرف روی input یا chevron در بعضی اجراهای production می‌تواند listbox را باز و بلافاصله ببندد؛ این رفتار ناشی از مدیریت focus در popover non-modal کتابخانهٔ React Aria 1.22.1 است. مسیرهای تست‌شده و کاربردی (تایپ، ArrowDown، انتخاب ماوس/کیبورد، Escape) کار می‌کنند؛ اما «بازشدن با یک کلیک خالی» به‌صورت محصولی تأیید نمی‌شود. برای رفع کامل این quirk نیاز به اصلاح/ارتقای کتابخانه یا پیاده‌سازی کنترل‌شدهٔ open state است. این مورد در بخش ریسک‌ها باز است.

### QA-R01 — race استخراج gymId

`frontend/tests/finance-qa-regressions.spec.ts` پیش از خواندن `pathname` صریحاً `await expect(page).toHaveURL(/\/gyms\/[^/]+$/)` را انتظار می‌کشد (خط ۲۲۳). هیچ شناسهٔ `undefined` به API فرستاده نمی‌شود. ۸ تست مالی این فایل پاس شدند.

### QA-R02 — motion در production

`frontend/tests/responsive-hardening.spec.ts:1003` تابع `durationMs` را معرفی می‌کند که `ms` و `s` را نرمال می‌کند. assertionهای زیر حفظ شدند:

- Standard = ۱۵۰ms و easing شامل `cubic-bezier`
- Expressive = ۳۵۰ms و easing
- button transition = ۱۵۰ms
- sheet animation = ۳۵۰ms
- reduced-motion fallback

نتیجه: ۲ project (`chromium` و `responsive`) بدون retry پاس.

### QA-R03 — انتخاب مربی در صفحهٔ سوپرادمین

**ریشهٔ ناپایداری:** option در `AsyncPicker` بعد از fetch و در popover متحرک ظاهر می‌شود؛ تست قدیمی بدون انتظار readiness کلیک می‌کرد. رویکرد میانی `focus()+Enter` هم انتخاب را ثبت نمی‌کرد (دیالوگ با پیام «انتخاب مربی الزامی است» باز می‌ماند) و رد شد.

**اصلاح:** `frontend/tests/superuser-context.spec.ts:294` تا `:333`:

- انتظار visible شدن option.
- کلیک واقعی روی option (بدون force).
- assertion `toHaveValue(editedCoachName)` / `toHaveValue(secondCoachName)` برای اثبات ثبت انتخاب.

نتیجه: تست هدفمند ۱/۱ و کل suite سوپرادمین ۱۵/۱۵ پاس.

## ۴. نتایج واقعی دستورها

| دستور | نتیجه | لاگ |
|---|---|---|
| `TZ=UTC pytest -q` (backend، `_test`) | **۲۱۶ passed** | `evidence/backend-full.log` |
| `TZ=UTC pytest tests/test_migrations.py -q` | **۸ passed** | `evidence/migrations-utc.log` |
| `alembic check` روی DB تازهٔ `_test` | **No new upgrade operations detected** | `evidence/alembic-check.log` |
| `ruff check app tests scripts` | **All checks passed** | `evidence/ruff-check.log` |
| `ruff format --check` روی فایل‌های تغییر‌یافته | **passed** | — |
| `mypy app` | **Success: no issues found in 45 source files** | `evidence/mypy.log` |
| `biome check ./` (frontend) | **Checked 166 files، بدون خطا** | `evidence/frontend-lint.log` |
| `node --test tests-unit/*.test.mjs` | **۱۶ pass، ۰ fail** | `evidence/frontend-node.log` |
| `VITE_API_URL= npm run build` | **passed** (tsc + Vite + service worker) | `evidence/frontend-build.log` |
| Playwright کامل، اجرای اول، `--retries=0` | **۱۴۰ pass، ۱ skip طراحی‌شده، ۰ fail** | `evidence/playwright-full-run1.log` |
| Playwright کامل، اجرای دوم، `--retries=0` | **۱۴۰ pass، ۱ skip طراحی‌شده، ۰ fail** | `evidence/playwright-full-run2.log` |
| تست‌های هدفمند مالی backend | **۶ passed** | `evidence/finance-targeted-backend.log` |
| تست‌های هدفمند مالی frontend | **۹ passed** (۸ تست + setup) | `evidence/finance-targeted-frontend.log` |
| UI-R01 هدفمند، تکرار ۲ بار | **۷ passed** | `evidence/ui-r01-repeat.log` |
| QA-R02، هر دو project | **۳ passed** | `evidence/qa-r02.log` |
| QA-R03 هدفمند | **۱ passed** | `evidence/qa-r03.log` |

- skip طراحی‌شده: `athlete-archive.spec.ts:116` در project `mobile-admin` (بازیابی گروهی روی موبایل).
- هیچ retry فعال نبود. دو اجرای کامل پشت‌سرهم روی یک محیط disposable سبز بودند.
- در جریان تلاش برای اصلاح product-level UI-R01 (`menuTrigger="input"`)، یک اجرای کامل میانی **۱۳۸ pass و ۲ fail** داشت (کلیک‌بازکردن coach picker و انتخاب کیبوردی حرکت). آن تغییر product revert شد و اجرای نهایی با build `6c7fe452` سبز است؛ لاگ میانی برای شفافیت در `evidence/playwright-intermediate-product-attempt.log` نگه داشته شد.

## ۵. شواهد حفظ داده و هم‌زمانی

- دیتابیس اصلی `gym_finance_sandbox_v2`:
  - `finance_sale = 2` (بدون تغییر نسبت به قبل از دور دوم)
  - `finance_program_request = 1` (بدون تغییر)
  - `finance_payment = 2`
  - revision = `c3f4a5b6d7e8`
- هیچ reset یا migrate روی دیتابیس اصلی/dev/stage/production انجام نشد؛ فقط migration جدید روی main اعمال و بکاپ نگه داشته شد.
- تست `test_qa_concurrent_purchase_retry_is_atomic` صریحاً `len(sales) == len(payments) == len(requests) == 1` را assert می‌کند.
- تست `test_qa_purchase_failure_rolls_back_and_retry_recovers` بعد از شکست، صفر sale/payment و بعد از retry دقیقاً یک sale/request را assert می‌کند.
- تست metadata-only برای باقی‌مانده‌های ۰ تا ۹، `base_price_irr` را در payload هر PUT بررسی می‌کند؛ ۱۰٫۵ تومان نیز به‌صورت UI ساخته و ویرایش شد.
- جزئیات در `evidence/data-preservation.txt`.

## ۶. فایل‌های اصلی تغییر‌یافته

**Backend:**

- `backend/app/services/finance.py` — resolverهای FIN-R01، تراکنش FIN-R02.
- `backend/app/finance_models.py` — مدل‌های مالی/قرارداد و archive metadata.
- `backend/app/api/routes/finance.py` — مسیرهای مالی.
- `backend/app/alembic/versions/c3f4a5b6d7e8_finance_bigint_contract_archive_metadata.py`
- `backend/tests/test_migrations.py` — تست upgrade با override آرشیوشدهٔ legacy.
- `backend/tests/api/routes/test_finance_qa_regressions.py` — regressionهای R01/R02 و تست‌های قبلی.

**Frontend:**

- `frontend/src/lib/finance-ui.ts` — `irrToTomanInput` و تبدیل دقیق.
- `frontend/src/pages/finance/CoachPlanPage.tsx` — مقدار فرم ویرایش.
- صفحات مالی و `finance-api.ts` / `i18n.tsx` / `index.css` / generated client — هماهنگ‌سازی دور قبلی.
- `frontend/tests/finance-qa-regressions.spec.ts` — R03 و QA-R01.
- `frontend/tests/categories.spec.ts`، `program-authoring.spec.ts`، `athletes-list.spec.ts` — harness readiness برای UI-R01.
- `frontend/tests/responsive-hardening.spec.ts` — QA-R02.
- `frontend/tests/superuser-context.spec.ts` — QA-R03.
- `frontend/src/components/M3.tsx` در نسخهٔ نهایی **تغییر نکرده** است.

## ۷. ریسک‌ها و موارد حل‌نشده

1. **UI-R01 — کلیک خالی روی combobox:** مسیر تایپ/کیبورد/انتخاب ماوس معتبر است، اما یک کلیک صرف روی input یا chevron می‌تواند popover را باز و بلافاصله ببندد. این رفتار کتابخانه‌ای React Aria 1.22.1 با popover non-modal است. اگر «بازشدن با یک کلیک» الزام محصول باشد، نیاز به ارتقای کتابخانه یا پیاده‌سازی سفارشی open state دارد. در این دور، product component عمداً تغییر نکرد تا regressionهای کلیک/کیبورد ایجاد نشود.
2. **Ruff format در کل repo:** `ruff check app tests scripts` پاس است و فایل‌های تغییر‌یافته با `ruff format --check` پاس می‌شوند؛ اما اجرای repo-wide روی `app` هنوز ۱۶ فایل (و در کل ۳۵ فایل) از قبل unformatted گزارش می‌کند. برای جلوگیری از diff پرتعداد، آن فایل‌ها بازفرمت نشدند. این یک بدهی ابزاری از قبل موجود است.
3. **پوشش اجرا:** دو اجرای کامل Playwright روی یک ماشین/یک محیط disposable سبز شدند؛ این جایگزین تست بار، درگاه واقعی، مرورگرهای متنوع یا ممیزی قانونی نیست.
4. **بدون تأیید انتشار:** هیچ P1 مالی باز شناخته‌شده‌ای در این اعتبارسنجی باقی نمانده است، اما به‌دلیل مورد ۱ (quirk رابط) و تغییرات کامیت‌نشده، تأیید نهایی انتشار اعلام نمی‌شود.

## ۸. وضعیت نهایی

- FIN-R01، FIN-R02، FIN-R03، QA-R01، QA-R02 و QA-R03 با شواهد اجرایی پاس شدند.
- UI-R01 در مسیرهای تست‌شده و تایپ واقعی پاس شد؛ quirk کلیک خالی به‌عنوان مورد باز ثبت شده است.
- تمام تغییرات همچنان **uncommitted** برای review باقی مانده‌اند.
- گزارش و شواهد تاریخی در `/Users/sajad/Documents/Tasks/gym-app/docs/qa/finance-sandbox-v2-retest-2026-11-10/` دست‌نخورده‌اند.
