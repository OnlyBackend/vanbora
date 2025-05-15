from fastapi import APIRouter
from src.presentation import auth, users, trips, reservations

router = APIRouter()

router.include_router(auth.router, prefix="/api", tags=["auth"])
router.include_router(users.router, prefix="/api", tags=["users"])
router.include_router(trips.router, prefix="/api", tags=["trips"])
router.include_router(reservations.router, prefix="/api", tags=["reservations"]) 