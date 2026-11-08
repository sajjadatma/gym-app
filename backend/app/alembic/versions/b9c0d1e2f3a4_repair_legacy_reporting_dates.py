"""repair legacy reporting dates from authoritative source events

Revision ID: b9c0d1e2f3a4
Revises: a7b8c9d0e1f2
Create Date: 2026-11-08

The original reporting-date backfill used ``created_at`` for every legacy
row. This migration repairs only rows whose original source event is
unambiguous and still present:

* subscription receivables: the period encoded in ``source_key``;
* commission receivables: the receipt/advance encoded in ``source_key``;
* ASCORA coach-share receivables: the linked earning receipt/advance;
* platform credits: the refund journal or cancelled invoice;
* applied customer-credit movements: a single matching ADVANCE_APPLIED
  journal for the invoice.

Rows without an authoritative source are left untouched. Amounts, journals,
audit rows and immutable timestamps are never changed.
"""

from __future__ import annotations

from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE platform_receivable pr
        SET recognized_on = (split_part(pr.source_key, ':', 4) || '-01')::date
        WHERE pr.source_type = 'SUBSCRIPTION'
          AND split_part(pr.source_key, ':', 1) = 'subscription'
          AND split_part(pr.source_key, ':', 4) ~ '^[0-9]{4}-[0-9]{2}$'
        """
    )
    op.execute(
        """
        UPDATE platform_receivable pr
        SET recognized_on = r.received_on
        FROM finance_receipt r
        WHERE pr.source_type = 'COMMISSION'
          AND split_part(pr.source_key, ':', 1) = 'receipt'
          AND split_part(pr.source_key, ':', 2) = r.id::text
        """
    )
    op.execute(
        """
        UPDATE platform_receivable pr
        SET recognized_on = COALESCE(
            m.applied_on,
            (m.created_at AT TIME ZONE 'Asia/Tehran')::date
        )
        FROM finance_credit_movement m
        WHERE pr.source_type = 'COMMISSION'
          AND split_part(pr.source_key, ':', 1) = 'advance'
          AND split_part(pr.source_key, ':', 2) = m.id::text
        """
    )
    op.execute(
        """
        UPDATE platform_receivable pr
        SET recognized_on = r.received_on
        FROM finance_coach_earning e
        JOIN finance_receipt r ON r.id = e.receipt_id
        WHERE pr.source_type = 'COACH_ASCORA_SHARE'
          AND pr.source_id = e.id
          AND e.receipt_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE platform_receivable pr
        SET recognized_on = COALESCE(
            m.applied_on,
            (m.created_at AT TIME ZONE 'Asia/Tehran')::date
        )
        FROM finance_coach_earning e
        JOIN finance_credit_movement m ON m.id = e.credit_movement_id
        WHERE pr.source_type = 'COACH_ASCORA_SHARE'
          AND pr.source_id = e.id
          AND e.credit_movement_id IS NOT NULL
        """
    )

    # platform_credit is append-only through a trigger; the derived reporting
    # date is the only field this migration changes.
    op.execute(
        "ALTER TABLE platform_credit DISABLE TRIGGER platform_credit_immutable"
    )
    op.execute(
        """
        UPDATE platform_credit pc
        SET recognized_on = j.posting_date
        FROM finance_refund rf
        JOIN finance_journal j ON j.id = rf.journal_id
        WHERE pc.source_type = 'REFUND'
          AND pc.source_id = rf.id
          AND rf.journal_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE platform_credit pc
        SET recognized_on = i.cancelled_on
        FROM platform_invoice_cancellation c
        JOIN platform_invoice i ON i.id = c.invoice_id
        WHERE pc.source_type = 'INVOICE_CANCELLATION'
          AND pc.source_id = c.id
          AND i.cancelled_on IS NOT NULL
        """
    )
    op.execute(
        "ALTER TABLE platform_credit ENABLE TRIGGER platform_credit_immutable"
    )

    op.execute(
        """
        UPDATE finance_credit_movement m
        SET applied_on = j.posting_date
        FROM finance_journal j
        JOIN finance_journal_line l ON l.journal_id = j.id
        WHERE m.kind = 'APPLIED'
          AND m.invoice_id IS NOT NULL
          AND j.source_type = 'finance_invoice'
          AND j.source_id = m.invoice_id
          AND j.event_type = 'ADVANCE_APPLIED'
          AND l.debit_irr = m.amount_irr
          AND (
              SELECT count(*)
              FROM finance_journal j2
              WHERE j2.source_type = 'finance_invoice'
                AND j2.source_id = m.invoice_id
                AND j2.event_type = 'ADVANCE_APPLIED'
          ) = 1
        """
    )


def downgrade() -> None:
    # The prior created-at fallback cannot be distinguished from rows that
    # were already correct. This repair is intentionally forward-only.
    pass
