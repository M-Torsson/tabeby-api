from typing import Optional, List
import os
from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, Request, Response
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func, text, inspect
from datetime import datetime

from .auth import get_current_admin, get_db, oauth2_scheme
from .security import create_access_token, create_refresh_token, verify_password, get_password_hash, decode_token
from . import models, schemas
from .rbac import all_permissions, default_roles
from .doctors import require_profile_secret

router = APIRouter(tags=["Staff & RBAC"])

# دعم تغيير كلمة مرور الموظف عبر /staff/password (متوافق مع الفرونت)


def _collect_permissions(db: Session, staff: Optional[models.Staff], admin: models.Admin) -> List[str]:
    # super-admin always all permissions
    if getattr(admin, "is_superuser", False):
        return all_permissions()

    perms: set[str] = set()
    # Admins (non super) get default admin role permissions
    try:
        from .rbac import default_roles as _defaults
        perms.update(_defaults().get("admin", {}).get("permissions", []))
    except Exception:
        pass

    # If a staff context is provided, merge role and direct staff permissions
    if staff and staff.role_id:
        role_perms = db.query(models.RolePermission).options(load_only(models.RolePermission.permission)).filter_by(role_id=staff.role_id).all()
        perms.update(p.permission for p in role_perms)
    if staff:
        direct = db.query(models.StaffPermission).options(load_only(models.StaffPermission.permission)).filter_by(staff_id=staff.id).all()
        perms.update(p.permission for p in direct)
    return sorted(perms)


def _ensure_seed(db: Session):
    # seed roles only if table empty
    count = db.query(models.Role).count()
    if count:
        return
    defaults = default_roles()
    for key, meta in defaults.items():
        role = models.Role(key=key, name=meta.get("name") or key, description=meta.get("description"))
        db.add(role)
        db.flush()
        for p in meta.get("permissions", []):
            db.add(models.RolePermission(role_id=role.id, permission=p))
    db.commit()


def _ensure_staff_table(db: Session):
    try:
        # quick probe to see if table exists
        db.execute(text("SELECT 1 FROM staff LIMIT 1"))
        return
    except Exception:
        try:
            from .database import Base as _Base
            bind = db.get_bind()
            if bind is not None:
                _Base.metadata.create_all(bind=bind)
        except Exception:
            # ignore; will be handled in dynamic insert fallback
            pass


