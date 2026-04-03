from fastapi import APIRouter

from online_cinema.api.routes.auth import router as auth_router
from online_cinema.api.routes.commerce import admin_router as commerce_admin_router
from online_cinema.api.routes.commerce import router as commerce_router
from online_cinema.api.routes.health import router as health_router
from online_cinema.api.routes.movies import router as movies_router
from online_cinema.api.routes.users import admin_router
from online_cinema.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(movies_router, tags=["movies"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(commerce_router, tags=["commerce"])
api_router.include_router(commerce_admin_router, prefix="/admin", tags=["admin"])
