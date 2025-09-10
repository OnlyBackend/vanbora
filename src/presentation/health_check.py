from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.infra.auth import authenticate_user, create_access_token
from datetime import timedelta

router = APIRouter()

@router.get("/health/")
async def health_check():
    return {"status": "healthy"}