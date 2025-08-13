from io import StringIO
import csv
from fastapi import APIRouter, Depends, HTTPException
import secrets
import importlib
from typing import Any
 
# Dynamically import pyotp to avoid static analysis import errors; fail gracefully at runtime if missing
try:
    pyotp: Any = importlib.import_module("pyotp")  # type: ignore
except Exception:
    pyotp = None  # type: ignore
from sqlalchemy.orm import Session

from .auth import get_current_admin, get_db, oauth2_scheme
from .security import decode_token
from . import models, schemas
from .rbac import all_permissions, default_roles

router = APIRouter(prefix="/users", tags=["Users"])


def _require_pyotp():
    if pyotp is None:  # type: ignore
        raise HTTPException(status_code=500, detail="pyotp is not installed. Please install 'pyotp' in the active environment.")


@router.get("/me", response_model=schemas.AdminOut)
def get_me(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """
    نقطة موحّدة تُعيد معلومات المستخدم سواء كان أدمن أو موظف.
    - إذا كان رمز JWT من نوع access (أدمن) => تُعيد بيانات الأدمن.
    - إذا كان من نوع staff => تُعيد بيانات الموظف بصيغة AdminOut (مع is_staff=True).
    هذا يمنع تسجيل الخروج الفوري عندما يستدعي الفرونت /users/me برمز موظف.
    """
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="رمز الوصول غير صالح")

    t = data.get("type")
    if t == "access":
        # تحقق من القائمة السوداء وحالة الأدمن
        jti = data.get("jti")
        sub = data.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
        if jti:
            bl = db.query(models.BlacklistedToken).filter_by(jti=jti).first()
            if bl:
                raise HTTPException(status_code=401, detail="تم تسجيل الخروج")
        admin = db.query(models.Admin).filter_by(id=int(sub)).first()
        if not admin or not getattr(admin, "is_active", True):
            raise HTTPException(status_code=401, detail="المستخدم غير متاح")
        # اشتق الدور والصلاحيات الافتراضية للأدمن
        if getattr(admin, "is_superuser", False):
            role_key = "super-admin"
            perms = all_permissions()
        else:
            role_key = "admin"
            perms = default_roles().get("admin", {}).get("permissions", [])
        return schemas.AdminOut(
            id=admin.id,
            name=admin.name,
            email=admin.email,
            is_active=getattr(admin, "is_active", True),
            is_superuser=getattr(admin, "is_superuser", False),
            two_factor_enabled=False,
            is_admin=True,
            is_staff=False,
            role=role_key,
            permissions=perms,
        )

    if t == "staff":
        sub = data.get("sub")
        if not sub or not str(sub).startswith("staff:"):
            raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
        staff_id = int(str(sub).split(":", 1)[1])
        # حمّل أعمدة آمنة فقط
        from sqlalchemy.orm import load_only
        s = (
            db.query(models.Staff)
            .options(load_only(
                models.Staff.id,
                models.Staff.name,
                models.Staff.email,
                models.Staff.role_id,
                models.Staff.role_key,
                models.Staff.status,
            ))
            .filter_by(id=staff_id)
            .first()
        )
        if not s or (s.status or "active") != "active":
            raise HTTPException(status_code=401, detail="المستخدم غير متاح")
        # اجمع صلاحيات الدور + صلاحيات مباشرة للموظف
        perms: set[str] = set()
        if s.role_id:
            rps = db.query(models.RolePermission).filter_by(role_id=s.role_id).all()
            perms.update(p.permission for p in rps)
        dps = db.query(models.StaffPermission).filter_by(staff_id=s.id).all()
        perms.update(p.permission for p in dps)
        return schemas.AdminOut(
            id=s.id,
            name=s.name,
            email=s.email,
            is_active=True,
            is_superuser=False,
            two_factor_enabled=False,
            is_admin=False,
            is_staff=True,
            role=s.role_key or "staff",
            permissions=sorted(perms),
        )

    # نوع غير متوقع
    raise HTTPException(status_code=401, detail="نوع الرمز غير صحيح")


