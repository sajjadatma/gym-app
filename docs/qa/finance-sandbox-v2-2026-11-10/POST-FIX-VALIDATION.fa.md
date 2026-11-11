# اعتبارسنجی پس از اصلاح — فیچر مالی ASCORA

**تاریخ:** ۱۰ نوامبر ۲۰۲۶ · ۱۹ آبان ۱۴۰۵  
**منطقهٔ زمانی گزارش:** Asia/Tehran  
**برنچ:** `codex/finance-sandbox-v2`  
**کامیت مبنا:** `0b94e5cb3fd80560766e71d98eeaafee8c64c734`  
**وضعیت کار:** تغییرات در worktree هدف اعمال شده‌اند؛ هیچ push، merge یا deploy انجام نشده است.

## ۱. نتیجهٔ کلی

تمام موارد **FIN-01 تا FIN-12** و **QC-01** اصلاح شدند و هر مورد با حداقل یک تست regression قابل اجرا پوشش داده شد. تست‌های بازتولید QA به regressionهای پایدار پروژه تبدیل شدند؛ تست‌ها حذف، skip یا ضعیف نشدند.

| بخش | نتیجه |
|---|---|
| کل suite بک‌اند | **۲۰۹ passed**، ۱۳ warning (همه deprecation) |
| تست‌های migration | **۷ passed**؛ همچنین **۷ passed** با `TZ=UTC` |
| Ruff | پاک |
| Mypy | پاک؛ ۴۵ فایل |
| Alembic check | «No new upgrade operations detected» |
| Frontend lint (Biome) | پاک؛ ۱۶۶ فایل |
| TypeScript | پاک |
| Frontend build | موفق |
| تست‌های Node | **۱۶ passed** |
| Playwright مالی (finance-sandbox + QA regressions) | **۱۱ passed** (شامل setup) |
| کل Playwright | **۱۱۹ passed، ۲ flaky (پاس در retry)، ۱۸ skipped** |

## ۲. وضعیت FIN/QC

| مورد | وضعیت | فایل‌های اصلی تغییرکرده | تست اثبات |
|---|---|---|---|
| **FIN-01** تسویهٔ هم‌زمان و رزرو دوبارهٔ مانده | Fixed | `backend/app/services/finance.py` | `test_qa_concurrent_settlements_do_not_overreserve`، `test_qa_concurrent_settlement_and_refund_never_overlap`، `test_qa_concurrent_auto_settle_does_not_overpay` |
| **FIN-02** فیلتر دسته در همهٔ اقلام گزارش | Fixed | `backend/app/services/finance.py` | `test_qa_category_filter_excludes_other_payments`، `test_qa_category_filter_is_consistent_for_mixed_settlements`، `test_qa_completed_settlement_and_refund_category_totals`، `test_qa_global_report_and_csv_match_gym_report` |
| **FIN-03** refund جزئی تجمعی و دقیق | Fixed | `backend/app/services/finance.py` | `test_qa_repeated_partial_refunds_do_not_exceed_party_allocation` |
| **FIN-04** وضعیت تاریخی تسویه در گزارش | Fixed | `backend/app/services/finance.py` | `test_qa_historical_pending_is_preserved[complete]`، `[cancel]` |
| **FIN-05** ابطال مجوز خرید پس از full refund | Fixed | `backend/app/services/finance.py`، `backend/app/finance_models.py` | `test_qa_refunded_purchase_cannot_be_fulfilled`، `test_qa_partial_refund_does_not_cancel_purchase_request` |
| **FIN-06** دامنهٔ مبلغ و BIGINT | Fixed | `backend/app/finance_models.py`، migration `c3f4a5b6d7e8` | `test_qa_normal_large_sale_is_supported`، `test_qa_amount_plus_tax_over_supported_range_is_rejected`، `test_finance_money_columns_are_bigint...`، `test_finance_amounts_survive_bigint_upgrade`، `test_finance_bigint_downgrade_refuses...` |
| **FIN-07** تسویهٔ درآمد قبلی مربی غیرفعال | Fixed | `backend/app/services/finance.py`، `backend/app/api/routes/finance.py`، `backend/app/finance_models.py` | `test_qa_departed_coach_can_receive_existing_earnings`، `test_qa_auto_settle_pays_departed_coach`، `test_qa_coach_selector_includes_departed_coach_with_balance` |
| **FIN-08** تعارض کلید idempotency | Fixed | `backend/app/services/finance.py` | `test_qa_refund_idempotency_cannot_return_another_payment`، `test_qa_settlement_idempotency_rejects_payload_change`، `test_qa_purchase_idempotency_rejects_different_plan` |
| **FIN-09** refund هم‌زمان و تکراری | Fixed | `backend/app/services/finance.py` | `test_qa_concurrent_duplicate_refund_is_idempotent`، `test_qa_concurrent_different_refunds_respect_remaining` |
| **FIN-10** resolve قرارداد تاریخی پس از جایگزینی | Fixed | `backend/app/services/finance.py`، `backend/app/finance_models.py`، migration `c3f4a5b6d7e8` | `test_qa_contract_update_preserves_backdated_sale_policy`، `test_qa_coach_contract_historical_resolution_after_rebase` |
| **FIN-11** parser ارقام فارسی/عربی و فرم‌های مالی | Fixed | `frontend/src/lib/finance-ui.ts`، `frontend/src/lib/finance-validation.ts`، صفحات مالی، `frontend/src/i18n.tsx` | تست‌های Playwright «Persian and Arabic-Indic sale amounts...»، «Persian tax edit...»، «Persian refund and settlement amounts...»، و `test_qa_tax_update_rejects_explicit_null_percent` |
| **FIN-12** اعتبار preview وابسته به payload فعلی | Fixed | `frontend/src/pages/finance/FinanceSalesPage.tsx` | «changing the category invalidates the previous preview» و «a delayed preview response cannot validate a newer form» |
| **QC-01** انطباق motion ناوبری مالی | Fixed | `frontend/src/index.css` | `frontend/tests-unit/motion-system.test.mjs` — **۱۶/۱۶** |

