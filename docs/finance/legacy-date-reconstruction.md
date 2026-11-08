# Legacy Reporting-Date Reconstruction

**Date:** 2026-11-08
**Scope:** Phase 5A.7-R1 legacy reporting-date investigation
**Environment:** Local synthetic data only

## 1. Background

Migration `a7b8c9d0e1f2_add_reporting_date_semantics.py` backfilled the new
reporting dates from `created_at`:

- `platform_receivable.recognized_on`
- `platform_credit.recognized_on`
- `finance_credit_movement.applied_on` for `APPLIED` rows
- `platform_invoice.cancelled_on`
- finance-period boundaries

`created_at` is the time the row was recorded, not necessarily the business
date of the source event. For rows created after the canonical date fields
existed, the service writes the business date directly. This record covers
only pre-5A.3 rows.

## 2. Authoritative sources found

The following source events are still present and unambiguous:

| Legacy row | Authoritative source | Repair |
|---|---|---|
| `platform_receivable` `source_type='SUBSCRIPTION'` | `source_key` format `subscription:<agreement>:<gym>:YYYY-MM` | First day of the encoded period |
| `platform_receivable` `source_type='COMMISSION'` with `source_key='receipt:<receipt_id>:<line_id>'` | `finance_receipt.received_on` | Receipt business date |
| `platform_receivable` `source_type='COMMISSION'` with `source_key='advance:<movement_id>:<line_id>'` | `finance_credit_movement.applied_on` | Applied business date, with local `created_at` only when the movement has no applied date |
| `platform_receivable` `source_type='COACH_ASCORA_SHARE'` | `source_id` → `finance_coach_earning.receipt_id` / `credit_movement_id` | Linked receipt `received_on` or credit movement `applied_on` |
| `platform_credit` `source_type='REFUND'` | `source_id` → `finance_refund.journal_id` → `finance_journal.posting_date` | Refund posting date |
| `platform_credit` `source_type='INVOICE_CANCELLATION'` | `source_id` → `platform_invoice_cancellation.invoice_id` → `platform_invoice.cancelled_on` | Cancellation business date |
| `finance_credit_movement` `kind='APPLIED'` | Exactly one `ADVANCE_APPLIED` journal for the invoice with a matching debit amount | Journal `posting_date` |

Migration `b9c0d1e2f3a4_repair_legacy_reporting_dates.py` applies these
repairs. It changes only the derived reporting-date columns. Amounts,
journals, allocations, audit rows and immutable timestamps are not changed.
The `platform_credit` append-only trigger is disabled only for the derived
date update and re-enabled in the same migration.

## 3. Irrecoverable or ambiguous cases

These cases are left unchanged and remain documented limitations:

1. **Rows with no source linkage.** A `platform_receivable` with an
   unrecognised source key/type (for example a legacy manual row) keeps the
   `created_at` backfill. There is no authoritative event to recover.
2. **Ambiguous applied advances.** If an invoice has more than one
   `ADVANCE_APPLIED` journal, a legacy credit movement cannot be matched to a
   unique journal. The migration leaves `applied_on` unchanged rather than
   guessing. A single unambiguous matching journal is repaired.
3. **Missing source rows.** If the original receipt, credit movement,
   earning, refund journal or cancellation row no longer exists, the date is
   not reconstructed.
4. **Membership freeze/resume history.** Historical membership end dates are
   reconstructed from append-only `finance_audit` resume events
   (`finance.membership.resumed`, with `resume_on` and `paused_days`). If a
   membership's `frozen_days` exceeds the audited resume total, the history is
   incomplete. Gym summary reports fail closed with
   `membership_history_incomplete` rather than infer the past from today's
   mutable `end_date`.
5. **Cancelled membership without `cancelled_at`.** A legacy row in that
   state is not counted in historical renewals because the cancellation date
   cannot be established without inventing it.

## 4. Verification

- `backend/tests/test_finance_migrations.py::test_reporting_date_repair_uses_authoritative_source_events`
  verifies subscription, receipt-linked commission, refund-credit,
  cancellation-credit and applied-movement repairs. It also verifies that a
  manual receivable remains unchanged and that a refund journal's posting date
  and a platform-credit amount are preserved.
- The existing reporting-date backfill and immutable-preservation migration
  tests still pass.
- Migration suite: **16 passed** (local PostgreSQL).
