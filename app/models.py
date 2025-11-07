from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, Table, Text, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
from .timezone_utils import now_utc_for_storage

# ===== User Accounts (role + phone, global id) =====

class UserAccount(Base):
    __tablename__ = "user_accounts"

    # هذا هو user_server_id الذي سنعيده للفرونت
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uid = Column(String, nullable=True, index=True)  # Firebase UID أو معرف خارجي
    user_role = Column(String, nullable=False, index=True)  # patient | secretary | doctor
    phone_number = Column(String, nullable=False, unique=True, index=True)
    # روابط اختيارية إلى جداول المجال
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=now_utc_for_storage)


# ===== Patient Profile (per user account) =====

class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_account_id = Column(Integer, ForeignKey("user_accounts.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    patient_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False, index=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)  # keep as provided format (e.g., DD/MM/YYYY)
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # حالة تفعيل المريض
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_utc_for_storage)
    # تمت إزالة دعم 2FA وتفضيلات التنبيه لتبسيط النظام

    refresh_tokens = relationship("RefreshToken", back_populates="admin", cascade="all, delete-orphan")

    # RBAC linkage: an admin may also be a staff member (optional)
    staff = relationship("Staff", back_populates="admin", uselist=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=now_utc_for_storage)
    # session metadata (تمت إزالة الأعمدة غير الموجودة من قاعدة البيانات)

    admin = relationship("Admin", back_populates="refresh_tokens")


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now_utc_for_storage)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=now_utc_for_storage)


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    used = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=now_utc_for_storage)


class Activity(Base):
    __tablename__ = "activities"

    # معرف نصي (UUID مثلاً)
    id = Column(String, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, index=True, nullable=False)
    at = Column(DateTime, index=True, nullable=False, default=now_utc_for_storage)

# فهارس مفيدة
Index("ix_activities_admin_at_desc", Activity.admin_id, Activity.at.desc()) if False else None

# ===== RBAC: Roles, Permissions, Staff =====


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # relationship to role-permissions and staff
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    staff = relationship("Staff", back_populates="role")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False)
    permission = Column(String, index=True, nullable=False)
    __table_args__ = (
        UniqueConstraint("role_id", "permission", name="uq_role_permission"),
    )

    role = relationship("Role", back_populates="permissions")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), index=True, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), index=True, nullable=True)
    role_key = Column(String, nullable=True)  # denormalized for quick reads
    department = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    status = Column(String, index=True, nullable=False, default="active")
    avatar_url = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)  # optional credential for staff login (separate from admins)
    created_at = Column(DateTime, default=now_utc_for_storage)

    admin = relationship("Admin", back_populates="staff")
    role = relationship("Role", back_populates="staff")

    # direct extra permissions (optional per-user overrides)
    permissions = relationship("StaffPermission", back_populates="staff", cascade="all, delete-orphan")


class StaffPermission(Base):
    __tablename__ = "staff_permissions"

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), index=True, nullable=False)
    permission = Column(String, index=True, nullable=False)
    __table_args__ = (
        UniqueConstraint("staff_id", "permission", name="uq_staff_permission"),
    )

    staff = relationship("Staff", back_populates="permissions")

# ===== Departments =====

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    head_of_department = Column(String(255), nullable=True)
    staff_count = Column(Integer, default=0)
    services_count = Column(Integer, default=0)
    status = Column(String(20), default='active')
    location = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    working_hours = Column(String(255), nullable=True)
    budget = Column(DECIMAL(10, 2), nullable=True)
    manager_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

# ===== Doctor Profile (raw JSON persisted) =====

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, default="default")
    raw_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

# ===== Doctors (denormalized + raw profile_json) =====

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    image_url = Column(String, nullable=True)
    specialty = Column(String, nullable=True, index=True)
    clinic_state = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    experience_years = Column(Integer, nullable=True)
    patients_count = Column(Integer, nullable=True)
    profile_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

# ===== Secretaries (for secretary code generation) =====

