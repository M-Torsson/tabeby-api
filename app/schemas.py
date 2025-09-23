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


# ===== Secretary Code Generator Schemas =====

class SecretaryCodeRequest(BaseModel):
    clinic_id: int
    doctor_name: str
    secretary_name: str
    created_date: str  # format: "10/07/2025 10:00 am"

class SecretaryCodeResponse(BaseModel):
    secretary_id: int
    result: str = "successfuly"


# ===== Secretary Login Schemas =====

class SecretaryLoginRequest(BaseModel):
    secretary_code: int

class SecretaryLoginResponse(BaseModel):
    status: str = "successfuly"
    clinic_id: int
    secretary_id: str  # format: "S-{clinic_id}"
    doctor_name: str
    secretary_name: str
    created_date: str
    receiving_patients: int | None = None


# ===== Patient User Registration Schemas =====

class PatientUserRegisterRequest(BaseModel):
    user_uid: str
    user_role: str  # must be 'patient'
    phone_number: str

class PatientUserRegisterResponse(BaseModel):
    message: str = "ok"
    user_server_id: str  # formatted P-<id>
    user_role: str

# ===== Booking (Create Table) Schemas =====

class BookingCreateRequest(BaseModel):
    clinic_id: int
    days: dict  # raw nested day structure as provided

class BookingCreateResponse(BaseModel):
    status: str
    message: str
    capacity_total: int | None = None  # السعة المستنتجة أو المرسلة (إن وجدت) لإرجاعها في الاستجابة


# ===== Patient Booking Schemas =====

class PatientBookingRequest(BaseModel):
    # إما أن يرسل booking_id الجاهز أو يتركه ليُولد تلقائياً
    booking_id: str | None = None
    token: int | None = None  # اختياري، سيتم تجاهله إذا لا يطابق التسلسل المتوقع
    patient_id: str | None = None  # يمكن توليده تلقائياً حسب العيادة
    name: str
    phone: str
    source: Literal["patient_app", "secretary_app"]
    status: str | None = None  # يمكن إرسال قيمة إنجليزية وسيتم تحويلها للعربية
    created_at: str | None = None
    secretary_id: str | None = None  # فقط عند الحجز من السكرتير
    # في حال عدم إرسال booking_id نحتاج clinic_id + date
    clinic_id: int | None = None
    date: str | None = None  # صيغة YYYY-MM-DD

class PatientBookingResponse(BaseModel):
    message: str
    booking_id: str
    token: int
    capacity_used: int
    capacity_total: int
    status: str
    clinic_id: int
    date: str
    patient_id: str | None = None  # مُعاد الآن لإظهار رقم المراجع (يختلف حسب المصدر)


# ===== Add Day (Next Date) Schemas =====
class AddDayRequest(BaseModel):
    clinic_id: int
    # يمكن إرسال capacity_total مخصص؛ إن لم يُرسل ننسخ من آخر يوم موجود
    capacity_total: int | None = None
    # حالة اليوم الجديد (افتراضياً open)
    status: str | None = None  # مثال: open / closed
    # تخطي شرط امتلاء اليوم الأخير وإضافة اليوم الجديد بالقوة
    force_add: bool | None = False
    # تاريخ مخصص لإضافته (إن أُرسل نتجاهل حساب اليوم التالي)، يدعم أيضاً المفتاح date_added في الطلب
    date: str | None = Field(default=None, validation_alias="date_added")

class AddDayResponse(BaseModel):
    status: str  # نجاح / فشل عربي
    message: str
    date_added: str | None = None  # التاريخ الذي تم إضافته


# ===== Full Booking Days Fetch Schema =====
class BookingDaysFullResponse(BaseModel):
    clinic_id: int
    days: dict  # يحتوي نفس البنية المخزنة


# ===== Edit Patient Booking Status =====
class EditPatientBookingRequest(BaseModel):
    clinic_id: int
    booking_id: str  # إجباري الآن - نستخدمه لاستخراج التاريخ والمريض
    status: str  # يمكن إرسال إنجليزي (booked, served, ...) أو عربي

class EditPatientBookingResponse(BaseModel):
    message: str
    clinic_id: int
    booking_id: str
    old_status: str
    new_status: str


# ===== Save/Close Table Schemas =====
class SaveTableRequest(BaseModel):
    clinic_id: int
    # اسم الحقل الجديد: table_date (بدلاً من closed_date) ليطابق العمود الجديد
    table_date: str = Field(validation_alias="closed_date")  # YYYY-MM-DD (يقبل closed_date أيضاً للتوافق)
    # نجعل الحقول التالية اختيارية ليُمكن الاكتفاء بإرسال التاريخ فقط
    capacity_total: int | None = None
    capacity_served: int | None = None
    capacity_cancelled: int | None = None
    patients: list[dict] | None = None

class SaveTableResponse(BaseModel):
    status: str

class CloseTableRequest(BaseModel):
    clinic_id: int
    date: str  # التاريخ المراد حذفه

class CloseTableResponse(BaseModel):
    status: str
    removed_all: bool