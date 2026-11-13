from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest,
    SendOtpRequest, VerifyOtpRequest
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.register(data)

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.login(data)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh_token(data.refresh_token)

@router.post("/otp/send")
async def send_mobile_otp(data: SendOtpRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.send_mobile_otp(data)

@router.post("/otp/verify")
async def verify_mobile_otp(data: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.verify_mobile_otp(data)

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"success": True, "message": "Logged out successfully"}
