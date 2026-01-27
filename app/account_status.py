# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
from .database import SessionLocal
from . import models
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Account Status"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



class DoctorStatusRequest(BaseModel):
    doctor_id: int
    is_active: bool


class PatientStatusRequest(BaseModel):
    patient_id: str
    is_active: bool  


class PatientStatusResponse(BaseModel):
    patient_id: str
    is_active: bool


class StatusResponse(BaseModel):
    id: int
    name: str
    status: str
    message: str



@router.post("/doctor/status", response_model=StatusResponse)
def update_doctor_status(
    payload: DoctorStatusRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تغيير حالة تفعيل الدكتور
    - doctor_id: رقم الدكتور من جدول doctors
    - is_active: true للتفعيل، false للإيقاف
    يحدث الحالة في:
    1. حقل status في جدول doctors
    2. حقل account_status في profile_json
    """
    doctor = db.query(models.Doctor).filter_by(id=payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="doctor not found")
    
    new_status = "active" if payload.is_active else "inactive"
    doctor.status = new_status
    
    if doctor.profile_json:
        try:
            profile = json.loads(doctor.profile_json)
            if isinstance(profile, dict):
                general_info = profile.get("general_info", {})
                if isinstance(general_info, dict):
                    general_info["account_status"] = payload.is_active
                    general_info.pop("accountStatus", None)
                    profile["general_info"] = general_info
                    doctor.profile_json = json.dumps(profile, ensure_ascii=False)
        except Exception as e:
            pass
    
    db.commit()
    db.refresh(doctor)
    
    message = "تم تفعيل الدكتور بنجاح" if payload.is_active else "تم إيقاف الدكتور بنجاح"
    
    return StatusResponse(
        id=doctor.id,
        name=doctor.name,
        status=doctor.status,
        message=message
    )


@router.get("/doctor/{doctor_id}/status")
def get_doctor_status(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على حالة الدكتور الحالية
    """
    doctor = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="doctor not found")
    
    return {
        "doctor_id": doctor.id,
        "name": doctor.name,
        "status": doctor.status,
        "is_active": doctor.status == "active"
    }



@router.post("/patient/status", response_model=PatientStatusResponse)
def update_patient_status(
    payload: PatientStatusRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تغيير حالة تفعيل المريض
    - patient_id: معرف المريض بصيغة "P-123" أو "123"
    - is_active: true للتفعيل، false للإيقاف
    """
    patient_id_str = payload.patient_id.strip()
    if patient_id_str.upper().startswith("P-"):
        patient_id_str = patient_id_str.split("-", 1)[1]
    
    try:
        patient_id_int = int(patient_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid patient_id format; expected P-<id> or <id>")
    
    ua = db.query(models.UserAccount).filter_by(id=patient_id_int).first()
    if not ua:
        raise HTTPException(status_code=404, detail="user_account not found")
    
    profile = db.query(models.PatientProfile).filter_by(user_account_id=ua.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="patient_profile not found")
    
    if not hasattr(profile, 'is_active'):
        raise HTTPException(
            status_code=500, 
            detail="Database migration required: run migrations/add_patient_is_active.sql first"
        )
    
    profile.is_active = payload.is_active
    db.commit()
    db.refresh(profile)
    
    return PatientStatusResponse(
        patient_id=f"P-{patient_id_int}",
        is_active=profile.is_active
    )


@router.get("/patient/{patient_id}/status")
def get_patient_status(
    patient_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على حالة المريض الحالية
    patient_id: معرف المريض بصيغة "P-123" أو "123"
    """
    patient_id_str = patient_id.strip()
    if patient_id_str.upper().startswith("P-"):
        patient_id_str = patient_id_str.split("-", 1)[1]
    
    try:
        patient_id_int = int(patient_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid patient_id format; expected P-<id> or <id>")
    
    ua = db.query(models.UserAccount).filter_by(id=patient_id_int).first()
    if not ua:
        raise HTTPException(status_code=404, detail="user_account not found")
    
    profile = db.query(models.PatientProfile).filter_by(user_account_id=ua.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="patient_profile not found")
    
    is_active = getattr(profile, 'is_active', True)
    
    return {
        "patient_id": f"P-{patient_id_int}",
        "is_active": is_active
    }
