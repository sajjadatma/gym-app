import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import configure_logging

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


configure_logging()
logger = logging.getLogger("app.request")

if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        send_default_pii=False,
        environment=settings.SENTRY_ENVIRONMENT or settings.FASTAPI_ENV,
        max_request_body_size="never",
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

settings.BODY_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def hardening_middleware(request: Request, call_next: Any) -> Response:
    request_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    method = request.method
    path = request.url.path
    safe_path = re.sub(
        r"/password-recovery/[^/]+", "/password-recovery/[redacted]", path
    )
    content_length = request.headers.get("content-length")
    if path.endswith("/athletes/import") or path.endswith(
        "/athletes/import/preview"
    ):
        # The import route enforces its own bounded read and returns the
        # established 400/import_file_too_large contract.
        limit = None
    elif method == "POST" and path.endswith("/body-files"):
        limit = settings.BODY_ANALYSIS_MAX_BYTES
    else:
        limit = settings.MAX_JSON_BODY_BYTES
    try:
        if (
            limit is not None
            and method in {"POST", "PUT", "PATCH"}
            and content_length is not None
        ):
            try:
                too_large = int(content_length) > limit
            except ValueError:
                too_large = False
            if too_large:
                response: Response = JSONResponse(
                    status_code=413,
                    content={"detail": "request_too_large"},
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": method,
                "path": safe_path,
            },
        )
        raise
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 1)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": method,
                "path": safe_path,
                "status": response.status_code if "response" in locals() else 500,
                "duration_ms": duration_ms,
            },
        )

    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Referrer-Policy", "strict-origin-when-cross-origin"
    )
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; base-uri 'self'; object-src 'none'; "
            "frame-ancestors 'none'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            f"font-src 'self'; connect-src {settings.CSP_CONNECT_SRC}; "
            "form-action 'self'"
        ),
    )
    if settings.HSTS_ENABLED:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


app.include_router(api_router, prefix=settings.API_V1_STR)
if FRONTEND_DIR.exists():
    app.frontend("/", directory=FRONTEND_DIR)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (FRONTEND_DIR / full_path).resolve()
        if FRONTEND_DIR.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")
