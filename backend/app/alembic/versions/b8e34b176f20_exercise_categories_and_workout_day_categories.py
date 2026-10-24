"""Exercise catalog categories and immutable workout-day category snapshots.

Revision ID: b8e34b176f20
Revises: 0c51ff8f04c4
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "b8e34b176f20"
down_revision = "0c51ff8f04c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercise_category",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(100), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gym_id", "name_key", name="uq_exercise_category_gym_name"),
    )
    op.create_index("ix_exercise_category_gym_id", "exercise_category", ["gym_id"])
    op.create_index(
        "uq_exercise_category_global",
        "exercise_category",
        ["name_key"],
        unique=True,
        postgresql_where=sa.text("gym_id IS NULL"),
    )
    op.add_column("exercise", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_exercise_category",
        "exercise",
        "exercise_category",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_exercise_category_id", "exercise", ["category_id"])
    op.add_column("workout_day", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.add_column(
        "workout_day", sa.Column("category_name", sa.String(100), nullable=True)
    )
    op.create_foreign_key(
        "fk_workout_day_category",
        "workout_day",
        "exercise_category",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_workout_day_category_id", "workout_day", ["category_id"])
    bind = op.get_bind()
    categories: dict[tuple[uuid.UUID | None, str], uuid.UUID] = {}

    def category_for(name: str, gym_id: uuid.UUID | None) -> uuid.UUID:
        name = " ".join(name.split()) or "بدون دسته‌بندی"
        key = name.casefold()
        if (None, key) in categories:
            return categories[(None, key)]
        if (gym_id, key) not in categories:
            category_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO exercise_category (id, name, name_key, gym_id, created_at) "
                    "VALUES (:id, :name, :key, :gym, :created)"
                ),
                {
                    "id": category_id,
                    "name": name,
                    "key": key,
                    "gym": gym_id,
                    "created": datetime.now(UTC),
                },
            )
            categories[(gym_id, key)] = category_id
        return categories[(gym_id, key)]

    # Global catalog first, so matching custom exercises can share its categories.
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, muscle_group, gym_id, is_custom FROM exercise ORDER BY is_custom"
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        category_id = category_for(
            row["muscle_group"], row["gym_id"] if row["is_custom"] else None
        )
        bind.execute(
            sa.text("UPDATE exercise SET category_id = :category WHERE id = :id"),
            {"category": category_id, "id": row["id"]},
        )
    op.alter_column("exercise", "category_id", nullable=False)

    # Preserve historical titles and movement snapshots. Only uniform days get
    # one category; mixed days keep all of their existing movements unchanged.
    days = (
        bind.execute(
            sa.text(
                "SELECT d.id, p.gym_id FROM workout_day d "
                "JOIN workout_program_version v ON v.id = d.version_id "
                "JOIN workout_program p ON p.id = v.program_id"
            )
        )
        .mappings()
        .all()
    )
    for day in days:
        groups = (
            bind.execute(
                sa.text(
                    "SELECT DISTINCT muscle_group FROM workout_exercise WHERE day_id = :id"
                ),
                {"id": day["id"]},
            )
            .scalars()
            .all()
        )
        if len(groups) == 1:
            category_id = category_for(groups[0], day["gym_id"])
            bind.execute(
                sa.text(
                    "UPDATE workout_day SET category_id = :category, category_name = :name WHERE id = :id"
                ),
                {"category": category_id, "name": groups[0], "id": day["id"]},
            )

    templates = (
        bind.execute(sa.text("SELECT id, gym_id, content FROM program_template"))
        .mappings()
        .all()
    )
    for template in templates:
        content = template["content"] or {}
        for day in content.get("days", []):
            template_groups = {
                item["muscle_group"]
                for item in day.get("exercises", [])
                if item.get("muscle_group")
            }
            if len(template_groups) == 1:
                name = next(iter(template_groups))
                day["category_id"] = str(category_for(name, template["gym_id"]))
                day["category_name"] = name
        bind.execute(
            sa.text(
                "UPDATE program_template SET content = CAST(:content AS JSON) WHERE id = :id"
            ),
            {"id": template["id"], "content": json.dumps(content, ensure_ascii=False)},
        )


def downgrade() -> None:
    op.drop_constraint("fk_workout_day_category", "workout_day", type_="foreignkey")
    op.drop_index("ix_workout_day_category_id", table_name="workout_day")
    op.drop_column("workout_day", "category_name")
    op.drop_column("workout_day", "category_id")
    op.drop_constraint("fk_exercise_category", "exercise", type_="foreignkey")
    op.drop_index("ix_exercise_category_id", table_name="exercise")
    op.drop_column("exercise", "category_id")
    op.drop_index("uq_exercise_category_global", table_name="exercise_category")
    op.drop_index("ix_exercise_category_gym_id", table_name="exercise_category")
    op.drop_table("exercise_category")
