from fastapi import APIRouter

from app.api.routes import (
    athletes,
    exercises,
    gyms,
    login,
    programs,
    templates,
    users,
    utils,
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(gyms.router)
api_router.include_router(athletes.router)
api_router.include_router(exercises.router)
api_router.include_router(programs.router)
api_router.include_router(templates.router)
api_router.include_router(utils.router)