## ۳. جزئیات اصلاحات

### FIN-01 — قفل مشترک مالی و رزرو اتمیک

- یک advisory lock تراکنشی در سطح باشگاه (`pg_advisory_xact_lock` با کلید پایدار باشگاه) برای settlement، refund، complete/cancel، auto-settle و مصرف خرید اضافه شد.
- `_eligible_allocations` هنگام رزرو، ردیف‌های allocation را با `FOR UPDATE OF finance_allocation` قفل می‌کند و مانده را بعد از قفل دوباره محاسبه می‌کند.
- `complete_settlement` قبل از تکمیل، مجموع itemها و سقف هر allocation را دوباره اعتبارسنجی می‌کند؛ یک settlement ناسازگار قبلی بی‌صدا COMPLETED نمی‌شود.
- تست race با Barrier **قبل از ورود به سرویس** هماهنگ می‌شود؛ barrier داخل helper مانده نیست تا قفل قبل از آن deadlock نسازد. `ThreadPoolExecutor` با timeout و `finally` برای listener/cleanup استفاده می‌کند.
- assertionهای race فقط status نیستند؛ تعداد و مجموع رکوردهای مالی نیز بررسی می‌شوند.

### FIN-02 — فیلتر category در تمام اقلام

- فیلتر category از sale به payment، allocation، refund، settlement item و مانده‌های as-of متصل شد.
- settlement چنددسته‌ای بر اساس itemهای منطبق جمع می‌شود، نه با نسبت‌دادن کل مبلغ settlement به هر دسته.
- گزارش باشگاهی، global، overview و CSV همچنان از یک تابع مشترک استفاده می‌کنند.

### FIN-03 — refund تجمعی

- سهم هر refund از **ظرفیت باقی‌ماندهٔ همان allocation** و با محاسبات صحیح محاسبه می‌شود.
- residual به ترتیب پایدار طرف‌ها توزیع می‌شود؛ نه به ترتیب تصادفی ردیف‌های دیتابیس.
- full refund، سهم هر طرف را دقیقاً به صفر می‌رساند و هیچ طرفی از allocation اولیه عبور نمی‌کند.

### FIN-04 — گزارش تاریخی

- وضعیت settlement در cutoff از `requested_at`، `completed_at` و `cancelled_at` بازسازی می‌شود؛ status فعلی ملاک نیست.
- pending و completed هر کدام از itemهای منطبق محاسبه می‌شوند.
- مرز روز و منطقهٔ زمانی به‌صورت صریح `Asia/Tehran` است؛ `finance_today()` نیز از همین منطقه استفاده می‌کند.
- گزارش دیروز قبل و بعد از complete/cancel امروز برابر می‌ماند.

### FIN-05 — refund و مجوز برنامه

- full refund یک درخواست `REQUESTED` را به `CANCELLED` می‌برد.
- مصرف درخواست علاوه بر status، وجود پرداخت موفق و نبود refund کامل را تحت همان advisory lock بررسی می‌کند.
- partial refund درخواست را باطل نمی‌کند.
- برنامهٔ قبلاً تحویل‌شده حذف یا بازنویسی نمی‌شود؛ refund پس از تحویل فقط رویداد مالی جداگانه است.
- خطاهای جدید: `program_request_cancelled`، `program_purchase_refunded`، `program_request_payment_missing`.

