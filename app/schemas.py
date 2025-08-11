from pydantic import BaseModel, EmailStr, ConfigDict, Field
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
    two_factor_enabled: bool | None = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    token_type: str = Field(default="bearer", serialization_alias="tokenType")


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    # يقبل refreshToken (camelCase) و refresh_token (snake_case)
    refresh_token: str = Field(validation_alias="refreshToken")


# ===== User/Profile updates =====
class AdminUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SecurityUpdate(BaseModel):
    revoke_all_sessions: bool | None = None
    two_factor_enabled: bool | None = None
    email_security_alerts: bool | None = None
    push_login_alerts: bool | None = None
    critical_only: bool | None = None


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


# ===== Two-Factor Auth (2FA) =====
class TwoFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_svg: Optional[str] = None


class TwoFAEnableRequest(BaseModel):
    code: str


class TwoFAStatusResponse(BaseModel):
    two_factor_enabled: bool


# ===== Sessions =====
class SessionOut(BaseModel):
    id: int
    device: Optional[str] = None
    ip: Optional[str] = None
    last_seen: Optional[datetime] = None
    current: bool


# ===== Recovery Codes =====
class RecoveryCodeOut(BaseModel):
    code: str
    used: bool


class RecoveryCodesResponse(BaseModel):
    codes: List[RecoveryCodeOut]

