"""Vercel FastAPI entrypoint.

Vercel loads the top-level ``app`` object. The application lives in the
backend workspace, so prepend it to ``sys.path`` before importing.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402,F401

__all__ = ["app"]
