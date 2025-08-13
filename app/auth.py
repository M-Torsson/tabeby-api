from datetime import datetime, timezone, timedelta
import uuid
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, load_only
from sqlalchemy import text, func

from .database import SessionLocal
from . import models, schemas
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from .mailer import send_password_reset

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

    # حمّل فقط الأعمدة اللازمة لتجنّب فشل SELECT إذا كانت أعمدة اختيارية غير موجودة في المخطط
    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.is_active, models.Admin.is_superuser))
        .filter_by(id=int(admin_id))
        .first()
    )
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="المستخدم غير متاح")

    return admin


@router.get("/me", response_model=schemas.AdminOut)
def auth_me(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """يعيد معلومات المستخدم لكلاً من الأدمن والموظف لمنع تسجيل الخروج عند التحديث."""
    from .rbac import all_permissions, default_roles
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="رمز الوصول غير صالح")
    t = data.get("type")
    if t == "access":
        sub = data.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
        admin = db.query(models.Admin).filter_by(id=int(sub)).first()
        if not admin or not getattr(admin, "is_active", True):
            raise HTTPException(status_code=401, detail="المستخدم غير متاح")
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
    elif t == "staff":
        sub = data.get("sub")
        if not sub or not str(sub).startswith("staff:"):
            raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
        staff_id = int(str(sub).split(":", 1)[1])
        from sqlalchemy.orm import load_only
        s = (
            db.query(models.Staff)
            .options(load_only(models.Staff.id, models.Staff.name, models.Staff.email, models.Staff.role_key, models.Staff.role_id, models.Staff.status))
            .filter_by(id=staff_id)
            .first()
        )
        if not s or (s.status or "active") != "active":
            raise HTTPException(status_code=401, detail="المستخدم غير متاح")
        # اجمع صلاحيات الدور الافتراضي لعرضها (اختياري)
        try:
            perms = default_roles().get(s.role_key or "staff", {}).get("permissions", [])
        except Exception:
            perms = []
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
            permissions=perms,
        )
    else:
        raise HTTPException(status_code=401, detail="نوع الرمز غير صحيح")


