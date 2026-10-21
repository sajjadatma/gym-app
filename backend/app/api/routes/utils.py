from fastapi import APIRouter

router = APIRouter(tags=["utils"])


@router.get("/utils/health-check/")
def health_check() -> bool:
    return True
