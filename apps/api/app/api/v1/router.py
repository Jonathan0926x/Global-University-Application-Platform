from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.applications import router as applications_router
from app.api.v1.preferences import router as preferences_router
from app.api.v1.documents import router as documents_router
from app.api.v1.counselor import router as counselor_router
from app.api.v1.institutions import router as institutions_router
from app.api.v1.requirements import router as requirements_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profiles_router)
api_router.include_router(institutions_router)
api_router.include_router(requirements_router)
api_router.include_router(applications_router)
api_router.include_router(preferences_router)
api_router.include_router(documents_router)
api_router.include_router(counselor_router)

