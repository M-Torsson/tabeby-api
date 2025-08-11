import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, load_only

from . import models, schemas
from .auth import get_db, get_current_admin

router = APIRouter(prefix="/admins", tags=["Admins"])

SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "muthana.tursson@gmail.com").lower()


def ensure_admin_power(current_admin: models.Admin):
    # يُسمح لمن لديه is_superuser أو بريد السوبر الأدمن المُحدد
    if current_admin.is_superuser:
        return
    if (current_admin.email or "").lower() == SUPER_ADMIN_EMAIL:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ليست لديك صلاحية كافية")


@router.get("/", response_model=List[schemas.AdminBrief])
def list_admins(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    ensure_admin_power(current_admin)
    admins = db.query(models.Admin).all()
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


@router.patch("/{admin_id}", response_model=schemas.AdminBrief)
def update_admin(admin_id: int, payload: schemas.AdminAdminUpdate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    ensure_admin_power(current_admin)

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
        exists = db.query(models.Admin).filter(models.Admin.email == payload.email, models.Admin.id != admin.id).first()
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
    ensure_admin_power(current_admin)

    admin = (
        db.query(models.Admin)
        .options(load_only(models.Admin.id, models.Admin.email, models.Admin.name, models.Admin.is_superuser))
        .filter_by(id=admin_id)
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    db.delete(admin)
    db.commit()
    return {"message": "تم حذف الإدمن"}
