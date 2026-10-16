from fastapi import APIRouter

from app.api import applications, cover_letters, cv_generations, jobs, usage

api_router = APIRouter()
api_router.include_router(jobs.router)
api_router.include_router(cv_generations.router)
api_router.include_router(cover_letters.router)
api_router.include_router(applications.router)
api_router.include_router(usage.router)
