# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Clinic Status"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/close_clinic", response_model=schemas.ClinicStatusResponse)
def update_clinic_status(
    payload: schemas.ClinicStatusUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """تحديث حالة العيادة (مفتوحة/مغلقة).
    
    Args:
        payload: يحتوي على clinic_id و is_closed (true/false)
    
    Returns:
        حالة العيادة المحدثة
    """
    clinic_status = db.query(models.ClinicStatus).filter(
        models.ClinicStatus.clinic_id == payload.clinic_id
    ).first()
    
    if clinic_status:
        clinic_status.is_closed = payload.is_closed
        db.add(clinic_status)
        db.commit()
        db.refresh(clinic_status)
    else:
        clinic_status = models.ClinicStatus(
            clinic_id=payload.clinic_id,
            is_closed=payload.is_closed
        )
        db.add(clinic_status)
        db.commit()
        db.refresh(clinic_status)
    
    return schemas.ClinicStatusResponse(
        clinic_id=clinic_status.clinic_id,
        is_closed=clinic_status.is_closed
    )


@router.get("/close_clinic", response_model=schemas.ClinicStatusResponse)
def get_clinic_status(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """الحصول على حالة العيادة الحالية.
    
    Args:
        clinic_id: رقم العيادة
    
    Returns:
        حالة العيادة (مفتوحة/مغلقة)
    """
    clinic_status = db.query(models.ClinicStatus).filter(
        models.ClinicStatus.clinic_id == clinic_id
    ).first()
    
    if not clinic_status:
        return schemas.ClinicStatusResponse(
            clinic_id=clinic_id,
            is_closed=False
        )
    
    return schemas.ClinicStatusResponse(
        clinic_id=clinic_status.clinic_id,
        is_closed=clinic_status.is_closed
    )
