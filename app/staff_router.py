from typing import Optional, List
import os
from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, Request, Response
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func, text
from datetime import datetime

from .auth import get_current_admin, get_db, oauth2_scheme
from .security import create_access_token, create_refresh_token, verify_password, get_password_hash, decode_token
from . import models, schemas
from .rbac import all_permissions, default_roles

router = APIRouter(tags=["Staff & RBAC"])


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


@router.post("/staff/login")
def staff_login(
    data: Optional[schemas.LoginRequest] = None,
    email: Optional[str] = Form(default=None),
    password: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    # Accept JSON body (LoginRequest) or form-data fields gracefully
    if data is not None:
        email = data.email
        password = data.password
    if not email or not password:
        raise HTTPException(status_code=400, detail="يجب إرسال البريد وكلمة المرور")
    s = db.query(models.Staff).filter(func.lower(models.Staff.email) == email.strip().lower()).first()
    if not s or not s.password_hash or not verify_password(password, s.password_hash) or s.status != "active":
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    access = create_access_token(subject=f"staff:{s.id}", extra={"type": "staff"})
    refresh = create_refresh_token(subject=f"staff:{s.id}")
    return {
        "data": {
            "accessToken": access["token"],
            "refreshToken": refresh["token"],
            "tokenType": "bearer",
            "user": {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "role": s.role_key,
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
    s = db.query(models.Staff).filter_by(id=staff_id).first()
    if not s or s.status != "active":
        raise HTTPException(status_code=401, detail="المستخدم غير متاح")
    return s


@router.get("/staff/me", response_model=schemas.StaffItem)
def staff_me(current_staff: models.Staff = Depends(get_current_staff)):
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
        created_at=current_staff.created_at,
    )


@router.post("/staff/{staff_id}/set-password")
async def staff_set_password(staff_id: int, request: Request, password: Optional[str] = Form(default=None), db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # only admins with update permission can set staff password
    s = db.query(models.Staff).filter_by(id=staff_id).first()
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
    s.password_hash = get_password_hash(pwd)
    db.add(s)
    db.commit()
    return {"message": "ok"}


@router.get("/staff", response_model=schemas.StaffListResponse)
def list_staff(
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: models.Admin = Depends(get_current_admin),
):
    _ensure_seed(db)
    perms = _collect_permissions(db, None, current_admin)
    _require_perm(perms, "staff.read")

    q = db.query(models.Staff)
    if search:
        s = f"%{search.strip().lower()}%"
        q = q.filter(func.lower(models.Staff.name).like(s) | func.lower(models.Staff.email).like(s))
    total = q.count()
    rows = q.order_by(models.Staff.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
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
            created_at=r.created_at,
        )
        for r in rows
    ]
    return schemas.StaffListResponse(items=items, total=total)


@router.post("/staff", response_model=schemas.StaffItem, status_code=201)
async def create_staff(request: Request, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    _ensure_staff_table(db)
    perms = _collect_permissions(db, None, current_admin)
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
        # email uniqueness (if table exists; otherwise this will raise and we fallback)
        exists = db.query(models.Staff).filter(func.lower(models.Staff.email) == payload.email.lower()).first()
        if exists:
            raise HTTPException(status_code=400, detail="البريد مستخدم مسبقاً")

        staff = models.Staff(
            name=(payload.name or payload.email.split("@")[0]),
            email=payload.email.lower(),
            role_id=None,
            role_key="staff",
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
            msg = "database_error"
            if debug:
                msg = f"database_error | orm: {e} | dynamic: {e2}"
            return Response(content=msg, status_code=500, headers={"Content-Type": "text/plain"})


@router.get("/staff/{staff_id}", response_model=schemas.StaffItem)
def get_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    perms = _collect_permissions(db, None, current_admin)
    _require_perm(perms, "staff.read")
    s = db.query(models.Staff).filter_by(id=staff_id).first()
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
        created_at=s.created_at,
    )


@router.patch("/staff/{staff_id}", response_model=schemas.StaffItem)
def update_staff(staff_id: int, payload: schemas.StaffUpdate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = db.query(models.Staff).filter_by(id=staff_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.update")

    if payload.email and payload.email.lower() != s.email.lower():
        exists = db.query(models.Staff).filter(func.lower(models.Staff.email) == payload.email.lower(), models.Staff.id != s.id).first()
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
    if payload.role_id is not None or payload.role is not None:
        role = None
        if payload.role_id is not None:
            role = db.query(models.Role).filter_by(id=payload.role_id).first()
        elif payload.role is not None:
            role = db.query(models.Role).filter_by(key=payload.role).first()
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
    db.refresh(s)
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
        created_at=s.created_at,
    )


# تمت إزالة نقطة provision لعدم خلط الموظفين مع حسابات الأدمن


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = db.query(models.Staff).filter_by(id=staff_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.delete")

    db.delete(s)
    db.commit()
    return {"message": "deleted"}


@router.post("/staff/{staff_id}/activate")
def activate_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = db.query(models.Staff).filter_by(id=staff_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.activate")
    s.status = "active"
    db.add(s)
    db.commit()
    return {"message": "ok"}


@router.post("/staff/{staff_id}/deactivate")
def deactivate_staff(staff_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    s = db.query(models.Staff).filter_by(id=staff_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    perms = _collect_permissions(db, s, current_admin)
    _require_perm(perms, "staff.activate")
    s.status = "inactive"
    db.add(s)
    db.commit()
    return {"message": "ok"}
