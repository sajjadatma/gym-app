from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "application/pdf": (".pdf", b"%PDF"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
OBJECT_KEY_PREFIX = "body-analysis"
BRAND_LOGO_MAX_BYTES = 512 * 1024
_BRAND_TYPES = {
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
}


def _branding_dir() -> Path:
    return settings.BODY_ANALYSIS_DIR.parent / "branding"


def object_storage_enabled() -> bool:
    return bool(settings.BODY_ANALYSIS_BUCKET and settings.AWS_ENDPOINT_URL_S3)


@lru_cache(maxsize=1)
def _s3_client() -> Any:
    import boto3  # type: ignore[import-untyped]
    from botocore.config import Config  # type: ignore[import-untyped]

    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL_S3,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(s3={"addressing_style": "path"}),
    )


def _object_key(stored_name: str) -> str:
    return f"{OBJECT_KEY_PREFIX}/{stored_name}"


async def save_body_analysis_upload(
    upload: UploadFile,
) -> tuple[str, str, int]:
    original_name = (upload.filename or "").strip()
    if not original_name:
        raise HTTPException(status_code=400, detail="file_name_required")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported_file_type")
    content_type = (upload.content_type or "").lower()
    type_info = ALLOWED_TYPES.get(content_type)
    if not type_info:
        raise HTTPException(status_code=400, detail="unsupported_file_type")
    _canonical_extension, magic = type_info
    if content_type == "application/pdf" and extension != ".pdf":
        raise HTTPException(status_code=400, detail="file_content_mismatch")
    if content_type == "image/png" and extension != ".png":
        raise HTTPException(status_code=400, detail="file_content_mismatch")
    if content_type == "image/jpeg" and extension not in {".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="file_content_mismatch")
    if extension == ".jpeg":
        extension = ".jpg"

    data = await upload.read(settings.BODY_ANALYSIS_MAX_BYTES + 1)
    if len(data) > settings.BODY_ANALYSIS_MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    if not data:
        raise HTTPException(status_code=400, detail="file_is_empty")
    if not data.startswith(magic):
        raise HTTPException(status_code=400, detail="file_content_mismatch")

    stored_name = f"{uuid.uuid4().hex}{extension}"
    if object_storage_enabled():
        try:
            await run_in_threadpool(
                _s3_client().put_object,
                Bucket=settings.BODY_ANALYSIS_BUCKET,
                Key=_object_key(stored_name),
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:  # noqa: BLE001 - surface storage outages as 502
            logger.exception("object storage upload failed")
            raise HTTPException(
                status_code=502, detail="storage_unavailable"
            ) from exc
        return original_name[:255], stored_name, len(data)

    settings.BODY_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    destination = settings.BODY_ANALYSIS_DIR / stored_name
    destination.write_bytes(data)
    return original_name[:255], stored_name, len(data)


def delete_stored_file(stored_name: str) -> None:
    if object_storage_enabled():
        _s3_client().delete_object(
            Bucket=settings.BODY_ANALYSIS_BUCKET,
            Key=_object_key(stored_name),
        )
        return
    path = settings.BODY_ANALYSIS_DIR / stored_name
    if path.parent != settings.BODY_ANALYSIS_DIR:
        return
    path.unlink(missing_ok=True)


def delete_stored_files(stored_names: Iterable[str]) -> None:
    """Best-effort, idempotent removal of stored files after a DB rollback/commit.

    Callers only run this once the database state is final: after a successful
    commit when deleting records, or after a rollback when an upload was not
    persisted. A failed delete therefore leaves a harmless orphan object instead
    of a row that points at a missing file.
    """
    for stored_name in stored_names:
        try:
            delete_stored_file(stored_name)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            logger.warning("could not delete body analysis file %s", stored_name)


def read_stored_file(stored_name: str) -> bytes:
    if not object_storage_enabled():
        return stored_file_path(stored_name).read_bytes()
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    try:
        response = _s3_client().get_object(
            Bucket=settings.BODY_ANALYSIS_BUCKET,
            Key=_object_key(stored_name),
        )
        return bytes(response["Body"].read())
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
            raise HTTPException(
                status_code=404, detail="file_not_found"
            ) from exc
        logger.exception("object storage download failed for %s", stored_name)
        raise HTTPException(
            status_code=502, detail="storage_unavailable"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface storage outages as 502
        logger.exception("object storage download failed for %s", stored_name)
        raise HTTPException(
            status_code=502, detail="storage_unavailable"
        ) from exc


def stored_file_path(stored_name: str) -> Path:
    path = settings.BODY_ANALYSIS_DIR / stored_name
    if path.parent != settings.BODY_ANALYSIS_DIR or not path.exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    return path


async def save_branding_logo(
    upload: UploadFile, gym_id: uuid.UUID
) -> tuple[str, str]:
    content_type = (upload.content_type or "").lower()
    type_info = _BRAND_TYPES.get(content_type)
    if not type_info:
        raise HTTPException(status_code=400, detail="unsupported_image_type")
    extension, magic = type_info
    data = await upload.read(BRAND_LOGO_MAX_BYTES + 1)
    if len(data) > BRAND_LOGO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="logo_too_large")
    if not data or not data.startswith(magic):
        raise HTTPException(status_code=400, detail="file_content_mismatch")

    key = f"branding/{gym_id}/{uuid.uuid4().hex}{extension}"
    if object_storage_enabled():
        try:
            await run_in_threadpool(
                _s3_client().put_object,
                Bucket=settings.BODY_ANALYSIS_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:  # noqa: BLE001 - surface storage outages as 502
            logger.exception("branding logo upload failed")
            raise HTTPException(
                status_code=502, detail="storage_unavailable"
            ) from exc
        return key, content_type

    destination = _branding_dir() / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return key, content_type


def read_branding_logo(key: str) -> bytes:
    if object_storage_enabled():
        from botocore.exceptions import ClientError

        try:
            response = _s3_client().get_object(
                Bucket=settings.BODY_ANALYSIS_BUCKET, Key=key
            )
            return bytes(response["Body"].read())
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            )
            if status == 404:
                raise HTTPException(
                    status_code=404, detail="logo_not_found"
                ) from exc
            raise HTTPException(
                status_code=502, detail="storage_unavailable"
            ) from exc
    path = _branding_dir() / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="logo_not_found")
    return path.read_bytes()


def delete_branding_logo(key: str) -> None:
    try:
        if object_storage_enabled():
            _s3_client().delete_object(
                Bucket=settings.BODY_ANALYSIS_BUCKET, Key=key
            )
            return
        path = _branding_dir() / key
        path.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - best-effort cleanup
        logger.warning("could not delete branding logo %s", key)
