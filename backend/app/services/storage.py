from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "application/pdf": (".pdf", b"%PDF"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


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

    settings.BODY_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = settings.BODY_ANALYSIS_DIR / stored_name
    destination.write_bytes(data)
    return original_name[:255], stored_name, len(data)


def delete_stored_file(stored_name: str) -> None:
    path = settings.BODY_ANALYSIS_DIR / stored_name
    if path.parent != settings.BODY_ANALYSIS_DIR:
        return
    path.unlink(missing_ok=True)


def delete_stored_files(stored_names: Iterable[str]) -> None:
    """Best-effort, idempotent removal of stored files after a DB rollback/commit.

    Callers only run this once the database state is final: after a successful
    commit when deleting records, or after a rollback when an upload was not
    persisted. A failed unlink therefore leaves a harmless orphan file instead
    of a row that points at a missing file.
    """
    for stored_name in stored_names:
        try:
            delete_stored_file(stored_name)
        except OSError:
            logger.warning("could not delete body analysis file %s", stored_name)


def stored_file_path(stored_name: str) -> Path:
    path = settings.BODY_ANALYSIS_DIR / stored_name
    if path.parent != settings.BODY_ANALYSIS_DIR or not path.exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    return path
