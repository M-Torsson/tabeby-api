from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, Table, Text, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

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
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    # session metadata (تمت إزالة الأعمدة غير الموجودة من قاعدة البيانات)

    admin = relationship("Admin", back_populates="refresh_tokens")


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    used = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Activity(Base):
    __tablename__ = "activities"

    # معرف نصي (UUID مثلاً)
    id = Column(String, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, index=True, nullable=False)
    at = Column(DateTime, index=True, nullable=False, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ===== Doctor Profile (raw JSON persisted) =====

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, default="default")
    raw_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)