@router.post("/admin/register", response_model=schemas.AdminOut, status_code=201)
async def register_admin(request: Request, db: Session = Depends(get_db)):
    # دعم JSON أو form/multipart
    content_type = request.headers.get("content-type", "").lower()
    name = email = password = None
    if content_type.startswith("application/json"):
        data = await request.json()
        name = (data.get("name") or data.get("fullName") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password")
    else:
        form = await request.form()
        name = (form.get("name") or form.get("fullName") or "").strip()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password")

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="يجب إرسال name, email, password")

    # تحقق بشكل غير حساس لحالة الأحرف لتجنّب تكرار بنفس البريد بحروف كبيرة/صغيرة
    exists = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email))
        .filter(func.lower(models.Admin.email) == email)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

    # حاول الإدراج عبر ORM، وإن فشل بسبب أعمدة غير موجودة (مخطط قديم) فسنستخدم إدراجاً ديناميكياً حسب الأعمدة المتاحة
    admin = models.Admin(
        name=name,
        email=email,
        password_hash=get_password_hash(password),
        is_active=True,
        is_superuser=False,
    )
    try:
        db.add(admin)
        db.commit()
        # ابنِ الاستجابة من حقول معروفة لتجنّب تحميل أعمدة غير موجودة
        return schemas.AdminOut.model_validate({
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "is_active": admin.is_active,
            "is_superuser": admin.is_superuser,
            "two_factor_enabled": False,
        })
    except Exception as e:
        db.rollback()
        print("[WARN] admins insert via ORM failed, trying dynamic insert:", e)
        try:
            cols_res = db.execute(
                text(
                    """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'admins' AND table_schema = 'public'
                    """
                )
            )
            cols = [(r[0], (r[1] or '').upper(), r[2]) for r in cols_res]
            available_cols = {c for c, _, _ in cols}
            must_have = {c for c, nul, d in cols if nul == 'NO' and d is None}
            now = datetime.utcnow()
            base_values = {
                "name": name,
                "email": email,
                "password_hash": get_password_hash(password),
                "is_active": True,
                "is_superuser": False,
                "created_at": now,
                # الأعمدة الاختيارية الجديدة، إن وُجدت سنمرر قيمها الافتراضية
                # أزلنا أعمدة التفضيلات / 2FA إن وُجدت سابقاً
            }
            use_keys = [k for k in base_values.keys() if k in available_cols]
            missing_required = [k for k in must_have if k not in use_keys and k not in {"id"}]
            if missing_required:
                # في جداول قديمة، عادة لا توجد أعمدة إلزامية إضافية
                raise RuntimeError(f"admins missing required cols without defaults: {missing_required}")
            columns_csv = ", ".join(use_keys)
            placeholders = ", ".join(f":{k}" for k in use_keys)
            sql = f"INSERT INTO admins ({columns_csv}) VALUES ({placeholders})"
            params = {k: base_values[k] for k in use_keys}
            db.execute(text(sql), params)
            db.commit()
            # اجلب السجل الذي أُدرج للتو بأعمدة آمنة
            admin_row = (
                db.query(models.Admin)
                .options(load_only(models.Admin.id, models.Admin.name, models.Admin.email, models.Admin.is_active, models.Admin.is_superuser))
                .filter(func.lower(models.Admin.email) == email)
                .first()
            )
            if not admin_row:
                raise HTTPException(status_code=500, detail="database_error")
            return schemas.AdminOut.model_validate({
                "id": admin_row.id,
                "name": admin_row.name,
                "email": admin_row.email,
                "is_active": admin_row.is_active,
                "is_superuser": admin_row.is_superuser,
                "two_factor_enabled": False,
            })
        except Exception as e2:
            db.rollback()
            print("[ERROR] dynamic insert into admins failed:", e2)
            raise HTTPException(status_code=500, detail="database_error")


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    # دعم JSON أو form: إذا كان Content-Type JSON نقرأ الحقول email/password، وإلا نقرأ form username/password
    email: Optional[str] = None
    password: Optional[str] = None

    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        data = await request.json()
        email = (data.get("email") or data.get("username") or "").strip().lower()
        password = data.get("password")
    else:
        form = await request.form()
        # OAuth2 form uses 'username'
        email = (form.get("username") or form.get("email") or "").strip().lower()
        password = form.get("password")

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="يجب إرسال البريد الإلكتروني وكلمة المرور")

    admin: Optional[models.Admin] = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.password_hash, models.Admin.is_active))
        .filter(func.lower(models.Admin.email) == email)
        .first()
    )
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="بيانات الدخول غير صحيحة")

    # خزّن الحقول قبل أي commit (حتى لا ت expire وتُحمل من قاعدة البيانات بأعمدة ناقصة)
    admin_id_val = admin.id
    admin_name_val = admin.name
    admin_email_val = admin.email

    # أنشئ رمز التحديث أولاً وسجّل بيانات الجلسة
    refresh = create_refresh_token(subject=str(admin_id_val))
    # ثبّت تاريخ الانتهاء ليكون naive (بدون tzinfo) لتفادي مشاكل Postgres
    exp_val = refresh["exp"]
    if isinstance(exp_val, datetime) and exp_val.tzinfo is not None:
        exp_val = exp_val.replace(tzinfo=None)
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    # حاول إدراج سجل الجلسة مع البيانات الكاملة، وإن فشل بسبب اختلاف المخطط نفّذ إدراجاً بسيطاً
    try:
        rt = models.RefreshToken(
            jti=refresh["jti"],
            admin_id=admin_id_val,
            expires_at=exp_val,
            revoked=False,
            created_at=datetime.utcnow(),
        )
        db.add(rt)
        db.commit()
    except Exception as e:
        db.rollback()
        print("[WARN] refresh_tokens insert failed, falling back to minimal insert:", e)
        try:
            cols_res = db.execute(
                text(
                    """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'refresh_tokens' AND table_schema = 'public'
                    """
                )
            )
            cols = [(r[0], (r[1] or '').upper(), r[2]) for r in cols_res]
            available_cols = {c for c, _, _ in cols}
            must_have = {c for c, nul, d in cols if nul == 'NO' and d is None}
            now = datetime.utcnow()
            base_values = {
                "jti": refresh["jti"],
                "admin_id": admin_id_val,
                "expires_at": exp_val,
                "revoked": False,
                "created_at": now,
            }
            use_keys = [k for k in base_values.keys() if k in available_cols]
            missing_required = [k for k in must_have if k not in use_keys and k not in {"id"}]
            if missing_required:
                raise RuntimeError(f"refresh_tokens missing required cols without defaults: {missing_required}")
            columns_csv = ", ".join(use_keys)
            placeholders = ", ".join(f":{k}" for k in use_keys)
            sql = f"INSERT INTO refresh_tokens ({columns_csv}) VALUES ({placeholders})"
            params = {k: base_values[k] for k in use_keys}
            db.execute(text(sql), params)
            db.commit()
        except Exception as e2:
            db.rollback()
            print("[ERROR] minimal/dynamic refresh_tokens insert failed:", e2)
            raise HTTPException(status_code=500, detail="database_error")

    # اجعل رمز الوصول يحمل sid (يشير إلى جلسة الريفريش)
    access = create_access_token(subject=str(admin_id_val), extra={"sid": refresh["jti"]})

    # أعد الاستجابة داخل data كما طلب الفرونت، بصيغة camelCase
    return {
        "data": {
            "accessToken": access["token"],
            "refreshToken": refresh["token"],
            "tokenType": "bearer",
            "user": {"id": admin_id_val, "name": admin_name_val, "email": admin_email_val},
        }
    }


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


