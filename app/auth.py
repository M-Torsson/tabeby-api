from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
def register_admin(payload: schemas.AdminCreate, db: Session = Depends(get_db)):
    exists = db.query(models.Admin).filter_by(email=payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    admin = models.Admin(
        name=payload.name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@router.post("/login", response_model=schemas.TokenPair)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 form uses 'username' field; we'll treat it as email
    admin: Optional[models.Admin] = db.query(models.Admin).filter_by(email=form_data.username).first()
    if not admin or not verify_password(form_data.password, admin.password_hash):
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
