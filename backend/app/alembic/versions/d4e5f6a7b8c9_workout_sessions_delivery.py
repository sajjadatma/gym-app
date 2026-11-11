"""Workout execution history and explicit request delivery states.

Revision ID: d4e5f6a7b8c9
Revises: c3f4a5b6d7e8
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3f4a5b6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_finance_program_request_status", "finance_program_request", type_="check")
    op.create_check_constraint("ck_finance_program_request_status", "finance_program_request", "status IN ('REQUESTED', 'IN_PROGRESS', 'FULFILLED', 'CANCELLED')")
    # Only known, unpublished drafts are reclassified; orphaned historic records
    # are not reopened because their former delivery state cannot be inferred.
    op.execute("UPDATE finance_program_request r SET status='IN_PROGRESS', fulfilled_at=NULL FROM workout_program_version v WHERE v.purchase_request_id=r.id AND v.status='DRAFT' AND r.status='FULFILLED'")
    op.create_table(
        "workout_session",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("gym_id", sa.Uuid(), sa.ForeignKey("gym.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("workout_program_version.id", ondelete="SET NULL")),
        sa.Column("day_id", sa.Uuid(), sa.ForeignKey("workout_day.id", ondelete="SET NULL")),
        sa.Column("program_title", sa.String(255), nullable=False),
        sa.Column("day_title", sa.String(255), nullable=False),
        sa.Column("performed_on", sa.Date(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("effort", sa.Integer()),
        sa.Column("note", sa.String(2000)),
        sa.Column("sets", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("gym_id", "athlete_user_id", "idempotency_key", name="uq_workout_session_retry"),
        sa.CheckConstraint("effort IS NULL OR (effort >= 1 AND effort <= 10)", name="ck_workout_session_effort"),
    )
    for column in ("gym_id", "athlete_user_id", "version_id", "performed_on"):
        op.create_index(f"ix_workout_session_{column}", "workout_session", [column])


def downgrade() -> None:
    op.drop_table("workout_session")
    op.execute("UPDATE finance_program_request SET status='FULFILLED' WHERE status='IN_PROGRESS'")
    op.drop_constraint("ck_finance_program_request_status", "finance_program_request", type_="check")
    op.create_check_constraint("ck_finance_program_request_status", "finance_program_request", "status IN ('REQUESTED', 'FULFILLED', 'CANCELLED')")
