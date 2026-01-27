# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
from .dependencies import require_profile_secret
import json

router = APIRouter(prefix="/api", tags=["Clinic Info"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/clinic/info")
def save_clinic_info(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    حفظ أو تحديث معلومات العيادة
    clinic_id ثابت = 1 دائماً
    
    Body:
    {
        "clinic_name": "Tabeby",
        "address": "123 Medical Plaza...",
        "email": "contact@medixpro-clinic.com",
        "phone": "+9647755841",
        "website": "https://medixpro-clinic.com"
    }
    """
    # clinic_id ثابت = 1
    clinic_id = 1
    
    # البحث عن الدكتور
    doctor = db.query(models.Doctor).filter(models.Doctor.id == clinic_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة")
    
    # قراءة البروفايل الحالي
    try:
        profile = json.loads(doctor.profile_json) if doctor.profile_json else {}
    except Exception:
        profile = {}
    
    # تحديث معلومات العيادة
    if "clinic_info" not in profile:
        profile["clinic_info"] = {}
    
    clinic_info = profile["clinic_info"]
    
    # تحديث الحقول
    if "clinic_name" in payload:
        clinic_info["clinic_name"] = payload["clinic_name"]
    if "address" in payload:
        clinic_info["address"] = payload["address"]
    if "email" in payload:
        clinic_info["email"] = payload["email"]
    if "phone" in payload:
        clinic_info["phone"] = payload["phone"]
    if "website" in payload:
        clinic_info["website"] = payload["website"]
    
    profile["clinic_info"] = clinic_info
    
    # حفظ التغييرات
    doctor.profile_json = json.dumps(profile, ensure_ascii=False)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    
    return {
        "success": True,
        "message": "تم حفظ معلومات العيادة بنجاح",
        "clinic_info": clinic_info
    }


@router.get("/clinic/info")
def get_clinic_info(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على معلومات العيادة
    clinic_id ثابت = 1 دائماً
    """
    clinic_id = 1
    
    doctor = db.query(models.Doctor).filter(models.Doctor.id == clinic_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة")
    
    try:
        profile = json.loads(doctor.profile_json) if doctor.profile_json else {}
    except Exception:
        profile = {}
    
    clinic_info = profile.get("clinic_info", {})
    
    return {
        "clinic_id": clinic_id,
        "clinic_name": clinic_info.get("clinic_name", ""),
        "address": clinic_info.get("address", ""),
        "email": clinic_info.get("email", ""),
        "phone": clinic_info.get("phone", ""),
        "website": clinic_info.get("website", "")
    }
