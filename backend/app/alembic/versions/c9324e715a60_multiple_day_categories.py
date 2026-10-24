"""Allow multiple category snapshots per workout day.

Revision ID: c9324e715a60
Revises: b8e34b176f20
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "c9324e715a60"
down_revision = "b8e34b176f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("category_ids", "category_names"):
        op.add_column(
            "workout_day",
            sa.Column(name, sa.JSON(), nullable=False, server_default="[]"),
        )
    connection = op.get_bind()
    for row in connection.execute(
        sa.text("SELECT id, category_id, category_name FROM workout_day")
    ).mappings():
        connection.execute(
            sa.text(
                "UPDATE workout_day SET category_ids=CAST(:ids AS json), category_names=CAST(:names AS json) WHERE id=:id"
            ),
            {
                "id": row["id"],
                "ids": json.dumps(
                    [str(row["category_id"])] if row["category_id"] else []
                ),
                "names": json.dumps(
                    [row["category_name"]] if row["category_name"] else []
                ),
            },
        )
    for name in ("category_ids", "category_names"):
        op.alter_column("workout_day", name, server_default=None)


def downgrade() -> None:
    op.drop_column("workout_day", "category_names")
    op.drop_column("workout_day", "category_ids")
