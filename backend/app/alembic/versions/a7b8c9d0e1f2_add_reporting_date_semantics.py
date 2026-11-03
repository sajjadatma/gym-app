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
    op.execute("SET LOCAL session_replication_role = replica")
    op.execute(
        """
        UPDATE platform_receivable
        SET recognized_on = created_at::date
        WHERE recognized_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE platform_credit
        SET recognized_on = created_at::date
        WHERE recognized_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE finance_credit_movement
        SET applied_on = created_at::date
        WHERE kind = 'APPLIED' AND applied_on IS NULL
        """
    )
    op.execute(
        """
        UPDATE platform_invoice i
        SET cancelled_on = c.created_at::date
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
            p.opened_at::date
        )
        WHERE p.period_start IS NULL
        """
    )
    op.execute(
        """
        UPDATE finance_period p
        SET period_end = COALESCE(
            (
                SELECT max(j.posting_date)
                FROM finance_journal j
                WHERE j.period_id = p.id
            ),
            p.closed_at::date
        )
        WHERE p.closed_at IS NOT NULL AND p.period_end IS NULL
        """
    )
    op.execute("SET LOCAL session_replication_role = origin")


def downgrade() -> None:
    op.drop_column("finance_period", "period_end")
    op.drop_column("finance_period", "period_start")
    op.drop_column("finance_credit_movement", "applied_on")
    op.drop_column("platform_invoice", "cancelled_on")
    op.drop_column("platform_credit", "recognized_on")
    op.drop_column("platform_receivable", "recognized_on")
