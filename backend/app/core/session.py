from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.core.config import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def set_auth_cookies(response: Response, token: str) -> None:
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def token_from_request(request: Request, bearer_token: str | None) -> tuple[str | None, bool]:
    """Return the token and whether it arrived via the browser cookie."""
    if bearer_token:
        return bearer_token, False
    cookie = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    return cookie, bool(cookie)


def verify_csrf(request: Request) -> bool:
    """Double-submit check for cookie-authenticated unsafe requests."""
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not header or not cookie:
        return False
    return secrets.compare_digest(header, cookie)
