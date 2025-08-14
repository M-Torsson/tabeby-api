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
    two_factor_enabled: bool = False  # مُعاد للتوافق فقط (لا عمود في قاعدة البيانات)
    # RBAC derived fields for frontend
    is_admin: bool | None = None
    is_staff: bool | None = None
    role: str | None = None
    permissions: list[str] | None = None


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
    current: bool


# ===== RBAC (Roles/Permissions/Staff) =====
class RoleOut(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    permissions: list[str]


class PermissionList(BaseModel):
    items: list[str]


class StaffItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: Optional[str] = None
    role_id: Optional[int] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    status: Literal["active", "on_leave", "inactive"]
    avatar_url: Optional[str] = None
    created_at: datetime


class StaffListResponse(BaseModel):
    items: list[StaffItem]
    total: int


class StaffCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    role_id: Optional[int] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[Literal["active", "on_leave", "inactive"]] = None
    avatar_url: Optional[str] = None
    permissions: Optional[list[str]] = None


# ===== Recovery Codes =====
class RecoveryCodeOut(BaseModel):
    code: str
    used: bool


class RecoveryCodesResponse(BaseModel):
    codes: List[RecoveryCodeOut]

# ===== Departments =====

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    location: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    status: Optional[Literal['active', 'inactive']] = 'active'

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    location: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    status: Optional[Literal['active', 'inactive']] = None
    working_hours: Optional[str] = None
    budget: Optional[float] = None
    manager_id: Optional[int] = None

class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    staff_count: int = 0
    services_count: int = 0
    status: str
    location: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class DepartmentListResponse(BaseModel):
    items: List[DepartmentOut]
    total: int

class DepartmentStats(BaseModel):
    total_departments: int
    active_departments: int
    inactive_departments: int
    total_staff: int
    total_services: int
    growth_rate: float