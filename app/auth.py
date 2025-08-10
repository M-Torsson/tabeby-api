from datetime import datetime, timezone, timedelta
import uuid
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models, schemas
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.Admin:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="رمز الوصول غير صالح")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نوع الرمز غير صحيح")

    jti = payload.get("jti")
    admin_id = payload.get("sub")
    if not jti or not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="رمز ناقص البيانات")

    # رفض الرمز إن كان في القائمة السوداء
    bl = db.query(models.BlacklistedToken).filter_by(jti=jti).first()
    if bl:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="تم تسجيل الخروج")

    admin = db.get(models.Admin, int(admin_id))
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="المستخدم غير متاح")

    return admin


@router.post("/admin/register", response_model=schemas.AdminOut, status_code=201)
async def register_admin(request: Request, db: Session = Depends(get_db)):
    # دعم JSON أو form/multipart
    content_type = request.headers.get("content-type", "").lower()
    name = email = password = None
    if content_type.startswith("application/json"):
        data = await request.json()
        name = (data.get("name") or data.get("fullName") or "").strip()
        email = (data.get("email") or "").strip()
        password = data.get("password")
    else:
        form = await request.form()
        name = (form.get("name") or form.get("fullName") or "").strip()
        email = (form.get("email") or "").strip()
        password = form.get("password")

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="يجب إرسال name, email, password")

    exists = db.query(models.Admin).filter_by(email=email).first()
    if exists:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

    admin = models.Admin(
        name=name,
        email=email,
        password_hash=get_password_hash(password),
        is_active=True,
        is_superuser=False,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # أعد نموذج Pydantic صريحاً من خصائص ORM
    return schemas.AdminOut.model_validate(admin, from_attributes=True)


@router.post("/login", response_model=schemas.TokenPair)
async def login(request: Request, db: Session = Depends(get_db)):
    # دعم JSON أو form: إذا كان Content-Type JSON نقرأ الحقول email/password، وإلا نقرأ form username/password
    email: Optional[str] = None
    password: Optional[str] = None

    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        data = await request.json()
        email = (data.get("email") or data.get("username") or "").strip()
        password = data.get("password")
    else:
        form = await request.form()
        # OAuth2 form uses 'username'
        email = (form.get("username") or form.get("email") or "").strip()
        password = form.get("password")

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="يجب إرسال البريد الإلكتروني وكلمة المرور")

    admin: Optional[models.Admin] = db.query(models.Admin).filter_by(email=email).first()
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="بيانات الدخول غير صحيحة")

    access = create_access_token(subject=str(admin.id))
    refresh = create_refresh_token(subject=str(admin.id))

    # خزّن رمز التحديث في قاعدة البيانات
    db.add(
        models.RefreshToken(
            jti=refresh["jti"],
            admin_id=admin.id,
            expires_at=refresh["exp"],
            revoked=False,
        )
    )
    db.commit()

    return {"access_token": access["token"], "refresh_token": refresh["token"]}


@router.post("/logout")
def logout(current_admin: models.Admin = Depends(get_current_admin), token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # ضع رمز الوصول في القائمة السوداء حتى انتهاء صلاحيته
    payload = decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        # exp من jose عادةً يكون رقم ثانية يونكس
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if isinstance(exp, int) else exp
        exists = db.query(models.BlacklistedToken).filter_by(jti=jti).first()
        if not exists:
            db.add(models.BlacklistedToken(jti=jti, expires_at=expires_at))
            db.commit()

    # ألغِ جميع رموز التحديث للحساب (خيار آمن لتسجيل الخروج الكامل)
    db.query(models.RefreshToken).filter_by(admin_id=current_admin.id, revoked=False).update({models.RefreshToken.revoked: True})
    db.commit()
    return {"message": "تم تسجيل الخروج بنجاح"}


@router.post("/change-password")
def change_password(payload: schemas.ChangePasswordRequest, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # تحقق من كلمة المرور الحالية
    if not verify_password(payload.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    # حدّث كلمة المرور
    current_admin.password_hash = get_password_hash(payload.new_password)
    db.add(current_admin)
    db.commit()
    return {"message": "تم تغيير كلمة المرور"}


@router.post("/refresh", response_model=schemas.TokenPair)
def refresh_tokens(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="رمز التحديث غير صالح")

    if data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نوع الرمز غير صحيح")

    jti = data.get("jti")
    admin_id = data.get("sub")
    if not jti or not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="رمز ناقص البيانات")

    # تحقق من الرمز في قاعدة البيانات
    rt: Optional[models.RefreshToken] = db.query(models.RefreshToken).filter_by(jti=jti).first()
    if not rt or rt.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="تم إلغاء الرمز")

    # افحص انتهاء الصلاحية
    if isinstance(rt.expires_at, datetime) and rt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="انتهت صلاحية الرمز")

    admin = db.get(models.Admin, int(admin_id))
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="المستخدم غير متاح")

    # دوّر الرمز: ألغِ القديم وأنشئ جديداً
    rt.revoked = True
    access = create_access_token(subject=str(admin.id))
    new_refresh = create_refresh_token(subject=str(admin.id))
    db.add(
        models.RefreshToken(
            jti=new_refresh["jti"],
            admin_id=admin.id,
            expires_at=new_refresh["exp"],
            revoked=False,
        )
    )
    db.commit()

    return {"access_token": access["token"], "refresh_token": new_refresh["token"]}


# ===== Password reset flow =====
RESET_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    # رد عام دائماً لمنع تسريب وجود البريد
    admin = db.query(models.Admin).filter_by(email=payload.email).first()
    if admin:
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex  # 64-hex
        expires_at = datetime.utcnow() + timedelta(minutes=RESET_EXPIRE_MINUTES)
        db.add(models.PasswordResetToken(token=raw_token, admin_id=admin.id, expires_at=expires_at, used=False))
        db.commit()
        # إرسال البريد يُنفّذ لاحقاً؛ نطبع الرابط أثناء التطوير فقط
        reset_link = f"{FRONTEND_BASE_URL}/auth/reset?token={raw_token}"
        print("[DEV] Reset link:", reset_link)
    return {"status": "sent"}


@router.get("/reset-password/verify", response_model=schemas.VerifyResetResponse)
def verify_reset_token(token: str, db: Session = Depends(get_db)):
    prt = db.query(models.PasswordResetToken).filter_by(token=token).first()
    if not prt:
        return {"valid": False, "reason": "invalid"}
    if prt.used:
        return {"valid": False, "reason": "used"}
    now = datetime.utcnow()
    if prt.expires_at < now:
        return {"valid": False, "reason": "expired"}
    expires_in = int((prt.expires_at - now).total_seconds())
    return {"valid": True, "expires_in": expires_in}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    prt = db.query(models.PasswordResetToken).filter_by(token=payload.token).first()
    if not prt:
        raise HTTPException(status_code=400, detail="invalid")
    if prt.used:
        raise HTTPException(status_code=410, detail="used")
    if prt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="expired")

    admin = db.get(models.Admin, prt.admin_id)
    if not admin:
        raise HTTPException(status_code=400, detail="invalid")

    # تعيين كلمة المرور الجديدة وإبطال الجلسات
    admin.password_hash = get_password_hash(payload.new_password)
    db.query(models.RefreshToken).filter_by(admin_id=admin.id, revoked=False).update({models.RefreshToken.revoked: True})
    prt.used = True

    db.add(admin)
    db.add(prt)
    db.commit()
    return {"status": "ok"}