### FIN-06 — BIGINT و سقف مبلغ

- همهٔ ستون‌های پولی finance به `BIGINT` منتقل شدند: sale، sale tax، payment، allocation، settlement، settlement item، refund، refund adjustment، plan، program request و tax fixed amount.
- سقف end-to-end برابر **۱٬۰۰۰٬۰۰۰٬۰۰۰٬۰۰۰٬۰۰۰ IRR** (یک کوادریلیون ریال) تعیین شد؛ این مقدار داخل safe-integer جاوااسکریپت است.
- محدودیت در Pydantic و سرویس اعمال می‌شود؛ base + tax نیز قبل از درج بررسی می‌شود.
- migration جدید `c3f4a5b6d7e8_finance_bigint_contract_archive_metadata.py` داده‌های قبلی را حفظ می‌کند.
- downgrade در صورت وجود مقدار بزرگ‌تر از INTEGER با `RuntimeError` روشن متوقف می‌شود و truncate نمی‌کند.

### FIN-07 — مربی غیرفعال

- ایجاد settlement برای مربی، دیگر به membership فعال وابسته نیست؛ وجود allocation قابل پرداخت در همان باشگاه ملاک است.
- فروش/قرارداد جدید همچنان به membership فعال نیاز دارد.
- endpoint انتخاب مربی با `with_balance=true` مربیان غیرفعال دارای طلب را با `is_active=false` و `has_balance=true` برمی‌گرداند.
- auto-settle نیز مربیان سابق دارای allocation را پرداخت می‌کند و به آن‌ها دسترسی مالی جدید نمی‌دهد.

### FIN-08 و FIN-09 — idempotency

- refund: مقایسهٔ `payment_id` و `amount_irr`؛ کلید با پرداخت یا مبلغ متفاوت → `409 idempotency_key_reused`.
- settlement: مقایسهٔ `party`، `party_user_id` و `amount_irr`.
- purchase: مقایسهٔ ورزشکار، `plan_id` و `outcome`.
- refund پس از قفل payment دوباره idempotency را بررسی می‌کند؛ در برخورد unique، رکورد موجود با fingerprint معتبر برگردانده می‌شود.
- دو refund هم‌زمان با کلید یکسان همان refund ID را برمی‌گردانند و فقط یک refund/adjustment ایجاد می‌شود.
- دو refund هم‌زمان با کلیدهای متفاوت از سقف باقی‌مانده عبور نمی‌کنند.

### FIN-10 — قرارداد تاریخی

- جست‌وجوی قرارداد پلتفرم و مربی، علاوه بر `ACTIVE`، نسخه‌های `ARCHIVED` را نیز برای تاریخ‌های گذشته در نظر می‌گیرد.
- `archived_at` به قرارداد پلتفرم و مربی اضافه شد؛ قرارداد در تاریخ آرشیو به بعد دیگر انتخاب نمی‌شود ولی برای تاریخ‌های قبل از آرشیو قابل resolve است.
- ترتیب قطعی: `effective_from` نزولی، سپس `version` نزولی. تغییر چندباره در یک روز با آخرین version همان روز resolve می‌شود.
- fallback پیش‌فرض/override و همگام‌سازی قرارداد مربی با همان resolver زمانی هماهنگ شد.
- snapshotهای فروش قبلی دست‌نخورده‌اند. برای ردیف‌های archived قدیمی که `archived_at` ندارند، resolver بر اساس بازه و version عمل می‌کند؛ این سازگاری در بخش ریسک‌ها ثبت شده است.

### FIN-11 — parser مشترک

- parser مشترک `finance-ui.ts` ارقام لاتین، فارسی و عربی‌هندی را می‌پذیرد.
- جداکننده‌های هزارگان `٬`، `,` و فاصله پشتیبانی می‌شوند؛ جداکنندهٔ اعشار `٫` و `.` است.
- تومان حداکثر یک رقم اعشار (چون IRR = تومان × ۱۰) و درصد حداکثر دو رقم اعشار (basis point) دارد.
- NaN، Infinity، منفی، overflow و precision غیرمجاز قبل از ارسال رد می‌شوند.
- خطا کنار فیلد با `role="alert"` و `aria-invalid` نمایش داده می‌شود.
- مالیات صفر درصدی حفظ می‌شود؛ صفر به‌عنوان «بدون تغییر» یا null تفسیر نمی‌شود.
- backend نیز `calculation=PERCENT` همراه `percent_bp=null` صریح را با `400 invalid_tax_value` رد می‌کند.

