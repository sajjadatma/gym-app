from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.audit import audit
from app.core.config import settings
from app.core.rate_limit import (
    client_ip,
    consume_or_429,
    reset_rate_limit,
)
from app.core.security import get_password_hash
from app.core.session import clear_auth_cookies, set_auth_cookies
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


def _require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.FRONTEND_HOST.rstrip("/"):
        raise HTTPException(status_code=403, detail="origin_not_allowed")


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    response: Response,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    _require_trusted_origin(request)
    email = form_data.username.strip().lower()
    consume_or_429(
        session=session,
        request=request,
        scope="login_ip",
        identity="all",
        limit=settings.LOGIN_IP_RATE_LIMIT,
        window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
    )
    consume_or_429(
        session=session,
        request=request,
        scope="login",
        identity=email,
        limit=settings.LOGIN_RATE_LIMIT,
        window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
    )
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="invalid_credentials")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="inactive_user")
    reset_rate_limit(session, f"login:{client_ip(request)}:{email}")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        user.id,
        expires_delta=access_token_expires,
        token_version=user.token_version,
    )
    set_auth_cookies(response, token)
    return Token(access_token=token)


@router.post("/auth/logout", response_model=Message)
def logout(
    response: Response,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    user = session.exec(
        select(User).where(User.id == current_user.id).with_for_update()
    ).one()
    user.token_version += 1
    session.add(user)
    session.commit()
    clear_auth_cookies(response)
    audit("auth.logout_all_sessions", actor_id=user.id)
    return Message(message="logged_out")


@router.post("/password-recovery/{email}")
def recover_password(
    request: Request, email: str, session: SessionDep
) -> Message:
    _require_trusted_origin(request)
    consume_or_429(
        session=session,
        request=request,
        scope="recovery_ip",
        identity="all",
        limit=settings.RECOVERY_IP_RATE_LIMIT,
        window_seconds=settings.RECOVERY_RATE_WINDOW_SECONDS,
    )
    consume_or_429(
        session=session,
        request=request,
        scope="recovery",
        identity=email.strip().lower(),
        limit=settings.RECOVERY_RATE_LIMIT,
        window_seconds=settings.RECOVERY_RATE_WINDOW_SECONDS,
    )
    user = crud.get_user_by_email(session=session, email=email)
    if user and user.hashed_password and user.is_active:
        reset_token = generate_password_reset_token(
            email=user.email, token_version=user.token_version
        )
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
def reset_password(
    request: Request, session: SessionDep, body: NewPassword
) -> Message:
    consume_or_429(
        session=session,
        request=request,
        scope="reset",
        identity="endpoint",
        limit=20,
        window_seconds=3600,
    )
    payload = verify_password_reset_token(token=body.token)
    if not payload:
        raise HTTPException(status_code=400, detail="invalid_token")
    # Lock the row so concurrent redemptions of the same reset token cannot both
    # pass the version check before one of them commits the increment.
    user = session.exec(
        select(User).where(User.email == payload.subject).with_for_update()
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="inactive_user")
    if user.token_version != payload.token_version:
        raise HTTPException(status_code=400, detail="invalid_token")
    user.hashed_password = get_password_hash(body.new_password)
    user.must_change_password = False
    user.token_version += 1
    session.add(user)
    session.commit()
    return Message(message="password_updated")


@router.post("/auth/accept-invitation")
def accept_invitation(
    request: Request, session: SessionDep, body: AcceptInvitation
) -> Message:
    consume_or_429(
        session=session,
        request=request,
        scope="invitation",
        identity="endpoint",
        limit=20,
        window_seconds=3600,
    )
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
