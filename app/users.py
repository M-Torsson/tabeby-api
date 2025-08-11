from io import StringIO
import csv
from fastapi import APIRouter, Depends, HTTPException
import secrets
import pyotp
from sqlalchemy.orm import Session

from .auth import get_current_admin, get_db, oauth2_scheme
from .security import decode_token
from . import models, schemas

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=schemas.AdminOut)
def get_me(current_admin: models.Admin = Depends(get_current_admin)):
    return schemas.AdminOut.model_validate(current_admin, from_attributes=True)


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
    # إلغاء الجلسات
    if payload.revoke_all_sessions:
        db.query(models.RefreshToken).filter_by(admin_id=current_admin.id, revoked=False).update({models.RefreshToken.revoked: True})
    # تحديث تفضيلات الأمان
    updated = False
    for field in ["two_factor_enabled", "email_security_alerts", "push_login_alerts", "critical_only"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(current_admin, field, val)
            updated = True
    if updated:
        db.add(current_admin)
    db.commit()
    return {"message": "تم تحديث إعدادات الأمان"}


# ===== 2FA =====
@router.post("/me/2fa/setup", response_model=schemas.TwoFASetupResponse)
def setup_2fa(current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    # أنشئ سرّ TOTP جديد واحفظه مؤقتاً في two_factor_secret
    secret = pyotp.random_base32()
    current_admin.two_factor_secret = secret
    db.add(current_admin)
    db.commit()

    # otpauth URL
    issuer = "Tabeby"
    otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(name=current_admin.email, issuer_name=issuer)

    # QR SVG (اختياري): سنعيد None لتبسيط التنفيذ الآن
    return {"secret": secret, "otpauth_url": otpauth_url, "qr_svg": None}


@router.post("/me/2fa/enable", response_model=schemas.TwoFAStatusResponse)
def enable_2fa(payload: schemas.TwoFAEnableRequest, current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    if not current_admin.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA secret not initialized")
    totp = pyotp.TOTP(current_admin.two_factor_secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    current_admin.two_factor_enabled = True
    db.add(current_admin)
    db.commit()
    return {"two_factor_enabled": True}


@router.post("/me/2fa/disable", response_model=schemas.TwoFAStatusResponse)
def disable_2fa(payload: schemas.TwoFAEnableRequest | None = None, current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    # يمكن اشتراط كود لتعطيل 2FA
    if current_admin.two_factor_enabled and payload and current_admin.two_factor_secret:
        totp = pyotp.TOTP(current_admin.two_factor_secret)
        if not totp.verify(payload.code, valid_window=1):
            raise HTTPException(status_code=400, detail="Invalid 2FA code")
    current_admin.two_factor_enabled = False
    current_admin.two_factor_secret = None
    db.add(current_admin)
    db.commit()
    return {"two_factor_enabled": False}


# ===== Sessions =====
@router.get("/me/sessions", response_model=list[schemas.SessionOut])
def list_sessions(current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    sessions = db.query(models.RefreshToken).filter_by(admin_id=current_admin.id, revoked=False).order_by(models.RefreshToken.created_at.desc()).all()
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
            "device": s.device,
            "ip": s.ip,
            "last_seen": s.last_seen,
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
