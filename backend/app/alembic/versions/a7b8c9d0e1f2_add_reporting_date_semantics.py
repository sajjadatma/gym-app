"""add reporting date semantics

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_receivable",
        sa.Column("recognized_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "platform_credit",
        sa.Column("recognized_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "platform_invoice",
        sa.Column("cancelled_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "finance_credit_movement",
        sa.Column("applied_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "finance_period",
        sa.Column("period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "finance_period",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    # Only platform_credit needs its immutability trigger bypassed for this
    # derived-date backfill. Use targeted DDL instead of a superuser-only GUC.
    op.execute(
        "ALTER TABLE platform_credit DISABLE TRIGGER platform_credit_immutable"
    )
    op.execute(
        """
        UPDATE platform_receivable
        SET recognized_on = (created_at AT TIME ZONE 'Asia/Tehran')::date
        WHERE recognized_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE platform_credit
        SET recognized_on = (created_at AT TIME ZONE 'Asia/Tehran')::date
        WHERE recognized_on IS NULL
        """
    )
    op.execute(
        "ALTER TABLE platform_credit ENABLE TRIGGER platform_credit_immutable"
    )
    op.execute(
        """
        UPDATE finance_credit_movement m
        SET applied_on = (
            m.created_at AT TIME ZONE COALESCE(
                (
                    SELECT fs.timezone
                    FROM finance_customer_credit c
                    LEFT JOIN finance_settings fs ON fs.gym_id = c.gym_id
                    WHERE c.id = m.credit_id
                ),
                'Asia/Tehran'
            )
        )::date
        WHERE m.kind = 'APPLIED' AND m.applied_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE platform_invoice i
        SET cancelled_on = (c.created_at AT TIME ZONE 'Asia/Tehran')::date
        FROM platform_invoice_cancellation c
        WHERE c.invoice_id = i.id AND i.cancelled_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE finance_period p
        SET period_start = COALESCE(
            (
                SELECT min(j.posting_date)
                FROM finance_journal j
                WHERE j.period_id = p.id
            ),
            (
                p.opened_at AT TIME ZONE COALESCE(
                    (
                        SELECT fs.timezone
                        FROM finance_settings fs
                        WHERE fs.gym_id = p.gym_id
                    ),
                    'Asia/Tehran'
                )
            )::date
        )
        WHERE p.period_start IS NULL
        """
    )
    op.execute(
        """
        UPDATE finance_period p
        SET period_end = (
            p.closed_at AT TIME ZONE COALESCE(
                (
                    SELECT fs.timezone
                    FROM finance_settings fs
                    WHERE fs.gym_id = p.gym_id
                ),
                'Asia/Tehran'
            )
        )::date
        WHERE p.closed_at IS NOT NULL AND p.period_end IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("finance_period", "period_end")
    op.drop_column("finance_period", "period_start")
    op.drop_column("finance_credit_movement", "applied_on")
    op.drop_column("platform_invoice", "cancelled_on")
    op.drop_column("platform_credit", "recognized_on")
    op.drop_column("platform_receivable", "recognized_on")