### FIN-12 — preview fingerprint

- preview به fingerprint canonical از category، مبلغ، tax IDs مرتب‌شده، مربی و تاریخ گره خورده است.
- هر تغییر مؤثر، preview را پاک و mutation قبلی را reset می‌کند.
- پاسخ دیررس preview با مقایسهٔ fingerprint در `onSuccess`/`onError` نادیده گرفته می‌شود.
- دکمهٔ ثبت فقط وقتی فعال است که preview فعلی با payload جاری یکی باشد.
- توضیح فروش (description) چون در تخصیص مالی اثر ندارد، از fingerprint خارج است.

### QC-01 — motion

- `background 160ms ease` و `color 160ms ease` با tokenهای مشترک
  `--m3-motion-standard-effects-fast` و `--m3-motion-standard-easing` جایگزین شدند.
- تست motion و reduced motion سبز است.

## ۴. Migration و سازگاری داده

- migration جدید: `backend/app/alembic/versions/c3f4a5b6d7e8_finance_bigint_contract_archive_metadata.py`
- تغییرات:
  - `BIGINT` برای ۱۸ ستون پولی finance
  - افزودن `archived_at` به `finance_platform_contract` و `finance_coach_contract`
- روی دیتابیس تازه و دیتابیس دارای داده آزمایش شد.
- تست `test_finance_amounts_survive_bigint_upgrade` یک فروش با مبلغ `2,147,483,647` را قبل از upgrade درج و بعد از upgrade بررسی می‌کند.
- تست downgrade نشان می‌دهد در صورت وجود مبلغ `3,000,000,000` downgrade با خطای روشن متوقف می‌شود.
- `alembic check` هیچ drift مدل/دیتابیس نشان نمی‌دهد.
- snapshot قرارداد، مالیات و allocation فروش‌های قبلی بازنویسی نشده است.

## ۵. دستورهای اجراشده و نتیجهٔ واقعی

```text
cd backend
ENV_FILE=.env.qa PYTHONPATH=. pytest -q
# 209 passed, 13 warnings

ENV_FILE=.env.qa PYTHONPATH=. pytest tests/test_migrations.py -q
# 7 passed

TZ=UTC ENV_FILE=.env.qa PYTHONPATH=. pytest tests/test_migrations.py -q
# 7 passed

ruff check app tests
# All checks passed

mypy app
# Success: no issues found in 45 source files

alembic check
# No new upgrade operations detected

cd frontend
biome check --no-errors-on-unmatched --files-ignore-unknown=true ./
# Checked 166 files, no fixes applied

tsc -p tsconfig.build.json
# exit 0

npm run build
# built successfully; service worker cache build 75ed3ee2c8f28b9e

node --test tests-unit/*.test.mjs
# tests 16, pass 16, fail 0

VITE_API_URL=http://127.0.0.1:8020 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8021 \
PLAYWRIGHT_API_URL=http://127.0.0.1:8020 \
playwright test tests/finance-sandbox.spec.ts tests/finance-qa-regressions.spec.ts --project=chromium
# 11 passed (including admin setup; 6 QA regression + 4 finance journeys)

VITE_API_URL=http://127.0.0.1:8020 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8021 \
PLAYWRIGHT_API_URL=http://127.0.0.1:8020 \
playwright test --retries=1
# 119 passed, 2 flaky (passed on retry), 18 skipped
# flaky items: controls English locale, responsive account sheet
```

**نکتهٔ محیط تست:** اجرای اول Playwright با `VITE_API_URL` قدیمی (8010) به‌جای origin تست (8020) شروع شد و باعث ۱۹ خطای fixture شد. پس از هم‌راستاکردن `VITE_API_URL`، `PLAYWRIGHT_API_URL` و `FRONTEND_HOST`، همهٔ تست‌ها سبز شدند؛ این خطا مربوط به محصول نبود.

**نکتهٔ flaky بودن کل suite:** در اجرای نهایی با `--retries=1`، دو تست غیرمالی (`controls` در locale انگلیسی و `responsive-hardening` در account sheet) در اجرای اول flaky بودند و در retry پاس شدند. تست‌های مالی و regressionهای این گزارش در همان اجرا پایدار بودند. این flakeها به تست‌های تعاملی قدیمی مربوط‌اند و در این اصلاح تغییری در آن مسیرها داده نشده است.

## ۶. پوشش رابط و شواهد تصویری

