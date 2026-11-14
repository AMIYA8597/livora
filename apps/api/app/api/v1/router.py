from fastapi import APIRouter
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.profiles.router import router as profiles_router
from app.modules.lifestyle.router import router as lifestyle_router
from app.modules.properties.router import router as properties_router
from app.modules.search.router import router as search_router
from app.modules.flatmates.router import router as flatmates_router
from app.modules.matching.router import router as matching_router
from app.modules.groups.router import router as groups_router
from app.modules.applications.router import router as applications_router
from app.modules.appointments.router import router as appointments_router
from app.modules.owners.router import router as owners_router
from app.modules.tenants.router import router as tenants_router
from app.modules.pg_management.router import router as pg_router
from app.modules.messaging.router import router as messaging_router
from app.modules.notifications.router import router as notifications_router
from app.modules.verification.router import router as verification_router
from app.modules.moderation.router import router as moderation_router
from app.modules.administration.router import router as administration_router
from app.modules.storage.router import router as storage_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(profiles_router)
api_router.include_router(lifestyle_router)
api_router.include_router(properties_router)
api_router.include_router(search_router)
api_router.include_router(flatmates_router)
api_router.include_router(matching_router)
api_router.include_router(groups_router)
api_router.include_router(applications_router)
api_router.include_router(appointments_router)
api_router.include_router(owners_router)
api_router.include_router(tenants_router)
api_router.include_router(pg_router)
api_router.include_router(messaging_router)
api_router.include_router(notifications_router)
api_router.include_router(verification_router)
api_router.include_router(moderation_router)
api_router.include_router(administration_router)
api_router.include_router(storage_router)
