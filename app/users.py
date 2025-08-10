from io import StringIO
import csv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .auth import get_current_admin, get_db
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
    # إن أراد المستخدم إلغاء كل الجلسات، نضع كل رموز التحديث كمُلغاة
    if payload.revoke_all_sessions:
        db.query(models.RefreshToken).filter_by(admin_id=current_admin.id, revoked=False).update({models.RefreshToken.revoked: True})
        db.commit()
    return {"message": "تم تحديث إعدادات الأمان"}
