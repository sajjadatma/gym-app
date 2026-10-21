from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.models import GymMembershipRole


def get_membership_roles(session: Session, membership_id: uuid.UUID) -> set[str]:
    rows = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == membership_id
        )
    ).all()
    return {row.role for row in rows}