- هر هفت صفحهٔ مالی باشگاه — overview، contracts، sales، taxes، settlements، reports و coach-plan — در عرض‌های **۳۹۰** و **۱۲۸۰** بررسی شدند: RTL، بدون سرریز کل صفحه و بدون uncaught error.
- پنل مالی global admin و جریان athlete purchase → coach request → ساخت برنامه در تست‌های Playwright مالی پوشش داده شد.
- تصاویر:
  - [`finance-sales-390.png`](evidence/finance-sales-390.png)
  - [`finance-reports-1280.png`](evidence/finance-reports-1280.png)
  - [`stale-preview-invalidated.png`](evidence/stale-preview-invalidated.png)
  - [`tax-invalid-error.png`](evidence/tax-invalid-error.png)

## ۷. ریسک‌ها و ابهام‌های باقی‌مانده

1. **قراردادهای archived قدیمی:** ردیف‌های archived قبل از افزودن `archived_at` مقدار تاریخی ندارند. resolver با بازهٔ `effective_from`/`effective_to` و version کار می‌کند؛ برای تاریخ‌های خیلی نزدیک به آرشیو، دادهٔ قدیمی ممکن است نتواند قطعی‌تر از این بازسازی شود. snapshots فروش‌های موجود تغییر نکرده‌اند.
2. **refund پس از تحویل برنامه:** سیاست فعلی این است که برنامهٔ تحویل‌شده حذف یا origin آن بازنویسی نشود؛ refund فقط رویداد مالی جداگانه است. اگر سیاست محصول بخواهد برنامه پس از refund باطل شود، نیازمند تصمیم و پیاده‌سازی جداگانه است.
3. **سقف مبلغ:** سقف ۱٬۰۰۰٬۰۰۰٬۰۰۰٬۰۰۰٬۰۰۰ IRR یک انتخاب end-to-end برای safe-integer است؛ BIGINT دیتابیس ظرفیت بیشتری دارد. این سقف برای هر تراکنش است و جمع تجمعی گزارش‌ها جداگانه کران‌دار نشده است؛ در مقادیر تجمعی بسیار بزرگ، محدودیت safe-integer جاوااسکریپت دوباره مطرح می‌شود. اگر نیاز تجاری بالاتر شد، باید UI و API همزمان بازبینی شوند.
4. **category در settlement چنددسته‌ای:** گزارش بر اساس itemها تفکیک می‌شود؛ خود رکورد settlement یک مبلغ کل دارد و نمایش تفصیلی آن در UI فعلی تغییر نکرده است.
5. **تست production:** این کار در sandbox محلی با پرداخت شبیه‌سازی‌شده انجام شده است؛ درگاه واقعی، TLS، backup عملیاتی و ممیزی قانونی مالیات خارج از محدوده‌اند.

## ۸. خلاصهٔ diff

```text
backend/app/api/routes/finance.py                  |  31 +-
backend/app/finance_models.py                      | 106 +--
backend/app/services/finance.py                    | 867 +++++++++++++++++++++++-----
backend/tests/test_migrations.py                   | 207 +++++
frontend/src/client/types.gen.ts                   |  23 +-
frontend/src/i18n.tsx                              |  49 ++
frontend/src/index.css                             |   6 +-
frontend/src/lib/finance-api.ts                    |  16 +-
frontend/src/lib/finance-ui.ts                     |  69 ++
frontend/src/pages/MyProgramPage.tsx               |   4 +-
frontend/src/pages/finance/CoachPlanPage.tsx       |  21 +-
frontend/src/pages/finance/FinanceContractsPage.tsx|  34 +-
frontend/src/pages/finance/FinanceSalesPage.tsx    | 124 ++-
frontend/src/pages/finance/FinanceSettlementsPage.tsx | 62 +-
frontend/src/pages/finance/FinanceTaxesPage.tsx    |  72 +-
```

فایل‌های جدید:

- `backend/app/alembic/versions/c3f4a5b6d7e8_finance_bigint_contract_archive_metadata.py`
- `backend/tests/api/routes/test_finance_qa_regressions.py`
- `frontend/src/lib/finance-validation.ts`
- `frontend/tests/finance-qa-regressions.spec.ts`
- همین گزارش و پوشهٔ `evidence/`

فایل‌های untracked قبلی worktree، از جمله `docs/decision-tree.html`، `docs/_tree-data.json` و `.preview/`، حفظ شده‌اند و بخشی از این اصلاح مالی نیستند.

## ۹. وضعیت نهایی

- هیچ merge، push یا deploy انجام نشد.
- تغییرات برای بررسی در worktree هدف باقی مانده‌اند.
- گزارش اصلی QA و لاگ‌های شکست اولیه در مسیر تاریخی خود دست‌نخورده‌اند.
- موردی که با تست قابل اتکا اثبات نشده باشد، fixed اعلام نشده است.
