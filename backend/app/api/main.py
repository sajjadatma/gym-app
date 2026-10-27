from fastapi import APIRouter

from app.api.routes import (
    athletes,
    exercise_categories,
    exercises,
    gyms,
    login,
    people,
    programs,
    superuser_athletes,
    superuser_coaches,
    templates,
    users,
    utils,
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(gyms.router)
api_router.include_router(athletes.router)
api_router.include_router(superuser_coaches.router)
api_router.include_router(superuser_athletes.router)
api_router.include_router(people.router)
api_router.include_router(exercises.router)
api_router.include_router(exercise_categories.router)
api_router.include_router(programs.router)
api_router.include_router(templates.router)
api_router.include_router(utils.router)
