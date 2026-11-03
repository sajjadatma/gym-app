# Phase 5A.2 — Local Financial Workflow Acceptance

**Date:** 2026-11-03
**Branch:** `feat/ascora-finance`
**Scope:** Local-only end-to-end financial acceptance with synthetic data
**Status:** **PASS — LOCAL GO for 5A.2**

## 1. Environment and data

- Local PostgreSQL, backend and FastAPI test client only.
- All data is synthetic and disposable; no real financial data.
- No Vercel/Neon change, remote deployment, provider integration or merge to `main`.

## 2. Acceptance suite

Primary suite: `backend/tests/api/routes/test_finance_acceptance_5a2.py` (5 tests)

| Requirement | Test | Key assertions |
|---|---|---|
| Gym sales, invoices, installments, receipts | `test_gym_sales_installments_receipts_refund_credit_and_failures` | Invoice issue `1100/4000`; installments `400k/600k`; two receipts `1000/1100`; invoice-issue replay with one journal; receipt replay with one journal; over-allocation `400` leaves journal count unchanged; valid retry succeeds |
| Refunds, credits, allocation | same test | Refund `4100/1000`; receipt excess creates `2000` advance; credit application `2000/1100`; credit balance `100k → 0`; second application `400 insufficient_customer_credit`; invoice balance `200k` |
| Coach agreements, earnings, settlements | `test_coach_commission_subscription_settlement_and_platform_payment` | Coach allocation `5100/2100`; settlement `2100/2200`; confirmation `2200/1000`; double-confirm returns same settlement with one `COACH_SETTLED` journal |
| ASCORA commission and subscription billing | same test | HYBRID agreement; subscription `1100/4000` `500k`; commission `1100/4100` `100k`; accrual replay with one journal; platform invoice lines `500k` subscription + `100k` commission; payment `1000/1100` `600k`; payment history amount/method/reference |
| Group contracts, discounts, consolidated invoices | `test_group_contract_discount_cancellation_payment_and_exports` | Two-gym invoice; per-branch `gym_id`; each line gross `100k`, discount `5k`, amount `95k`; discount journal per line; cancellation status `CANCELLED`; second cancel idempotent; cancelled invoice excluded from `invoiced_fees_irr`; reissue; partial payment |
| Platform cancellations, payment history, exports | same test | Cancellation journal `1100/4100`; payment journal `1000/1100`; payment replay with one journal; changed-payload `409`; parsed platform CSV asserts recognized revenue `190k`, collected fees `90k`, receivable `100k`; parsed owner CSV asserts allocation `90k`, sales `1M`, platform payable `5k`; payment history amount/method/reference |
| Authorized/unauthorized roles | `test_role_authorization_matrix_for_local_acceptance` | Superuser, owner, finance staff, coach and athlete read matrix; owner cross-gym summary denied; staff cross-gym settings denied; staff invoice write denied; staff expense write allowed after grant; coach/athlete invoice write denied; owner cross-gym invoice `404`; Superuser platform access `200` |
| Failure, retry, idempotency | acceptance tests | Receipt, invoice, platform payment, accrual and settlement replays; changed payload rejected; over-allocation and second credit application fail without corrupting state; valid retry after failure |
| Journal reconciliation | all acceptance tests | Exact account-code/debit/credit tuples for every asserted finance and platform journal; every journal checked for balanced debits and credits |

Additional interaction test:

| Requirement | Test | Key assertions |
|---|---|---|
| Coach refund adjustment and platform refund credit | `test_coached_invoice_refund_posts_coach_adjustment_and_platform_reversal` | `COACH_ADJUSTMENT` `2100/5100` `30k`; platform `PLATFORM_FEE_REVERSAL` `1100/4100` `10k` |

## 3. Independent review

A fresh-context independent reviewer ran the acceptance suite and the related finance/platform set before the final additions. It found **no confirmed accounting defect**. It identified coverage gaps that were then closed:

| Review finding | Resolution |
|---|---|
| Group invoice did not assert per-branch allocation | Added per-line `gym_id`, `gross_irr`, `discount_irr`, `amount_irr` assertions (`95k` / `5k` each) |
| Export assertions were header-only/vacuous | Added CSV parsing and exact platform/owner metric assertions against posted journals |
| Platform invoice composition not asserted | Added `500k` subscription + `100k` commission line assertions |
| Cancellation effect not asserted | Added `CANCELLED` status, idempotent second cancel and exclusion from `invoiced_fees_irr` |
| Receipt replay did not prove no duplicate journal | Added journal-count assertion after replay |
| Role matrix was read-only | Added denied invoice writes for staff/coach/athlete, allowed staff expense write after grant, and cross-gym resource denial |
| Coach refund adjustment not exercised | Added the coach refund/platform reversal interaction test |
| Credit side effects not asserted | Added credit balance and second-apply failure assertions |
| Idempotency limited | Added invoice issue, accrual, settlement-confirm and platform-payment replay assertions |

## 4. Commands and results

| Check | Result |
|---|---|
| Acceptance suite (`test_finance_acceptance_5a2.py`) | **5 passed** |
| Finance + platform related suites | **139 passed** |
| Full backend regression | **308 passed** |
| Ruff | Clean |
| Mypy | Clean |

## 5. Journal reconciliation evidence

Exact expected lines were asserted for:

- `INVOICE_ISSUED` — `1100` debit / `4000` credit
- `RECEIPT_CONFIRMED` — `1000` debit / `1100` credit, plus `2000` credit for excess
- `ADVANCE_APPLIED` — `2000` debit / `1100` credit
- `REFUND_RECORDED` — `4100` debit / `1000` credit
- `COACH_ALLOCATION` — `5100` debit / `2100` credit
- `COACH_SETTLEMENT` — `2100` debit / `2200` credit
- `COACH_SETTLED` — `2200` debit / `1000` credit
- `COACH_ADJUSTMENT` — `2100` debit / `5100` credit
- Subscription `PLATFORM_FEE` — `1100` debit / `4000` credit
- Commission `PLATFORM_FEE` — `1100` debit / `4100` credit
- Group discount `PLATFORM_FEE_REVERSAL` — per-line `1100` credit / `4100` debit
- `PLATFORM_INVOICE_CANCEL` — per-line `1100` debit / `4100` credit
- `PLATFORM_PAYMENT` — `1000` debit / `1100` credit

Every helper also asserts total debits equal total credits for the selected journal.

## 6. Remaining risks

- No confirmed accounting defect was found in 5A.2.
- The acceptance suite is representative, not exhaustive; specialized suites still cover installment reminders, expenses, reconciliation lines, coach discrepancies and platform owner access.
- #15/#71, #34 and #91 remain **Partial/Outstanding**; no feature completion is claimed.
- Medium/Low findings from 5A.1 remain accepted for local-only work with Phase 5B follow-ups.
- 5A.3–5A.7 have not started.
