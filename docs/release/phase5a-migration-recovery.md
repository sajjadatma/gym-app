# Phase 5A.4 — Migration, Concurrency, Idempotency and Docker Backup/Restore

**Date:** 2026-11-04
**Branch:** `feat/ascora-finance`
**Scope:** Local-only migration safety, concurrency/idempotency stress and Docker recovery
**Status:** PASS — LOCAL GO for 5A.4

## 1. Migration safety

Migration: `backend/app/alembic/versions/a7b8c9d0e1f2_add_reporting_date_semantics.py`

### 1.1 Round-trip verification

`test_reporting_date_migration_preserves_immutable_rows` performs:

1. upgrade to `f1a2b3c4d5e6`;
2. seed existing gym/platform finance rows;
3. snapshot row-level checksums for journals, journal lines, payments, allocations, invoice lines, platform credits/applications and sequences;
4. upgrade to head;
5. downgrade to `f1a2b3c4d5e6`;
6. upgrade to head again;
7. assert the same checksums after every step.

Covered immutable families:

- `finance_journal`, `finance_journal_line`
- `platform_journal`, `platform_journal_line`
- `platform_payment`, `platform_payment_allocation`
- `platform_invoice_line`
- `platform_credit`, `platform_credit_application`
- `finance_invoice`, `finance_invoice_line`
- `finance_receipt`, `finance_receipt_allocation`
- `finance_customer_credit`, `finance_credit_movement`
- `finance_sequence`, `platform_sequence`

The round-trip snapshot does not yet cover audit rows, invoice cancellations/reversals or platform operations; those are recorded as remaining evidence gaps.

`test_reporting_date_migration_backfills_existing_rows` also verifies the new columns:

- `platform_receivable.recognized_on`
- `platform_credit.recognized_on`
- `platform_invoice.cancelled_on`
- `finance_credit_movement.applied_on`
- `finance_period.period_start` / `period_end`

Backfill uses explicit business timezones:

- platform rows: `(created_at AT TIME ZONE 'Asia/Tehran')::date`;
- gym finance rows: the gym’s `finance_settings.timezone`, falling back to `Asia/Tehran`;
- `period_end`: `closed_at` in gym time, matching `close_period`.

### 1.2 Trigger bypass review

The migration no longer uses `session_replication_role = replica`. It uses:

```sql
ALTER TABLE platform_credit DISABLE TRIGGER platform_credit_immutable;
UPDATE platform_credit ...;
ALTER TABLE platform_credit ENABLE TRIGGER platform_credit_immutable;
```

The bypass is scoped to the one table whose trigger blocks the derived-date backfill. It requires table ownership, not superuser, and is reset before the remaining backfills. Existing journal, line, payment, allocation, invoice-line, credit-application and sequence facts are not written by the migration.

### 1.3 Runtime `applied_on`

`apply_customer_credit` now writes `applied_on=received_on`, so new applied-credit rows use the business date rather than the creation timestamp.

### 1.4 Independent migration review

A fresh-context reviewer found:

| Finding | Status |
|---|---|
| HIGH: superuser-only `session_replication_role` | **Resolved** — targeted trigger DDL |
| HIGH: timezone-dependent `::date` backfill | **Resolved** — explicit Asia/Tehran / gym timezone |
| HIGH: `applied_on` never written | **Resolved** — runtime write added |
| Medium: `period_end` backfill mismatch | **Resolved** — uses `closed_at` in gym time |
| Medium: preservation evidence weak | **Improved** — round-trip checksums and credit/application coverage |
| Medium: new reporting columns remain mutable by direct SQL | **Accepted risk** — see §5 |

The reviewer’s verdict after fixes: the migration is safe to accept from a migration/data-safety standpoint; no Critical/High issues remain.

## 2. Concurrency and idempotency

New suite: `backend/tests/api/routes/test_finance_concurrency_5a4.py` — **7 passed**

| Scenario | Assertion |
|---|---|
| Concurrent duplicate receipt with the same key | Both return the same receipt; exactly one `RECEIPT_CONFIRMED` journal |
| Concurrent platform payments | One succeeds, one rejects; one payment row and one platform payment journal; no overpay |
| Concurrent platform invoice cancellation | Both return success; exactly one cancellation row; invoice `CANCELLED` |
| Concurrent group invoice issuance | One succeeds, one rejects; exactly one group invoice and two per-gym invoice lines |
| Concurrent refund recording | One succeeds, one conflicts; exactly one `REFUND_RECORDED` journal |
| Concurrent coach settlements | One succeeds, one rejects; exactly one settlement row, amount `300,000`, and one `COACH_SETTLEMENT` journal |
| Concurrent subscription accrual with the same key | Both return the same receivable; exactly one subscription `PLATFORM_FEE` journal |

