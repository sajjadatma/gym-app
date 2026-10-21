from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app import crud
from app.api.deps import SessionDep
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import (
    AcceptInvitation,
    Message,
    NewPassword,
    Token,
    User,
)
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_invitation_token,
    verify_password_reset_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="invalid_credentials")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="inactive_user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    user = crud.get_user_by_email(session=session, email=email)
    if user and user.hashed_password and user.is_active:
        reset_token = generate_password_reset_token(email=user.email)
        email_data = generate_reset_password_email(
            email_to=user.email, token=reset_token
        )
        try:
            send_email(
                email_to=user.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        except Exception:
            logger.exception("password recovery email could not be delivered")
    return Message(message="password_recovery_requested")


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="invalid_token")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="inactive_user")
    user.hashed_password = get_password_hash(body.new_password)
    user.must_change_password = False
    session.add(user)
    session.commit()
    return Message(message="password_updated")


@router.post("/auth/accept-invitation")
def accept_invitation(session: SessionDep, body: AcceptInvitation) -> Message:
    email = verify_invitation_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="invalid_or_expired_invitation")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if user.hashed_password:
        raise HTTPException(status_code=400, detail="invitation_already_used")
    user.hashed_password = get_password_hash(body.new_password)
    user.must_change_password = False
    user.is_active = True
    session.add(user)
    session.commit()
    return Message(message="account_activated")