class Secretary(Base):
    __tablename__ = "secretaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    secretary_id = Column(Integer, unique=True, index=True, nullable=False)  # 6-digit generated code
    clinic_id = Column(Integer, index=True, nullable=False)
    doctor_name = Column(String, nullable=False)
    secretary_name = Column(String, nullable=False)
    created_date = Column(String, nullable=False)  # storing as string as per API spec
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # حالة تفعيل السكرتير
    created_at = Column(DateTime, default=now_utc_for_storage)


# ===== Ads (raw JSON payload per clinic) =====

class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    # store the full ad JSON (normalized) exactly as sent by client
    payload_json = Column(Text, nullable=False)
    ad_status = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_utc_for_storage)

    # helpful index
    __table_args__ = (
        Index("ix_ads_clinic_id_created", "clinic_id", "created_at"),
    )

# ===== Booking Tables (per clinic, days JSON) =====

class BookingTable(Base):
    __tablename__ = "booking_tables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    days_json = Column(Text, nullable=False)  # full JSON structure of days
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)
    __table_args__ = (
        Index("ix_booking_tables_clinic", "clinic_id"),
    )


# ===== Booking Archived Days (each saved/closed day in its own row) =====

class BookingArchive(Base):
    __tablename__ = "booking_archives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    # اليوم المؤرشف (date فقط بدون وقت)
    table_date = Column(String, nullable=False, index=True)  # صيغة YYYY-MM-DD
    capacity_total = Column(Integer, nullable=False)
    capacity_served = Column(Integer, nullable=True)
    capacity_cancelled = Column(Integer, nullable=True)
    patients_json = Column(Text, nullable=False)  # نسخة مبسطة من المرضى
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

    __table_args__ = (
        Index("ix_booking_archives_clinic_date", "clinic_id", "table_date"),
    )


# ===== Golden Booking Table (separate from regular bookings) =====

class GoldenBookingTable(Base):
    __tablename__ = "golden_booking_tables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    days_json = Column(Text, nullable=False)  # golden book days structure
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)
    __table_args__ = (
        Index("ix_golden_booking_tables_clinic", "clinic_id"),
    )


# ===== Golden Booking Archives =====

class GoldenBookingArchive(Base):
    __tablename__ = "golden_booking_archives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    table_date = Column(String, nullable=False, index=True)  # YYYY-MM-DD
    capacity_total = Column(Integer, nullable=False)
    capacity_served = Column(Integer, nullable=True)
    capacity_cancelled = Column(Integer, nullable=True)
    patients_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)

    __table_args__ = (
        Index("ix_golden_booking_archives_clinic_date", "clinic_id", "table_date"),
    )


# ===== Clinic Status (track if clinic is open/closed) =====

class ClinicStatus(Base):
    __tablename__ = "clinic_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, unique=True, index=True, nullable=False)
    is_closed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)


# ===== Golden Payments (track monthly payments for golden bookings) =====

class GoldenPayment(Base):
    __tablename__ = "golden_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(Integer, index=True, nullable=False)
    booking_id = Column(String(255), unique=True, nullable=False, index=True)
    patient_name = Column(String(255), nullable=False)
    code = Column(String(4), nullable=False)
    exam_date = Column(String(20), nullable=False)
    book_status = Column(String(50), nullable=False, default="تمت المعاينة")
    amount = Column(Integer, nullable=False, default=1500)
    payment_month = Column(String(7), nullable=False, index=True)  # Format: YYYY-MM
    payment_status = Column(String(20), nullable=False, default="not_paid", index=True)
    created_at = Column(DateTime, default=now_utc_for_storage)
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)
    
    __table_args__ = (
        Index("ix_golden_payments_clinic_month", "clinic_id", "payment_month"),
    )


# ===== App Maintenance Mode =====

class AppMaintenance(Base):
    """جدول لإدارة وضع الصيانة للتطبيق"""
    __tablename__ = "app_maintenance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    message_ar = Column(Text, nullable=True)  # الرسالة بالعربي
    message_en = Column(Text, nullable=True)  # الرسالة بالإنجليزي
    updated_at = Column(DateTime, default=now_utc_for_storage, onupdate=now_utc_for_storage)
    updated_by = Column(String, nullable=True)  # من قام بالتحديث