@router.patch("/me", response_model=schemas.AdminOut)
def update_me(payload: schemas.AdminUpdate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    changed = False
    if payload.name is not None:
        current_admin.name = payload.name
        changed = True
    if payload.email is not None:
        # تأكد من عدم تكرار البريد
        exists = db.query(models.Admin).filter(models.Admin.email == payload.email, models.Admin.id != current_admin.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        current_admin.email = payload.email
        changed = True
    if changed:
        db.add(current_admin)
        db.commit()
        db.refresh(current_admin)
    return schemas.AdminOut.model_validate(current_admin, from_attributes=True)


@router.get("/me/export")
def export_me(current_admin: models.Admin = Depends(get_current_admin)):
    # صدر البيانات كـ CSV نصي بسيط
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "is_active", "is_superuser"]) 
    writer.writeheader()
    writer.writerow({
        "id": current_admin.id,
        "name": current_admin.name,
        "email": current_admin.email,
        "is_active": current_admin.is_active,
        "is_superuser": current_admin.is_superuser,
    })
    return {"filename": "me.csv", "content": output.getvalue()}


@router.patch("/me/security")
def update_security(payload: schemas.SecurityUpdate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # إلغاء الجلسات فقط (أزلنا 2FA والتفضيلات)
    if payload.revoke_all_sessions:
        db.query(models.RefreshToken).filter_by(admin_id=current_admin.id, revoked=False).update({models.RefreshToken.revoked: True})
        db.commit()
    return {"message": "تم"}


@router.get("/me/security")
def get_security(current_admin: models.Admin = Depends(get_current_admin)):
    return {}


# تم حذف مسارات 2FA بالكامل


# ===== Sessions =====
@router.get("/me/sessions", response_model=list[schemas.SessionOut])
def list_sessions(current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    from sqlalchemy.orm import load_only
    sessions = db.query(models.RefreshToken)
    sessions = sessions.options(
        load_only(
            models.RefreshToken.id,
            models.RefreshToken.jti,
            models.RefreshToken.admin_id,
            models.RefreshToken.expires_at,
            models.RefreshToken.revoked,
            models.RefreshToken.created_at,
        )
    ).filter_by(admin_id=current_admin.id, revoked=False)
    sessions = sessions.order_by(models.RefreshToken.created_at.desc()).all()
    # حدد current بمطابقة sid من رمز الوصول مع jti لرمز التحديث
    sid = None
    try:
        payload = decode_token(token)
        sid = payload.get("sid")
    except Exception:
        sid = None
    out = []
    for s in sessions:
        out.append({
            "id": s.id,
            "current": True if sid and sid == s.jti else False,
        })
    return out


# ===== Recovery Codes =====
def _generate_recovery_codes(n: int = 10) -> list[str]:
    return [secrets.token_hex(4) + "-" + secrets.token_hex(4) for _ in range(n)]


@router.get("/me/recovery-codes", response_model=schemas.RecoveryCodesResponse)
def get_recovery_codes(current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.query(models.RecoveryCode).filter_by(admin_id=current_admin.id).order_by(models.RecoveryCode.created_at.desc()).all()
    codes = [{"code": r.code, "used": r.used} for r in rows]
    return {"codes": codes}


@router.post("/me/recovery-codes", response_model=schemas.RecoveryCodesResponse)
def rotate_recovery_codes(rotate: bool | None = None, current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    # احذف القديمة ثم أنشئ مجموعة جديدة
    db.query(models.RecoveryCode).filter_by(admin_id=current_admin.id).delete()
    codes = _generate_recovery_codes(10)
    for c in codes:
        db.add(models.RecoveryCode(admin_id=current_admin.id, code=c, used=False))
    db.commit()
    return {"codes": [{"code": c, "used": False} for c in codes]}
