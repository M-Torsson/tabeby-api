from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Literal, Optional, List
from datetime import datetime

class PatientCreate(BaseModel):
    name: str
    email: EmailStr

class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr


# ===== Schemas for Admin/Auth =====
class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    is_active: bool
    is_superuser: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ===== User/Profile updates =====
class AdminUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SecurityUpdate(BaseModel):
    revoke_all_sessions: bool | None = None


class AdminBrief(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Literal["admin", "super-admin"]


class AdminAdminUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: Literal["admin", "super-admin"] | None = None
    active: bool | None = None


# ===== Password Reset Flow =====
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyResetResponse(BaseModel):
    valid: bool
    expires_in: int | None = None
    reason: Literal["invalid", "expired", "used"] | None = None


# ===== Activity =====
ActivityType = Literal[
    "password_changed",
    "login_new_device",
    "profile_updated",
    "security_modified",
    "document_downloaded",
    "new_device_registered",
    "failed_login_attempt",
    "account_recovery_initiated",
    "security_alert",
]

ActivityStatus = Literal["success", "warning", "error", "info"]


class ActivityCreate(BaseModel):
    email: Optional[EmailStr] = None
    type: ActivityType
    title: str
    description: Optional[str] = None
    at: Optional[datetime] = None
    status: ActivityStatus


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: ActivityType
    title: str
    description: Optional[str] = None
    status: ActivityStatus
    at: datetime


class ActivityListResponse(BaseModel):
    items: List[ActivityOut]
    total: int
    nextCursor: Optional[str] = None