Existing suites continue to cover concurrent invoice numbering, concurrent receipts with different keys, opening-balance/correction races, idempotent retries, and failed over-allocation leaving no journal.

## 3. Docker backup/restore drill

Command: `scripts/ci/backup-restore-drill.sh` against a fresh local CI stack at migration head `a7b8c9d0e1f2`.

Result: **PASS**

Restored finance counts:

```text
finance_period=1, finance_journal=3, finance_journal_line=7,
finance_invoice=1, finance_invoice_line=1, finance_receipt=1,
finance_receipt_allocation=1, finance_customer_credit=1,
finance_credit_movement=1, finance_sequence=3
```

Restored platform counts:

```text
platform_agreement=1, platform_receivable=1, platform_credit=1,
platform_credit_application=1, platform_invoice=1, platform_invoice_line=1,
platform_payment=1, platform_payment_allocation=1, platform_journal=1,
platform_journal_line=2, platform_sequence=2
```

Verifier result: `ok:true`, no failures. Checks included:

- exact restored counts vs backup for legacy and platform tables, plus hardcoded key finance counts; the verifier reports all finance counts but does not yet compare every finance table to a backup count file;
- balanced finance/platform journals and at least two lines each;
- receipt/allocation consistency;
- no cross-gym allocations;
- customer-credit balance vs movements;
- invoice/receipt/journal sequence bounds;
- platform payment/allocation, credit and sequence integrity;
- upload-file presence and size.

Measured drill duration: **189.85 seconds (~3 min 10 s)**, including backup, isolated restore, verification, live restore and readiness check. This is well under the approved **60-minute** local threshold.

The drill now forces `COMPOSE_PROJECT_NAME=gym-ci` and unsets ambient `BACKUP_RCLONE_REMOTE`/`ENV_FILE`, so a developer’s production Compose environment cannot be targeted accidentally.

## 4. Regression evidence

| Check | Result |
|---|---|
| Migration tests | **14 passed** |
| Concurrency suite | **7 passed** |
| Date-semantics + concurrency under `TZ=UTC` | **21 passed** |
| Full backend regression | **331 passed** |
| Full backend under `TZ=UTC` | **331 passed** |
| Ruff | Clean |
| Mypy | Clean |

## 5. Remaining risks

- **Release workflow drill isolation.** The release workflow runs the drill after the full Playwright suite on a non-fresh stack. The drill requires a fresh stack and its global count assertions can fail there. This is a release-gate wiring issue, not a local data-safety defect; it is recorded for 5B and was not changed under the local-only constraint.
- **Finance exact-count comparison is partial.** The verifier reports all finance counts but only legacy/platform counts and a hardcoded key finance subset are compared. A future backup-count file should cover every finance table.
- **Concurrency gaps.** Concurrent invoice cancellation + payment and concurrent credit application + invoice issue are not yet separate acceptance tests; the advisory-lock design covers them but test evidence is partial.
- **New reporting columns are mutable by direct SQL.** `platform_receivable.recognized_on`, `platform_invoice.cancelled_on`, `finance_credit_movement.applied_on`, and `finance_period.period_start/period_end` are not included in the existing immutability trigger comparisons. Application paths do not rewrite them, but a role with `UPDATE` could. This is a Medium integrity-hardening item for 5A.5/5B, not a migration-safety defect.
- The migration backfill uses `created_at`/`closed_at` where no explicit business date exists; legacy rows can still differ from the journal business date. New rows use the canonical business date.
- The preservation test does not yet snapshot audit rows, invoice cancellations/reversals or platform operations.
- Custom gym timezones are handled in SQL but the migration tests exercise the `Asia/Tehran` fallback; an invalid timezone name would fail closed.
- A post-migration negative test proving `platform_credit_immutable` is active again is not yet added.
- 5A.3 limitations remain: historical coach payable and membership renewal metrics are not fully as-of; some historical CSV balance rows use current state; legacy recognized-on backfill may differ from journal business dates.
- No comprehensive historical correctness or 100% endpoint date-conformance is claimed.

## 6. Scope boundary

No 5A.5–5A.7 work was started. No deployment, Vercel/Neon change, merge, provider integration, real data or new product feature was introduced.
