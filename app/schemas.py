# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


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
    refresh_token: str = Field(validation_alias="refreshToken")


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyResetResponse(BaseModel):
    valid: bool
    expires_in: int | None = None
    reason: Literal["invalid", "expired", "used"] | None = None


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


class TwoFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_svg: Optional[str] = None


class TwoFAEnableRequest(BaseModel):
    code: str


class TwoFAStatusResponse(BaseModel):
    two_factor_enabled: bool


class SessionOut(BaseModel):
    id: int
    current: bool


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


class RecoveryCodeOut(BaseModel):
    code: str
    used: bool


class RecoveryCodesResponse(BaseModel):
    codes: List[RecoveryCodeOut]


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



class SecretaryCodeRequest(BaseModel):
    clinic_id: int
    doctor_name: str
    secretary_name: str
    created_date: str  # format: "10/07/2025 10:00 am"

class SecretaryCodeResponse(BaseModel):
    secretary_id: int
    result: str = "successfuly"



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



class PatientUserRegisterRequest(BaseModel):
    user_uid: str
    user_role: str  # must be 'patient'
    phone_number: str

class PatientUserRegisterResponse(BaseModel):
    message: str = "ok"
    user_server_id: str  # formatted P-<id>
    user_role: str



class PatientProfileCreateRequest(BaseModel):
    user_server_id: str  # e.g., P-1
    patient_name: str
    phone_number: str
    gender: str | None = None
    date_of_birth: str | None = None  # keep as DD/MM/YYYY per your example

class PatientProfileResponse(BaseModel):
    id: int
    user_server_id: str
    patient_name: str
    phone_number: str
    gender: str | None = None
    date_of_birth: str | None = None
    is_active: bool = True  # حالة تفعيل المريض
    created_at: datetime
    updated_at: datetime


class BookingCreateRequest(BaseModel):
    clinic_id: int
    days: dict  # raw nested day structure as provided

class BookingCreateResponse(BaseModel):
    status: str
    message: str
    capacity_total: int | None = None  # السعة المستنتجة أو المرسلة (إن وجدت) لإرجاعها في الاستجابة



class PatientBookingRequest(BaseModel):
    booking_id: str | None = None
    token: int | None = None  # اختياري، سيتم تجاهله إذا لا يطابق التسلسل المتوقع
    patient_id: str | None = None  # يمكن توليده تلقائياً حسب العيادة
    name: str
    phone: str
    source: Literal["patient_app", "secretary_app"]
    status: str | None = None  # يمكن إرسال قيمة إنجليزية وسيتم تحويلها للعربية
    created_at: str | None = None
    secretary_id: str | None = None  # فقط عند الحجز من السكرتير
    clinic_id: int | None = None
    date: str | None = None  # صيغة YYYY-MM-DD (اختياري للمريض - سيبحث عن أقرب يوم متاح)

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


class AddDayRequest(BaseModel):
    clinic_id: int
    capacity_total: int | None = None
    status: str | None = None  # مثال: open / closed
    force_add: bool | None = False
    date: str | None = Field(default=None, validation_alias="date_added")

class AddDayResponse(BaseModel):
    status: str  # نجاح / فشل عربي
    message: str
    date_added: str | None = None  # التاريخ الذي تم إضافته


class BookingDaysFullResponse(BaseModel):
    clinic_id: int
    days: dict  # يحتوي نفس البنية المخزنة


class EditPatientBookingRequest(BaseModel):
    clinic_id: int
    booking_id: str  # إجباري الآن - نستخدمه لاستخراج التاريخ والمريض
    status: str  # يمكن إرسال أي نص مباشرة ("الغاء الحجز", "ملغى", "تم الحجز", إلخ)
    token: int | None = None  # اختياري - للحجوزات الذهبية: للبحث عن الحجز النشط فقط

class EditPatientBookingResponse(BaseModel):
    message: str
    clinic_id: int
    booking_id: str
    old_status: str
    new_status: str
    patient_id: str | None = None


class SaveTableRequest(BaseModel):
    clinic_id: int
    table_date: str = Field(validation_alias="closed_date")  # YYYY-MM-DD (يقبل closed_date أيضاً للتوافق)
    capacity_total: int | None = None
    capacity_served: int | None = None
    capacity_cancelled: int | None = None
    patients: list[dict] | None = None

class SaveTableResponse(BaseModel):
    status: str


class BookingArchiveItem(BaseModel):
    table_date: str
    capacity_total: int
    capacity_served: int | None = None
    capacity_cancelled: int | None = None
    patients: list[dict] = []  # مفكوك من patients_json

class BookingArchivesListResponse(BaseModel):
    clinic_id: int
    items: list[BookingArchiveItem]


class AllDaysResponse(BaseModel):
    clinic_id: int
    days: dict  # key=date string -> day object (capacity_total, patients, ...)

class CloseTableRequest(BaseModel):
    clinic_id: int
    date: str  # التاريخ المراد حذفه

class CloseTableResponse(BaseModel):
    status: str
    removed_all: bool


class GoldenTableCreateRequest(BaseModel):
    clinic_id: int
    days: dict  # بنفس شكل booking days

class GoldenTableCreateResponse(BaseModel):
    status: str
    message: str

class GoldenBookingRequest(BaseModel):
    clinic_id: int
    date: str  # YYYY-MM-DD
    patient_id: str
    name: str
    phone: str
    auto_assign: bool = True  # إذا كان True يبحث عن أقرب يوم متاح، False يحجز في التاريخ المحدد فقط

class GoldenBookingResponse(BaseModel):
    message: str
    code: str  # 4 digits
    booking_id: str
    token: int
    capacity_used: int
    capacity_total: int
    status: str
    clinic_id: int
    date: str
    patient_id: str | None = None


class VerifyGoldenCodeRequest(BaseModel):
    clinic_id: int
    code: str
    date: str | None = None  # اختياري - إذا لم يُرسل نبحث في كل التواريخ


class VerifyGoldenCodeResponse(BaseModel):
    status: str  # "success" أو "error"
    message: str | None = None
    patient_name: str | None = None
    patient_phone: str | None = None
    patient_id: str | None = None
    booking_id: str | None = None
    token: int | None = None
    booking_status: str | None = None
    booking_date: str | None = None


class ClinicStatusUpdateRequest(BaseModel):
    clinic_id: int
    is_closed: bool

class ClinicStatusResponse(BaseModel):
    clinic_id: int
    is_closed: bool


class GoldenPatientPaymentRequest(BaseModel):
    clinic_id: int
    exam_date: str  # Format: DD/MM/YYYY
    book_status: str
    patient_name: str
    booking_id: str
    code: str

class GoldenPatientPaymentResponse(BaseModel):
    message: str
    booking_id: str
    patient_name: str
    amount: int
    payment_month: str
    payment_status: Optional[str] = None  # لا يظهر في response