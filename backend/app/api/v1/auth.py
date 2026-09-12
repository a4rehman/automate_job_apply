from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserProfile
from app.models.automation import AutomationSettings
from app.schemas.auth import Token, UserRegister, UserLogin, UserResponse
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token)
async def register_user(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )
    
    # Create user
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create associated user profile
    profile = UserProfile(
        user_id=user.id,
        full_name=user_in.full_name or user_in.email.split("@")[0],
    )
    db.add(profile)

    # Create default automation settings
    auto_settings = AutomationSettings(
        user_id=user.id,
    )
    db.add(auto_settings)

    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)

    await audit_service.log_event(
        db=db,
        event_type="USER_REGISTERED",
        user_id=user.id,
        entity_type="USER",
        entity_id=user.id,
        details={"email": user.email}
    )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=profile.full_name
    )

@router.post("/login", response_model=Token)
async def login_user(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # Fetch profile for full name
    prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = prof_res.scalar_one_or_none()
    full_name = profile.full_name if profile else ""

    await audit_service.log_event(
        db=db,
        event_type="USER_LOGGED_IN",
        user_id=user.id,
        entity_type="USER",
        entity_id=user.id
    )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=full_name
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user
