from fastapi import APIRouter, Depends, HTTPException, Query, Form
from typing import Optional, Dict, Any
from pydantic import BaseModel

from backend.services.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_user, TokenPayload
)
from backend.services.security import UserRole, UserCreate, UserResponse, rbac_service, Permission
from backend.db.session import get_db_session
from backend.models.models import User
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "readonly"
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


DEMO_USERS = {
    "admin": {
        "id": "user_admin_001",
        "username": "admin",
        "email": "admin@hospital.org",
        "password_hash": hash_password("Admin123!"),
        "role": UserRole.ADMIN,
        "full_name": "System Administrator",
        "is_active": True,
    },
    "physician": {
        "id": "user_phys_001",
        "username": "physician",
        "email": "dr.smith@hospital.org",
        "password_hash": hash_password("Physician123!"),
        "role": UserRole.PHYSICIAN,
        "full_name": "Dr. James Smith",
        "is_active": True,
    },
    "nurse": {
        "id": "user_nurse_001",
        "username": "nurse",
        "email": "nurse.jones@hospital.org",
        "password_hash": hash_password("Nurse123!"),
        "role": UserRole.NURSE,
        "full_name": "Sarah Jones, RN",
        "is_active": True,
    },
}


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    if request.username in DEMO_USERS:
        raise HTTPException(status_code=400, detail="Username already exists")

    role = UserRole(request.role) if request.role in [r.value for r in UserRole] else UserRole.READONLY
    user_id = f"user_{uuid.uuid4().hex[:8]}"

    DEMO_USERS[request.username] = {
        "id": user_id,
        "username": request.username,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "role": role,
        "full_name": request.full_name or request.username,
        "is_active": True,
    }

    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=28800,
        user={
            "id": user_id,
            "username": request.username,
            "email": request.email,
            "role": role.value,
            "full_name": request.full_name,
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user_data = DEMO_USERS.get(request.username)

    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(request.password, user_data["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user_data["is_active"]:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(user_data["id"], user_data["role"])
    refresh_token = create_refresh_token(user_data["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=28800,
        user={
            "id": user_data["id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"].value,
            "full_name": user_data["full_name"],
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    payload = decode_token(request.refresh_token)
    if not payload or payload.token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_data = None
    for ud in DEMO_USERS.values():
        if ud["id"] == payload.sub:
            user_data = ud
            break

    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user_data["id"], user_data["role"])
    new_refresh = create_refresh_token(user_data["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=28800,
        user={
            "id": user_data["id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"].value,
            "full_name": user_data["full_name"],
        }
    )


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(user: TokenPayload = Depends(get_current_user)):
    for ud in DEMO_USERS.values():
        if ud["id"] == user.sub:
            return {
                "id": ud["id"],
                "username": ud["username"],
                "email": ud["email"],
                "role": ud["role"].value,
                "full_name": ud["full_name"],
                "permissions": [p.value for p in rbac_service.get_permissions(ud["role"])],
            }

    return {
        "id": user.sub,
        "username": "unknown",
        "role": user.role.value,
        "permissions": [p.value for p in rbac_service.get_permissions(user.role)],
    }


@router.get("/permissions")
async def list_permissions(user: TokenPayload = Depends(get_current_user)):
    return {
        "role": user.role.value,
        "permissions": [p.value for p in rbac_service.get_permissions(user.role)],
    }