@router.post("/refresh")
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
    from sqlalchemy.orm import load_only
    rt: Optional[models.RefreshToken] = db.query(models.RefreshToken)
    rt = rt.options(
        load_only(
            models.RefreshToken.id,
            models.RefreshToken.jti,
            models.RefreshToken.admin_id,
            models.RefreshToken.expires_at,
            models.RefreshToken.revoked,
            models.RefreshToken.created_at,
        )
    ).filter_by(jti=jti).first()
    if not rt or rt.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="تم إلغاء الرمز")

    # افحص انتهاء الصلاحية
    if isinstance(rt.expires_at, datetime) and rt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="انتهت صلاحية الرمز")

    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.is_active))
        .filter_by(id=int(admin_id))
        .first()
    )
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="المستخدم غير متاح")

    # دوّر الرمز: ألغِ القديم وأنشئ جديداً
    rt.revoked = True
    access = create_access_token(subject=str(admin.id))
    new_refresh = create_refresh_token(subject=str(admin.id))
    new_exp = new_refresh["exp"]
    if isinstance(new_exp, datetime) and new_exp.tzinfo is not None:
        new_exp = new_exp.replace(tzinfo=None)
    try:
        db.add(
            models.RefreshToken(
                jti=new_refresh["jti"],
                admin_id=admin.id,
                expires_at=new_exp,
                revoked=False,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("[WARN] refresh insert on rotate failed, trying dynamic insert:", e)
        try:
            cols_res = db.execute(
                text(
                    """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'refresh_tokens' AND table_schema = 'public'
                    """
                )
            )
            cols = [(r[0], (r[1] or '').upper(), r[2]) for r in cols_res]
            available_cols = {c for c, _, _ in cols}
            must_have = {c for c, nul, d in cols if nul == 'NO' and d is None}
            now = datetime.utcnow()
            base_values = {
                "jti": new_refresh["jti"],
                "admin_id": admin.id,
                "expires_at": new_exp,
                "revoked": False,
                "created_at": now,
            }
            use_keys = [k for k in base_values.keys() if k in available_cols]
            missing_required = [k for k in must_have if k not in use_keys and k not in {"id"}]
            if missing_required:
                raise RuntimeError(f"refresh_tokens missing required cols without defaults: {missing_required}")
            columns_csv = ", ".join(use_keys)
            placeholders = ", ".join(f":{k}" for k in use_keys)
            sql = f"INSERT INTO refresh_tokens ({columns_csv}) VALUES ({placeholders})"
            params = {k: base_values[k] for k in use_keys}
            db.execute(text(sql), params)
            db.commit()
        except Exception as e2:
            db.rollback()
            print("[ERROR] dynamic insert on rotate failed:", e2)
            raise HTTPException(status_code=500, detail="database_error")

    return {
        "data": {
            "accessToken": access["token"],
            "refreshToken": new_refresh["token"],
            "tokenType": "bearer",
        }
    }


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
        reset_link = f"{FRONTEND_BASE_URL}/auth/reset?token={raw_token}"
        # أرسل البريد إن كان SMTP مُعداً، وإلا اطبعه أثناء التطوير
        sent = send_password_reset(payload.email, reset_link)
        if not sent:
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

    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name))
        .filter_by(id=prt.admin_id)
        .first()
    )
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