def _staff_available_columns(db: Session) -> set[str]:
    # Try SQLAlchemy inspector first (works across SQLite/Postgres/etc.)
    try:
        bind = db.get_bind()
        if bind is not None:
            insp = inspect(bind)
            cols = [c.get("name") for c in insp.get_columns("staff")]  # type: ignore
            return {c for c in cols if c}
    except Exception:
        pass
    # Fallback to Postgres information_schema
    try:
        rows = db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'staff'
                """
            )
        )
        return {r[0] for r in rows}
    except Exception:
        return set()


@router.get("/users/me", response_model=schemas.AdminOut)
def users_me(current_admin: models.Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    _ensure_seed(db)
    # لا نربط الأدمن بالستاف: الدور والصلاحيات تُشتق من حساب الأدمن فقط
    if getattr(current_admin, "is_superuser", False):
        role_key = "super-admin"
        perms = all_permissions()
    else:
        role_key = "admin"
        from .rbac import default_roles
        perms = default_roles().get("admin", {}).get("permissions", [])
    return schemas.AdminOut(
        id=current_admin.id,
        name=current_admin.name,
        email=current_admin.email,
        is_active=getattr(current_admin, "is_active", True),
        is_superuser=getattr(current_admin, "is_superuser", False),
        two_factor_enabled=False,
        is_admin=True,
        is_staff=False,
        role=role_key,
        permissions=perms,
    )


@router.get("/permissions", response_model=schemas.PermissionList)
def list_permissions(current_admin: models.Admin = Depends(get_current_admin)):
    # Anyone authenticated can view permissions list (public catalog)
    return schemas.PermissionList(items=all_permissions())


@router.get("/roles", response_model=List[schemas.RoleOut])
def list_roles(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    _ensure_seed(db)
    roles = db.query(models.Role).all()
    out: List[schemas.RoleOut] = []
    for r in roles:
        perms = [rp.permission for rp in db.query(models.RolePermission).filter_by(role_id=r.id).all()]
        out.append(schemas.RoleOut(id=r.id, key=r.key, name=r.name, description=r.description, permissions=perms))
    return out


@router.patch("/roles/{role_id}/permissions")
def update_role_permissions(role_id: int, body: dict, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    if not getattr(current_admin, "is_superuser", False):
        raise HTTPException(status_code=403, detail="غير مسموح")
    perms: List[str] = body.get("permissions") or []
    # validate
    valid = set(all_permissions())
    for p in perms:
        if p not in valid:
            raise HTTPException(status_code=400, detail=f"permission '{p}' is invalid")
    role = db.query(models.Role).filter_by(id=role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="الدور غير موجود")
    # replace
    db.query(models.RolePermission).filter_by(role_id=role_id).delete()
    for p in perms:
        db.add(models.RolePermission(role_id=role_id, permission=p))
    db.commit()
    return {"message": "ok"}


def _require_perm(perms: List[str], needed: str):
    if needed not in perms:
        raise HTTPException(status_code=403, detail="صلاحية غير كافية")


# ===== Staff auth (separate from admins) =====


def _resolve_actor_and_perms(token: str, db: Session) -> tuple[Optional[models.Admin], Optional[models.Staff], List[str]]:
    """حلّل الرمز وأعد (أدمن، موظف، صلاحيات).
    - أدمن: اجلب صلاحياته الافتراضية (غير السوبر = admin defaults، السوبر = كل الصلاحيات)
    - موظف: اجمع صلاحيات الدور (role_id أو role_key) + الصلاحيات المباشرة + صلاحيات الدور الافتراضي من rbac
    """
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="رمز الوصول غير صالح")
    t = payload.get("type")
    if t == "access":
        admin = (
            db.query(models.Admin)
            .options(load_only(models.Admin.id, models.Admin.is_active, models.Admin.is_superuser))
            .filter_by(id=int(payload.get("sub")))
            .first()
        )
        if not admin or not getattr(admin, "is_active", True):
            raise HTTPException(status_code=401, detail="غير مصرح")
        if getattr(admin, "is_superuser", False):
            return admin, None, all_permissions()
        from .rbac import default_roles as _defaults
        perms = _defaults().get("admin", {}).get("permissions", [])
        return admin, None, perms
    if t == "staff":
        sub = payload.get("sub")
        if not sub or not str(sub).startswith("staff:"):
            raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
        staff_id = int(str(sub).split(":", 1)[1])
        s = (
            db.query(models.Staff)
            .options(load_only(models.Staff.id, models.Staff.role_id, models.Staff.role_key, models.Staff.status))
            .filter_by(id=staff_id)
            .first()
        )
        if not s or (s.status or "active") != "active":
            raise HTTPException(status_code=401, detail="غير مصرح")
        perms_set: set[str] = set()
        if s.role_id:
            rps = db.query(models.RolePermission).filter_by(role_id=s.role_id).all()
            perms_set.update(p.permission for p in rps)
        else:
            role_key_val = getattr(s, "role_key", None) or "staff"
            role = db.query(models.Role).filter_by(key=role_key_val).first()
            if role:
                rps = db.query(models.RolePermission).filter_by(role_id=role.id).all()
                perms_set.update(p.permission for p in rps)
        dps = db.query(models.StaffPermission).filter_by(staff_id=s.id).all()
        perms_set.update(p.permission for p in dps)
        try:
            from .rbac import default_roles as _defaults
            perms_set.update(_defaults().get(getattr(s, "role_key", None) or "staff", {}).get("permissions", []))
        except Exception:
            pass
        return None, s, sorted(perms_set)
    raise HTTPException(status_code=401, detail="نوع الرمز غير صحيح")


@router.post("/staff/login")
async def staff_login(request: Request, db: Session = Depends(get_db)):
    _ensure_staff_table(db)
    # يجب وجود عمود password_hash لدعم تسجيل دخول الموظف
    if "password_hash" not in _staff_available_columns(db):
        raise HTTPException(status_code=500, detail="إعداد قاعدة البيانات ناقص: عمود password_hash غير موجود في staff")

    # قبول JSON أو form
    email = None
    password = None
    try:
        content_type = (request.headers.get("content-type") or "").lower()
        if content_type.startswith("application/json"):
            body = await request.json()
            if isinstance(body, dict):
                email = (body.get("email") or "").strip()
                password = body.get("password")
        else:
            form = await request.form()
            email = (form.get("email") or "").strip()
            password = form.get("password")
    except Exception:
        pass
    if not email or not password:
        raise HTTPException(status_code=400, detail="يجب إرسال البريد وكلمة المرور")

    # جلب الموظف والتأكد من الحالة وكلمة المرور
    row = (
        db.execute(
            text("SELECT id, name, email, role_key, status, password_hash FROM staff WHERE LOWER(email)=:e LIMIT 1"),
            {"e": email.lower()},
        )
        .mappings()
        .first()
    )
    if not row or (row.get("status") or "active") != "active":
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    pwd_hash = row.get("password_hash")
    if not pwd_hash or not verify_password(password, pwd_hash):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    token = create_access_token(subject=f"staff:{int(row.get('id'))}", extra={"type": "staff"})
    return {
        "data": {
            "accessToken": token["token"],
            "tokenType": "bearer",
            "user": {
                "id": int(row.get("id")),
                "name": row.get("name") or email.split("@")[0],
                "email": row.get("email") or email,
                "role": row.get("role_key") or "staff",
            },
        }
    }


def get_current_staff(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.Staff:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="رمز الوصول غير صالح")
    if payload.get("type") != "staff":
        raise HTTPException(status_code=401, detail="نوع الرمز غير صحيح")
    sub = payload.get("sub")
    if not sub or not str(sub).startswith("staff:"):
        raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
    staff_id = int(str(sub).split(":",1)[1])
    # load only columns that actually exist
    avail = _staff_available_columns(db)
    load_cols = [models.Staff.id, models.Staff.name, models.Staff.email]
    if "role_id" in avail: load_cols.append(models.Staff.role_id)
    if "role_key" in avail: load_cols.append(models.Staff.role_key)
    if "department" in avail: load_cols.append(models.Staff.department)
    if "phone" in avail: load_cols.append(models.Staff.phone)
    if "status" in avail: load_cols.append(models.Staff.status)
    if "avatar_url" in avail: load_cols.append(models.Staff.avatar_url)
    if "created_at" in avail: load_cols.append(models.Staff.created_at)
    s = (
        db.query(models.Staff)
        .options(load_only(*load_cols))
        .filter_by(id=staff_id)
        .first()
    )
    if not s or s.status != "active":
        raise HTTPException(status_code=401, detail="المستخدم غير متاح")
    return s


@router.get("/staff/me", response_model=schemas.StaffItem)
def staff_me(current_staff: models.Staff = Depends(get_current_staff)):
    """إرجاع بيانات الموظف الحالي."""
    return current_staff

# دعم تغيير كلمة مرور الموظف عبر /staff/password (متوافق مع الفرونت)
@router.post("/staff/password")
async def staff_password_change_api(payload: schemas.ChangePasswordRequest, current_staff: models.Staff = Depends(get_current_staff), db: Session = Depends(get_db)):
    """تغيير كلمة مرور الموظف الحالي عبر /staff/password (متوافق مع الفرونت)."""
    cols = _staff_available_columns(db)
    if "password_hash" not in cols:
        raise HTTPException(status_code=400, detail="إعداد كلمة المرور غير مدعوم في هذا الإصدار من قاعدة البيانات")
    row = (
        db.execute(
            text("SELECT password_hash FROM staff WHERE id=:id"),
            {"id": current_staff.id},
        )
        .first()
    )
    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="لا توجد كلمة مرور حالية محددة")
    if not verify_password(payload.current_password, row[0]):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    db.execute(text("UPDATE staff SET password_hash=:ph WHERE id=:id"), {"ph": get_password_hash(payload.new_password), "id": current_staff.id})
    db.commit()
    return {"message": "تم تغيير كلمة المرور"}
    return schemas.StaffItem(
        id=current_staff.id,
        name=current_staff.name,
        email=current_staff.email,
        role=current_staff.role_key,
        role_id=current_staff.role_id,
        department=current_staff.department,
        phone=current_staff.phone,
        status=current_staff.status,
        avatar_url=current_staff.avatar_url,
        created_at=getattr(current_staff, "created_at", datetime.utcnow()),
    )


@router.post("/staff/{staff_id}/set-password")
async def staff_set_password(staff_id: int, request: Request, password: Optional[str] = Form(default=None), db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # only admins with update permission can set staff password
    s = (
        db.query(models.Staff)
        .options(load_only(models.Staff.id))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.update")
    pwd = password
    if not pwd:
        # try JSON
        try:
            content_type = (request.headers.get("content-type") or "").lower()
            if content_type.startswith("application/json"):
                data = await request.json()
                pwd = (data or {}).get("password")
        except Exception:
            pwd = None
    if not pwd:
        raise HTTPException(status_code=400, detail="password مطلوب")
    # ensure column exists in DB before setting
    cols = _staff_available_columns(db)
    if "password_hash" not in cols:
        raise HTTPException(status_code=400, detail="إعداد كلمة المرور غير مدعوم في هذا الإصدار من قاعدة البيانات")
    # safe direct update to avoid selecting non-existent columns
    db.execute(text("UPDATE staff SET password_hash=:ph WHERE id=:id"), {"ph": get_password_hash(pwd), "id": staff_id})
    db.commit()
    return {"message": "ok"}


@router.post("/staff/me/change-password")
async def staff_change_password(payload: schemas.ChangePasswordRequest, current_staff: models.Staff = Depends(get_current_staff), db: Session = Depends(get_db)):
    """تغيير كلمة مرور الموظف نفسه دون الحاجة لصلاحيات إدارية."""
    # تأكد من دعم عمود كلمة المرور
    cols = _staff_available_columns(db)
    if "password_hash" not in cols:
        raise HTTPException(status_code=400, detail="إعداد كلمة المرور غير مدعوم في هذا الإصدار من قاعدة البيانات")
    # اجلب الهاش الحالي بشكل مباشر لتفادي تحميل أعمدة غير موجودة
    row = (
        db.execute(
            text("SELECT password_hash FROM staff WHERE id=:id"),
            {"id": current_staff.id},
        )
        .first()
    )
    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="لا توجد كلمة مرور حالية محددة")
    if not verify_password(payload.current_password, row[0]):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    # حدّث الهاش
    db.execute(text("UPDATE staff SET password_hash=:ph WHERE id=:id"), {"ph": get_password_hash(payload.new_password), "id": current_staff.id})
    db.commit()
    return {"message": "تم تغيير كلمة المرور"}


@router.get("/staff", response_model=schemas.StaffListResponse)
def list_staff(
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    _ensure_seed(db)
    _, _, perms = _resolve_actor_and_perms(token, db)
    _require_perm(perms, "staff.read")

    avail = _staff_available_columns(db)
    load_cols = [models.Staff.id, models.Staff.name, models.Staff.email]
    if "role_id" in avail: load_cols.append(models.Staff.role_id)
    if "role_key" in avail: load_cols.append(models.Staff.role_key)
    if "department" in avail: load_cols.append(models.Staff.department)
    if "phone" in avail: load_cols.append(models.Staff.phone)
    if "status" in avail: load_cols.append(models.Staff.status)
    if "avatar_url" in avail: load_cols.append(models.Staff.avatar_url)
    if "created_at" in avail: load_cols.append(models.Staff.created_at)
    q = db.query(models.Staff).options(load_only(*load_cols))
    if search:
        s = f"%{search.strip().lower()}%"
        q = q.filter(func.lower(models.Staff.name).like(s) | func.lower(models.Staff.email).like(s))
    total = q.count()
    # ترتيب مرن: created_at إن وُجد وإلا حسب id تنازلياً
    if "created_at" in avail:
        rows = q.order_by(models.Staff.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    else:
        rows = q.order_by(models.Staff.id.desc()).offset((page - 1) * limit).limit(limit).all()
    items = [
        schemas.StaffItem(
            id=r.id,
            name=r.name,
            email=r.email,
            role=r.role_key,
            role_id=r.role_id,
            department=r.department,
            phone=r.phone,
            status=r.status,
            avatar_url=r.avatar_url,
            created_at=getattr(r, "created_at", datetime.utcnow()),
        )
        for r in rows
    ]
    return schemas.StaffListResponse(items=items, total=total)


@router.post("/staff", response_model=schemas.StaffItem, status_code=201)
async def create_staff(request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    _ensure_staff_table(db)
    _ensure_seed(db)  # تأكد من وجود الأدوار الافتراضية
    # استخرج نوع الهوية: أدمن أو موظف
    actor_admin: Optional[models.Admin] = None
    actor_staff: Optional[models.Staff] = None
    perms: List[str] = []
    try:
        payload = decode_token(token)
        t = payload.get("type")
        if t == "access":
            actor_admin = db.query(models.Admin).options(load_only(models.Admin.id, models.Admin.is_active, models.Admin.is_superuser)).filter_by(id=int(payload.get("sub"))).first()
            if not actor_admin or not getattr(actor_admin, "is_active", True):
                raise HTTPException(status_code=401, detail="غير مصرح")
            perms = _collect_permissions(db, None, actor_admin)
        elif t == "staff":
            sub = payload.get("sub")
            if not sub or not str(sub).startswith("staff:"):
                raise HTTPException(status_code=401, detail="رمز ناقص البيانات")
            staff_id = int(str(sub).split(":", 1)[1])
            actor_staff = (
                db.query(models.Staff)
                .options(load_only(models.Staff.id, models.Staff.role_id, models.Staff.role_key, models.Staff.status))
                .filter_by(id=staff_id)
                .first()
            )
            if not actor_staff or (actor_staff.status or "active") != "active":
                raise HTTPException(status_code=401, detail="غير مصرح")
            # صلاحيات الموظف = دور + صلاحيات مباشرة
            perms_set = set()
            # من role_id إن وجد
            if actor_staff.role_id:
                rps = db.query(models.RolePermission).filter_by(role_id=actor_staff.role_id).all()
                perms_set.update(p.permission for p in rps)
            else:
                # وإلا من role_key كحل بديل (حيث قد لا نحدد role_id في سجلات قديمة)
                if hasattr(models, 'Role'):
                    role_key_val = getattr(actor_staff, 'role_key', None) or 'staff'
                    role = db.query(models.Role).filter_by(key=role_key_val).first()
                    if role:
                        rps = db.query(models.RolePermission).filter_by(role_id=role.id).all()
                        perms_set.update(p.permission for p in rps)
            dps = db.query(models.StaffPermission).filter_by(staff_id=actor_staff.id).all()
            perms_set.update(p.permission for p in dps)
            # دمج صلاحيات الدور الافتراضي حسب role_key كحل متوافق للأدوار القديمة
            try:
                from .rbac import default_roles as _defaults
                rk = getattr(actor_staff, 'role_key', None) or 'staff'
                perms_set.update(_defaults().get(rk, {}).get('permissions', []))
            except Exception:
                pass
            perms = sorted(perms_set)
        else:
            raise HTTPException(status_code=401, detail="نوع الرمز غير صحيح")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="رمز الوصول غير صالح")

    _require_perm(perms, "staff.create")

    # Accept JSON or form
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    try:
        payload = schemas.StaffCreate.model_validate(data)
    except Exception as e_val:
        raise HTTPException(status_code=400, detail="يجب إرسال email و password (واسم اختياري)")

    try:
        # يجب توفر عمود password_hash لدعم كلمات مرور الموظفين
        available_cols = _staff_available_columns(db)
        if "password_hash" not in available_cols:
            raise HTTPException(status_code=500, detail="إعداد قاعدة البيانات ناقص: عمود password_hash غير موجود في staff")

        # email uniqueness (avoid selecting non-existent columns)
        exists = (
            db.query(models.Staff)
            .options(load_only(models.Staff.id, models.Staff.email))
            .filter(func.lower(models.Staff.email) == payload.email.lower())
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="البريد مستخدم مسبقاً")

        # حدد role_id المطلوب إن أرسله العميل: يدعم role_id أو role/systemRole (بالاسم أو المفتاح، غير حساس لحالة الأحرف)
        desired_role_id = None
        try:
            role_id_raw = (data.get("role_id") if isinstance(data, dict) else None)
            role_key_or_name = None
            for k in ("role", "systemRole", "roleKey"):
                v = (data.get(k) if isinstance(data, dict) else None)
                if v:
                    role_key_or_name = str(v)
                    break
            if role_id_raw not in (None, ""):
                try:
                    desired_role_id = int(role_id_raw)
                except Exception:
                    desired_role_id = None
            if desired_role_id is None and role_key_or_name:
                from sqlalchemy import or_, func
                rv = role_key_or_name.strip()
                r = (
                    db.query(models.Role)
                    .filter(or_(func.lower(models.Role.key) == rv.lower(), func.lower(models.Role.name) == rv.lower()))
                    .first()
                )
                if r:
                    desired_role_id = r.id
        except Exception:
            desired_role_id = None

        # إدخال عبر ORM عندما يكون العمود متاحاً
        try:
            # حدد role_id الافتراضي لدور "staff" إن وُجد
            role_id_val = None
            role_key_val = "staff"
            try:
                # إن لم يرسل العميل اختياراً محدداً، استخدم staff
                role_obj = db.query(models.Role).filter_by(key="staff").first()
                if role_obj:
                    role_id_val = role_obj.id
                    role_key_val = role_obj.key
            except Exception:
                role_id_val = None
                role_key_val = "staff"
            if desired_role_id is not None:
                # اجلب الدور المختار لتعيين role_key بدقة
                r = db.query(models.Role).filter_by(id=desired_role_id).first()
                if r:
                    role_id_val = r.id
                    role_key_val = r.key
            staff = models.Staff(
                name=(payload.name or payload.email.split("@")[0]),
                email=payload.email.lower(),
                role_id=role_id_val,
                role_key=role_key_val,
                department=None,
                phone=None,
                status="active",
                password_hash=get_password_hash(payload.password),
            )
            db.add(staff)
            db.commit()
            db.refresh(staff)
            return schemas.StaffItem(
                id=staff.id,
                name=staff.name,
                email=staff.email,
                role=staff.role_key,
                role_id=staff.role_id,
                department=staff.department,
                phone=staff.phone,
                status=staff.status,
                avatar_url=staff.avatar_url,
                created_at=staff.created_at,
            )
        except Exception:
            # إدراج ديناميكي إن فشل ORM
            db.rollback()
            now = datetime.utcnow()
            # احسب role_key الفعلي للديناميكي أيضًا
            dyn_role_key = "staff"
            if desired_role_id is not None:
                rr = db.query(models.Role).filter_by(id=desired_role_id).first()
                if rr:
                    dyn_role_key = rr.key
            elif db.query(models.Role).filter_by(key="staff").first():
                dyn_role_key = db.query(models.Role).filter_by(key="staff").first().key

            base_values = {
                "name": (payload.name or payload.email.split("@")[0]),
                "email": payload.email.lower(),
                # حاول تعيين role_id إن أمكن
                "role_id": (desired_role_id if desired_role_id is not None else (db.query(models.Role).filter_by(key="staff").first().id if db.query(models.Role).filter_by(key="staff").first() else None)),
                "role_key": dyn_role_key,
                "department": None,
                "phone": None,
                "status": "active",
                "avatar_url": None,
                "password_hash": get_password_hash(payload.password),
                "created_at": now,
            }
            use_keys = [k for k in base_values.keys() if k in available_cols]
            columns_csv = ", ".join(use_keys)
            placeholders = ", ".join(f":{k}" for k in use_keys)
            sql = f"INSERT INTO staff ({columns_csv}) VALUES ({placeholders})"
            params = {k: base_values[k] for k in use_keys}
            db.execute(text(sql), params)
            db.commit()
            id_row = db.execute(text("SELECT id FROM staff WHERE LOWER(email)=:e ORDER BY id DESC LIMIT 1"), {"e": payload.email.lower()}).first()
            new_id = id_row[0] if id_row else None
            return schemas.StaffItem(
                id=int(new_id) if new_id is not None else 0,
                name=(payload.name or payload.email.split("@")[0]),
                email=payload.email.lower(),
                role="staff",
                role_id=None,
                department=None,
                phone=None,
                status="active",
                avatar_url=None,
                created_at=now,
            )
    except Exception as e:
        # likely due to schema drift (missing columns). Try minimal/dynamic insert.
        db.rollback()
        try:
            cols_res = db.execute(
                text(
                    """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'staff' AND table_schema = 'public'
                    """
                )
            )
            cols = [(r[0], (r[1] or '').upper(), r[2]) for r in cols_res]
            available = {c for c, _, _ in cols}
            must_have = {c for c, nul, d in cols if nul == 'NO' and d is None}
            # If table seems missing (no columns), try to create tables then re-read
            if not available:
                try:
                    from .database import Base as _Base
                    bind = db.get_bind()
                    if bind is not None:
                        _Base.metadata.create_all(bind=bind)
                    # re-fetch columns
                    cols_res = db.execute(
                        text(
                            """
                            SELECT column_name, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = 'staff' AND table_schema = 'public'
                            """
                        )
                    )
                    cols = [(r[0], (r[1] or '').upper(), r[2]) for r in cols_res]
                    available = {c for c, _, _ in cols}
                    must_have = {c for c, nul, d in cols if nul == 'NO' and d is None}
                except Exception:
                    pass
            now = datetime.utcnow()
            base_values = {
                "admin_id": None,
                "name": (payload.name or payload.email.split("@")[0]),
                "email": payload.email.lower(),
                "role_id": None,
                "role_key": "staff",
                "department": None,
                "phone": None,
                "status": "active",
                "avatar_url": None,
                "password_hash": get_password_hash(payload.password),
                "created_at": now,
            }
            use_keys = [k for k in base_values.keys() if k in available]
            # ensure required columns are covered with non-null values
            missing_required = [k for k in must_have if (k not in use_keys or base_values.get(k) is None) and k not in {"id"}]
            if missing_required:
                raise RuntimeError(f"staff missing required cols without defaults: {missing_required}")
            if not use_keys:
                raise RuntimeError("staff table not found or has no usable columns")
            columns_csv = ", ".join(use_keys)
            placeholders = ", ".join(f":{k}" for k in use_keys)
            sql = f"INSERT INTO staff ({columns_csv}) VALUES ({placeholders})"
            params = {k: base_values[k] for k in use_keys}
            db.execute(text(sql), params)
            db.commit()
            # fetch id only to build response safely without selecting missing columns
            id_row = db.execute(text("SELECT id FROM staff WHERE LOWER(email)=:e ORDER BY id DESC LIMIT 1"), {"e": payload.email.lower()}).first()
            new_id = id_row[0] if id_row else None
            return schemas.StaffItem(
                id=int(new_id) if new_id is not None else 0,
                name=(payload.name or payload.email.split("@")[0]),
                email=payload.email.lower(),
                role="staff",
                role_id=None,
                department=None,
                phone=None,
                status="active",
                avatar_url=None,
                created_at=now,
            )
        except Exception as e2:
            db.rollback()
            print("[ERROR] staff insert failed:", e)
            print("[ERROR] staff dynamic insert failed:", e2)
            # Return plain text 500 with exact Content-Type (no charset) to satisfy client expectations
            debug = (os.getenv("DEBUG_ERRORS") or "").lower() in {"1", "true", "yes"}
            msg = "Internal Server Error"
            if debug:
                msg = f"Internal Server Error | orm: {e} | dynamic: {e2}"
            return Response(content=msg, status_code=500, headers={"Content-Type": "text/plain"})


@router.get("/staff/{staff_id}", response_model=schemas.StaffItem)
def get_staff(staff_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    _, _, perms = _resolve_actor_and_perms(token, db)
    _require_perm(perms, "staff.read")
    avail = _staff_available_columns(db)
    load_cols = [models.Staff.id, models.Staff.name, models.Staff.email]
    if "role_id" in avail: load_cols.append(models.Staff.role_id)
    if "role_key" in avail: load_cols.append(models.Staff.role_key)
    if "department" in avail: load_cols.append(models.Staff.department)
    if "phone" in avail: load_cols.append(models.Staff.phone)
    if "status" in avail: load_cols.append(models.Staff.status)
    if "avatar_url" in avail: load_cols.append(models.Staff.avatar_url)
    if "created_at" in avail: load_cols.append(models.Staff.created_at)
    s = (
        db.query(models.Staff)
        .options(load_only(*load_cols))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    return schemas.StaffItem(
        id=s.id,
        name=s.name,
        email=s.email,
        role=s.role_key,
        role_id=s.role_id,
        department=s.department,
        phone=s.phone,
        status=s.status,
        avatar_url=s.avatar_url,
        created_at=getattr(s, "created_at", datetime.utcnow()),
    )


@router.patch("/staff/{staff_id}", response_model=schemas.StaffItem)
async def update_staff(staff_id: int, request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    avail = _staff_available_columns(db)
    load_cols = [models.Staff.id, models.Staff.name, models.Staff.email]
    if "role_id" in avail: load_cols.append(models.Staff.role_id)
    if "role_key" in avail: load_cols.append(models.Staff.role_key)
    if "department" in avail: load_cols.append(models.Staff.department)
    if "phone" in avail: load_cols.append(models.Staff.phone)
    if "status" in avail: load_cols.append(models.Staff.status)
    if "avatar_url" in avail: load_cols.append(models.Staff.avatar_url)
    if "created_at" in avail: load_cols.append(models.Staff.created_at)
    s = (
        db.query(models.Staff)
        .options(load_only(*load_cols))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    _, _, perms = _resolve_actor_and_perms(token, db)
    _require_perm(perms, "staff.update")

    # Accept JSON or form-data
    try:
        content_type = (request.headers.get("content-type") or "").lower()
        if content_type.startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
        # Normalize types for form-data
        if isinstance(data, dict):
            if "role_id" in data and isinstance(data.get("role_id"), str) and data.get("role_id").strip() != "":
                try:
                    data["role_id"] = int(data["role_id"])  # type: ignore
                except Exception:
                    pass
            if "permissions" in data and isinstance(data.get("permissions"), str):
                data["permissions"] = [p.strip() for p in data["permissions"].split(",") if p.strip()]
        payload = schemas.StaffUpdate.model_validate(data)
    except Exception:
        raise HTTPException(status_code=400, detail="بيانات التعديل غير صحيحة")

    try:
        if payload.email and payload.email.lower() != s.email.lower():
            exists = (
                db.query(models.Staff)
                .options(load_only(models.Staff.id, models.Staff.email))
                .filter(func.lower(models.Staff.email) == payload.email.lower(), models.Staff.id != s.id)
                .first()
            )
            if exists:
                raise HTTPException(status_code=400, detail="البريد مستخدم مسبقاً")
            s.email = payload.email.lower()
        if payload.name is not None:
            s.name = payload.name
        if payload.department is not None:
            s.department = payload.department
        if payload.phone is not None:
            s.phone = payload.phone
        if payload.status is not None:
            s.status = payload.status
        if payload.avatar_url is not None:
            s.avatar_url = payload.avatar_url
        # دعم role_id أو role/systemRole كسلسلة (key أو name)
        if payload.role_id is not None or payload.role is not None or (isinstance(data, dict) and (data.get("systemRole") is not None)):
            role = None
            if payload.role_id is not None:
                role = db.query(models.Role).filter_by(id=payload.role_id).first()
            else:
                role_key_or_name = payload.role
                if role_key_or_name is None and isinstance(data, dict):
                    role_key_or_name = data.get("systemRole")
                if role_key_or_name is not None:
                    from sqlalchemy import or_, func
                    rv = str(role_key_or_name).strip()
                    role = (
                        db.query(models.Role)
                        .filter(or_(func.lower(models.Role.key) == rv.lower(), func.lower(models.Role.name) == rv.lower()))
                        .first()
                    )
            if not role:
                raise HTTPException(status_code=400, detail="الدور غير موجود")
            s.role_id = role.id
            s.role_key = role.key
        if payload.permissions is not None:
            # replace direct permissions
            db.query(models.StaffPermission).filter_by(staff_id=s.id).delete()
            valid = set(all_permissions())
            for p in payload.permissions:
                if p not in valid:
                    raise HTTPException(status_code=400, detail=f"permission '{p}' is invalid")
                db.add(models.StaffPermission(staff_id=s.id, permission=p))

        db.add(s)
        db.commit()
        return schemas.StaffItem(
            id=s.id,
            name=s.name,
            email=s.email,
            role=s.role_key,
            role_id=s.role_id,
            department=s.department,
            phone=s.phone,
            status=s.status,
            avatar_url=s.avatar_url,
            created_at=getattr(s, "created_at", datetime.utcnow()),
        )
    except Exception as e:
        db.rollback()
        debug = (os.getenv("DEBUG_ERRORS") or "").lower() in {"1", "true", "yes"}
        msg = "Internal Server Error"
        if debug:
            msg = f"Internal Server Error | update: {e}"
        return Response(content=msg, status_code=500, headers={"Content-Type": "text/plain"})


# تمت إزالة نقطة provision لعدم خلط الموظفين مع حسابات الأدمن


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = (
        db.query(models.Staff)
        .options(load_only(models.Staff.id, models.Staff.role_id))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.delete")

    try:
        # Remove dependent rows to avoid FK errors if cascade is not set
        db.query(models.StaffPermission).filter_by(staff_id=s.id).delete()
        # Use direct delete to avoid ORM selecting missing columns
        db.execute(text("DELETE FROM staff WHERE id=:id"), {"id": s.id})
        db.commit()
        return {"message": "deleted"}
    except Exception as e:
        db.rollback()
        debug = (os.getenv("DEBUG_ERRORS") or "").lower() in {"1", "true", "yes"}
        msg = "Internal Server Error"
        if debug:
            msg = f"Internal Server Error | delete: {e}"
        return Response(content=msg, status_code=500, headers={"Content-Type": "text/plain"})


@router.post("/staff/{staff_id}/activate")
def activate_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # Fetch minimal fields for permission check
    s = (
        db.query(models.Staff)
        .options(load_only(models.Staff.id, models.Staff.role_id))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.activate")
    # Direct update to avoid selecting missing columns
    db.execute(text("UPDATE staff SET status='active' WHERE id=:id"), {"id": staff_id})
    db.commit()
    return {"message": "ok"}


@router.post("/staff/{staff_id}/deactivate")
def deactivate_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = (
        db.query(models.Staff)
        .options(load_only(models.Staff.id, models.Staff.role_id))
        .filter_by(id=staff_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.activate")
    db.execute(text("UPDATE staff SET status='inactive' WHERE id=:id"), {"id": staff_id})
    db.commit()
    return {"message": "ok"}


@router.get("/api/staff/all")
def get_all_staff(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    Get all staff members from the database.
    Requires Doctor-Secret authentication.
    Similar to /api/patients/all endpoint.
    """
    staff_members = db.query(models.Staff).all()
    result = []
    
    for staff in staff_members:
        result.append({
            "id": staff.id,
            "name": staff.name,
            "email": staff.email,
            "role_key": getattr(staff, 'role_key', None),
            "department": getattr(staff, 'department', None),
            "phone": getattr(staff, 'phone', None),
            "status": getattr(staff, 'status', 'active'),
            "avatar_url": getattr(staff, 'avatar_url', None),
            "created_at": getattr(staff, 'created_at', None)
        })
    
    return result


