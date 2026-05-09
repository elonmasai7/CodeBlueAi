from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import structlog

logger = structlog.get_logger()


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class UserRole(str, Enum):
    ADMIN = "admin"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    RESIDENT = "resident"
    PHARMACIST = "pharmacist"
    READONLY = "readonly"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.READONLY
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    full_name: Optional[str] = None
    is_active: bool = True


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    exp: datetime
    iat: datetime = Field(default_factory=datetime.utcnow)
    token_type: TokenType = TokenType.ACCESS


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 28800


class Permission(str, Enum):
    READ_PATIENT = "read:patient"
    WRITE_PATIENT = "write:patient"
    READ_VITALS = "read:vitals"
    WRITE_VITALS = "write:vitals"
    READ_LABS = "read:labs"
    WRITE_LABS = "write:labs"
    RUN_ANALYSIS = "run:analysis"
    DISPATCH_ALERT = "dispatch:alert"
    VIEW_AUDIT = "view:audit"
    MANAGE_USERS = "manage:users"
    FHIR_READ = "fhir:read"
    FHIR_WRITE = "fhir:write"


ROLE_PERMISSIONS: Dict[UserRole, list[Permission]] = {
    UserRole.ADMIN: [p for p in Permission],
    UserRole.PHYSICIAN: [
        Permission.READ_PATIENT, Permission.WRITE_PATIENT,
        Permission.READ_VITALS, Permission.WRITE_VITALS,
        Permission.READ_LABS, Permission.WRITE_LABS,
        Permission.RUN_ANALYSIS, Permission.DISPATCH_ALERT,
        Permission.FHIR_READ, Permission.FHIR_WRITE,
    ],
    UserRole.NURSE: [
        Permission.READ_PATIENT, Permission.WRITE_PATIENT,
        Permission.READ_VITALS, Permission.WRITE_VITALS,
        Permission.READ_LABS, Permission.DISPATCH_ALERT,
        Permission.FHIR_READ,
    ],
    UserRole.RESIDENT: [
        Permission.READ_PATIENT,
        Permission.READ_VITALS, Permission.WRITE_VITALS,
        Permission.READ_LABS,
        Permission.RUN_ANALYSIS,
        Permission.FHIR_READ,
    ],
    UserRole.PHARMACIST: [
        Permission.READ_PATIENT,
        Permission.READ_VITALS,
        Permission.READ_LABS,
        Permission.FHIR_READ,
    ],
    UserRole.READONLY: [
        Permission.READ_PATIENT,
        Permission.READ_VITALS,
        Permission.READ_LABS,
        Permission.VIEW_AUDIT,
        Permission.FHIR_READ,
    ],
}


class RBACService:
    def __init__(self):
        self._cache: Dict[str, list[Permission]] = {}

    def get_permissions(self, role: UserRole) -> list[Permission]:
        return ROLE_PERMISSIONS.get(role, [])

    def has_permission(self, role: UserRole, permission: Permission) -> bool:
        return permission in self.get_permissions(role)

    def has_any_permission(self, role: UserRole, permissions: list[Permission]) -> bool:
        user_perms = self.get_permissions(role)
        return any(p in user_perms for p in permissions)

    def has_all_permissions(self, role: UserRole, permissions: list[Permission]) -> bool:
        user_perms = self.get_permissions(role)
        return all(p in user_perms for p in permissions)

    def filter_by_permission(self, role: UserRole, resources: list[Dict], permission: Permission) -> list[Dict]:
        if not self.has_permission(role, permission):
            return []
        return resources


rbac_service = RBACService()


def require_permission(*permissions: Permission):
    def decorator(func):
        func._required_permissions = permissions
        return func
    return decorator


def check_permission(role: UserRole, permission: Permission) -> bool:
    return rbac_service.has_permission(role, permission)
