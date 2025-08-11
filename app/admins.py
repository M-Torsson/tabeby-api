import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, load_only

from . import models, schemas
from .auth import get_db, get_current_admin

router = APIRouter(prefix="/admins", tags=["Admins"])

# نقطة ترقية إدمن إلى سوبر أدمن (تشخيصية)
@router.post("/{admin_id}/promote", response_model=schemas.AdminBrief, include_in_schema=False)
def promote_admin(admin_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # يسمح فقط لسوبر أدمن حالي أو صاحب البريد المسجل كـ SUPER_ADMIN_EMAIL
    if not (current_admin.is_superuser or (current_admin.email or '').lower() == SUPER_ADMIN_EMAIL):
        raise HTTPException(status_code=403, detail="غير مسموح")
    admin = db.query(models.Admin).filter_by(id=admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    admin.is_superuser = True
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "role": "super-admin",
    }

SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "muthana.tursson@gmail.com").lower()
AUTO_PROMOTE_FIRST_ADMIN = os.getenv("AUTO_PROMOTE_FIRST_ADMIN", "true").lower() in ("1", "true", "yes")


def ensure_admin_power(current_admin: models.Admin, db: Session):
    # يُسمح لمن لديه is_superuser أو بريد السوبر الأدمن المُحدد
    if current_admin.is_superuser:
        return
    if (current_admin.email or "").strip().lower() == SUPER_ADMIN_EMAIL:
        return
    # في حال لا يوجد أي superuser في النظام، فعِّل ترقية أول إدمن تلقائياً عند الحاجة
    any_super = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.is_superuser))
        .filter_by(is_superuser=True)
        .first()
    )
    if not any_super and AUTO_PROMOTE_FIRST_ADMIN:
        current_admin.is_superuser = True
        db.add(current_admin)
        db.commit()
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ليست لديك صلاحية كافية")


@router.get("/_diagnose")
def diagnose_admins(request: Request, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # حالة البيئة (لا نعرض أسراراً)
    env = {
        "SUPER_ADMIN_EMAIL": SUPER_ADMIN_EMAIL,
        "AUTO_PROMOTE_FIRST_ADMIN": AUTO_PROMOTE_FIRST_ADMIN,
    }
    # تحقق من وجود هيدر التوثيق
    has_auth_header = bool(request.headers.get("authorization"))
    # حالة قاعدة البيانات
    any_super = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.is_superuser))
        .filter_by(is_superuser=True)
        .first()
    )
    admins = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.name, models.Admin.email, models.Admin.is_superuser))
        .all()
    )
    admins_brief = [
        {"id": a.id, "name": a.name, "email": a.email, "role": "super-admin" if a.is_superuser else "admin"}
        for a in admins
    ]
    allowed_now = current_admin.is_superuser or (current_admin.email or "").strip().lower() == SUPER_ADMIN_EMAIL
    would_autopromote = False
    if not allowed_now and not any_super and AUTO_PROMOTE_FIRST_ADMIN:
        would_autopromote = True
    return {
        "env": env,
        "auth": {
            "has_auth_header": has_auth_header,
            "current": {
                "id": current_admin.id,
                "email": current_admin.email,
                "is_superuser": current_admin.is_superuser,
            },
        },
        "db": {
            "any_superuser": bool(any_super),
            "admins_count": len(admins_brief),
        },
        "access": {
            "allowed_now": allowed_now,
            "would_autopromote": would_autopromote,
        },
        "sampleAdmins": admins_brief[:25],
    }


@router.post("/_ensure_super")
def ensure_super(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    # إن لم يوجد سوبر ويتم السماح بالترقية التلقائية، أو إن كان البريد يطابق بريد السوبر المحدد، رقِّ المستخدم الحالي
    any_super = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.is_superuser))
        .filter_by(is_superuser=True)
        .first()
    )
    if (current_admin.email or "").strip().lower() == SUPER_ADMIN_EMAIL or (not any_super and AUTO_PROMOTE_FIRST_ADMIN):
        if not current_admin.is_superuser:
            current_admin.is_superuser = True
            db.add(current_admin)
            db.commit()
        return {"status": "ok", "is_superuser": True}
    raise HTTPException(status_code=403, detail="غير مسموح بالترقية")


@router.get("/", response_model=List[schemas.AdminBrief])
def list_admins(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    ensure_admin_power(current_admin, db)
    admins = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.name, models.Admin.email, models.Admin.is_superuser))
        .all()
    )
    # ابنِ تمثيلاً موجزاً يتضمن الدور
    result = []
    for a in admins:
        result.append({
            "id": a.id,
            "name": a.name,
            "email": a.email,
            "role": "super-admin" if a.is_superuser else "admin",
        })
    return result


# مسار توافق قديم إذا كان الفرونت ما زال يستدعي /admins/list (يفضل تحديثه إلى /admins)
@router.get("/list", response_model=List[schemas.AdminBrief], include_in_schema=False)
def list_admins_legacy(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    return list_admins(db=db, current_admin=current_admin)


@router.patch("/{admin_id}", response_model=schemas.AdminBrief)
def update_admin(admin_id: int, payload: schemas.AdminAdminUpdate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    ensure_admin_power(current_admin, db)

    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.is_superuser))
        .filter_by(id=admin_id)
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # تحديث جزئي
    changed = False
    if payload.name is not None:
        admin.name = payload.name
        changed = True
    if payload.email is not None:
        exists = (
            db.query(models.Admin)
            .options(load_only(models.Admin.id, models.Admin.email))
            .filter(models.Admin.email == payload.email, models.Admin.id != admin.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        admin.email = payload.email
        changed = True
    if payload.role is not None:
        admin.is_superuser = payload.role == "super-admin"
        changed = True
    if payload.active is not None:
        admin.is_active = payload.active
        changed = True

    if changed:
        db.add(admin)
        db.commit()
        db.refresh(admin)

    return {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "role": "super-admin" if admin.is_superuser else "admin",
    }


@router.delete("/{admin_id}")
def delete_admin(admin_id: int, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    print(f"[DELETE_ADMIN] طلب حذف الإدمن: id={admin_id}, بواسطة: {current_admin.email} (superuser={current_admin.is_superuser})")
    ensure_admin_power(current_admin, db)
    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.is_superuser))
        .filter_by(id=admin_id)
        .first()
    )
    print(f"[DELETE_ADMIN] الإدمن المستهدف: {admin}")
    if not admin:
        print(f"[DELETE_ADMIN] الإدمن غير موجود: id={admin_id}")
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    try:
        db.delete(admin)
        db.commit()
        print(f"[DELETE_ADMIN] تم حذف الإدمن بنجاح: id={admin_id}")
        return {"message": "تم حذف الإدمن"}
    except Exception as e:
        print(f"[DELETE_ADMIN][ERROR] خطأ أثناء الحذف: {e}")
        raise HTTPException(status_code=500, detail=f"خطأ أثناء حذف الإدمن: {e}")
