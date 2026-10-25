from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep

router = APIRouter(tags=["utils"])


@router.get("/utils/health-check/")
def health_check() -> bool:
    """Liveness: the process is running and able to answer."""
    return True


@router.get("/utils/ready/")
def readiness_check(session: SessionDep) -> dict[str, str]:
    """Readiness: the process can reach its database dependency."""
    try:
        session.exec(select(1)).one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return {"status": "ready"}
