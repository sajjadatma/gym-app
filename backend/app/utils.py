from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import emails
import jwt
from jinja2 import Environment, select_autoescape
from jwt.exceptions import InvalidTokenError

from app.core import security
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailData:
    html_content: str
    subject: str


@dataclass(frozen=True)
class PurposeToken:
    subject: str
    token_version: int


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / template_name
    ).read_text(encoding="utf-8")
    environment = Environment(
        autoescape=select_autoescape(default_for_string=True, default=True)
    )
    template = environment.from_string(template_str)
    return template.render(**context)


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    if not settings.emails_enabled:
        raise RuntimeError("email_delivery_not_configured")
    assert settings.EMAILS_FROM_EMAIL  # For type checker
    redirected = bool(settings.EMAIL_REDIRECT_TO)
    target = str(settings.EMAIL_REDIRECT_TO or email_to)
    safe_subject = f"[{settings.FASTAPI_ENV or 'test'}] {subject}" if redirected else subject
    message = emails.message.Message(
        subject=safe_subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options: dict[str, Any] = {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
    }
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=target, smtp=smtp_options)
    logger.info(
        "email_delivery_attempted",
        extra={"status_code": response.status_code, "redirected": redirected},
    )


def generate_reset_password_email(email_to: str, token: str) -> EmailData:
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(
        html_content=html_content,
        subject=f"{settings.PROJECT_NAME} - بازیابی رمز عبور",
    )


def generate_invitation_email(
    *, email_to: str, full_name: str | None, gym_name: str, token: str
) -> EmailData:
    link = f"{settings.FRONTEND_HOST}/accept-invitation?token={token}"
    html_content = render_email_template(
        template_name="invitation.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "full_name": full_name or email_to,
            "gym_name": gym_name,
            "valid_hours": settings.INVITATION_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(
        html_content=html_content,
        subject=f"{settings.PROJECT_NAME} - دعوت به {gym_name}",
    )


def _generate_token(
    email: str, purpose: str, hours: int, token_version: int = 0
) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(hours=hours)
    return jwt.encode(
        {
            "exp": expires.timestamp(),
            "nbf": now,
            "sub": email,
            "purpose": purpose,
            "token_version": token_version,
        },
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def _decode_purpose_token(token: str, purpose: str) -> PurposeToken | None:
    try:
        decoded = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
    except InvalidTokenError:
        return None
    if decoded.get("purpose") != purpose:
        return None
    subject = decoded.get("sub")
    token_version = decoded.get("token_version", 0)
    if (
        not subject
        or not isinstance(token_version, int)
        or isinstance(token_version, bool)
        or token_version < 0
    ):
        return None
    return PurposeToken(subject=str(subject), token_version=token_version)


def decode_purpose_token(token: str, purpose: str) -> str | None:
    payload = _decode_purpose_token(token, purpose)
    return payload.subject if payload else None


def generate_password_reset_token(email: str, token_version: int = 0) -> str:
    return _generate_token(
        email,
        "reset_password",
        settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
        token_version,
    )


def verify_password_reset_token(token: str) -> PurposeToken | None:
    return _decode_purpose_token(token, "reset_password")


def generate_invitation_token(email: str) -> str:
    return _generate_token(email, "invitation", settings.INVITATION_EXPIRE_HOURS)


def verify_invitation_token(token: str) -> str | None:
    return decode_purpose_token(token, "invitation")
