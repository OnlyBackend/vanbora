from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.schemas import UserCreate, UserOut
from src.domain.models import User
from src.infra.database import get_db
from src.infra.auth import get_password_hash, get_current_active_user
from src.infra.repositories import UserRepository

router = APIRouter()

@router.post("/register/", response_model=UserOut)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await UserRepository.get_by_username(db, user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_driver=user_in.is_driver,
        pix_key=user_in.pix_key if user_in.is_driver else None,  # só motorista
        balance=0 
    )
    user = await UserRepository.create(db, user)
    return user

@router.get("/users/me/", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user 