@router.post("/api/staff/create")
def create_staff_simple(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    إنشاء موظف جديد - نسخة بسيطة مع Doctor-Secret فقط
    """
    try:
        email = payload.get("email")
        password = payload.get("password", "")
        name = payload.get("name")
        
        if not email or not name:
            raise HTTPException(status_code=400, detail="يجب إرسال email و name")
        
        # قص كلمة المرور إلى 72 بايت (حد bcrypt الأقصى)
        password_bytes = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        
        # التحقق من عدم تكرار الإيميل
        existing = db.query(models.Staff).filter(models.Staff.email == email).first()
        if existing:
            raise HTTPException(status_code=409, detail="الإيميل مستخدم مسبقاً")
        
        # hash كلمة المرور
        import bcrypt
        password_hash = bcrypt.hashpw(password_bytes.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # إنشاء الموظف
        new_staff = models.Staff(
            email=email,
            name=name,
            password_hash=password_hash
        )
        
        # إضافة الحقول الاختيارية
        if "role_key" in payload:
            new_staff.role_key = payload["role_key"]
        if "department" in payload:
            new_staff.department = payload["department"]
        if "phone" in payload:
            new_staff.phone = payload["phone"]
        
        # تعيين الحالة
        new_staff.status = 'active'
        
        db.add(new_staff)
        db.commit()
        db.refresh(new_staff)
        
        return {
            "success": True,
            "id": new_staff.id,
            "name": new_staff.name,
            "email": new_staff.email,
            "message": "تم إنشاء الموظف بنجاح"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ: {str(e)}")


@router.post("/api/staff/status")
def update_staff_status(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تحديث حالة الموظف (مفعل/غير مفعل)
    
    Body:
        {
            "staff_id": 35,
            "is_active": false
        }
    
    Returns:
        {
            "staff_id": 35,
            "is_active": false,
            "message": "تم تحديث حالة الموظف بنجاح"
        }
    """
    staff_id = payload.get("staff_id")
    is_active = payload.get("is_active")
    
    if staff_id is None:
        raise HTTPException(status_code=400, detail="يجب إرسال staff_id")
    if is_active is None:
        raise HTTPException(status_code=400, detail="يجب إرسال is_active")
    
    # التحقق من وجود الموظف
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    
    # تحديث الحالة
    new_status = "active" if is_active else "inactive"
    db.execute(text("UPDATE staff SET status=:status WHERE id=:id"), {"status": new_status, "id": staff_id})
    db.commit()
    
    return {
        "staff_id": staff_id,
        "is_active": is_active,
        "status": new_status,
        "message": "تم تحديث حالة الموظف بنجاح"
    }


@router.patch("/api/staff/{staff_id}")
def update_staff_info(
    staff_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تعديل معلومات الموظف
    
    Body:
        {
            "name": "اسم جديد",
            "email": "new@email.com",
            "phone": "0771234567",
            "department": "قسم جديد"
        }
    
    Returns: بيانات الموظف المحدثة
    """
    # التحقق من وجود الموظف
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    
    # تحديث الحقول المرسلة فقط
    if "name" in payload and payload["name"]:
        staff.name = payload["name"]
    if "email" in payload and payload["email"]:
        staff.email = payload["email"]
    if "phone" in payload:
        setattr(staff, 'phone', payload["phone"])
    if "department" in payload:
        setattr(staff, 'department', payload["department"])
    
    db.add(staff)
    db.commit()
    db.refresh(staff)
    
    return {
        "id": staff.id,
        "name": staff.name,
        "email": staff.email,
        "role_key": getattr(staff, 'role_key', None),
        "department": getattr(staff, 'department', None),
        "phone": getattr(staff, 'phone', None),
        "status": getattr(staff, 'status', 'active'),
        "avatar_url": getattr(staff, 'avatar_url', None),
        "created_at": getattr(staff, 'created_at', None),
        "message": "تم تحديث معلومات الموظف بنجاح"
    }
