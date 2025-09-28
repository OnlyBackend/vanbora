from fastapi import APIRouter
from src.presentation import auth, users, trips, reservations, health_check

router = APIRouter()

router.include_router(health_check.router, prefix="/api/v1", tags=["health"])
router.include_router(auth.router, prefix="/api/v1", tags=["auth"])
router.include_router(users.router, prefix="/api/v1", tags=["users"])
router.include_router(trips.router, prefix="/api/v1", tags=["trips"])
router.include_router(reservations.router, prefix="/api/v1", tags=["reservations"])